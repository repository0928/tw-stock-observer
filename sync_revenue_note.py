"""
同步月營收備註（revenue_note）
來源：
  上市：https://openapi.twse.com.tw/v1/opendata/t187ap05_L  （含備註欄位）
  上櫃：https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O（含備註欄位）

備註欄位說明：
  - MOPS 月報「備註」欄，記載各公司當月營收異常原因或補充說明
  - 常見關鍵字：需求增加、需求減少、匯率影響、交屋、庫存去化...
  - 值為 "－" / "-" / "--" 視為無備註，存 NULL
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


def clean_note(val):
    """清理備註：空值或佔位符號回傳 None"""
    if val is None:
        return None
    v = str(val).strip()
    if v in ("", "－", "-", "--", "－－", "N/A", "無"):
        return None
    return v


def sync_notes(label, items):
    """通用備註更新，只更新有備註的欄位；無備註則清空"""
    updated = 0
    for item in items:
        # 取公司代號
        symbol = str(
            item.get("公司代號") or
            item.get("SecuritiesCompanyCode") or
            item.get("CompanyID") or ""
        ).strip()
        if not symbol or not symbol.isdigit():
            continue

        note = clean_note(item.get("備註") or item.get("Remark") or item.get("remark"))

        try:
            cur.execute("SAVEPOINT sp_note")
            cur.execute(
                """UPDATE stocks SET
                    revenue_note = %s,
                    updated_at   = %s
                   WHERE symbol = %s""",
                (note, datetime.now(timezone.utc), symbol)
            )
            cur.execute("RELEASE SAVEPOINT sp_note")
            if cur.rowcount > 0:
                updated += 1
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT sp_note")
            print(f"  處理{label} {symbol} 失敗: {e}")

    return updated


# ==================== 上市備註 ====================
print("下載上市月營收備註 (t187ap05_L)...")
try:
    r = requests.get(
        "https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
        timeout=30, verify=False
    )
    items_tse = r.json()
    print(f"  共 {len(items_tse)} 筆")
except Exception as e:
    print(f"  ❌ 下載失敗: {e}")
    items_tse = []

updated_tse = sync_notes("上市", items_tse)
conn.commit()
print(f"✅ 上市備註更新: {updated_tse} 筆")


# ==================== 上櫃備註 ====================
print("下載上櫃月營收備註 (mopsfin_t187ap05_O)...")
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

updated_otc = sync_notes("上櫃", items_otc)
conn.commit()
print(f"✅ 上櫃備註更新: {updated_otc} 筆")


# ==================== 統計 ====================
cur.execute("SELECT COUNT(*) FROM stocks WHERE revenue_note IS NOT NULL")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM stocks WHERE revenue_note LIKE '%需求增加%'")
demand = cur.fetchone()[0]
print(f"\n📊 統計：共 {total} 筆有備註，其中含「需求增加」: {demand} 筆")

cur.close()
conn.close()
print("✅ 月營收備註同步完成！")
