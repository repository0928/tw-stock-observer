"""
財務資料爬蟲（ROE / ROA / 負債比率）

來源：
  - ROE、ROA     : Goodinfo 財務績效頁面（需模擬 JS cookie 挑戰）
  - 負債比率      : FinMind TaiwanStockBalanceSheet API（免費，無反爬蟲）
"""

import asyncio
import logging
import re
import time
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Goodinfo
# ---------------------------------------------------------------------------

_TZ_OFFSET = -480  # 台灣 UTC+8，JS GetTimezoneOffset() 回傳 -480

GOODINFO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://goodinfo.tw/tw/index.asp",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ---------------------------------------------------------------------------
# FinMind
# ---------------------------------------------------------------------------

FINMIND_URL = (
    "https://api.finmindtrade.com/api/v4/data"
    "?dataset=TaiwanStockBalanceSheet&data_id={stock_id}&start_date={start_date}&token="
)


# ---------------------------------------------------------------------------
# 工具函數
# ---------------------------------------------------------------------------

def _excel_serial() -> float:
    """目前時間的 Excel 日期序號（Goodinfo JS 格式）"""
    return time.time() / 86400 - _TZ_OFFSET / 1440 + 25569


def _build_client_key() -> str:
    """模擬 Goodinfo JS 產生的 CLIENT_KEY cookie"""
    s = _excel_serial()
    return f"2.3|43115.1593771044|46448.4927104377|{_TZ_OFFSET}|{s}|{s}|0"


def _pf(text: str) -> Optional[float]:
    """字串轉 float，失敗回 None"""
    try:
        cleaned = re.sub(r"[^\d.\-]", "", text)
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Goodinfo 爬取（ROE / ROA）
# ---------------------------------------------------------------------------

