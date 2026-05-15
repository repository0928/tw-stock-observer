"""
財務資料抓取（季度財務 + ROE / ROA / 負債比率）

資料來源：FinMind API
  - TaiwanStockBalanceSheet:
      TotalAssets, Equity, Liabilities_per,
      ContractLiabilitiesCurrent（合約負債）, Inventories（存貨）
  - TaiwanStockFinancialStatements:
      IncomeAfterTaxes（稅後淨利）, Revenue（營收）, GrossProfit（毛利）

token 從環境變數 FINMIND_TOKEN 讀取，可提高使用上限至 600 req/hr。
"""

import asyncio
import logging
import os
from datetime import date, timedelta
from typing import Optional

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
                        wait = 2 ** attempt * 5
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


def _date_to_quarter(date_str: str) -> Optional[tuple]:
    """
    將 FinMind 日期字串（YYYY-MM-DD）轉為 (year, quarter)。
    回傳 None 表示無法解析。
    """
    try:
        month = int(date_str[5:7])
        year = int(date_str[:4])
        quarter = (month - 1) // 3 + 1
        return year, quarter
    except (ValueError, IndexError):
        return None


async def fetch_goodinfo_financial(stock_id: str) -> dict:
    """
    取得單支股票的：
      - ROE、ROA、負債比率（寫回 stocks 表）
      - quarterly 陣列（寫入 stock_quarterly_financials 表）

    quarterly 格式：
    [
      {
        "year": int, "quarter": int,
        "gross_margin": float | None,
        "net_income":   int   | None,
        "revenue":      int   | None,
        "contract_liabilities": int | None,
        "inventories":  int   | None,
      },
      ...  (最近 8 季，由新到舊)
    ]

    資料來源：FinMind（免費 API）
      - TaiwanStockBalanceSheet:
          TotalAssets, Equity, Liabilities_per,
          ContractLiabilitiesCurrent / ContractLiabilities, Inventories
      - TaiwanStockFinancialStatements:
          IncomeAfterTaxes / IncomeAfterTax, Revenue, GrossProfit
    """
    result: dict = {
        "roe": None,
        "roa": None,
        "debt_ratio": None,
        "quarterly": [],
    }

    # 730 天 ≈ 2 年，確保 YoY 對比有足夠的歷史季度資料
    start = (date.today() - timedelta(days=730)).strftime("%Y-%m-%d")

    bs_data = await _finmind_get("TaiwanStockBalanceSheet", stock_id, start)
    await asyncio.sleep(_INTER_CALL_DELAY)
    fs_data = await _finmind_get("TaiwanStockFinancialStatements", stock_id, start)

    # ── ROE / ROA / 負債比率（現有邏輯，保留） ──────────────────────────────

    # 負債比率
    liab_rows = [r for r in bs_data if r["type"] == "Liabilities_per"]
    if liab_rows:
        liab_rows.sort(key=lambda x: x["date"], reverse=True)
        try:
            result["debt_ratio"] = float(liab_rows[0]["value"])
        except (ValueError, TypeError):
            pass

    asset_rows  = [r for r in bs_data if r["type"] == "TotalAssets"]
    equity_rows = [r for r in bs_data if r["type"] == "Equity"]

    if asset_rows and equity_rows:
        asset_rows.sort(key=lambda x: x["date"],  reverse=True)
        equity_rows.sort(key=lambda x: x["date"], reverse=True)

        latest_year  = asset_rows[0]["date"][:4]
        total_assets = float(asset_rows[0]["value"])
        equity       = float(equity_rows[0]["value"])

        ni_rows = [
            r for r in fs_data
            if r["type"] in ("IncomeAfterTaxes", "IncomeAfterTax")
            and r["date"].startswith(latest_year)
        ]
        if ni_rows:
            net_income_ttm = sum(float(r["value"]) for r in ni_rows)
            if equity and equity != 0:
                result["roe"] = round(net_income_ttm / equity * 100, 2)
            if total_assets and total_assets != 0:
                result["roa"] = round(net_income_ttm / total_assets * 100, 2)

        logger.info(
            f"財務資料 {stock_id} ({latest_year}): "
            f"ROE={result['roe']}, ROA={result['roa']}, 負債比率={result['debt_ratio']}"
        )

    # ── 季度資料解析 ─────────────────────────────────────────────────────────

    # 建立 (year, quarter) → 資料 的 dict，最終合併成 quarterly 陣列

    quarterly_map: dict[tuple, dict] = {}

    def _get_or_create(yq: tuple) -> dict:
        if yq not in quarterly_map:
            quarterly_map[yq] = {
                "year": yq[0], "quarter": yq[1],
                "gross_margin":     None,
                "operating_margin": None,
                "net_income":       None,
                "revenue":          None,
                "contract_liabilities": None,
                "inventories":      None,
            }
        return quarterly_map[yq]

    # ── fs_data：Revenue, GrossProfit, OperatingIncome, IncomeAfterTaxes ──────

    # 先把 Revenue 各季收集
    rev_by_yq: dict[tuple, float] = {}
    for r in fs_data:
        if r["type"] == "Revenue":
            yq = _date_to_quarter(r["date"])
            if yq:
                try:
                    rev_by_yq[yq] = float(r["value"])
                except (ValueError, TypeError):
                    pass

    # GrossProfit
    for r in fs_data:
        if r["type"] == "GrossProfit":
            yq = _date_to_quarter(r["date"])
            if not yq:
                continue
            try:
                gp = float(r["value"])
                rev = rev_by_yq.get(yq)
                entry = _get_or_create(yq)
                entry["revenue"] = int(rev) if rev is not None else None
                if rev and rev != 0:
                    entry["gross_margin"] = round(gp / rev * 100, 2)
            except (ValueError, TypeError):
                pass

    # OperatingIncome → 計算季度營業利益率
    for r in fs_data:
        if r["type"] in ("OperatingIncome", "OperatingProfit"):
            yq = _date_to_quarter(r["date"])
            if not yq:
                continue
            try:
                op_income = float(r["value"])
                rev = rev_by_yq.get(yq)
                entry = _get_or_create(yq)
                if rev and rev != 0:
                    entry["operating_margin"] = round(op_income / rev * 100, 2)
            except (ValueError, TypeError):
                pass

    # IncomeAfterTaxes（各季單季值）
    for r in fs_data:
        if r["type"] in ("IncomeAfterTaxes", "IncomeAfterTax"):
            yq = _date_to_quarter(r["date"])
            if not yq:
                continue
            try:
                entry = _get_or_create(yq)
                entry["net_income"] = int(float(r["value"]))
                # 也補 revenue（若 GrossProfit loop 未填）
                if entry["revenue"] is None and yq in rev_by_yq:
                    entry["revenue"] = int(rev_by_yq[yq])
            except (ValueError, TypeError):
                pass

    # Revenue（補漏：有 revenue 但沒有 GrossProfit 的季度）
    for yq, rev in rev_by_yq.items():
        entry = _get_or_create(yq)
        if entry["revenue"] is None:
            entry["revenue"] = int(rev)

    # ── bs_data：ContractLiabilities, Inventories ────────────────────────────

    # 合約負債：優先取 ContractLiabilitiesCurrent，備用 ContractLiabilities
    for r in bs_data:
        if r["type"] in ("ContractLiabilitiesCurrent", "ContractLiabilities"):
            yq = _date_to_quarter(r["date"])
            if not yq:
                continue
            try:
                entry = _get_or_create(yq)
                # 若已有值（Current 優先，不被 general 覆蓋）
                if entry["contract_liabilities"] is None or r["type"] == "ContractLiabilitiesCurrent":
                    entry["contract_liabilities"] = int(float(r["value"]))
            except (ValueError, TypeError):
                pass

    # 存貨
    for r in bs_data:
        if r["type"] == "Inventories":
            yq = _date_to_quarter(r["date"])
            if not yq:
                continue
            try:
                entry = _get_or_create(yq)
                entry["inventories"] = int(float(r["value"]))
            except (ValueError, TypeError):
                pass

    # ── 排序：由新到舊，取最近 8 季 ─────────────────────────────────────────
    sorted_quarters = sorted(quarterly_map.values(),
                             key=lambda x: (x["year"], x["quarter"]),
                             reverse=True)
    result["quarterly"] = sorted_quarters[:8]

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
            results[stock_id] = {"roe": None, "roa": None, "debt_ratio": None, "quarterly": []}
    return results


# --- 快速測試 ----------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import json

    async def _test():
        stock_id = sys.argv[1] if len(sys.argv) > 1 else "2330"
        print(f"Token: {'有設定' if _FINMIND_TOKEN else '未設定'}")
        print(f"測試: {stock_id}")
        data = await fetch_goodinfo_financial(stock_id)
        print(f"ROE={data['roe']}  ROA={data['roa']}  負債比率={data['debt_ratio']}")
        print(f"季度資料（最近 {len(data['quarterly'])} 季）:")
        for q in data["quarterly"]:
            print(f"  {q['year']}Q{q['quarter']}  毛利率={q['gross_margin']}%  "
                  f"淨利={q['net_income']}  營收={q['revenue']}  "
                  f"合約負債={q['contract_liabilities']}  存貨={q['inventories']}")

    asyncio.run(_test())
