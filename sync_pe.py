import requests
import psycopg2
import urllib3
from datetime import datetime, UTC
urllib3.disable_warnings()

conn = psycopg2.connect(
    host="43.167.191.181",
    port=31218,
    database="zeabur",
    user="root",
    password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh"
)
cur = conn.cursor()

# 上市
print("下載上市本益比資料...")
r = requests.get(
    "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?response=json",
    timeout=30, verify=False
)
data = r.json()
rows = data.get("data", [])

updated = 0
for row in rows:
    symbol = row[0].strip()
    if not symbol.isdigit():
        continue
    try:
        dy  = float(row[2]) if row[2] not in ('-', '--', '') else None  # 殖利率
        pe  = float(row[5]) if row[5] not in ('-', '--', '') else None  # 本益比
        pb  = float(row[6]) if row[6] not in ('-', '--', '') else None  # 淨值比
        cur.execute(
            "UPDATE stocks SET dividend_yield = %s, pe_ratio = %s, pb_ratio = %s, updated_at = %s WHERE symbol = %s",
            (dy, pe, pb, datetime.now(UTC), symbol)
        )
        updated += 1
    except Exception as e:
        print(f"處理 {symbol} 失敗: {e}")

conn.commit()
print(f"✅ 上市本益比更新: {updated} 筆")

# 上櫃
print("下載上櫃本益比資料...")
r2 = requests.get(
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis",
    timeout=30, verify=False
)
updated2 = 0
for item in r2.json():
    symbol = item.get("SecuritiesCompanyCode", "").strip()
    if not symbol.isdigit():
        continue
    try:
        pe = float(item.get("PriceEarningRatio", "0")) if item.get("PriceEarningRatio", "-") not in ("-", "", "0") else None
        pb = float(item.get("PriceBookRatio", "0")) if item.get("PriceBookRatio", "-") not in ("-", "", "0") else None
        cur.execute(
            "UPDATE stocks SET pe_ratio = %s, pb_ratio = %s, updated_at = %s WHERE symbol = %s",
            (pe, pb, datetime.now(UTC), symbol)
        )
        updated2 += 1
    except Exception as e:
        print(f"處理上櫃 {symbol} 失敗: {e}")

conn.commit()
cur.close()
conn.close()
print(f"✅ 上櫃本益比更新: {updated2} 筆")
print("✅ 完成！")