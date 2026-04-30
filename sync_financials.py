"""
同步財報比率（季更新）
毛利率、營業利益率、淨利率、ROE、ROA、負債比率

上市：https://openapi.twse.com.tw/v1/opendata/t187ap04_L
上櫃：https://openapi.twse.com.tw/v1/opendata/t187ap04_R
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
    if v in ("--", "", "N/A", "－", "0"):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def find_field(item, *candidates):
    for key in candidates:
        if key in item and item[key] not in (None, "", "--"):
            return item[key]
    return None


def sync_market(label, url):
    print(f"下載{label}財報比率資料...")
    try:
        r = requests.get(url, timeout=30, verify=False)
        items = r.json()
    except Exception as e:
        print(f"  ❌ 下載失敗: {e}")
        return 0

    updated = 0
    for item in items:
        symbol_raw = find_field(item, "公司代號", "CompanyID", "company_id")
        if not symbol_raw:
            continue
        symbol = str(symbol_raw).strip()
        if not symbol.isdigit():
            continue
        try:
            # 毛利率
            gross = safe_float(find_field(item,
                "毛利率", "毛利率(%)", "GrossMargin", "gross_margin",
                "Gross_Profit_Margin"))

            # 營業利益率
            op = safe_float(find_field(item,
                "營業利益率", "營業利益率(%)", "OperatingMargin",
                "operating_margin", "Operating_Profit_Margin"))

            # 稅後純益率 / 淨利率
            net = safe_float(find_field(item,
                "稅後純益率", "淨利率", "淨利率(%)", "NetMargin",
                "net_margin", "Net_Profit_Margin", "After_Tax_Net_Profit_Margin"))

            # ROE（股東權益報酬率）
            roe = safe_float(find_field(item,
                "股東權益報酬率(%)", "股東權益報酬率", "ROE",
                "Return_On_Equity", "roe"))

            # ROA（資產報酬率）
            roa = safe_float(find_field(item,
                "資產報酬率(%)", "資產報酬率", "ROA",
                "Return_On_Assets", "roa"))

            # 負債比率
            debt = safe_float(find_field(item,
                "負債佔資產比率(%)", "負債比率", "負債比率(%)", "DebtRatio",
                "debt_ratio", "Debt_To_Asset_Ratio"))

            # 全部都是 None 就跳過
            if all(v is None for v in [gross, op, net, roe, roa, debt]):
                continue

            cur.execute(
                """UPDATE stocks SET
                    gross_margin     = COALESCE(%s, gross_margin),
                    operating_margin = COALESCE(%s, operating_margin),
                    net_margin       = COALESCE(%s, net_margin),
                    roe              = COALESCE(%s, roe),
                    roa              = COALESCE(%s, roa),
                    debt_ratio       = COALESCE(%s, debt_ratio),
                    updated_at       = %s
                   WHERE symbol = %s""",
                (gross, op, net, roe, roa, debt, datetime.now(UTC), symbol)
            )
            updated += 1
        except Exception as e:
            print(f"  處理{label} {symbol} 失敗: {e}")

    conn.commit()
    print(f"✅ {label}財報更新: {updated} 筆")
    return updated


# ==================== 上市 ====================
sync_market("上市", "https://openapi.twse.com.tw/v1/opendata/t187ap04_L")

# ==================== 上櫃 ====================
sync_market("上櫃", "https://openapi.twse.com.tw/v1/opendata/t187ap04_R")

cur.close()
conn.close()
print("✅ 財報同步完成！")
