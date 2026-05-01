"""
同步融資/融券餘額
上市：TWSE MI_MARGN API
上櫃：TPEx openapi

欄位：margin_long（融資餘額，張）、margin_short（融券餘額，張）
"""
import requests
import psycopg2
from datetime import datetime, timezone
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


def parse_int(val):
    """解析整數，去除千分位逗號"""
    v = str(val).replace(",", "").strip()
    if v in ("--", "", "X", "N/A", "－"):
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


# ==================== 上市融資/融券 (MI_MARGN) ====================
# MI_MARGN 欄位（依 TWSE 說明）：
# [0]  股票代號
# [1]  股票名稱
# [2]  融資買進（股）
# [3]  融資賣出（股）
# [4]  融資現金償還（股）
# [5]  融資前日餘額（股）
# [6]  融資今日餘額（股）   <- margin_long
# [7]  融資限額（股）
# [8]  融券買進（股）
# [9]  融券賣出（股）
# [10] 融券現券償還（股）
# [11] 融券前日餘額（股）
# [12] 融券今日餘額（股）   <- margin_short
# [13] 融券限額（股）
print("下載上市融資/融券資料 (MI_MARGN)...")
MARGN_URLS = [
    "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&selectType=ALL",
    "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&selectType=MS",
    "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN",
]
rows = []
for _url in MARGN_URLS:
    try:
        r = requests.get(_url, timeout=30, verify=False, headers={"User-Agent": "Mozilla/5.0"})
        body = r.text.strip()
        if not body or body.startswith("<"):
            print(f"  {_url} -> 非 JSON，跳過")
            continue
        data = r.json()
        if isinstance(data, list):
            rows = data
            print(f"  使用 URL: {_url}，共 {len(rows)} 筆")
            break
        stat = data.get("stat", "")
        # MI_MARGN 新版格式：回傳 tables 陣列，融資融券明細在 tables[1]
        if "tables" in data:
            tables = data["tables"]
            rows = tables[1]["data"] if len(tables) > 1 else (tables[0]["data"] if tables else [])
        else:
            rows = data.get("data", [])
        print(f"  使用 URL: {_url}，stat={stat}，共 {len(rows)} 筆")
        if rows:
            break
        print(f"  stat={stat}（可能為假日/非交易日），嘗試下一 URL")
    except Exception as e:
        print(f"  {_url} -> 失敗: {e}")
if not rows:
    print("  MI_MARGN 無資料（假日或非交易時間），跳過")

updated_tse = 0
for row in rows:
    if len(row) < 13:
        continue
    symbol = str(row[0]).strip()
    if not symbol.isdigit():
        continue
    try:
        # MI_MARGN 單位為千股，1 千股 = 1 張，直接使用不需除以 1000
        margin_long  = parse_int(row[6])
        margin_short = parse_int(row[12])
        if margin_long is None and margin_short is None:
            continue
        cur.execute(
            """UPDATE stocks SET margin_long=%s, margin_short=%s, updated_at=%s WHERE symbol=%s""",
            (margin_long, margin_short, datetime.now(timezone.utc), symbol)
        )
        updated_tse += 1
    except Exception as e:
        print(f"  處理上市 {symbol} 失敗: {e}")

conn.commit()
print(f"上市融資/融券更新: {updated_tse} 筆")


# ==================== 上櫃融資/融券 ====================
print("下載上櫃融資/融券資料...")
OTC_MARGIN_URLS = [
    "https://www.tpex.org.tw/openapi/v1/tpex_margin_trading_balance",
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_trading",
    "https://www.tpex.org.tw/openapi/v1/tpex_margin_trading",
    "https://www.tpex.org.tw/openapi/v1/tpex_margin_trading_info",
]

otc_items = []
for url in OTC_MARGIN_URLS:
    try:
        r2 = requests.get(url, timeout=15, verify=False)
        if r2.status_code == 200 and r2.text.strip().startswith("["):
            otc_items = r2.json()
            print(f"  使用 URL: {url}，共 {len(otc_items)} 筆")
            if otc_items:
                print(f"  欄位: {list(otc_items[0].keys())}")
            break
        else:
            print(f"  {url} -> HTTP {r2.status_code}，非 JSON")
    except Exception as e:
        print(f"  {url} -> 失敗: {e}")

if not otc_items:
    print("  上櫃融資/融券 API 無可用 URL，跳過")

updated_otc = 0
for item in otc_items:
    symbol = str(
        item.get("SecuritiesCompanyCode") or
        item.get("CompanyID") or
        item.get("公司代號") or ""
    ).strip()
    if not symbol.isdigit():
        continue
    try:
        long_val = parse_int(
            item.get("MarginPurchaseTodayBalance") or
            item.get("MarginBalance") or
            item.get("融資餘額") or
            item.get("融資今日餘額")
        )
        short_val = parse_int(
            item.get("ShortSaleTodayBalance") or
            item.get("ShortBalance") or
            item.get("融券餘額") or
            item.get("融券今日餘額")
        )
        if long_val is not None and long_val > 100_000_000:
            long_val = round(long_val / 1000)
        if short_val is not None and short_val > 100_000_000:
            short_val = round(short_val / 1000)
        if long_val is None and short_val is None:
            continue
        cur.execute(
            """UPDATE stocks SET margin_long=%s, margin_short=%s, updated_at=%s WHERE symbol=%s""",
            (long_val, short_val, datetime.now(timezone.utc), symbol)
        )
        updated_otc += 1
    except Exception as e:
        print(f"  處理上櫃 {symbol} 失敗: {e}")

conn.commit()
cur.close()
conn.close()
print(f"上櫃融資/融券更新: {updated_otc} 筆")
print("融資/融券同步完成！")
