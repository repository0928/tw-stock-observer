"""
同步三大法人買賣超資料
上市：TWSE T86 API
上櫃：TPEx openapi
單位統一存為「張」（1張=1000股）
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


def parse_int(val):
    """解析整數，去除千分位逗號"""
    v = str(val).replace(",", "").strip()
    if v in ("--", "", "X", "N/A"):
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


# ==================== 上市三大法人 ====================
print("下載上市三大法人資料...")
r = requests.get(
    "https://www.twse.com.tw/rwd/zh/fund/T86?response=json&selectType=ALL",
    timeout=30, verify=False
)
data = r.json()
rows = data.get("data", [])

# T86 欄位說明：
# [0]  證券代號
# [1]  證券名稱
# [2]  外陸資買進股數(不含外資自營商)
# [3]  外陸資賣出股數(不含外資自營商)
# [4]  外陸資買賣超股數(不含外資自營商)  ← foreign_net_buy
# [5]  外資自營商買進股數
# [6]  外資自營商賣出股數
# [7]  外資自營商買賣超股數
# [8]  投信買進股數
# [9]  投信賣出股數
# [10] 投信買賣超股數                    ← investment_trust_net_buy
# [11] 自營商買賣超股數(合計)            ← dealer_net_buy
# [12] 自營商買進股數(自行買賣)
# [13] 自營商賣出股數(自行買賣)
# [14] 自營商買進股數(避險)
# [15] 自營商賣出股數(避險)
# [16] 自營商買賣超股數(避險)
# [17] 三大法人買賣超股數

updated = 0
for row in rows:
    if len(row) < 12:
        continue
    symbol = str(row[0]).strip()
    if not symbol.isdigit():
        continue
    try:
        # 單位：股 → 轉換為張（/1000）
        foreign_shares   = parse_int(row[4])
        trust_shares     = parse_int(row[10])
        dealer_shares    = parse_int(row[11])

        foreign   = round(foreign_shares / 1000) if foreign_shares is not None else None
        trust     = round(trust_shares   / 1000) if trust_shares   is not None else None
        dealer    = round(dealer_shares  / 1000) if dealer_shares  is not None else None

        cur.execute(
            """UPDATE stocks SET
                foreign_net_buy = %s,
                investment_trust_net_buy = %s,
                dealer_net_buy = %s,
                updated_at = %s
               WHERE symbol = %s""",
            (foreign, trust, dealer, datetime.now(UTC), symbol)
        )
        updated += 1
    except Exception as e:
        print(f"處理上市三大法人 {symbol} 失敗: {e}")

conn.commit()
print(f"✅ 上市三大法人更新: {updated} 筆")


# ==================== 上櫃三大法人 ====================
# TPEx 三大法人 JSON API 目前尚未找到可用端點，跳過
print("下載上櫃三大法人資料...")
OTC_3INSTI_URLS = [
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_3insti_info",
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_3insti",
]

otc_inst_items = []
for url in OTC_3INSTI_URLS:
    try:
        r2 = requests.get(url, timeout=15, verify=False)
        if r2.status_code == 200 and r2.text.strip().startswith('['):
            otc_inst_items = r2.json()
            print(f"  使用 URL: {url}，共 {len(otc_inst_items)} 筆")
            break
        else:
            print(f"  URL 回傳非 JSON ({r2.status_code}): {url}")
    except Exception as e:
        print(f"  URL 失敗: {e}")

if not otc_inst_items:
    print("  ⚠️ 上櫃三大法人 API 尚未找到可用 URL，跳過")

updated2 = 0
for item in otc_inst_items:
    symbol = item.get("SecuritiesCompanyCode", "").strip()
    if not symbol.isdigit():
        continue
    try:
        # TPEx 欄位（單位：張）
        foreign = parse_int(item.get("ForeignInvestorsNetBuyOrSellShares",
                            item.get("Foreign_Investor_Net_Buy_Sell", "")))
        trust   = parse_int(item.get("InvestmentTrustNetBuyOrSellShares",
                            item.get("Investment_Trust_Net_Buy_Sell", "")))
        dealer  = parse_int(item.get("DealerNetBuyOrSellShares",
                            item.get("Dealer_Net_Buy_Sell", "")))

        # 若欄位名稱不同，嘗試 ForeignNetBuy 等變體
        if foreign is None:
            for key in item:
                if "Foreign" in key and "Net" in key:
                    foreign = parse_int(item[key])
                    break
        if trust is None:
            for key in item:
                if ("Trust" in key or "InvestmentTrust" in key) and "Net" in key:
                    trust = parse_int(item[key])
                    break
        if dealer is None:
            for key in item:
                if "Dealer" in key and "Net" in key:
                    dealer = parse_int(item[key])
                    break

        cur.execute(
            """UPDATE stocks SET
                foreign_net_buy = %s,
                investment_trust_net_buy = %s,
                dealer_net_buy = %s,
                updated_at = %s
               WHERE symbol = %s""",
            (foreign, trust, dealer, datetime.now(UTC), symbol)
        )
        updated2 += 1
    except Exception as e:
        print(f"處理上櫃三大法人 {symbol} 失敗: {e}")

conn.commit()
cur.close()
conn.close()
print(f"✅ 上櫃三大法人更新: {updated2} 筆")
print("✅ 三大法人同步完成！")
