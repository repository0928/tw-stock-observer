"""
共用工具：資料庫連線 retry + HTTP 請求 retry

使用方式：
    from db_utils import connect_with_retry, get_with_retry

    conn = connect_with_retry()
    r = get_with_retry("https://...")
"""

import time
import psycopg2
import requests

# ── 資料庫連線設定 ────────────────────────────────────────────
DB_CONFIG = dict(
    host="43.167.191.181",
    port=31218,
    database="zeabur",
    user="root",
    password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh",
)


def connect_with_retry(max_retries: int = 3, delay: int = 10) -> psycopg2.extensions.connection:
    """
    建立 PostgreSQL 連線，失敗時自動重試。

    Args:
        max_retries: 最多嘗試次數（預設 3）
        delay:       每次重試前等待秒數（預設 10）

    Returns:
        psycopg2 connection 物件

    Raises:
        psycopg2.OperationalError: 達到最大重試次數後仍失敗
    """
    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(**DB_CONFIG, connect_timeout=15)
            if attempt > 1:
                print(f"  ✅ 第 {attempt} 次連線成功")
            return conn
        except psycopg2.OperationalError as e:
            if attempt == max_retries:
                print(f"  ❌ 資料庫連線失敗，已重試 {max_retries} 次，放棄。")
                raise
            print(f"  ⚠️  資料庫連線失敗 (第 {attempt}/{max_retries} 次): {e}")
            print(f"      等待 {delay} 秒後重試...")
            time.sleep(delay)


def get_with_retry(
    url: str,
    max_retries: int = 3,
    delay: int = 5,
    **kwargs,
) -> requests.Response:
    """
    發送 GET 請求，遇到 Timeout / ConnectionError 時自動重試。

    Args:
        url:         目標 URL
        max_retries: 最多嘗試次數（預設 3）
        delay:       每次重試前等待秒數（預設 5）
        **kwargs:    傳給 requests.get() 的其餘參數

    Returns:
        requests.Response 物件

    Raises:
        requests.exceptions.RequestException: 達到最大重試次數後仍失敗
    """
    RETRYABLE = (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
    )
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, **kwargs)
            return r
        except RETRYABLE as e:
            if attempt == max_retries:
                print(f"  ❌ API 請求失敗，已重試 {max_retries} 次，放棄。URL={url}")
                raise
            print(f"  ⚠️  API 請求失敗 (第 {attempt}/{max_retries} 次): {e}")
            print(f"      等待 {delay} 秒後重試...")
            time.sleep(delay)
