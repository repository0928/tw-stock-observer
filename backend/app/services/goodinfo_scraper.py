"""
財務資料抓取（ROE / ROA / 負債比率）

全部改用 FinMind TaiwanStockBalanceSheet + TaiwanStockFinancialStatements API
- 免費、穩定、無反爬蟲、不會 IP 封鎖
- ROE = 全年稅後淨利 / 年末股東權益 * 100
- ROA = 全年稅後淨利 / 年末總資產 * 100
- 負債比率 = Liabilities_per（FinMind 直接提供）

修正：兩個 FinMind 呼叫改為「循序」而非 asyncio.gather() 並發，
      並加入 retry + 指數退避，避免 Zeabur 環境觸發 FinMind 速率限制。
"""

import asyncio
import logging
from datetime import date, timedelta

import aiohttp

logger = logging.getLogger(__name__)

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"

# 每次 FinMind 兩個 dataset 呼叫之間的間隔（秒）
_INTER_CALL_DELAY = 1.0
# 最多重試次數
_MAX_RETRIES = 3


async def _finmind_get(dataset: str, stock_id: str, start_date: str) -> list:
    """
    呼叫 FinMind API，回傳 data 陣列。
    自動重試：遇到 429 或空回應時，指數退避後重試，最多 _MAX_RETRIES 次。
    """
    url = (
        f"{FINMIND_BASE}"
        f"?dataset={dataset}&data_id={stock_id}&start_date={start_date}&token="
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
                    # FinMind 速率限制時有時回 200 但 data=[] 且 msg 含 "limit"
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

    資料來源：FinMind（免費 API，無反爬蟲限制）
      - TaiwanStockBalanceSheet: TotalAssets, Equity, Liabilities_per
      - TaiwanStockFinancialStatements: IncomeAfterTaxes（各季）

    ⚠️  兩個 dataset 改為循序呼叫（非並發），並在中間加 _INTER_CALL_DELAY 秒，
        避免批量同步時從同一 IP 觸發 FinMind 速率限制。

    Returns
    -------
    dict { "roe": float|None, "roa": float|None, "debt_ratio": float|None }
    """
    result = {"roe": None, "roa": None, "debt_ratio": None}

    # 取近 1.5 年資料，確保能拿到最新完整年度
    start = (date.today() - timedelta(days=548)).strftime("%Y-%m-%d")

    # ── 循序呼叫兩個 dataset，中間間隔 _INTER_CALL_DELAY 秒 ──────────────
    bs_data = await _finmind_get("TaiwanStockBalanceSheet", stock_id, start)
    await asyncio.sleep(_INTER_CALL_DELAY)
    fs_data = await _finmind_get("TaiwanStockFinancialStatements", stock_id, start)

    # ── 負債比率（直接由 FinMind 提供）─────────────────────────────────
    liab_rows = [r for r in bs_data if r["type"] == "Liabilities_per"]
    if liab_rows:
        liab_rows.sort(key=lambda x: x["date"], reverse=True)
        try:
            result["debt_ratio"] = float(liab_rows[0]["value"])
        except (ValueError, TypeError):
            pass

    # ── 最新完整年度的年末資產與權益 ───────────────────────────────────
    asset_rows = [r for r in bs_data if r["type"] == "TotalAssets"]
    equity_rows = [r for r in bs_data if r["type"] == "Equity"]

    if not asset_rows or not equity_rows:
        logger.warning(f"FinMind BalanceSheet 無資料 {stock_id}")
        return result

    asset_rows.sort(key=lambda x: x["date"], reverse=True)
    equity_rows.sort(key=lambda x: x["date"], reverse=True)

    latest_date = asset_rows[0]["date"]   # e.g. "2025-12-31"
    latest_year = latest_date[:4]         # "2025"

    total_assets = float(asset_rows[0]["value"])
    equity = float(equity_rows[0]["value"])

    # ── 該年度全年稅後淨利（各季加總）──────────────────────────────────
    ni_rows = [
        r for r in fs_data
        if r["type"] == "IncomeAfterTaxes" and r["date"].startswith(latest_year)
    ]

    if not ni_rows:
        logger.warning(
            f"FinMind FinancialStatements 無 {latest_year} 淨利資料 {stock_id}"
        )
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
    delay_seconds: float = 2.0,
) -> dict:
    """
    批量取得多支股票的財務資料。

    每支股票的兩個 FinMind 呼叫已在 fetch_goodinfo_financial 內循序執行，
    並且中間已有 _INTER_CALL_DELAY（1 秒）間隔。
    此處 delay_seconds 為「股票與股票之間」的額外等待（預設 2 秒）。

    總速率 ≈ 1 股票 / (2×_INTER_CALL_DELAY + delay_seconds)
           = 1 股票 / (2×1 + 2) = 1 股票 / 4 秒
           ≈ 15 支/分鐘，共 2 × 15 = 30 個 API 呼叫/分鐘 → FinMind 安全範圍。

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
