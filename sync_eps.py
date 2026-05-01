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

def sync_eps(data, market):
    updated = 0
    for item in data:
        symbol = item.get("公司代號", item.get("SecuritiesCompanyCode", "")).strip()
        if not symbol.isdigit():
            continue
        try:
            eps_str = item.get("基本每股盈餘(元)", item.get("基本每股盈餘", "")).strip()
            eps = float(eps_str) if eps_str not in ("", "--", "N/A") else None
            revenue_str = item.get("營業收入", "").strip()
            revenue = int(float(revenue_str)) if revenue_str not in ("", "--") else None
            net_income_str = item.get("稅後淨利", "").strip()
            net_income = int(float(net_income_str)) if net_income_str not in ("", "--") else None

            cur.execute("""
                UPDATE stocks SET 
                    eps = %s, revenue = %s, net_income = %s, updated_at = %s
                WHERE symbol = %s
            """, (eps, revenue, net_income, datetime.now(UTC), symbol))
            updated += 1
        except Exception as e:
            print(f"處理 {symbol} 失敗: {e}")
    return updated

# 上市
print("下載上市 EPS...")
r = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap14_L", timeout=30, verify=False)
updated1 = sync_eps(r.json(), "上市")
conn.commit()
print(f"✅ 上市 EPS: {updated1} 筆")

# 上櫃
print("下載上櫃 EPS...")
r2 = requests.get("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap14_O", timeout=30, verify=False)
updated2 = sync_eps(r2.json(), "上櫃")
conn.commit()
print(f"✅ 上櫃 EPS: {updated2} 筆")

cur.close()
conn.close()
print("✅ 完成！")