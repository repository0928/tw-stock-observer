"""
財務資料抓取（ROE / ROA / 負債比率）

全部改用 FinMind TaiwanStockBalanceSheet + TaiwanStockFinancialStatements API
- 免費、穩定、無反爬蟲、不會 IP 封鎖
- ROE = 全年稅後淨利 / 年末股東權益 * 100
- ROA = 全年稅後淨利 / 年末總資產 * 100
- 負債比率 = Liabilities_per（FinMind 直接提供）

token 從環境變數 FINMIND_TOKEN 讀取，可提高使用上限至 600 req/hr。
"""

import asyncio
import logging
import os
from datetime import date, timedelta

import aiohttp

logger = logging.getLogger(__name__)

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"
_FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")

# 兩個 dataset 呼叫之間的間隔（秒）
_INTER_CALL_DELAY = 1.0
# 最多重試次數
_MAX_RETRIES = 3


async def _finmind_get(dataset: str, stock_id: str, start_date: str) -> list:
    """
    呼叫 FinMind API，回傳 data 陣列。
    自動帶 token（若有設定），並在 429 或 limit msg 時指數退避重試。
    """
    url = (
        f"{FINMIND_BASE}"
        f"?dataset={dataset}&data_id={stock_id}&start_date={start_date}"
        f"&token={_FINMIND_TOKEN}"
    )
    for attempt in range(_MAX_RETRIES):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 429:
                        wait = 2 ** attempt * 5  # 5 / 10 / 20 秒
                        logger.warning(
                            f"FinMind 速率限制 {dataset} {stock_id}，"
                            f"{wait}s 後重試 (attempt {attempt+1})"
                        )
                        await asyncio.sleep(wait)
                        continue
                    if resp.status != 200:
                        logger.warning(
                            f"FinMind {dataset} {stock_id} HTTP {resp.status}"
                        )
                        return []
                    d = await resp.json()
                    data = d.get("data", [])
                    msg = d.get("msg", "")
                    if not data and "limit" in msg.lower():
                        wait = 2 ** attempt * 5
                        logger.warning(
                            f"FinMind limit msg '{msg}' {dataset} {stock_id}，"
                            f"{wait}s 後重試 (attempt {attempt+1})"
                        )
                        await asyncio.sleep(wait)
                        continue
                    return data
        except asyncio.TimeoutError:
            logger.warning(f"FinMind timeout {dataset} {stock_id} (attempt {attempt+1})")
            await asyncio.sleep(2 ** attempt * 3)
        except Exception as e:
            logger.error(f"FinMind {dataset} {stock_id} 失敗: {e}")
            return []
    logger.error(f"FinMind {dataset} {stock_id} 重試 {_MAX_RETRIES} 次後放棄")
    return []


async def fetch_goodinfo_financial(stock_id: str) -> dict:
    """
    取得單支股票的 ROE、ROA、負債比率。

    資料來源：FinMind（免費 API）
      - TaiwanStockBalanceSheet: TotalAssets, Equity, Liabilities_per
      - TaiwanStockFinancialStatements: IncomeAfterTaxes（各季）

    兩個 dataset 循序呼叫（非並發），中間間隔 _INTER_CALL_DELAY 秒。

    Returns
    -------
    dict { "roe": float|None, "roa": float|None, "debt_ratio": float|None }
    """
    result = {"roe": None, "roa": None, "debt_ratio": None}

    start = (date.today() - timedelta(days=548)).strftime("%Y-%m-%d")

    bs_data = await _finmind_get("TaiwanStockBalanceSheet", stock_id, start)
    await asyncio.sleep(_INTER_CALL_DELAY)
    fs_data = await _finmind_get("TaiwanStockFinancialStatements", stock_id, start)

    # 負債比率
    liab_rows = [r for r in bs_data if r["type"] == "Liabilities_per"]
    if liab_rows:
        liab_rows.sort(key=lambda x: x["date"], reverse=True)
        try:
            result["debt_ratio"] = float(liab_rows[0]["value"])
        except (ValueError, TypeError):
            pass

    # 年末資產與權益
    asset_rows = [r for r in bs_data if r["type"] == "TotalAssets"]
    equity_rows = [r for r in bs_data if r["type"] == "Equity"]

    if not asset_rows or not equity_rows:
        return result

    asset_rows.sort(key=lambda x: x["date"], reverse=True)
    equity_rows.sort(key=lambda x: x["date"], reverse=True)

    latest_year = asset_rows[0]["date"][:4]
    total_assets = float(asset_rows[0]["value"])
    equity = float(equity_rows[0]["value"])

    # 全年稅後淨利
    ni_rows = [
        r for r in fs_data
        if r["type"] == "IncomeAfterTaxes" and r["date"].startswith(latest_year)
    ]
    if not ni_rows:
        return result

    net_income = sum(float(r["value"]) for r in ni_rows)

    if equity and equity != 0:
        result["roe"] = round(net_income / equity * 100, 2)
    if total_assets and total_assets != 0:
        result["roa"] = round(net_income / total_assets * 100, 2)

    logger.info(
        f"財務資料 {stock_id} ({latest_year}): "
        f"ROE={result['roe']}, ROA={result['roa']}, 負債比率={result['debt_ratio']}"
    )
    return result


async def fetch_goodinfo_financial_batch(
    stock_ids: list,
    delay_seconds: float = 2.0,
) -> dict:
    """批量取得多支股票財務資料（保留向後相容）"""
    results = {}
    for i, stock_id in enumerate(stock_ids):
        if i > 0:
            await asyncio.sleep(delay_seconds)
        try:
            results[stock_id] = await fetch_goodinfo_financial(stock_id)
        except Exception as e:
            logger.error(f"批量爬取 {stock_id} 發生例外: {e}")
            results[stock_id] = {"roe": None, "roa": None, "debt_ratio": None}
    return results


# --- 快速測試 ----------------------------------------------------------------
if __name__ == "__main__":
    import sys

    async def _test():
        stock_id = sys.argv[1] if len(sys.argv) > 1 else "2330"
        print(f"Token: {'有設定' if _FINMIND_TOKEN else '未設定'}")
        print(f"測試: {stock_id}")
        data = await fetch_goodinfo_financial(stock_id)
        print(f"結果: {data}")

    asyncio.run(_test())
