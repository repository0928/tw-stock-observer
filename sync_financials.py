"""
同步財報比率（季更新）
來源：
  t187ap17_L → 上市 毛利率 / 營業利益率 / 稅後純益率
  t187ap14_L → 上市 EPS（基本每股盈餘）
  上櫃：TPEx openapi 目前尚未提供財報比率 JSON，待後續補充

ROE / ROA / 負債比：現行 TWSE openapi 無對應端點，暫不更新。
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
    if v in ("--", "", "N/A", "－", "－－"):
        return None
    try:
        f = float(v)
        return f if f != 0 else None
    except (ValueError, TypeError):
        return None


# ==================== 上市利潤率 (t187ap17_L) ====================
# 欄位（已確認）：
#   公司代號
#   毛利率(%)(營業毛利)/(營業收入)        → gross_margin
#   營業利益率(%)(營業利益)/(營業收入)     → operating_margin
#   稅後純益率(%)(稅後純益)/(營業收入)     → net_margin
print("下載上市利潤率資料 (t187ap17_L)...")
try:
    r = requests.get(
        "https://openapi.twse.com.tw/v1/opendata/t187ap17_L",
        timeout=30, verify=False
    )
    items = r.json()
    print(f"  共 {len(items)} 筆，欄位: {list(items[0].keys()) if items else '無'}")
except Exception as e:
    print(f"  ❌ 下載失敗: {e}")
    items = []

updated_margin = 0
for item in items:
    symbol = str(item.get("公司代號", "")).strip()
    if not symbol.isdigit():
        continue
    try:
        gross = safe_float(item.get("毛利率(%)(營業毛利)/(營業收入)"))
        op    = safe_float(item.get("營業利益率(%)(營業利益)/(營業收入)"))
        net   = safe_float(item.get("稅後純益率(%)(稅後純益)/(營業收入)"))

        if all(v is None for v in [gross, op, net]):
            continue

        try:
            cur.execute("SAVEPOINT sp_fin")
            cur.execute(
                """UPDATE stocks SET
                    gross_margin     = COALESCE(%s, gross_margin),
                    operating_margin = COALESCE(%s, operating_margin),
                    net_margin       = COALESCE(%s, net_margin),
                    updated_at       = %s
                   WHERE symbol = %s""",
                (gross, op, net, datetime.now(UTC), symbol)
            )
            cur.execute("RELEASE SAVEPOINT sp_fin")
            updated_margin += 1
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT sp_fin")
            print(f"  處理 {symbol} 利潤率失敗: {e}")
    except Exception as e:
        print(f"  處理 {symbol} 失敗: {e}")

conn.commit()
print(f"✅ 上市利潤率更新: {updated_margin} 筆")


# ==================== 上市 EPS (t187ap14_L) ====================
# 欄位（已確認）：
#   公司代號
#   基本每股盈餘(元)   → eps
print("下載上市 EPS 資料 (t187ap14_L)...")
try:
    r2 = requests.get(
        "https://openapi.twse.com.tw/v1/opendata/t187ap14_L",
        timeout=30, verify=False
    )
    items2 = r2.json()
    print(f"  共 {len(items2)} 筆")
except Exception as e:
    print(f"  ❌ 下載失敗: {e}")
    items2 = []

updated_eps = 0
for item in items2:
    symbol = str(item.get("公司代號", "")).strip()
    if not symbol.isdigit():
        continue
    try:
        eps = safe_float(item.get("基本每股盈餘(元)"))
        if eps is None:
            continue

        try:
            cur.execute("SAVEPOINT sp_eps")
            cur.execute(
                """UPDATE stocks SET
                    eps        = COALESCE(%s, eps),
                    updated_at = %s
                   WHERE symbol = %s""",
                (eps, datetime.now(UTC), symbol)
            )
            cur.execute("RELEASE SAVEPOINT sp_eps")
            updated_eps += 1
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT sp_eps")
            print(f"  處理 {symbol} EPS 失敗: {e}")
    except Exception as e:
        print(f"  處理 {symbol} 失敗: {e}")

conn.commit()
print(f"✅ 上市 EPS 更新: {updated_eps} 筆")


# ==================== 上櫃（暫不更新）====================
print("⚠️  上櫃財報 API 尚未找到可用 JSON 端點，跳過")
print("   （TPEx openapi 財報端點目前回傳 HTML）")


cur.close()
conn.close()
print("✅ 財報同步完成！")
