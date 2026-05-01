"""
同步注意股票 / 處置股票標記
上市：TWSE openapi announcement/attention + announcement/disposition
上櫃：TPEx openapi（嘗試對應端點）

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


def extract_symbol(item):
    """從各種欄位名稱取得股票代號"""
    for key in ("公司代號", "SecuritiesCompanyCode", "CompanyID", "stockNo", "Code"):
        v = item.get(key, "")
        if v:
            return str(v).strip()
    return ""


# ── Step 1：全清標記 ────────────────────────────────────────
print("清除所有注意/處置標記...")
cur.execute("UPDATE stocks SET is_attention = FALSE, is_disposed = FALSE")
conn.commit()
print(f"  ✅ 已清除（影響 {cur.rowcount} 筆）")


# ── Step 2：上市注意股票 ────────────────────────────────────
print("下載上市注意股票...")
ATTN_URLS = [
    # TWSE rwd API（與 T86/MI_MARGN 同域，較穩定）
    "https://www.twse.com.tw/rwd/zh/announcement/ATTENTION?response=json",
    "https://www.twse.com.tw/rwd/zh/notice/attention?response=json",
    # openapi 備選（目前回傳 HTML，留存以備日後修復）
    "https://openapi.twse.com.tw/v1/announcement/attention",
    "https://openapi.twse.com.tw/v1/opendata/t49sb12_1",
]
attn_items = []
for url in ATTN_URLS:
    try:
        r = requests.get(url, timeout=20, verify=False)
        if r.status_code == 200 and r.text.strip().startswith('['):
            attn_items = r.json()
            print(f"  使用 URL: {url}，共 {len(attn_items)} 筆")
            if attn_items:
                print(f"  欄位: {list(attn_items[0].keys())}")
            break
        else:
            print(f"  {url} → HTTP {r.status_code}，非 JSON")
    except Exception as e:
        print(f"  {url} → 失敗: {e}")

attn_count = 0
for item in attn_items:
    symbol = extract_symbol(item)
    if not symbol.isdigit():
        continue
    try:
        cur.execute("UPDATE stocks SET is_attention = TRUE WHERE symbol = %s", (symbol,))
        if cur.rowcount > 0:
            attn_count += 1
    except Exception as e:
        print(f"  注意 {symbol} 失敗: {e}")

conn.commit()
print(f"✅ 上市注意股票標記: {attn_count} 檔")


# ── Step 3：上市處置股票 ────────────────────────────────────
print("下載上市處置股票...")
DISP_URLS = [
    # TWSE rwd API
    "https://www.twse.com.tw/rwd/zh/announcement/DISPOSE?response=json",
    "https://www.twse.com.tw/rwd/zh/notice/dispose?response=json",
    # openapi 備選
    "https://openapi.twse.com.tw/v1/announcement/disposition",
    "https://openapi.twse.com.tw/v1/opendata/t49sb12_2",
]
disp_items = []
for url in DISP_URLS:
    try:
        r2 = requests.get(url, timeout=20, verify=False)
        if r2.status_code == 200 and r2.text.strip().startswith('['):
            disp_items = r2.json()
            print(f"  使用 URL: {url}，共 {len(disp_items)} 筆")
            if disp_items:
                print(f"  欄位: {list(disp_items[0].keys())}")
            break
        else:
            print(f"  {url} → HTTP {r2.status_code}，非 JSON")
    except Exception as e:
        print(f"  {url} → 失敗: {e}")

disp_count = 0
for item in disp_items:
    symbol = extract_symbol(item)
    if not symbol.isdigit():
        continue
    try:
        cur.execute("UPDATE stocks SET is_disposed = TRUE WHERE symbol = %s", (symbol,))
        if cur.rowcount > 0:
            disp_count += 1
    except Exception as e:
        print(f"  處置 {symbol} 失敗: {e}")

conn.commit()
print(f"✅ 上市處置股票標記: {disp_count} 檔")


# ── Step 4：上櫃注意/處置 ────────────────────────────────────
print("下載上櫃注意/處置資料...")
OTC_ATTN_URLS = [
    "https://www.tpex.org.tw/openapi/v1/tpex_attention_stock",
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_attention",
    "https://www.tpex.org.tw/openapi/v1/tpex_attention_stocks_info",
    "https://www.tpex.org.tw/openapi/v1/tpex_dailyquotes_attention",
]
OTC_DISP_URLS = [
    "https://www.tpex.org.tw/openapi/v1/tpex_disposition_stock",
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_disposition",
    "https://www.tpex.org.tw/openapi/v1/tpex_disposition_stocks_info",
]

def try_fetch_json(urls, label):
    for url in urls:
        try:
            r = requests.get(url, timeout=15, verify=False)
            if r.status_code == 200 and r.text.strip().startswith('['):
                items = r.json()
                print(f"  {label} 使用: {url}，共 {len(items)} 筆")
                return items
            else:
                print(f"  {url} → HTTP {r.status_code}，非 JSON")
        except Exception as e:
            print(f"  {url} → 失敗: {e}")
    print(f"  ⚠️  {label} 無可用 URL，跳過")
    return []

otc_attn = try_fetch_json(OTC_ATTN_URLS, "上櫃注意")
otc_disp = try_fetch_json(OTC_DISP_URLS, "上櫃處置")

otc_attn_count = 0
for item in otc_attn:
    symbol = extract_symbol(item)
    if not symbol.isdigit():
        continue
    cur.execute("UPDATE stocks SET is_attention = TRUE WHERE symbol = %s", (symbol,))
    if cur.rowcount > 0:
        otc_attn_count += 1

otc_disp_count = 0
for item in otc_disp:
    symbol = extract_symbol(item)
    if not symbol.isdigit():
        continue
    cur.execute("UPDATE stocks SET is_disposed = TRUE WHERE symbol = %s", (symbol,))
    if cur.rowcount > 0:
        otc_disp_count += 1

conn.commit()
print(f"✅ 上櫃注意: {otc_attn_count} 檔，處置: {otc_disp_count} 檔")

# 統計
cur.execute("SELECT COUNT(*) FROM stocks WHERE is_attention = TRUE")
total_attn = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM stocks WHERE is_disposed = TRUE")
total_disp = cur.fetchone()[0]
print(f"\n📊 目前標記：注意 {total_attn} 檔，處置 {total_disp} 檔")

cur.close()
conn.close()
print("✅ 注意/處置標記同步完成！")
