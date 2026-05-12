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
SURGE_THRESHOLD = 20.0  # 融資單日增幅超過此 % 視為急增

for row in rows:
    if len(row) < 13:
        continue
    symbol = str(row[0]).strip()
    if not symbol.isdigit():
        continue
    try:
        # MI_MARGN 單位為千股，1 千股 = 1 張
        margin_long_prev = parse_int(row[5])   # 前日餘額
        margin_long      = parse_int(row[6])   # 今日餘額
        margin_short     = parse_int(row[12])

        if margin_long is None and margin_short is None:
            continue

        # 計算融資日變動 %
        chg_pct = None
        surge = False
        if margin_long is not None and margin_long_prev and margin_long_prev > 0:
            raw_pct = (margin_long - margin_long_prev) / margin_long_prev * 100
            chg_pct = round(raw_pct, 2) if abs(raw_pct) <= 9999 else None
            surge = chg_pct is not None and chg_pct >= SURGE_THRESHOLD

        cur.execute(
            """UPDATE stocks SET
                margin_long = %s, margin_long_prev = %s,
                margin_long_chg_pct = %s, margin_surge = %s,
                margin_short = %s, updated_at = %s
               WHERE symbol = %s""",
            (margin_long, margin_long_prev, chg_pct, surge,
             margin_short, datetime.now(timezone.utc), symbol)
        )
        updated_tse += 1
    except Exception as e:
        conn.rollback()
        print(f"  處理上市 {symbol} 失敗: {e}")

conn.commit()
print(f"上市融資/融券更新: {updated_tse} 筆")


# ==================== 上櫃融資/融券 ====================
# TPEx openapi 端點已停用（回傳 HTML），改用網頁版 JSON 接口
# 格式：aaData 為二維陣列，欄位順序：
# [0]代號 [1]名稱 [2]融資買進 [3]融資賣出 [4]融資現金償還
# [5]融資前日餘額 [6]融資今日餘額 [7]融資限額
# [8]融券買進 [9]融券賣出 [10]融券現券償還
# [11]融券前日餘額 [12]融券今日餘額 [13]融券限額
print("下載上櫃融資/融券資料...")

from datetime import date as _date
today_str = _date.today().strftime("%Y/%m/%d")
# 轉為民國年格式（TPEx 使用）
y, m, d = _date.today().year - 1911, _date.today().month, _date.today().day
today_roc = f"{y}/{m:02d}/{d:02d}"

OTC_MARGIN_URLS = [
    f"https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=json&d={today_roc}",
    f"https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=json&d={today_str}",
    "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=json",
]

otc_rows = []
for url in OTC_MARGIN_URLS:
    try:
        r2 = requests.get(url, timeout=20, verify=False,
                          headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json",
                                   "Referer": "https://www.tpex.org.tw/"})
        if r2.status_code != 200:
            print(f"  {url} -> HTTP {r2.status_code}，跳過")
            continue
        body = r2.text.strip()
        if not body or body.startswith("<"):
            print(f"  {url} -> 回傳 HTML，跳過")
            continue
        data = r2.json()
        # 支援 tables 格式（與 TWSE 相同結構）和舊版 aaData 格式
        rows = []
        if "tables" in data:
            tables = data["tables"]
            if isinstance(tables, list):
                for t in tables:
                    candidate = t.get("data") or t.get("aaData") or []
                    if candidate:
                        rows = candidate
                        print(f"  tables[{tables.index(t)}] title={t.get('title','')}")
                        break
        if not rows:
            rows = data.get("aaData") or data.get("data") or []

        if rows:
            print(f"  使用 URL: {url}，共 {len(rows)} 筆")
            otc_rows = rows
            break
        else:
            stat = data.get("stat", "")
            print(f"  {url} -> 空資料，stat={stat}（可能為非交易日）")
    except Exception as e:
        print(f"  {url} -> 失敗: {e}")

if not otc_rows:
    print("  上櫃融資/融券無可用資料，跳過")

updated_otc = 0
for row in otc_rows:
    # 支援陣列格式（aaData）和物件格式
    if isinstance(row, list):
        if len(row) < 13:
            continue
        symbol = str(row[0]).strip()
        margin_long_prev = parse_int(row[5])
        margin_long      = parse_int(row[6])
        margin_short     = parse_int(row[12])
    elif isinstance(row, dict):
        symbol = str(
            row.get("SecuritiesCompanyCode") or row.get("CompanyID") or row.get("公司代號") or ""
        ).strip()
        margin_long_prev = parse_int(
            row.get("MarginPurchaseYesterdayBalance") or row.get("融資前日餘額"))
        margin_long = parse_int(
            row.get("MarginPurchaseTodayBalance") or row.get("MarginBalance") or row.get("融資今日餘額"))
        margin_short = parse_int(
            row.get("ShortSaleTodayBalance") or row.get("ShortBalance") or row.get("融券今日餘額"))
    else:
        continue

    if not symbol.isdigit():
        continue
    try:
        # 單位轉換：若超過 1 億，視為股數，除以 1000 轉為張
        if margin_long  is not None and margin_long  > 100_000_000:
            margin_long  = round(margin_long  / 1000)
        if margin_short is not None and margin_short > 100_000_000:
            margin_short = round(margin_short / 1000)
        if margin_long is None and margin_short is None:
            continue

        # 計算融資日變動 %
        chg_pct = None
        surge = False
        if margin_long is not None and margin_long_prev and margin_long_prev > 0:
            raw_pct = (margin_long - margin_long_prev) / margin_long_prev * 100
            # 超過合理範圍（±9999%）視為資料異常，設為 None
            chg_pct = round(raw_pct, 2) if abs(raw_pct) <= 9999 else None
            surge = chg_pct is not None and chg_pct >= SURGE_THRESHOLD

        cur.execute(
            """UPDATE stocks SET
                margin_long=%s, margin_long_prev=%s,
                margin_long_chg_pct=%s, margin_surge=%s,
                margin_short=%s, updated_at=%s
               WHERE symbol=%s""",
            (margin_long, margin_long_prev, chg_pct, surge,
             margin_short, datetime.now(timezone.utc), symbol)
        )
        updated_otc += 1
    except Exception as e:
        conn.rollback()   # 清除 aborted transaction，讓後續筆數繼續跑
        print(f"  處理上櫃 {symbol} 失敗: {e}")

conn.commit()
cur.close()
conn.close()
print(f"上櫃融資/融券更新: {updated_otc} 筆")
print("融資/融券同步完成！")
