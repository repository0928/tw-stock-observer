"""
解析 TWSE 與 TPEx Swagger，列出所有可用 API 端點與說明
"""
import requests, json, urllib3
urllib3.disable_warnings()

def parse_swagger(label, url):
    print(f"\n{'='*70}")
    print(f"【{label}】{url}")
    print('='*70)
    try:
        r = requests.get(url, timeout=20, verify=False)
        sw = r.json()
    except Exception as e:
        print(f"❌ 載入失敗: {e}"); return

    paths = sw.get("paths", {})
    print(f"共 {len(paths)} 個端點：\n")
    for path, methods in sorted(paths.items()):
        for method, info in methods.items():
            summary = info.get("summary") or info.get("description") or ""
            tags    = ", ".join(info.get("tags", []))
            print(f"  {method.upper():6} {path}")
            if summary: print(f"         → {summary}")
            if tags:    print(f"         tag: {tags}")

parse_swagger("台灣證交所 TWSE openapi",
              "https://openapi.twse.com.tw/v1/swagger.json")

parse_swagger("證券櫃檯買賣中心 TPEx openapi",
              "https://www.tpex.org.tw/openapi/swagger.json")
