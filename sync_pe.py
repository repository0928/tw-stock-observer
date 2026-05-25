import requests
import psycopg2
import urllib3
from datetime import datetime, timezone
from db_utils import connect_with_retry, get_with_retry
urllib3.disable_warnings()
UTC = timezone.utc

print("連線資料庫...")
conn = connect_with_retry()
cur = conn.cursor()

# TSE: fields=[code, name, close, yield%, div_year, pe, pb, report]
print("TSE pe/yield...")
r = get_with_retry(
    "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?response=json",
    timeout=30, verify=False
)
rows = r.json().get("data", [])
updated = 0
for row in rows:
    symbol = row[0].strip()
    if not symbol.isdigit():
        continue
    try:
        dy = float(row[3]) if row[3] not in ('-', '--', '') else None
        pe = float(row[5]) if row[5] not in ('-', '--', '') else None
        pb = float(row[6]) if row[6] not in ('-', '--', '') else None
        cur.execute(
            "UPDATE stocks SET dividend_yield=%s, pe_ratio=%s, pb_ratio=%s, updated_at=%s WHERE symbol=%s",
            (dy, pe, pb, datetime.now(UTC), symbol)
        )
        updated += 1
    except Exception as e:
        print(f"  {symbol} err: {e}")
conn.commit()
print(f"TSE done: {updated}")

# TPEx: fields include YieldRatio, PriceEarningRatio, PriceBookRatio
print("TPEx pe/yield...")
r2 = get_with_retry(
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis",
    timeout=30, verify=False
)
updated2 = 0
for item in r2.json():
    symbol = item.get("SecuritiesCompanyCode", "").strip()
    if not symbol.isdigit():
        continue
    try:
        dy = float(item["YieldRatio"]) if item.get("YieldRatio", "-") not in ("-", "", "0") else None
        pe = float(item["PriceEarningRatio"]) if item.get("PriceEarningRatio", "-") not in ("-", "", "0") else None
        pb = float(item["PriceBookRatio"]) if item.get("PriceBookRatio", "-") not in ("-", "", "0") else None
        cur.execute(
            "UPDATE stocks SET dividend_yield=%s, pe_ratio=%s, pb_ratio=%s, updated_at=%s WHERE symbol=%s",
            (dy, pe, pb, datetime.now(UTC), symbol)
        )
        updated2 += 1
    except Exception as e:
        print(f"  {symbol} err: {e}")
conn.commit()
cur.close()
conn.close()
print(f"TPEx done: {updated2}")
print("All done!")
