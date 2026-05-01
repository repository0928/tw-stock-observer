"""
同步注意股票 / 處置股票標記
上市：
  注意 → openapi.twse.com.tw/v1/announcement/notetrans  (Code)
  處置 → openapi.twse.com.tw/v1/announcement/punish     (Code)
上櫃：
  注意 → tpex_trading_warning_information (SecuritiesCompanyCode)
         tpex_trading_warning_note         (SecuritiesCompanyCode)
         tpex_esb_warning_information      (證券代號)
  處置 → tpex_disposal_information         (SecuritiesCompanyCode)
         tpex_esb_disposal_information     (證券代號)

策略：先全清 → 再逐一打標（確保下架的標記能即時移除）
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


def fetch_json(url, label):
    try:
        r = requests.get(url, timeout=20, verify=False, headers={"User-Agent": "Mozilla/5.0"})
        body = r.text.strip()
        if r.status_code == 200 and (body.startswith('[') or body.startswith('{')):
            data = r.json()
            items = data if isinstance(data, list) else data.get("data", [])
            print(f"  {label}: {len(items)} 筆")
            return items
        else:
            print(f"  {label}: HTTP {r.status_code}，非 JSON，跳過")
            return []
    except Exception as e:
        print(f"  {label} 失敗: {e}")
        return []


def extract_code(item):
    for key in ("Code", "SecuritiesCompanyCode", "CompanyID", "證券代號", "公司代號", "stockNo"):
        v = str(item.get(key, "")).strip()
        if v and v.isdigit():
            return v
    return ""


# ── Step 1：全清標記 ─────────────────────────────────────────────
print("清除所有注意/處置標記...")
cur.execute("UPDATE stocks SET is_attention = FALSE, is_disposed = FALSE")
conn.commit()
print(f"  ✅ 已清除（影響 {cur.rowcount} 筆）")


# ── Step 2：上市注意股票 ─────────────────────────────────────────
print("\n下載上市注意股票...")
attn_tse = fetch_json(
    "https://openapi.twse.com.tw/v1/announcement/notetrans",
    "TWSE notetrans"
)

attn_tse_count = 0
for item in attn_tse:
    code = extract_code(item)
    if not code:
        continue
    cur.execute("UPDATE stocks SET is_attention = TRUE WHERE symbol = %s", (code,))
    if cur.rowcount > 0:
        attn_tse_count += 1
conn.commit()
print(f"✅ 上市注意股票標記: {attn_tse_count} 檔")


# ── Step 3：上市處置股票 ─────────────────────────────────────────
print("\n下載上市處置股票...")
disp_tse = fetch_json(
    "https://openapi.twse.com.tw/v1/announcement/punish",
    "TWSE punish"
)

disp_tse_count = 0
for item in disp_tse:
    code = extract_code(item)
    if not code:
        continue
    cur.execute("UPDATE stocks SET is_disposed = TRUE WHERE symbol = %s", (code,))
    if cur.rowcount > 0:
        disp_tse_count += 1
conn.commit()
print(f"✅ 上市處置股票標記: {disp_tse_count} 檔")


# ── Step 4：上櫃注意股票 ─────────────────────────────────────────
print("\n下載上櫃注意股票...")
OTC_ATTN_URLS = [
    ("https://www.tpex.org.tw/openapi/v1/tpex_trading_warning_information", "TPEx warning_info"),
    ("https://www.tpex.org.tw/openapi/v1/tpex_trading_warning_note",        "TPEx warning_note"),
    ("https://www.tpex.org.tw/openapi/v1/tpex_esb_warning_information",     "TPEx esb_warning"),
]

otc_attn_codes = set()
for url, label in OTC_ATTN_URLS:
    for item in fetch_json(url, label):
        code = extract_code(item)
        if code:
            otc_attn_codes.add(code)

otc_attn_count = 0
for code in otc_attn_codes:
    cur.execute("UPDATE stocks SET is_attention = TRUE WHERE symbol = %s", (code,))
    if cur.rowcount > 0:
        otc_attn_count += 1
conn.commit()
print(f"✅ 上櫃注意股票標記: {otc_attn_count} 檔（共收集 {len(otc_attn_codes)} 個代號）")


# ── Step 5：上櫃處置股票 ─────────────────────────────────────────
print("\n下載上櫃處置股票...")
OTC_DISP_URLS = [
    ("https://www.tpex.org.tw/openapi/v1/tpex_disposal_information",     "TPEx disposal_info"),
    ("https://www.tpex.org.tw/openapi/v1/tpex_esb_disposal_information", "TPEx esb_disposal"),
]

otc_disp_codes = set()
for url, label in OTC_DISP_URLS:
    for item in fetch_json(url, label):
        code = extract_code(item)
        if code:
            otc_disp_codes.add(code)

otc_disp_count = 0
for code in otc_disp_codes:
    cur.execute("UPDATE stocks SET is_disposed = TRUE WHERE symbol = %s", (code,))
    if cur.rowcount > 0:
        otc_disp_count += 1
conn.commit()
print(f"✅ 上櫃處置股票標記: {otc_disp_count} 檔（共收集 {len(otc_disp_codes)} 個代號）")


# ── 統計 ──────────────────────────────────────────────────────────
cur.execute("SELECT COUNT(*) FROM stocks WHERE is_attention = TRUE")
total_attn = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM stocks WHERE is_disposed = TRUE")
total_disp = cur.fetchone()[0]
print(f"\n📊 目前標記：注意 {total_attn} 檔，處置 {total_disp} 檔")

cur.execute("SELECT symbol, name FROM stocks WHERE is_attention = TRUE ORDER BY symbol")
rows = cur.fetchall()
if rows:
    print("  注意股：", ", ".join(f"{r[0]} {r[1]}" for r in rows))

cur.execute("SELECT symbol, name FROM stocks WHERE is_disposed = TRUE ORDER BY symbol LIMIT 10")
rows = cur.fetchall()
if rows:
    print("  處置股(前10)：", ", ".join(f"{r[0]} {r[1]}" for r in rows))

cur.close()
conn.close()
print("\n✅ 注意/處置標記同步完成！")
