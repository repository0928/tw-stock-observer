"""
Goodinfo 財務資料爬蟲
Goodinfo Financial Data Scraper

參考: https://minkuanchen.medium.com/python爬蟲-goodinfo的財務報表-c1147eb125f6

爬取項目:
- ROE (股東權益報酬率 %)
- ROA (資產報酬率 %)
- 負債比率 (%)
"""

import asyncio
import logging
import re
from typing import Optional
from decimal import Decimal

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ─── Goodinfo 請求標頭（必須帶 Referer，否則會被擋）─────────────────────────
GOODINFO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://goodinfo.tw/tw/index.asp",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ─── Goodinfo 財務績效頁面 URL ────────────────────────────────────────────────
GOODINFO_BIZ_PERF_URL = "https://goodinfo.tw/tw/StockBzPerformance.asp?STOCK_ID={stock_id}"

# 想抓的指標關鍵字 → 對應欄位名稱
METRIC_MAP = {
    "ROE": "roe",         # 股東權益報酬率(%)
    "ROA": "roa",         # 資產報酬率(%)
    "負債比率": "debt_ratio",  # 負債比率(%)
}


def _parse_float(text: str) -> Optional[float]:
    """將字串轉為 float，失敗回傳 None"""
    try:
        cleaned = re.sub(r"[^\d.\-]", "", text)
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


async def fetch_goodinfo_financial(stock_id: str) -> dict:
    """
    從 Goodinfo 財務績效頁面爬取最新一年的 ROE、ROA、負債比率。

    Parameters
    ----------
    stock_id : str
        台股代碼，例如 "2330"

    Returns
    -------
    dict  含以下鍵值（無法取得時為 None）
        {
            "roe": float | None,
            "roa": float | None,
            "debt_ratio": float | None,
        }
    """
    result = {"roe": None, "roa": None, "debt_ratio": None}
    url = GOODINFO_BIZ_PERF_URL.format(stock_id=stock_id)

    try:
        # Goodinfo 有反爬蟲，需要先訪問首頁取得 cookie，再請求目標頁面
        async with aiohttp.ClientSession(headers=GOODINFO_HEADERS) as session:
            # Step 1: 先取得首頁，讓 cookie 生效
            try:
                await session.get(
                    "https://goodinfo.tw/tw/index.asp",
                    timeout=aiohttp.ClientTimeout(total=15),
                    ssl=False,
                )
                await asyncio.sleep(1)  # 模擬人工瀏覽延遲
            except Exception:
                pass  # 首頁失敗不影響主要請求

            # Step 2: 請求財務績效頁面
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=30),
                ssl=False,
            ) as response:
                if response.status != 200:
                    logger.warning(
                        f"Goodinfo 回應狀態 {response.status}，股票代碼: {stock_id}"
                    )
                    return result

                # Goodinfo 頁面編碼為 UTF-8
                html = await response.text(encoding="utf-8", errors="replace")

    except aiohttp.ClientError as e:
        logger.error(f"Goodinfo 請求失敗 {stock_id}: {e}")
        return result
    except asyncio.TimeoutError:
        logger.error(f"Goodinfo 請求超時 {stock_id}")
        return result

    # ─── HTML 解析 ────────────────────────────────────────────────────────────
    try:
        soup = BeautifulSoup(html, "lxml")
        result = _extract_metrics(soup, result)
    except Exception as e:
        logger.error(f"Goodinfo HTML 解析失敗 {stock_id}: {e}")

    logger.info(
        f"Goodinfo 財務資料 {stock_id}: "
        f"ROE={result['roe']}, ROA={result['roa']}, 負債比率={result['debt_ratio']}"
    )
    return result


def _extract_metrics(soup: BeautifulSoup, result: dict) -> dict:
    """
    從 BeautifulSoup 解析出 ROE、ROA、負債比率。

    Goodinfo 財務績效頁面的表格結構：
    - 每一列第一個 <td> 是指標名稱
    - 後續各欄是「最新年度 → 歷史年度」的數值
    - 我們取第一個非空、非 '-' 的數值作為最新值
    """
    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if not cells:
                continue

            label = cells[0].get_text(strip=True)

            for keyword, field_name in METRIC_MAP.items():
                if result[field_name] is not None:
                    continue  # 已取得，略過
                if keyword not in label:
                    continue

                # 取第一個有效數值（跳過標頭與空值）
                for cell in cells[1:]:
                    raw = cell.get_text(strip=True)
                    if not raw or raw in {"-", "N/A", "－", "—"}:
                        continue
                    val = _parse_float(raw)
                    if val is not None:
                        result[field_name] = val
                        break

    return result


# ─── 批量爬取（多支股票，加入延遲避免被封 IP）────────────────────────────────

async def fetch_goodinfo_financial_batch(
    stock_ids: list[str],
    delay_seconds: float = 3.0,
) -> dict[str, dict]:
    """
    批量爬取多支股票的財務資料。

    Parameters
    ----------
    stock_ids : list[str]
        股票代碼清單
    delay_seconds : float
        每次請求之間的延遲秒數（預設 3 秒，避免被 Goodinfo 封鎖）

    Returns
    -------
    dict  { stock_id: { "roe": ..., "roa": ..., "debt_ratio": ... } }
    """
    results = {}
    for i, stock_id in enumerate(stock_ids):
        if i > 0:
            await asyncio.sleep(delay_seconds)
        try:
            data = await fetch_goodinfo_financial(stock_id)
            results[stock_id] = data
            logger.info(f"[{i+1}/{len(stock_ids)}] {stock_id} 完成")
        except Exception as e:
            logger.error(f"批量爬取 {stock_id} 發生例外: {e}")
            results[stock_id] = {"roe": None, "roa": None, "debt_ratio": None}
    return results


# ─── 快速測試 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    async def _test():
        stock_id = sys.argv[1] if len(sys.argv) > 1 else "2330"
        print(f"測試爬取: {stock_id}")
        data = await fetch_goodinfo_financial(stock_id)
        print(f"結果: {data}")

    asyncio.run(_test())
