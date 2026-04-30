"""
偵錯腳本：列出各 API 的欄位名稱與第一筆資料
用途：找出正確的 JSON key，修正 sync 腳本
"""
import requests
import urllib3
urllib3.disable_warnings()

def probe(label, url, method="GET", data=None):
    print(f"\n{'='*60}")
    print(f"[{label}]")
    print(f"URL: {url}")
    try:
        if method == "POST":
            r = requests.post(url, data=data, timeout=15, verify=False)
        else:
            r = requests.get(url, timeout=15, verify=False)
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('Content-Type','')}")
        print(f"Body 前 300 字元: {r.text[:300]!r}")
        try:
            j = r.json()
            if isinstance(j, list) and len(j) > 0:
                item = j[0]
                print(f"\n✅ JSON 陣列，共 {len(j)} 筆")
                print(f"第 1 筆欄位名稱: {list(item.keys())}")
                print(f"第 1 筆資料: {item}")
            elif isinstance(j, dict):
                print(f"\n✅ JSON 物件，keys: {list(j.keys())}")
                # 如果有 data 欄位
                if 'data' in j and isinstance(j['data'], list) and len(j['data']) > 0:
                    print(f"data[0]: {j['data'][0]}")
            else:
                print(f"JSON: {j}")
        except Exception as je:
            print(f"❌ JSON 解析失敗: {je}")
    except Exception as e:
        print(f"❌ 請求失敗: {e}")

# ── TWSE 月營收 ──
probe("TWSE 上市月營收 t187ap05_L",
      "https://openapi.twse.com.tw/v1/opendata/t187ap05_L")

# ── TWSE 財報比率 ──
probe("TWSE 上市財報 t187ap04_L",
      "https://openapi.twse.com.tw/v1/opendata/t187ap04_L")

# ── TPEx 上櫃三大法人 ──
probe("TPEx 上櫃三大法人 (openapi v1)",
      "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_3insti_info")

# 備用 TPEx 三大法人 URL
probe("TPEx 上櫃三大法人 (web API)",
      "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge.php?o=json&t=D&s=0&l=zh-tw")

# ── TPEx 上櫃月營收 ──
probe("TWSE 上櫃月營收 t187ap05_R",
      "https://openapi.twse.com.tw/v1/opendata/t187ap05_R")

# ── 確認 TWSE T86 三大法人欄位（已成功，看一下欄位）──
probe("TWSE 上市三大法人 T86（前3筆）",
      "https://www.twse.com.tw/rwd/zh/fund/T86?response=json&selectType=ALL")

print("\n\n偵錯完成！")
