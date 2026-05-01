import requests
import psycopg2
import uuid
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

added = 0
updated = 0

print("下載上市股票...")
r = requests.get("https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=json", timeout=30, verify=False)
data = r.json()
rows = data.get("data", [])

for row in rows:
    symbol = row[0].strip()
    name = row[1].strip()
    if not symbol or not name or not symbol.isdigit():
        continue
    cur.execute("SELECT id FROM stocks WHERE symbol = %s", (symbol,))
    existing = cur.fetchone()
    if existing:
        cur.execute("UPDATE stocks SET name=%s, market_type=%s, is_active=true, is_suspended=false, updated_at=%s WHERE symbol=%s",
                    (name, "上市", datetime.utcnow(), symbol))
        updated += 1
    else:
        cur.execute("INSERT INTO stocks (id, symbol, name, market_type, is_active, is_suspended, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (str(uuid.uuid4()), symbol, name, "上市", True, False, datetime.utcnow(), datetime.utcnow()))
        added += 1

conn.commit()
print(f"上市: 新增 {added}, 更新 {updated}")

# 上櫃股票
added2 = updated2 = 0
print("下載上櫃股票...")
r2 = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", timeout=30, verify=False)
for item in r2.json():
    symbol = item.get("SecuritiesCompanyCode", "").strip()
    name = item.get("CompanyName", "").strip()
    if not symbol or not name or not symbol.isdigit():
        continue
    cur.execute("SELECT id FROM stocks WHERE symbol = %s", (symbol,))
    existing = cur.fetchone()
    if existing:
        cur.execute("UPDATE stocks SET name=%s, market_type=%s, is_active=true, is_suspended=false, updated_at=%s WHERE symbol=%s",
                    (name, "上櫃", datetime.utcnow(), symbol))
        updated2 += 1
    else:
        cur.execute("INSERT INTO stocks (id, symbol, name, market_type, is_active, is_suspended, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (str(uuid.uuid4()), symbol, name, "上櫃", True, False, datetime.utcnow(), datetime.utcnow()))
        added2 += 1

conn.commit()
print(f"上櫃: 新增 {added2}, 更新 {updated2}")

cur.close()
conn.close()
print("✅ 同步完成！")
print("\n確認行情欄位:")
print(data.get("fields"))
print("第一筆完整資料:", rows[0])