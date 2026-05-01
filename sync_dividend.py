"""
同步股利分派資料
上市：TWSE openapi t187ap06_L（上市公司股利分派情形）
上櫃：TPEx openapi（嘗試對應端點）

欄位：ex_dividend_date（除息日）、cash_dividend（現金股利，元）
"""
import requests
import psycopg2
from datetime import datetime, date, UTC
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


def parse_tw_date(val):
    """解析民國/西元日期字串，回傳 date 物件"""
    if not val:
        return None
    v = str(val).strip()
    try:
        if "/" in v:
            parts = v.split("/")
            if len(parts[0]) <= 3:
                return date(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        elif "-" in v:
            parts = v.split("-")
            if len(parts[0]) <= 3:
                return date(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        elif v.isdigit() and len(v) == 7:
            return date(int(v[:3]) + 1911, int(v[3:5]), int(v[5:7]))
        elif v.isdigit() and len(v) == 8:
            return date(int(v[:4]), int(v[4:6]), int(v[6:8]))
    except (ValueError, TypeError):
        pass
    return None


def safe_float(val):
    v = str(val).replace(",", "").strip()
    if v in ("--", "", "N/A", "－", "－－"):
        return None
    try:
        f = float(v)
        return f if f != 0 else None
    except (ValueError, TypeError):
        return None


# ==================== 上市股利 (t187ap06_L) ====================
print("下載上市股利分派資料...")
TSE_DIV_URLS = [
    "https://openapi.twse.com.tw/v1/opendata/t187ap06_L",  # 上市股利分派（季更新，部分時段可能空白）
    "https://openapi.twse.com.tw/v1/opendata/t187ap06_T",  # 備選
    "https://openapi.twse.com.tw/v1/exchangeReport/DIVIDEND_ALL",
]
items_tse = []
for _url in TSE_DIV_URLS:
    try:
        r = requests.get(_url, timeout=30, verify=False)
        body = r.text.strip()
        if not body or body.startswith('<'):
            print(f"  {_url} → 非 JSON，跳過")
            continue
        data = r.json()
        items_tse = data if isinstance(data, list) else data.get("data", [])
        print(f"  使用 URL: {_url}，共 {len(items_tse)} 筆")
        if items_tse:
            print(f"  欄位: {list(items_tse[0].keys())}")
            break
        print(f"  空回應，嘗試下一 URL")
    except Exception as e:
        print(f"  {_url} → 失敗: {e}")
if not items_tse:
    print("  ⚠️  上市股利 API 無資料，跳過（可能為季更新空窗期）")

updated_tse = 0
for item in items_tse:
    symbol = str(item.get("公司代號", item.get("SecuritiesCompanyCode", ""))).strip()
    if not symbol or not symbol.isdigit():
        continue

    # 除息日欄位嘗試（t187ap06_L 可能欄位名稱：「現金股利除息日」「除息日」）
    raw_date = (
        item.get("現金股利除息日") or item.get("除息日") or
        item.get("ExDividendDate") or item.get("CashDividendDate")
    )
    ex_date = parse_tw_date(raw_date)

    # 現金股利欄位嘗試（元/股）
    cash_div = safe_float(
        item.get("現金股利") or item.get("現金股息") or
        item.get("CashDividend") or item.get("現金股利(元)")
    )

    if ex_date is None and cash_div is None:
        continue

    try:
        cur.execute("SAVEPOINT sp_div")
        cur.execute(
            """UPDATE stocks SET
                ex_dividend_date = COALESCE(%s, ex_dividend_date),
                cash_dividend    = COALESCE(%s, cash_dividend),
                updated_at       = %s
               WHERE symbol = %s""",
            (ex_date, cash_div, datetime.now(UTC), symbol)
        )
        cur.execute("RELEASE SAVEPOINT sp_div")
        updated_tse += 1
    except Exception as e:
        cur.execute("ROLLBACK TO SAVEPOINT sp_div")
        print(f"  處理上市 {symbol} 失敗: {e}")

conn.commit()
print(f"✅ 上市股利更新: {updated_tse} 筆")


# ==================== 上櫃股利 ====================
print("下載上櫃股利分派資料...")
OTC_DIV_URLS = [
    "https://www.tpex.org.tw/openapi/v1/tpex_dividend_distribution",
    "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O",
    "https://www.tpex.org.tw/openapi/v1/mopsfin_187ap06_O",
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_dividend",
    "https://www.tpex.org.tw/openapi/v1/tpex_dividend_info",
]
items_otc = []
for url in OTC_DIV_URLS:
    try:
        r2 = requests.get(url, timeout=20, verify=False)
        if r2.status_code == 200 and r2.text.strip().startswith('['):
            items_otc = r2.json()
            print(f"  使用 URL: {url}，共 {len(items_otc)} 筆")
            if items_otc:
                print(f"  欄位: {list(items_otc[0].keys())}")
            break
        else:
            print(f"  {url} → HTTP {r2.status_code}，非 JSON")
    except Exception as e:
        print(f"  {url} → 失敗: {e}")

if not items_otc:
    print("  ⚠️  上櫃股利 API 無可用 URL，跳過")

updated_otc = 0
for item in items_otc:
    symbol = str(
        item.get("公司代號") or item.get("SecuritiesCompanyCode") or item.get("CompanyID") or ""
    ).strip()
    if not symbol or not symbol.isdigit():
        continue

    raw_date = (
        item.get("現金股利除息日") or item.get("除息日") or
        item.get("ExDividendDate") or item.get("CashDividendDate")
    )
    ex_date = parse_tw_date(raw_date)
    cash_div = safe_float(
        item.get("現金股利") or item.get("現金股息") or
        item.get("CashDividend") or item.get("現金股利(元)")
    )

    if ex_date is None and cash_div is None:
        continue

    try:
        cur.execute("SAVEPOINT sp_otc_div")
        cur.execute(
            """UPDATE stocks SET
                ex_dividend_date = COALESCE(%s, ex_dividend_date),
                cash_dividend    = COALESCE(%s, cash_dividend),
                updated_at       = %s
               WHERE symbol = %s""",
            (ex_date, cash_div, datetime.now(UTC), symbol)
        )
        cur.execute("RELEASE SAVEPOINT sp_otc_div")
        updated_otc += 1
    except Exception as e:
        cur.execute("ROLLBACK TO SAVEPOINT sp_otc_div")
        print(f"  處理上櫃 {symbol} 失敗: {e}")

conn.commit()
cur.close()
conn.close()
print(f"✅ 上櫃股利更新: {updated_otc} 筆")
print("✅ 股利同步完成！")
