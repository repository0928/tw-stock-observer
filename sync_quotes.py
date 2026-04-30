import requests
import psycopg2
from datetime import datetime
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

# 預先載入所有股票的流通股數，用於計算週轉率
print("載入股票流通股數...")
cur.execute("SELECT symbol, shares FROM stocks WHERE shares IS NOT NULL AND shares > 0")
shares_map = {row[0]: row[1] for row in cur.fetchall()}
print(f"  已載入 {len(shares_map)} 支股票的股數資料")

print("下載上市股票行情...")
r = requests.get("https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=json", timeout=30, verify=False)
data = r.json()
rows = data.get("data", [])
trade_date = data.get("date", "")

def parse_num(val):
    v = str(val).replace(",", "").strip()
    return float(v) if v not in ("--", "", "X") else None

updated = 0
for row in rows:
    symbol = row[0].strip()
    if not symbol.isdigit():
        continue
    try:
        open_p  = parse_num(row[4])
        high    = parse_num(row[5])
        low     = parse_num(row[6])
        close   = parse_num(row[7])
        change_str = row[8].replace(",", "").replace("+", "").strip()
        change  = float(change_str) if change_str not in ("--", "", "X") else None
        change_pct = round(change / (close - change) * 100, 2) if change and close and (close - change) != 0 else None

        # 上市成交量單位為「股」，直接儲存
        vol_str = row[2].replace(",", "").strip()
        try:
            volume = int(float(vol_str)) if vol_str else None
        except (ValueError, TypeError):
            volume = None

        # 週轉率 = 成交股數 / 流通股數 * 100
        shares = shares_map.get(symbol)
        turnover_rate = round(volume / shares * 100, 4) if volume and shares and shares > 0 else None

        cur.execute("""
            UPDATE stocks SET
                open_price = %s, high_price = %s, low_price = %s,
                close_price = %s, change_amount = %s, change_percent = %s,
                volume = %s, trade_date = %s, turnover_rate = %s, updated_at = NOW()
            WHERE symbol = %s
        """, (open_p, high, low, close, change, change_pct, volume, trade_date, turnover_rate, symbol))
        updated += 1
    except Exception as e:
        print(f"處理 {symbol} 失敗: {e}")

conn.commit()
print(f"✅ 上市行情更新完成！更新 {updated} 筆")

# 同步上櫃行情
print("下載上櫃股票行情...")
r2 = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", timeout=30, verify=False)
updated2 = 0

def safe_float(val, default=None):
    v = str(val).replace(",", "").strip()
    if v in ("--", "", "0", "N/A"):
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default

for item in r2.json():
    symbol = item.get("SecuritiesCompanyCode", "").strip()
    if not symbol.isdigit():
        continue
    try:
        close   = safe_float(item.get("Close", ""))
        open_p  = safe_float(item.get("Open", ""))
        high    = safe_float(item.get("High", ""))
        low     = safe_float(item.get("Low", ""))

        change_str = str(item.get("Change", "")).replace(",", "").replace("+", "").strip()
        change = None
        if change_str not in ("--", "", "X", "N/A"):
            try:
                change = float(change_str)
            except (ValueError, TypeError):
                change = None

        change_pct = round(change / (close - change) * 100, 2) if change and close and (close - change) != 0 else None

        # 上櫃 TradeVolume 單位為「張」（1張=1000股），乘以 1000 換算為股數以統一單位
        vol_str = str(item.get("TradeVolume", "")).replace(",", "").strip()
        try:
            volume = int(float(vol_str)) * 1000 if vol_str else None
        except (ValueError, TypeError):
            volume = None

        # 週轉率 = 成交股數 / 流通股數 * 100
        share