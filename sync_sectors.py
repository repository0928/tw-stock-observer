import requests
import psycopg2
import urllib3
from bs4 import BeautifulSoup
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

print("下載上市公司產業資料...")
r = requests.get(
    "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2",
    timeout=30, verify=False
)
r.encoding = 'big5'
soup = BeautifulSoup(r.text, 'lxml')

updated = 0
for row in soup.find_all('tr'):
    cols = row.find_all('td')
    if len(cols) < 5:
        continue
    code_name = cols[0].text.strip()
    sector = cols[4].text.strip()
    if '\u3000' in code_name and sector:
        symbol = code_name.split('\u3000')[0].strip()
        if symbol.isdigit():
            cur.execute(
                "UPDATE stocks SET sector = %s, updated_at = %s WHERE symbol = %s",
                (sector, datetime.now(UTC), symbol)
            )
            updated += 1

conn.commit()

# 上櫃公司
print("下載上櫃公司產業資料...")
r2 = requests.get(
    "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4",
    timeout=30, verify=False
)
r2.encoding = 'big5'
soup2 = BeautifulSoup(r2.text, 'lxml')

updated2 = 0
for row in soup2.find_all('tr'):
    cols = row.find_all('td')
    if len(cols) < 5:
        continue
    code_name = cols[0].text.strip()
    sector = cols[4].text.strip()
    if '\u3000' in code_name and sector:
        symbol = code_name.split('\u3000')[0].strip()
        if symbol.isdigit():
            cur.execute(
                "UPDATE stocks SET sector = %s, updated_at = %s WHERE symbol = %s",
                (sector, datetime.now(UTC), symbol)
            )
            updated2 += 1

conn.commit()
cur.close()
conn.close()
print(f"✅ 上市產業更新: {updated} 筆，上櫃產業更新: {updated2} 筆")