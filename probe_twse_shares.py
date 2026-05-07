"""
探測 TWSE 上市股數相關端點
"""
import requests, urllib3
urllib3.disable_warnings()

candidates = [
    ("t51sb02",    "https://openapi.twse.com.tw/v1/opendata/t51sb02"),
    ("t51sb05_L",  "https://openapi.twse.com.tw/v1/opendata/t51sb05_L"),
    ("t187ap03_L", "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"),
    ("t187ap16_L", "https://openapi.twse.com.tw/v1/opendata/t187ap16_L"),
    ("t187ap06_L", "https://openapi.twse.com.tw/v1/opendata/t187ap06_L"),
    ("t187ap07_L", "https://openapi.twse.com.tw/v1/opendata/t187ap07_L"),
    ("t187ap08_L", "https://openapi.twse.com.tw/v1/opendata/t187ap08_L"),
    ("BWIBBU_ALL-check", "https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_ALL?response=json"),
]

for label, url in candidates:
    try:
        r = requests.get(url, timeout=15, verify=False)
        body = r.text.strip()
        ct = r.headers.get('Content-Type','')
        if not body or body.startswith('<!'):
            print(f"❌ {label:20} HTML/空")
            continue
        if body.startswith('['):
            j = r.json()
            if j:
                keys = list(j[0].keys()) if isinstance(j[0], dict) else f"陣列({len(j[0])}欄)"
                # 找出含「股」「資本」「Capital」的欄位
                interesting = [k for k in (keys if isinstance(keys,list) else [])
                               if any(x in str(k) for x in ['股','資本','Capital','Share','share'])]
                print(f"✅ {label:20} {len(j):5}筆 | {keys}")
                if interesting:
                    print(f"   ★ 關鍵欄位: {interesting}")
                    print(f"   範例: { {k: j[0][k] for k in interesting[:4]} }")
            else:
                print(f"⚠️  {label:20} 空陣列")
        elif body.startswith('{'):
            j = r.json()
            data = j.get('data', [])
            fields = j.get('fields', j.get('title', []))
            print(f"✅ {label:20} data={len(data)}筆 | fields={fields}")
            if data:
                print(f"   首筆: {data[0]}")
        else:
            print(f"❓ {label:20} {body[:80]!r}")
    except Exception as e:
        print(f"❌ {label:20} {e}")
