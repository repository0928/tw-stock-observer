"""
同步 FCF（每股自由現金流）與利息保障倍數

資料來源：FinMind API
  - TaiwanStockCashFlowsStatement:
      NetCashProvidedByOperatingActivities（營業現金流）
      CapitalExpenditure（資本支出，通常為負值）
  - TaiwanStockFinancialStatements:
      OperatingIncome（營業利益，TTM）
      InterestExpenses / FinanceCosts（利息費用，TTM）

計算方式：
  FCF (TTM)      = 最近四季(營業現金流 + 資本支出)之合計
  FCF per share  = FCF / 流通股數
  Interest Cover = 營業利益(TTM) / 利息費用(TTM)

排程：每季（run_quarterly.py）
"""

import asyncio
import logging
import os
import psycopg2
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import aiohttp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── DB 連線 ──────────────────────────────────────────────────────────────────
DB_CONN = dict(
    host="43.167.191.181",
    port=31218,
    database="zeabur",
    user="root",
    password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh",
)

FINMIND_BASE  = "https://api.finmindtrade.com/api/v4/data"
FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")

# 抓近兩年資料（確保能取到足夠的四季）
START_DATE = (date.today() - timedelta(days=730)).strftime("%Y-%m-%d")

# 每支股票請求間隔（秒），避免觸發速率限制
DELAY = 2.5
MAX_RETRIES = 3


# ── FinMind 工具函式 ──────────────────────────────────────────────────────────

async def _finmind_get(session: aiohttp.ClientSession, dataset: str, stock_id: str) -> list:
    url = (
        f"{FINMIND_BASE}?dataset={dataset}&data_id={stock_id}"
        f"&start_date={START_DATE}&token={FINMIND_TOKEN}"
    )
    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 429:
                    wait = 2 ** attempt * 5
                    logger.warning(f"速率限制 {dataset} {stock_id}，{wait}s 後重試")
                    await asyncio.sleep(wait)
                    continue
                if resp.status != 200:
                    logger.warning(f"HTTP {resp.status} {dataset} {stock_id}")
                    return []
                d = await resp.json()
                data = d.get("data", [])
                if not data and "limit" in d.get("msg", "").lower():
                    wait = 2 ** attempt * 5
                    logger.warning(f"FinMind limit {dataset} {stock_id}，{wait}s 後重試")
                    await asyncio.sleep(wait)
                    continue
                return data
        except asyncio.TimeoutError:
            logger.warning(f"Timeout {dataset} {stock_id} (attempt {attempt+1})")
            await asyncio.sleep(2 ** attempt * 3)
        except Exception as e:
            logger.error(f"FinMind error {dataset} {stock_id}: {e}")
            return []
    return []


def _safe_float(val) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _date_to_quarter(date_str: str) -> tuple | None:
    try:
        month = int(date_str[5:7])
        year  = int(date_str[:4])
        return year, (month - 1) // 3 + 1
    except Exception:
        return None


# ── 核心計算 ──────────────────────────────────────────────────────────────────

