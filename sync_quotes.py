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
        # 去除 X 前綴（撮合異常標記，如 X0.00）
        change_str = row[8].replace(",", "").replace("+", "").replace("X", "").strip()
        change  = float(change_str) if change_str not in ("--", "", "") else None
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

def safe_float(val, default=None):
    v = str(val).replace(",", "").strip()
    if v in ("--", "", "N/A"):
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default

# TPEx openapi 可能回傳 HTML，嘗試多個 URL
OTC_QUOTE_URLS = [
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",
    "https://www.tpex.org.tw/openapi/v1/tpex_updown_quotes",
]
otc_items = []
otc_date = ""
for _url in OTC_QUOTE_URLS:
    try:
        r2 = requests.get(_url, timeout=30, verify=False,
                          headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        body = r2.text.strip()
        if not body or body.startswith("<"):
            print(f"  {_url} -> 回傳 HTML，跳過")
            continue
        data2 = r2.json()
        items = data2 if isinstance(data2, list) else data2.get("data", [])
        if items:
            otc_items = items
            # 嘗試取日期
            if isinstance(data2, dict):
                otc_date = data2.get("date", data2.get("Date", ""))
            print(f"  使用 URL: {_url}，共 {len(otc_items)} 筆")
            # 印出前兩筆供診斷（含 Date 格式與 TradingShares 值）
            for _dbg in otc_items[:2]:
                print(f"  [範例] {_dbg.get('SecuritiesCompanyCode')} Date={_dbg.get('Date')} TradingShares={_dbg.get('TradingShares')}")
            break
        else:
            print(f"  {_url} -> 空資料")
    except Exception as e:
        print(f"  {_url} -> 失敗: {e}")

if not otc_items:
    print("  上櫃行情 API 無可用 URL，跳過")

updated2 = 0
for item in otc_items:
    symbol = str(item.get("SecuritiesCompanyCode") or item.get("Code") or "").strip()
    if not symbol.isdigit():
        continue
    try:
        close   = safe_float(item.get("Close") or item.get("ClosingPrice"))
        open_p  = safe_float(item.get("Open")  or item.get("OpeningPrice"))
        high    = safe_float(item.get("High")  or item.get("HighestPrice"))
        low     = safe_float(item.get("Low")   or item.get("LowestPrice"))

        change_str = str(item.get("Change") or item.get("PriceChange") or "").replace(",", "").replace("+", "").strip()
        change = None
        if change_str not in ("--", "", "X", "N/A"):
            try:
                change = float(change_str)
            except (ValueError, TypeError):
                change = None

        change_pct = round(change / (close - change) * 100, 2) if change and close and (close - change) != 0 else None

        # 成交量
        # TradingShares = 已是股數（股），不需換算
        # TradeVolume   = 張（1張=1000股），需乘 1000
        if "TradingShares" in item:
            vol_str = str(item.get("TradingShares", "")).replace(",", "").strip()
            vol_multiplier = 1          # 已是股數
        else:
            vol_str = str(item.get("TradeVolume") or item.get("Volume") or "").replace(",", "").strip()
            vol_multiplier = 1000       # 張 → 股
        volume = None
        if vol_str and vol_str not in ("--", "", "N/A"):
            try:
                volume = int(float(vol_str)) * vol_multiplier
            except (ValueError, TypeError):
                volume = None

        # 週轉率 = 成交股數 / 流通股數 * 100，超過 9999% 視為異常
        shares = shares_map.get(symbol)
        if volume and shares and shares > 0:
            raw_tr = volume / shares * 100
            turnover_rate = round(raw_tr, 4) if raw_tr <= 9999 else None
        else:
            turnover_rate = None

        # 日期：TPEx 格式為民國年無分隔符 YYYMMDD（如 1150512）
        # 轉換為 YYYY-MM-DD（如 2026-05-12）
        item_date = str(item.get("Date") or item.get("date") or otc_date).strip()
        if item_date and len(item_date) == 7 and item_date.isdigit():
            roc_y = int(item_date[:3])
            item_date = f"{roc_y + 1911}-{item_date[3:5]}-{item_date[5:7]}"
        trade_date_val = item_date if item_date else datetime.now().strftime("%Y-%m-%d")

        cur.execute("""
            UPDATE stocks SET
                open_price = %s, high_price = %s, low_price = %s,
                close_price = %s, change_amount = %s, change_percent = %s,
                volume = %s, trade_date = %s, turnover_rate = %s, updated_at = NOW()
            WHERE symbol = %s
        """, (open_p, high, low, close, change, change_pct, volume, trade_date_val, turnover_rate, symbol))
        updated2 += 1
    except Exception as e:
        conn.rollback()
        print(f"處理上櫃 {symbol} 失敗: {e}")

conn.commit()
print(f"✅ 上櫃行情更新完成！更新 {updated2} 筆")

cur.close()
conn.close()
