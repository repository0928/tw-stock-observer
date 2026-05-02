"""
Sync listing_date, capital_stock, website, english_name, shares from:
  TSE: openapi.twse.com.tw/v1/opendata/t187ap03_L
  OTC: tpex.org.tw/openapi/v1/mopsfin_t187ap03_O
"""
import requests, psycopg2, urllib3, json
from datetime import datetime, timezone
urllib3.disable_warnings()
UTC = timezone.utc

conn = psycopg2.connect(
    host="43.167.191.181", port=31218,
    database="zeabur", user="root",
    password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh"
)
cur = conn.cursor()

def parse_date(val):
    v = str(val).strip().replace("-", "").replace("/", "")
    if len(v) == 8 and v.isdigit():
        return f"{v[:4]}-{v[4:6]}-{v[6:8]}"
    return None

def safe_bigint(val):
    try: return int(str(val).replace(",", "").strip())
    except: return None

def bulk_update(records):
    if not records: return 0
    vals = ','.join(cur.mogrify('(%s,%s,%s,%s,%s,%s)', r).decode() for r in records)
    cur.execute(f"""
        UPDATE stocks SET
            listing_date  = COALESCE(v.ld, listing_date),
            capital_stock = COALESCE(v.cs, capital_stock),
            website       = COALESCE(v.wb, website),
            english_name  = COALESCE(v.en, english_name),
            shares        = COALESCE(v.sh, shares),
            updated_at    = NOW()
        FROM (VALUES {vals}) AS v(ld,cs,wb,en,sh,symbol)
        WHERE stocks.symbol = v.symbol
    """)
    return len(records)

# === TSE ===
print("TSE basic info (t187ap03_L)...")
r = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", timeout=30, verify=False)
tse_records = []
for item in r.json():
    sym = str(item.get("公司代號", "")).strip()
    if not sym or not sym.isdigit(): continue
    tse_records.append((
        parse_date(item.get("上市日期", "")),
        safe_bigint(item.get("實收資本額")),
        item.get("網址", "").strip() or None,
        item.get("英文簡稱", "").strip() or None,
        safe_bigint(item.get("已發行普通股數或TDR原股發行股數")),
        sym
    ))
n = bulk_update(tse_records)
conn.commit()
print(f"  TSE done: {n}")

# === OTC ===
print("OTC basic info (mopsfin_t187ap03_O)...")
r2 = requests.get("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", timeout=30, verify=False)
otc_records = []
for item in r2.json():
    sym = str(item.get("SecuritiesCompanyCode", "")).strip()
    if not sym or not sym.isdigit(): continue
    otc_records.append((
        parse_date(item.get("DateOfListing", "")),
        safe_bigint(item.get("Paidin.Capital.NTDollars")),
        item.get("WebAddress", "").strip().strip("　") or None,
        item.get("Symbol", "").strip().strip("　") or None,
        safe_bigint(item.get("IssueShares")),
        sym
    ))
n2 = bulk_update(otc_records)
conn.commit()
print(f"  OTC done: {n2}")

# verify
cur.execute("SELECT COUNT(*) FROM stocks WHERE listing_date IS NOT NULL")
print(f"listing_date total: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM stocks WHERE website IS NOT NULL")
print(f"website total: {cur.fetchone()[0]}")

cur.close(); conn.close()
print("All done!")
