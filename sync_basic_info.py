"""
同步股票基本資料（股數、產業別、市場別）
上市：TWSE openapi t51sb01
上櫃：TPEx openapi tpex_mainboard_basic_info

補齊 shares 欄位後，sync_quotes.py 的 turnover_rate 即可正確計算。
"""
import requests
import psycopg2
from datetime import datetime, UTC
import urllib3
urllib3.disable_warnings()

conn = psycopg2.connect(
    host="43.167.191.181",
    port=31218,
    database="zeabur",
    user="root",
    password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh"
)
cur = conn.cursor()


def safe_bigint(val):
    """解析整數，支援千分位逗號及科學記號"""
    v = str(val).replace(",", "").strip()
    if v in ("--", "", "N/A", "－", "－－"):
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def upsert_basic(symbol, shares, industry, market, etf_override=None):
    """
    更新 stocks 表基本資料。
    - shares：流通股數（單位：股）
    - industry：產業別（若 API 有提供）
    - etf_override：None=不改 is_etf；True/False=強制設定
    """
    if not symbol or not symbol.strip():
        return False
    try:
        cur.execute("SAVEPOINT sp_basic")

        set_clauses = ["updated_at = %s"]
        params = [datetime.now(UTC)]

        if shares is not None:
            set_clauses.append("shares = %s")
            params.append(shares)
        if industry:
            set_clauses.append("industry = %s")
            params.append(industry)
        if market:
            set_clauses.append("market_type = %s")
            params.append(market)
        if etf_override is not None:
            set_clauses.append("is_etf = %s")
            params.append(etf_override)

        params.append(symbol)
        sql = f"UPDATE stocks SET {', '.join(set_clauses)} WHERE symbol = %s"
        cur.execute(sql, params)
        cur.execute("RELEASE SAVEPOINT sp_basic")
        return True
    except Exception as e:
        cur.execute("ROLLBACK TO SAVEPOINT sp_basic")
        print(f"  處理 {symbol} 失敗: {e}")
        return False


# ===== 上市：嘗試多個端點 =====
# t51sb01 目前回傳 HTML（損壞），改用 STOCK_DAY_ALL（行情，無股數）
# + BWIBBU_ALL（本益比，data 陣列格式）作為 symbol 清單來源
# 股數來源：openapi t187ap02_L（上市公司資本額資訊，若有）
TSE_SHARE_URLS = [
    "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",   # 上市基本資料（含已發行股數）★
    "https://openapi.twse.com.tw/v1/opendata/t187ap01_S",   # 備選
]

print("下載上市基本資料...")
items = []
for url in TSE_SHARE_URLS:
    try:
        r = requests.get(url, timeout=30, verify=False)
        body = r.text.strip()
        if r.status_code == 200 and body.startswith('['):
            items = r.json()
            if items:
                print(f"  使用 URL: {url}，共 {len(items)} 筆")
                print(f"  欄位: {list(items[0].keys())}")
                break
        else:
            print(f"  {url} → 非 JSON（{r.status_code}），跳過")
    except Exception as e:
        print(f"  {url} → 失敗: {e}")

if not items:
    print("  ⚠️  上市股數 API 無可用端點，上市 shares 本次跳過")

updated_tse = 0
for item in items:
    symbol = str(item.get("公司代號", item.get("CompanyID", ""))).strip()
    if not symbol:
        continue

    shares_val = None

    # ── 優先：已發行普通股數（t187ap03_L 直接提供，單位：股）──
    direct = safe_bigint(item.get("已發行普通股數或TDR原股發行股數"))
    if direct and direct > 0:
        shares_val = direct
    else:
        # 次選：實收資本額 / 普通股每股面額
        cap = safe_bigint(item.get("實收資本額"))
        par_raw = str(item.get("普通股每股面額", "10")).replace("新台幣", "").replace("元", "").strip()
        try:
            par = float(par_raw) or 10.0
        except (ValueError, TypeError):
            par = 10.0
        if cap and cap > 0:
            shares_val = int(cap // par)
        else:
            # 三選：千股欄位
            for k in item:
                if "股數" in k and "千" in k:
                    raw_val = safe_bigint(item[k])
                    if raw_val and raw_val > 0:
                        shares_val = raw_val * 1000
                        break

    industry = str(item.get("產業別", item.get("CFICode", ""))).strip() or None
    is_etf = symbol.startswith("00")

    if upsert_basic(symbol, shares_val, industry, "上市", etf_override=is_etf):
        updated_tse += 1

conn.commit()
print(f"✅ 上市基本資料更新: {updated_tse} 筆")


# ===== 上櫃 tpex_mainboard_basic_info =====
print("下載上櫃基本資料...")
OTC_BASIC_URLS = [
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_basic_info",
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",  # fallback：行情含部分基本資料
]

otc_items = []
for url in OTC_BASIC_URLS:
    try:
        r2 = requests.get(url, timeout=20, verify=False)
        if r2.status_code == 200 and r2.text.strip().startswith('['):
            otc_items = r2.json()
            print(f"  使用 URL: {url}，共 {len(otc_items)} 筆")
            if otc_items:
                print(f"  欄位: {list(otc_items[0].keys())}")
            break
        else:
            print(f"  {url} → HTTP {r2.status_code}，非 JSON，跳過")
    except Exception as e:
        print(f"  {url} → 失敗: {e}")

updated_otc = 0
for item in otc_items:
    symbol = str(
        item.get("SecuritiesCompanyCode") or
        item.get("CompanyID") or
        item.get("公司代號") or ""
    ).strip()
    if not symbol:
        continue

    shares_val = None

    # ── 優先：OutstandingShares / IssuedShares / 股數 欄位 ──
    for key in item:
        if any(k in key for k in ["OutstandingShares", "IssuedShares", "股數"]):
            raw_val = safe_bigint(item[key])
            if raw_val and raw_val > 0:
                shares_val = raw_val * 1000 if raw_val < 10_000_000 else raw_val
                break

    # ── 次選：Capitals（實收資本額，元）/ 10（面值 10 元）──
    # tpex_mainboard_quotes 的 Capitals 欄位即為此用途
    if shares_val is None:
        cap_raw = safe_bigint(item.get("Capitals"))
        if cap_raw and cap_raw > 0:
            shares_val = cap_raw // 10   # 面值 10 元 → 股數

    industry = str(
        item.get("IndustryCode") or
        item.get("Industry") or
        item.get("產業別") or ""
    ).strip() or None
    is_etf = symbol.startswith("00")

    if upsert_basic(symbol, shares_val, industry, "上櫃", etf_override=is_etf):
        updated_otc += 1

conn.commit()
print(f"✅ 上櫃基本資料更新: {updated_otc} 筆")

# 統計 shares 有值的股票數量
cur.execute("SELECT COUNT(*) FROM stocks WHERE shares IS NOT NULL AND shares > 0")
shares_filled = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM stocks")
total = cur.fetchone()[0]
print(f"\n📊 shares 補齊狀況：{shares_filled}/{total} 筆有值")

cur.close()
conn.close()
print("✅ 基本資料同步完成！")
