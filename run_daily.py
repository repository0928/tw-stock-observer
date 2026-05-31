"""
每日自動同步腳本（Zeabur Cron 使用）
排程：週一至週五 15:30 TST（07:30 UTC）

執行項目：
  - sync_quotes.py       每日行情（收盤價、漲跌、成交量、週轉率）
  - sync_margin.py       融資/融券餘額與急增警示
  - sync_institutional.py 三大法人買賣超與外資連續天數
  - sync_announcements.py 重大訊息
  - sync_attention.py    注意股/處置股標記
"""
import subprocess
import sys
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SCRIPTS = [
    "sync_quotes.py",
    "sync_margin.py",
    "sync_institutional.py",
    "sync_announcements.py",
    "sync_attention.py",
    "sync_klines_daily.py",   # 每日 K 線增量同步（含更新 klines_latest）
    "run_screener_cache.py",  # 更新 screener 快取（須在 K 線同步後執行）
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
    print(f"🕒 每日同步開始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
        print(f"✅ 每日同步完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
