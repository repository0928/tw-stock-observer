"""
同步重大訊息到 stock_announcements 表
上市：TWSE openapi t187ap04_L
上櫃：TPEx openapi mopsfin_t187ap04_O（或對應端點）

策略：INSERT ON CONFLICT DO NOTHING（歷史累積，不覆蓋已存在紀錄）
"""
import requests
import psycopg2
from datetime import datetime, date, UTC
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


def parse_tw_date(val):
    """
    解析民國/西元日期字串，回傳 date 物件
    支援格式：
      - 民國：113/04/30 → 2024-04-30
      - 西元：2024/04/30 或 2024-04-30
      - 純整數：1130430 → 2024-04-30
    """
    if not val:
        return None
    v = str(val).strip().replace("－", "-").replace("–", "-")
    try:
        # 民國（3碼年）
        if "/" in v:
            parts = v.split("/")
            if len(parts[0]) <= 3:  # 民國年
                year = int(parts[0]) + 1911
                month = int(parts[1])
                day = int(parts[2])
                return date(year, month, day)
            else:
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
        elif "-" in v:
            parts = v.split("-")
            if len(parts[0]) <= 3:
                year = int(parts[0]) + 1911
                return date(year, int(parts[1]), int(parts[2]))
            else:
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
        elif v.isdigit() and len(v) == 7:
            # 民國 7 碼：1130430
            year = int(v[:3]) + 1911
            month = int(v[3:5])
            day = int(v[5:7])
            return date(year, month, day)
        elif v.isdigit() and len(v) == 8:
            # 西元 8 碼：20240430
            return date(int(v[:4]), int(v[4:6]), int(v[6:8]))
    except (ValueError, TypeError):
        pass
    return None


def insert_announcement(symbol, announce_date, subject, content, source):
    """INSERT OR IGNORE 單筆重大訊息"""
    if not symbol or not announce_date or not subject:
        return False
    try:
        cur.execute("""
            INSERT INTO stock_announcements (symbol, announce_date, subject, content, source)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (symbol, announce_date, subject) DO NOTHING
        """, (symbol, announce_date, subject[:500] if subject else None,
              content[:2000] if content else None, source))
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"  INSERT {symbol} 失敗: {e}")
        return False


# ==================== 上市重大訊息 (t187ap04_L) ====================
print("下載上市重大訊息 (t187ap04_L)...")
try:
    r = requests.get(
        "https://openapi.twse.com.tw/v1/opendata/t187ap04_L",
        timeout=30, verify=False
    )
    items_tse = r.json()
    print(f"  共 {len(items_tse)} 筆")
    if items_tse:
        print(f"  欄位: {list(items_tse[0].keys())}")
except Exception as e:
    print(f"  ❌ 下載失敗: {e}")
    items_tse = []

inserted_tse = 0
for item in items_tse:
    symbol = str(item.get("公司代號", item.get("SecuritiesCompanyCode", ""))).strip()
    if not symbol:
        continue

    # 日期欄位嘗試
    raw_date = (
        item.get("發言日期") or item.get("AnnounceDate") or
        item.get("日期") or item.get("Date")
    )
    ann_date = parse_tw_date(raw_date)
    if not ann_date:
        ann_date = date.today()

    subject = str(
        item.get("主旨") or item.get("Subject") or
        item.get("發言主旨") or item.get("Title") or ""
    ).strip()
    content = str(
        item.get("說明") or item.get("Content") or
        item.get("發言內容") or ""
    ).strip()

    if insert_announcement(symbol, ann_date, subject or "（無主旨）", content, "TWSE"):
        inserted_tse += 1

conn.commit()
print(f"✅ 上市重大訊息新增: {inserted_tse} 筆")


# ==================== 上櫃重大訊息 ====================
print("下載上櫃重大訊息...")
OTC_ANN_URLS = [
    "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O",
    "https://www.tpex.org.tw/openapi/v1/mopsfin_187ap04_O",
]
items_otc = []
for url in OTC_ANN_URLS:
    try:
        r2 = requests.get(url, timeout=30, verify=False)
        if r2.status_code == 200 and r2.text.strip().startswith('['):
            items_otc = r2.json()
            print(f"  使用 URL: {url}，共 {len(items_otc)} 筆")
            if items_otc:
                print(f"  欄位: {list(items_otc[0].keys())}")
            break
        else:
            print(f"  {url} → HTTP {r2.status_code}，非 JSON")
    except Exception as e:
        print(f"  {url} → 失敗: {e}")

if not items_otc:
    print("  ⚠️  上櫃重大訊息 API 無可用 URL，跳過")

inserted_otc = 0
for item in items_otc:
    symbol = str(
        item.get("公司代號") or item.get("SecuritiesCompanyCode") or item.get("CompanyID") or ""
    ).strip()
    if not symbol:
        continue

    raw_date = (
        item.get("發言日期") or item.get("AnnounceDate") or
        item.get("日期") or item.get("Date")
    )
    ann_date = parse_tw_date(raw_date)
    if not ann_date:
        ann_date = date.today()

    subject = str(
        item.get("主旨") or item.get("Subject") or
        item.get("發言主旨") or item.get("Title") or ""
    ).strip()
    content = str(
        item.get("說明") or item.get("Content") or
        item.get("發言內容") or ""
    ).strip()

    if insert_announcement(symbol, ann_date, subject or "（無主旨）", content, "TPEx"):
        inserted_otc += 1

conn.commit()

# 統計
cur.execute("SELECT COUNT(*) FROM stock_announcements")
total = cur.fetchone()[0]
print(f"✅ 上櫃重大訊息新增: {inserted_otc} 筆")
print(f"\n📊 stock_announcements 表總計: {total} 筆")

cur.close()
conn.close()
print("✅ 重大訊息同步完成！")
