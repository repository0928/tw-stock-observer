"""
第二輪偵錯：找正確的財報比率 API + TPEx 上櫃 URL
"""
import requests
import urllib3
urllib3.disable_warnings()

def probe(label, url):
    print(f"\n{'='*60}")
    print(f"[{label}]")
    try:
        r = requests.get(url, timeout=15, verify=False)
        print(f"Status: {r.status_code} | CT: {r.headers.get('Content-Type','')[:50]}")
        body = r.text[:200]
        if body.startswith('[') or body.startswith('{'):
            try:
                j = r.json()
                if isinstance(j, list) and len(j) > 0:
                    print(f"✅ 陣列 {len(j)} 筆 | keys: {list(j[0].keys())}")
                elif isinstance(j, dict) and 'data' in j:
                    print(f"✅ 物件 data[0]: {j.get('data',[[]])[0] if j.get('data') else 'empty'}")
                else:
                    print(f"✅ {type(j)} | {str(j)[:150]}")
            except Exception as e:
                print(f"❌ JSON: {e}")
        else:
            print(f"❌ 非 JSON: {body[:100]!r}")
    except Exception as e:
        print(f"❌ 請求失敗: {e}")

# ── 財報比率候選 URL ──
probe("TWSE 財報 t187ap06_L", "https://openapi.twse.com.tw/v1/opendata/t187ap06_L")
probe("TWSE 財報 t187ap14_L", "https://openapi.twse.com.tw/v1/opendata/t187ap14_L")
probe("TWSE 財報 t187ap16_L", "https://openapi.twse.com.tw/v1/opendata/t187ap16_L")
probe("TWSE 財報 t187ap17_L", "https://openapi.twse.com.tw/v1/opendata/t187ap17_L")
probe("TWSE 財報 BWIBBU_ALL", "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_ALL?response=json")

# ── TPEx 候選 URL ──
probe("TPEx 月營收", "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_monthly_revenue")
probe("TPEx 三大法人", "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_3insti")
probe("TPEx 三大法人 v2", "https://www.tpex.org.tw/openapi/v2/tpex_mainboard_3insti_info")
probe("TPEx 市場資訊", "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis")

print("\n完成！")
