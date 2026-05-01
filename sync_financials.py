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
                (gross, op, net, datetime.now(timezone.utc), symbol)
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
                (eps, datetime.now(timezone.utc), symbol)
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


# ==================== 上櫃利潤率 (mopsfin_187ap17_O) ====================
# Swagger 確認路徑：/v1/mopsfin_187ap17_O（注意：無 t 前綴）
print("下載上櫃利潤率資料 (mopsfin_187ap17_O)...")
OTC_MARGIN_URLS = [
    "https://www.tpex.org.tw/openapi/v1/mopsfin_187ap17_O",
    "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap17_O",
]
items_otc_margin = []
for url in OTC_MARGIN_URLS:
    try:
        r3 = requests.get(url, timeout=30, verify=False)
        if r3.status_code == 200 and r3.text.strip().startswith('['):
            items_otc_margin = r3.json()
            print(f"  使用 URL: {url}，共 {len(items_otc_margin)} 筆")
            if items_otc_margin:
                print(f"  欄位: {list(items_otc_margin[0].keys())}")
            break
        else:
            print(f"  {url} → HTTP {r3.status_code}，非 JSON")
    except Exception as e:
        print(f"  {url} → 失敗: {e}")

if not items_otc_margin:
    print("  ⚠️  上櫃利潤率 API 無可用 URL，跳過")

updated_otc_margin = 0
for item in items_otc_margin:
    symbol = str(
        item.get("公司代號") or item.get("SecuritiesCompanyCode") or item.get("CompanyID") or ""
    ).strip()
    if not symbol.isdigit():
        continue
    try:
        # 欄位名稱可能與上市相同，或使用英文
        # TPEx 實際欄位：毛利率 / 營業利益率 / 稅後純益率（無括號後綴）
        gross = safe_float(
            item.get("毛利率(%)(營業毛利)/(營業收入)") or
            item.get("毛利率(%)") or
            item.get("毛利率") or
            item.get("GrossMargin") or
            item.get("GrossMarginRate")
        )
        op = safe_float(
            item.get("營業利益率(%)(營業利益)/(營業收入)") or
            item.get("營業利益率(%)") or
            item.get("營業利益率") or
            item.get("OperatingMargin") or
            item.get("OperatingMarginRate")
        )
        net = safe_float(
            item.get("稅後純益率(%)(稅後純益)/(營業收入)") or
            item.get("稅後純益率(%)") or
            item.get("稅後純益率") or
            item.get("NetMargin") or
            item.get("NetMarginRate")
        )

        if all(v is None for v in [gross, op, net]):
            continue

        try:
            cur.execute("SAVEPOINT sp_otc_fin")
            cur.execute(
                """UPDATE stocks SET
                    gross_margin     = COALESCE(%s, gross_margin),
                    operating_margin = COALESCE(%s, operating_margin),
                    net_margin       = COALESCE(%s, net_margin),
                    updated_at       = %s
                   WHERE symbol = %s""",
                (gross, op, net, datetime.now(timezone.utc), symbol)
            )
            cur.execute("RELEASE SAVEPOINT sp_otc_fin")
            updated_otc_margin += 1
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT sp_otc_fin")
            print(f"  處理上櫃 {symbol} 利潤率失敗: {e}")
    except Exception as e:
        print(f"  處理上櫃 {symbol} 失敗: {e}")

conn.commit()
print(f"✅ 上櫃利潤率更新: {updated_otc_margin} 筆")


# ==================== 上櫃 EPS (mopsfin_t187ap14_O) ====================
print("下載上櫃 EPS 資料 (mopsfin_t187ap14_O)...")
OTC_EPS_URLS = [
    "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap14_O",
    "https://www.tpex.org.tw/openapi/v1/mopsfin_187ap14_O",
]
items_otc_eps = []
for url in OTC_EPS_URLS:
    try:
        r4 = requests.get(url, timeout=30, verify=False)
        if r4.status_code == 200 and r4.text.strip().startswith('['):
            items_otc_eps = r4.json()
            print(f"  使用 URL: {url}，共 {len(items_otc_eps)} 筆")
            if items_otc_eps:
                print(f"  欄位: {list(items_otc_eps[0].keys())}")
            break
        else:
            print(f"  {url} → HTTP {r4.status_code}，非 JSON")
    except Exception as e:
        print(f"  {url} → 失敗: {e}")

if not items_otc_eps:
    print("  ⚠️  上櫃 EPS API 無可用 URL，跳過")

updated_otc_eps = 0
for item in items_otc_eps:
    symbol = str(
        item.get("公司代號") or item.get("SecuritiesCompanyCode") or item.get("CompanyID") or ""
    ).strip()
    if not symbol.isdigit():
        continue
    try:
        # TPEx 實際欄位：基本每股盈餘（無「元」後綴）
        eps = safe_float(
            item.get("基本每股盈餘(元)") or
            item.get("基本每股盈餘") or
            item.get("每股盈餘(元)") or
            item.get("每股盈餘") or
            item.get("EPS") or
            item.get("BasicEPS")
        )
        if eps is None:
            continue

        try:
            cur.execute("SAVEPOINT sp_otc_eps")
            cur.execute(
                """UPDATE stocks SET
                    eps        = COALESCE(%s, eps),
                    updated_at = %s
                   WHERE symbol = %s""",
                (eps, datetime.now(timezone.utc), symbol)
            )
            cur.execute("RELEASE SAVEPOINT sp_otc_eps")
            updated_otc_eps += 1
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT sp_otc_eps")
            print(f"  處理上櫃 {symbol} EPS 失敗: {e}")
    except Exception as e:
        print(f"  處理上櫃 {symbol} 失敗: {e}")

conn.commit()
print(f"✅ 上櫃 EPS 更新: {updated_otc_eps} 筆")


cur.close()
conn.close()
print("✅ 財報同步完成！")
