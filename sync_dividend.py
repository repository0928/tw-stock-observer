"""
同步股利分派資料
上市現金股利：TWSE openapi t187ap45_L（上市公司股利分派 - 可用）
  欄位：cash_dividend / dividend_per_share
上市除息日 / 上櫃：t187ap06_L / tpex_dividend_distribution（目前 API 暫時不通）
"""
import requests
import psycopg2
from datetime import datetime, date, timezone
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
    "https://openapi.twse.com.tw/v1/opendata/t187ap06_L",  # 上市股利分派（季更新）
    "https://www.twse.com.tw/rwd/zh/afterTrading/BFIAMU?response=json",  # 備選：股利分派
    "https://openapi.twse.com.tw/v1/opendata/t187ap06_T",
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
            (ex_date, cash_div, datetime.now(timezone.utc), symbol)
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
            (ex_date, cash_div, datetime.now(timezone.utc), symbol)
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


# ==================== TSE cash dividend (t187ap45_L) ====================
print("TSE cash dividend (t187ap45_L)...")
import json as _json

def _sf(v):
    try:
        f = float(str(v).replace(',','').strip())
        return f if f > 0 else None
    except:
        return None

r45 = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap45_L", timeout=30, verify=False)
tse45 = r45.json() if r45.text.strip().startswith('[') else []
tse_div = []
for item in tse45:
    sym = str(item.get("公司代號","")).strip()
    if not sym or not sym.isdigit():
        continue
    cash = (_sf(item.get("股東配發-盈餘分配之現金股利(元/股)", 0)) or 0) + \
           (_sf(item.get("股東配發-資本公積發放之現金(元/股)", 0)) or 0)
    if cash > 0:
        tse_div.append((cash, sym))

if tse_div:
    conn2 = psycopg2.connect(host="43.167.191.181", port=31218, database="zeabur", user="root", password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh")
    cur2 = conn2.cursor()
    for cd, sym in tse_div:
        cur2.execute("UPDATE stocks SET cash_dividend=%s, dividend_per_share=%s, updated_at=NOW() WHERE symbol=%s", (cd, cd, sym))
    conn2.commit()
    cur2.close(); conn2.close()
    print(f"  TSE done: {len(tse_div)}")

# ==================== OTC cash dividend (mopsfin_t187ap39_O) ====================
print("OTC cash dividend (mopsfin_t187ap39_O)...")
r39 = requests.get("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap39_O", timeout=30, verify=False)
otc39 = r39.json() if r39.text.strip().startswith('[') else []
latest = {}
for item in otc39:
    sym = str(item.get("公司代號","")).strip()
    if not sym or not sym.isdigit():
        continue
    yr = int(item.get("股利年度", 0) or 0)
    cash = (_sf(item.get("股東配發內容-盈餘分配之現金股利(元/股)", 0)) or 0) + \
           (_sf(item.get("股東配發內容-法定盈餘公積、資本公積發放之現金(元/股)", 0)) or 0)
    if sym not in latest or yr > latest[sym][0]:
        latest[sym] = (yr, cash if cash > 0 else None)

otc_div = [(v[1], sym) for sym, v in latest.items() if v[1]]
if otc_div:
    conn3 = psycopg2.connect(host="43.167.191.181", port=31218, database="zeabur", user="root", password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh")
    cur3 = conn3.cursor()
    for cd, sym in otc_div:
        cur3.execute("UPDATE stocks SET cash_dividend=%s, dividend_per_share=%s, updated_at=NOW() WHERE symbol=%s", (cd, cd, sym))
    conn3.commit()
    cur3.close(); conn3.close()
    print(f"  OTC done: {len(otc_div)}")

print("dividend sync complete!")
