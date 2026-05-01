"""
同步月營收資料（年增率 / 月增率）
上市：https://openapi.twse.com.tw/v1/opendata/t187ap05_L
上櫃：https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O
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

# DECIMAL(8,2) 最大值為 ±999999.99，但月增率超過此範圍時截斷
MAX_PCT = 999999.99


def safe_float(val):
    v = str(val).replace(",", "").strip()
    if v in ("--", "", "N/A", "－"):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def clamp_pct(val):
    """將百分比數值截斷在 DECIMAL(8,2) 範圍內"""
    if val is None:
        return None
    return max(-MAX_PCT, min(MAX_PCT, val))


def find_field(item, *candidates):
    for key in candidates:
        if key in item and item[key] not in (None, "", "--"):
            return item[key]
    return None


def sync_revenue(label, items):
    """通用處理：每筆用 SAVEPOINT 隔離，避免一筆錯誤炸掉整個 transaction"""
    updated = 0
    skipped = 0
    for item in items:
        symbol_raw = find_field(item, "公司代號", "SecuritiesCompanyCode", "CompanyID")
        if not symbol_raw:
            continue
        symbol = str(symbol_raw).strip()
        if not symbol.isdigit():
            continue

        yoy_raw = find_field(item,
            "營業收入-去年同月增減(%)",
            "去年同月增減(%)", "去年同月增減")
        mom_raw = find_field(item,
            "營業收入-上月比較增減(%)",
            "上月比較增減(%)", "上月比較增減")

        yoy = clamp_pct(safe_float(yoy_raw))
        mom = clamp_pct(safe_float(mom_raw))

        if yoy is None and mom is None:
            continue

        try:
            cur.execute("SAVEPOINT sp_rev")
            cur.execute(
                """UPDATE stocks SET
                    revenue_yoy = %s,
                    revenue_mom = %s,
                    updated_at  = %s
                   WHERE symbol = %s""",
                (yoy, mom, datetime.now(timezone.utc), symbol)
            )
            cur.execute("RELEASE SAVEPOINT sp_rev")
            updated += 1
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT sp_rev")
            skipped += 1
            # 只印非常規錯誤（overflow 已由 clamp 解決，剩下的才顯示）
            if "transaction is aborted" not in str(e):
                print(f"  處理{label} {symbol} 失敗: {e}")

    return updated, skipped


# ==================== 上市月營收 ====================
print("下載上市月營收資料...")
r = requests.get(
    "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
    timeout=30, verify=False
)
items_tse = r.json()
print(f"  共 {len(items_tse)} 筆")

updated, skipped = sync_revenue("上市", items_tse)
conn.commit()
print(f"✅ 上市月營收更新: {updated} 筆" + (f"（跳過 {skipped} 筆）" if skipped else ""))


# ==================== 上櫃月營收 ====================
print("下載上櫃月營收資料...")
try:
    r2 = requests.get(
        "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O",
        timeout=30, verify=False
    )
    items_otc = r2.json()
    print(f"  共 {len(items_otc)} 筆")
except Exception as e:
    print(f"  ❌ 下載失敗: {e}")
    items_otc = []

updated2, skipped2 = sync_revenue("上櫃", items_otc)
conn.commit()
print(f"✅ 上櫃月營收更新: {updated2} 筆" + (f"（跳過 {skipped2} 筆）" if skipped2 else ""))

cur.close()
conn.close()
print("✅ 月營收同步完成！")