async def calc_fcf_and_coverage(stock_id: str, shares: int | None) -> dict:
    """
    回傳 dict:
      free_cash_flow_ps : Decimal | None
      interest_coverage : Decimal | None
    """
    result = {"free_cash_flow_ps": None, "interest_coverage": None}

    async with aiohttp.ClientSession() as session:
        cf_data, fs_data = await asyncio.gather(
            _finmind_get(session, "TaiwanStockCashFlowsStatement", stock_id),
            _finmind_get(session, "TaiwanStockFinancialStatements", stock_id),
        )

    # ── FCF：近四季(營業現金流 + 資本支出) ────────────────────────────────────
    # FinMind 欄位名稱（已知別名）
    OP_CF_TYPES  = {"NetCashProvidedByOperatingActivities", "OperatingActivities"}
    CAPEX_TYPES  = {"CapitalExpenditure", "PurchaseOfPropertyPlantAndEquipment",
                    "AcquisitionOfPropertyPlantAndEquipment"}

    cf_by_yq: dict[tuple, dict] = {}
    for r in cf_data:
        yq = _date_to_quarter(r.get("date", ""))
        if not yq:
            continue
        val = _safe_float(r.get("value"))
        if val is None:
            continue
        rtype = r.get("type", "")
        entry = cf_by_yq.setdefault(yq, {"op_cf": None, "capex": None})
        if rtype in OP_CF_TYPES and entry["op_cf"] is None:
            entry["op_cf"] = val
        elif rtype in CAPEX_TYPES and entry["capex"] is None:
            entry["capex"] = val

    # 取最近四季，累加 FCF
    sorted_yq = sorted(cf_by_yq.keys(), reverse=True)[:4]
    fcf_total  = 0.0
    valid_qtrs = 0
    for yq in sorted_yq:
        e = cf_by_yq[yq]
        if e["op_cf"] is not None:
            # 資本支出在現金流量表通常已是負值；若為正值則取負
            capex = e["capex"] if e["capex"] is not None else 0.0
            if capex > 0:
                capex = -capex
            fcf_total  += e["op_cf"] + capex
            valid_qtrs += 1

    if valid_qtrs > 0 and shares and shares > 0:
        # 按實際有效季數比例年化
        fcf_annualized = fcf_total * (4 / valid_qtrs)
        fcf_ps = fcf_annualized / shares
        try:
            result["free_cash_flow_ps"] = Decimal(str(round(fcf_ps, 2)))
        except InvalidOperation:
            pass

    # ── 利息保障倍數：TTM 營業利益 / TTM 利息費用 ────────────────────────────
    OP_INC_TYPES  = {"OperatingIncome", "OperatingProfit"}
    INT_EXP_TYPES = {"InterestExpenses", "FinanceCosts", "InterestExpense",
                     "FinanceExpenses"}

    op_inc_by_yq:  dict[tuple, float] = {}
    int_exp_by_yq: dict[tuple, float] = {}

    for r in fs_data:
        yq = _date_to_quarter(r.get("date", ""))
        if not yq:
            continue
        val = _safe_float(r.get("value"))
        if val is None:
            continue
        rtype = r.get("type", "")
        if rtype in OP_INC_TYPES and yq not in op_inc_by_yq:
            op_inc_by_yq[yq] = val
        elif rtype in INT_EXP_TYPES and yq not in int_exp_by_yq:
            int_exp_by_yq[yq] = abs(val)  # 利息費用取絕對值

    recent_yq = sorted(set(op_inc_by_yq) | set(int_exp_by_yq), reverse=True)[:4]
    ttm_op_inc  = sum(op_inc_by_yq.get(yq, 0.0) for yq in recent_yq)
    ttm_int_exp = sum(int_exp_by_yq.get(yq, 0.0) for yq in recent_yq)

    if ttm_int_exp > 0:
        coverage = ttm_op_inc / ttm_int_exp
        try:
            result["interest_coverage"] = Decimal(str(round(coverage, 2)))
        except InvalidOperation:
            pass

    return result


# ── 主流程 ────────────────────────────────────────────────────────────────────

async def main():
    conn = psycopg2.connect(**DB_CONN)
    cur  = conn.cursor()

    # 取所有活躍個股（排除 ETF）及流通股數
    cur.execute("""
        SELECT symbol, shares
        FROM stocks
        WHERE is_active = TRUE AND is_etf = FALSE
        ORDER BY symbol
    """)
    rows = cur.fetchall()
    logger.info(f"共 {len(rows)} 支個股待同步")

    success = failed = skipped = 0

    for i, (symbol, shares) in enumerate(rows):
        if i > 0:
            await asyncio.sleep(DELAY)

        try:
            data = await calc_fcf_and_coverage(symbol, shares)
            fcf_ps   = data["free_cash_flow_ps"]
            coverage = data["interest_coverage"]

            if fcf_ps is None and coverage is None:
                skipped += 1
                if i % 50 == 0:
                    logger.info(f"  [{i+1}/{len(rows)}] {symbol} 無資料，跳過")
                continue

            cur.execute("""
                UPDATE stocks
                SET free_cash_flow_ps = %s,
                    interest_coverage = %s,
                    updated_at = NOW()
                WHERE symbol = %s
            """, (fcf_ps, coverage, symbol))
            conn.commit()
            success += 1

            if i % 20 == 0 or i < 5:
                logger.info(
                    f"  [{i+1}/{len(rows)}] {symbol} "
                    f"FCF/股={fcf_ps}  利息保障={coverage}"
                )

        except Exception as e:
            conn.rollback()
            logger.error(f"  [{i+1}/{len(rows)}] {symbol} 失敗: {e}")
            failed += 1

    cur.close()
    conn.close()
    logger.info(
        f"\n✅ 同步完成：成功 {success}，跳過 {skipped}，失敗 {failed}"
    )


if __name__ == "__main__":
    asyncio.run(main())
