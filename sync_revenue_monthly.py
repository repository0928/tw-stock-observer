"""
同步月營收資料（年增率 / 月增率）
上市：https://openapi.twse.com.tw/v1/opendata/t187ap05_L
上櫃：https://openapi.twse.com.tw/v1/opendata/t187ap05_R
"""
import requests
import psycopg2
from datetime import datetime, UTC
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


def safe_float(val):
    v = str(val).replace(",", "").strip()
    if v in ("--", "", "N/A", "－"):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def find_field(item, *candidates):
    """從多個候選欄位名稱中取出第一個有值的"""
    for key in candidates:
        if key in item and item[key] not in (None, "", "--"):
            return item[key]
    return None


# ==================== 上市月營收 ====================
print("下載上市月營收資料...")
r = requests.get(
    "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
    timeout=30, verify=False
)

updated = 0
for item in r.json():
    # 欄位名稱可能為中文或英文
    symbol_raw = find_field(item, "公司代號", "CompanyID", "company_id")
    if not symbol_raw:
        continue
    symbol = str(symbol_raw).strip()
    if not symbol.isdigit():
        continue
    try:
        # 上月比較增減(%) = revenue_mom
        # 去年同月增減(%)  = revenue_yoy
        yoy_raw = find_field(item,
            "去年同月增減(%)", "去年同月增減",
            "YoYChange", "yoy_change", "Year_Over_Year_Growth")
        mom_raw = find_field(item,
            "上月比較增減(%)", "上月比較增減",
            "MoMChange", "mom_change", "Month_Over_Month_Growth")

        yoy = safe_float(yoy_raw)
        mom = safe_float(mom_raw)

        if yoy is None and mom is None:
            continue

        cur.execute(
            """UPDATE stocks SET
                revenue_yoy = %s,
                revenue_mom = %s,
                updated_at = %s
               WHERE symbol = %s""",
            (yoy, mom, datetime.now(UTC), symbol)
        )
        updated += 1
    except Exception as e:
        print(f"處理上市月營收 {symbol} 失敗: {e}")

conn.commit()
print(f"✅ 上市月營收更新: {updated} 筆")


# ==================== 上櫃月營收 ====================
print("下載上櫃月營收資料...")
r2 = requests.get(
    "https://openapi.twse.com.tw/v1/opendata/t187ap05_R",
    timeout=30, verify=False
)

updated2 = 0
for item in r2.json():
    symbol_raw = find_field(item, "公司代號", "CompanyID", "company_id")
    if not symbol_raw:
        continue
    symbol = str(symbol_raw).strip()
    if not symbol.isdigit():
        continue
    try:
        yoy_raw = find_field(item,
            "去年同月增減(%)", "去年同月增減",
            "YoYChange", "yoy_change", "Year_Over_Year_Growth")
        mom_raw = find_field(item,
            "上月比較增減(%)", "上月比較增減",
            "MoMChange", "mom_change", "Month_Over_Month_Growth")

        yoy = safe_float(yoy_raw)
        mom = safe_float(mom_raw)

        if yoy is None and mom is None:
            continue

        cur.execute(
            """UPDATE stocks SET
                revenue_yoy = %s,
                revenue_mom = %s,
                updated_at = %s
               WHERE symbol = %s""",
            (yoy, mom, datetime.now(UTC), symbol)
        )
        updated2 += 1
    except Exception as e:
        print(f"處理上櫃月營收 {symbol} 失敗: {e}")

conn.commit()
cur.close()
conn.close()
print(f"✅ 上櫃月營收更新: {updated2} 筆")
print("✅ 月營收同步完成！")
