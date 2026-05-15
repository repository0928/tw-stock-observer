"""
每季自動同步腳本（Zeabur Cron 使用）
排程：每季財報公告後（1/15、4/15、7/15、10/15）09:00 TST（01:00 UTC）

執行項目：
  - sync_financials.py    財報比率（毛利率、營業利益率、淨利率）
  - sync_fundamental.py   本業獲利佔比、ROE 品質標記
  - sync_basic_info.py    公司基本資料（資本額、上市日期）
  - sync_basic_info2.py   公司基本資料補充
  - sync_sectors.py       產業分類更新
  - sync_stocks.py        股票清單更新（新掛牌、下市）
"""
import subprocess
import sys
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SCRIPTS = [
    "sync_financials.py",
    "sync_fundamental.py",
    "sync_fcf_interest.py",   # FCF 每股自由現金流 + 利息保障倍數
    "sync_basic_info.py",
    "sync_basic_info2.py",
    "sync_sectors.py",
    "sync_stocks.py",
]

def run(script: str):
    path = os.path.join(BASE_DIR, script)
    print(f"\n{'='*50}")
    print(f"▶ 執行 {script}  [{datetime.now().strftime('%H:%M:%S')}]")
    print(f"{'='*50}")
    result = subprocess.run(
        [sys.executable, path],
        capture_output=False,
        text=True,
    )
    if result.returncode != 0:
        print(f"⚠️  {script} 結束碼 {result.returncode}")
    return result.returncode

if __name__ == "__main__":
    print(f"📊 每季同步開始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    errors = []
    for script in SCRIPTS:
        code = run(script)
        if code != 0:
            errors.append(script)
    print(f"\n{'='*50}")
    if errors:
        print(f"⚠️  完成，{len(errors)} 個腳本異常: {errors}")
        sys.exit(1)
    else:
        print(f"✅ 每季同步完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
