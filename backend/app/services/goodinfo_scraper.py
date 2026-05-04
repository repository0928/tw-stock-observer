"""
財務資料抓取（ROE / ROA / 負債比率）

全部改用 FinMind TaiwanStockBalanceSheet + TaiwanStockFinancialStatements API
- 免費、穩定、無反爬蟲、不會 IP 封鎖
- ROE = 全年稅後淨利 / 年末股東權益 * 100
- ROA = 全年稅後淨利 / 年末總資產 * 100
- 負債比率 = Liabilities_per（FinMind 直接提供）
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"


async def _finmind_get(dataset: str, stock_id: str, start_date: str) -> list:
    """呼叫 FinMind API，回傳 data 陣列"""
    url = f"{FINMIND_BASE}?dataset={dataset}&data_id={stock_id}&start_date={start_date}&token="
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return []
                d = await resp.json()
                return d.get("data", [])
    except Exception as e:
        logger.error(f"FinMind {dataset} {stock_id} 失敗: {e}")
        return []


async def fetch_goodinfo_financial(stock_id: str) -> dict:
    """
    取得單支股票的 ROE、ROA、負債比率。

    資料來源：FinMind（免費 API，無反爬蟲限制）
      - TaiwanStockBalanceSheet: TotalAssets, Equity, Liabilities_per
      - TaiwanStockFinancialStatements: IncomeAfterTaxes（各季）

    Returns
    -------
    dict { "roe": float|None, "roa": float|None, "debt_ratio": float|None }
    """
    result = {"roe": None, "roa": None, "debt_ratio": None}

    # 取近 1.5 年資料，確保能拿到最新完整年度
    start = (date.today() - timedelta(days=548)).strftime("%Y-%m-%d")

    # 並發取兩個 dataset
    bs_data, fs_data = await asyncio.gather(
        _finmind_get("TaiwanStockBalanceSheet", stock_id, start),
        _finmind_get("TaiwanStockFinancialStatements", stock_id, start),
    )

    # ── 負債比率（直接由 FinMind 提供）─────────────────────────────────
    liab_rows = [r for r in bs_data if r["type"] == "Liabilities_per"]
    if liab_rows:
        liab_rows.sort(key=lambda x: x["date"], reverse=True)
        try:
            result["debt_ratio"] = float(liab_rows[0]["value"])
        except (ValueError, TypeError):
            pass

    # ── 最新完整年度的年末資產與權益 ───────────────────────────────────
    # 找最新有 TotalAssets 的年度（月份為 12-31 優先，否則取最新季末）
    asset_rows = [r for r in bs_data if r["type"] == "TotalAssets"]
    equity_rows = [r for r in bs_data if r["type"] == "Equity"]

    if not asset_rows or not equity_rows:
        logger.warning(f"FinMind BalanceSheet 無資料 {stock_id}")
        return result

    asset_rows.sort(key=lambda x: x["date"], reverse=True)
    equity_rows.sort(key=lambda x: x["date"], reverse=True)

    latest_date = asset_rows[0]["date"]          # e.g. "2025-12-31"
    latest_year = latest_date[:4]                # "2025"

    total_assets = float(asset_rows[0]["value"])
    equity = float(equity_rows[0]["value"])

    # ── 該年度全年稅後淨利（各季加總）──────────────────────────────────
    ni_rows = [
        r for r in fs_data
        if r["type"] == "IncomeAfterTaxes" and r["date"].startswith(latest_year)
    ]

    if not ni_rows:
        logger.warning(f"FinMind FinancialStatements 無 {latest_year} 淨利資料 {stock_id}")
        return result

    net_income = sum(float(r["value"]) for r in ni_rows)

    # ── 計算 ROE / ROA ─────────────────────────────────────────────────
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
    delay_seconds: float = 1.0,
) -> dict:
    """
    批量取得多支股票的財務資料。

    FinMind 不需要像 Goodinfo 一樣長時間等待，delay 可縮短至 1 秒。

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
            if (i + 1) % 50 == 0:
                logger.info(f"[{i+1}/{len(stock_ids)}] 批量財務同步進度")
        except Exception as e:
            logger.error(f"批量爬取 {stock_id} 發生例外: {e}")
            results[stock_id] = {"roe": None, "roa": None, "debt_ratio": None}
    return results


# --- 快速測試 ----------------------------------------------------------------

if __name__ == "__main__":
    import sys

    async def _test():
        stock_id = sys.argv[1] if len(sys.argv) > 1 else "2330"
        print(f"測試: {stock_id}")
        data = await fetch_goodinfo_financial(stock_id)
        print(f"結果: {data}")

    asyncio.run(_test())
