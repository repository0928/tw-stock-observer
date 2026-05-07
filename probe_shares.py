"""
探測 shares 相關 API，確認欄位與數值單位
"""
import requests, urllib3
urllib3.disable_warnings()

def probe(label, url):
    print(f"\n{'='*60}")
    print(f"[{label}]  {url}")
    try:
        r = requests.get(url, timeout=20, verify=False)
        print(f"  Status: {r.status_code}  CT: {r.headers.get('Content-Type','')[:60]}")
        body = r.text.strip()
        if not body:
            print("  ❌ 空回應"); return
        if body[0] in ('[', '{'):
            j = r.json()
            items = j if isinstance(j, list) else j.get("data", [])
            if items:
                print(f"  共 {len(items)} 筆")
                print(f"  欄位: {list(items[0].keys())}")
                for item in items[:3]:
                    print(f"  範例: {dict(list(item.items())[:8])}")
            else:
                print("  ✅ JSON 但空陣列")
        else:
            print(f"  ❌ 非 JSON: {body[:120]!r}")
    except Exception as e:
        print(f"  ❌ {e}")

# TWSE 上市基本資料
probe("TWSE t51sb01",      "https://openapi.twse.com.tw/v1/opendata/t51sb01")

# TWSE 備選：用 BWIBBU_ALL 看看欄位
probe("TWSE BWIBBU_ALL",   "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_ALL?response=json")

# TPEx 看 Capitals 的實際值（找 0050/2330 對照）
print("\n\n=== TPEx tpex_mainboard_quotes - Capitals 值 ===")
r2 = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", timeout=20, verify=False)
items2 = r2.json() if r2.text.strip().startswith('[') else []
for item in items2[:8]:
    print(f"  {item.get('SecuritiesCompanyCode'):8} {str(item.get('CompanyName',''))[:12]:12} "
          f"Capitals={item.get('Capitals')}  TradingShares={item.get('TradingShares')}")