async def _fetch_goodinfo_html(stock_id: str) -> Optional[str]:
    """
    取得 Goodinfo 財務績效頁面的 HTML。
    流程：首頁暖身 -> 模擬 JS 設定 CLIENT_KEY cookie -> 帶 REINIT 請求真實頁面。
    """
    reinit_val = str(_excel_serial())
    reinit_url = (
        f"https://goodinfo.tw/tw/StockBzPerformance.asp"
        f"?STOCK_ID={stock_id}&REINIT={reinit_val}"
    )
    jar = aiohttp.CookieJar(unsafe=True)

    try:
        async with aiohttp.ClientSession(headers=GOODINFO_HEADERS, cookie_jar=jar) as session:
            # Step 1: 訪問首頁取得伺服器端 session cookie
            try:
                await session.get(
                    "https://goodinfo.tw/tw/index.asp",
                    timeout=aiohttp.ClientTimeout(total=15),
                    ssl=False,
                )
                await asyncio.sleep(1.5)
            except Exception:
                pass

            # Step 2: 手動注入 CLIENT_KEY（模擬 JS setCookie）
            jar.update_cookies(
                {"CLIENT_KEY": _build_client_key()},
                response_url=aiohttp.client_reqrep.URL("https://goodinfo.tw"),
            )

            # Step 3: 帶 REINIT 請求真實頁面
            async with session.get(
                reinit_url,
                timeout=aiohttp.ClientTimeout(total=30),
                ssl=False,
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Goodinfo HTTP {resp.status} ({stock_id})")
                    return None
                html = await resp.text(encoding="utf-8", errors="replace")

                # 若仍是 JS 挑戰頁（< 3 KB），再試一次
                if len(html) < 3000:
                    await asyncio.sleep(2)
                    async with session.get(
                        reinit_url,
                        timeout=aiohttp.ClientTimeout(total=30),
                        ssl=False,
                    ) as resp2:
                        html = await resp2.text(encoding="utf-8", errors="replace")

                return html if len(html) > 3000 else None

    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.error(f"Goodinfo 請求失敗 {stock_id}: {e}")
        return None


def _extract_roe_roa(html: str) -> tuple:
    """
    從 Goodinfo 頁面 HTML 解析 ROE / ROA 一般平均值。

    頁面結構（摘要表）：
      header row : [..., 'ROE', 'ROA', 'EPS', ...]
      sub-header : ['平均(%)', '均成長', '平均(%)', '均成長', ...]
      data row   : ['一般平均', roe_avg, roe_growth, roa_avg, roa_growth, ...]

    每個指標在 header row 佔 1 格，但對應到 2 個 data 子欄（平均 + 均成長）。
    因此 roe_data_idx = 1 + (roe_header_idx - 1) * 2
    """
    soup = BeautifulSoup(html, "lxml")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row_idx, row in enumerate(rows):
            cells = row.find_all(["th", "td"])
            texts = [c.get_text(strip=True) for c in cells]
            if "ROE" not in texts or "ROA" not in texts:
                continue
            roe_hi = texts.index("ROE")
            roa_hi = texts.index("ROA")
            roe_di = 1 + (roe_hi - 1) * 2
            roa_di = 1 + (roa_hi - 1) * 2
            for data_row in rows[row_idx + 1: row_idx + 5]:
                dcells = data_row.find_all(["th", "td"])
                dtexts = [c.get_text(strip=True) for c in dcells]
                if dtexts and dtexts[0] == "一般平均":
                    roe = _pf(dtexts[roe_di]) if len(dtexts) > roe_di else None
                    roa = _pf(dtexts[roa_di]) if len(dtexts) > roa_di else None
                    return roe, roa
    return None, None


# ---------------------------------------------------------------------------
# FinMind 爬取（負債比率）
# ---------------------------------------------------------------------------

async def _fetch_finmind_debt_ratio(stock_id: str) -> Optional[float]:
    """
    從 FinMind TaiwanStockBalanceSheet 取得最新負債比率（Liabilities_per）。
    FinMind 免費 API，無需 token，無反爬蟲機制。
    """
    from datetime import date, timedelta
    start = (date.today() - timedelta(days=548)).strftime("%Y-%m-%d")  # 約 1.5 年前
    url = FINMIND_URL.format(stock_id=stock_id, start_date=start)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                rows = [
                    r for r in data.get("data", [])
                    if r.get("type") == "Liabilities_per"
                ]
                if not rows:
                    return None
                # 取最新日期
                rows.sort(key=lambda x: x["date"], reverse=True)
                return float(rows[0]["value"])
    except Exception as e:
        logger.error(f"FinMind 負債比率失敗 {stock_id}: {e}")
        return None


# ---------------------------------------------------------------------------
# 公開介面
# ---------------------------------------------------------------------------

async def fetch_goodinfo_financial(stock_id: str) -> dict:
    """
    取得單支股票的 ROE、ROA、負債比率。

    ROE / ROA  <- Goodinfo 財務績效頁
    負債比率   <- FinMind BalanceSheet API

    Returns
    -------
    dict { "roe": float|None, "roa": float|None, "debt_ratio": float|None }
    """
    result = {"roe": None, "roa": None, "debt_ratio": None}

    # ROE / ROA
    html = await _fetch_goodinfo_html(stock_id)
    if html:
        roe, roa = _extract_roe_roa(html)
        result["roe"] = roe
        result["roa"] = roa
    else:
        logger.warning(f"Goodinfo HTML 取得失敗 {stock_id}，ROE/ROA 設為 None")

    # 負債比率（不受 Goodinfo rate-limit 影響）
    result["debt_ratio"] = await _fetch_finmind_debt_ratio(stock_id)

    logger.info(
        f"財務資料 {stock_id}: "
        f"ROE={result['roe']}, ROA={result['roa']}, 負債比率={result['debt_ratio']}"
    )
    return result


async def fetch_goodinfo_financial_batch(
    stock_ids: list,
    delay_seconds: float = 3.0,
) -> dict:
    """
    批量取得多支股票的財務資料（每筆間隔 delay_seconds 秒）。

    Returns
    -------
    dict { stock_id: { "roe":..., "roa":..., "debt_ratio":... } }
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


# ---------------------------------------------------------------------------
# 快速測試
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    async def _test():
        stock_id = sys.argv[1] if len(sys.argv) > 1 else "2330"
        print(f"測試爬取: {stock_id}")
        data = await fetch_goodinfo_financial(stock_id)
        print(f"結果: {data}")

    asyncio.run(_test())
