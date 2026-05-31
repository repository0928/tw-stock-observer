"""
Screener 快取腳本
每天收盤後執行一次，跑完所有篩選器 SQL，結果存入 screener_cache 表。
"""

import logging
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_CONN = dict(
    host="43.167.191.181", port=31218, database="zeabur",
    user="root", password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh",
)

SCREENERS = {
    "ma20_breakout": """
        WITH latest AS (
            SELECT DISTINCT ON (symbol) symbol, date, close, sma_20
            FROM klines_latest
            WHERE sma_20 IS NOT NULL
              AND date >= (CURRENT_DATE - INTERVAL '20 days')::text
            ORDER BY symbol, date DESC
        ),
        prev5 AS (
            SELECT k.symbol, BOOL_OR(k.close <= k.sma_20) AS had_below
            FROM klines_latest k
            JOIN (SELECT symbol, date AS latest_date FROM latest) l ON k.symbol = l.symbol
            WHERE k.date >= (l.latest_date::date - INTERVAL '5 days')::text
              AND k.date < l.latest_date
            GROUP BY k.symbol
        )
        SELECT l.symbol FROM latest l JOIN prev5 p ON l.symbol = p.symbol
        WHERE l.close > l.sma_20 AND p.had_below = TRUE ORDER BY l.symbol
    """,
    "ma60_above": """
        SELECT symbol FROM (
            SELECT DISTINCT ON (symbol) symbol, close, sma_50
            FROM klines_latest
            WHERE sma_50 IS NOT NULL AND date >= (CURRENT_DATE - INTERVAL '20 days')::text
            ORDER BY symbol, date DESC
        ) t WHERE close > sma_50 ORDER BY symbol
    """,
    "rsi_oversold": """
        SELECT symbol FROM (
            SELECT DISTINCT ON (symbol) symbol, rsi_14
            FROM klines_latest
            WHERE rsi_14 IS NOT NULL AND date >= (CURRENT_DATE - INTERVAL '20 days')::text
            ORDER BY symbol, date DESC
        ) t WHERE rsi_14 < 30 ORDER BY symbol
    """,
    "macd_bullish": """
        WITH ranked AS (
            SELECT symbol, date, macd_histogram,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
            FROM klines_latest
            WHERE macd_histogram IS NOT NULL AND date >= (CURRENT_DATE - INTERVAL '20 days')::text
        ),
        chk AS (
            SELECT symbol,
                   MAX(CASE WHEN rn = 1 THEN macd_histogram END) AS h1,
                   MAX(CASE WHEN rn BETWEEN 2 AND 3 THEN macd_histogram END) AS h2
            FROM ranked WHERE rn <= 3 GROUP BY symbol
        )
        SELECT symbol FROM chk WHERE h1 > 0 AND h2 <= 0 ORDER BY symbol
    """,
    "golden_cross": """
        WITH ranked AS (
            SELECT symbol, date, sma_20, sma_50,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
            FROM klines_latest
            WHERE sma_20 IS NOT NULL AND sma_50 IS NOT NULL
              AND date >= (CURRENT_DATE - INTERVAL '20 days')::text
        ),
        agg AS (
            SELECT symbol,
                   MAX(CASE WHEN rn = 1 THEN sma_20 END) AS ma20,
                   MAX(CASE WHEN rn = 1 THEN sma_50 END) AS ma50,
                   MAX(CASE WHEN rn BETWEEN 2 AND 5 THEN CASE WHEN sma_20 <= sma_50 THEN 1 ELSE 0 END END) AS had_below
            FROM ranked WHERE rn <= 5 GROUP BY symbol
        )
        SELECT symbol FROM agg WHERE ma20 > ma50 AND had_below = 1 ORDER BY symbol
    """,
    "gross_margin_rising": """
        WITH r AS (
            SELECT symbol, gross_margin,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY year DESC, quarter DESC) AS rn
            FROM stock_quarterly_financials WHERE gross_margin IS NOT NULL
        ),
        p AS (
            SELECT symbol, COUNT(*) AS cnt, MIN(gross_margin) AS min_gm,
                   MAX(CASE WHEN rn=1 THEN gross_margin END) AS gm1,
                   MAX(CASE WHEN rn=2 THEN gross_margin END) AS gm2,
                   MAX(CASE WHEN rn=3 THEN gross_margin END) AS gm3,
                   MAX(CASE WHEN rn=4 THEN gross_margin END) AS gm4
            FROM r WHERE rn <= 4 GROUP BY symbol
        )
        SELECT symbol, gm1, gm2, gm3, gm4 FROM p WHERE cnt = 4 AND min_gm >= 30
    """,
    "operating_margin_rising": """
        WITH r AS (
            SELECT symbol, operating_margin,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY year DESC, quarter DESC) AS rn
            FROM stock_quarterly_financials WHERE operating_margin IS NOT NULL
        ),
        p AS (
            SELECT symbol, COUNT(*) AS cnt, MIN(operating_margin) AS min_om,
                   MAX(CASE WHEN rn=1 THEN operating_margin END) AS om1,
                   MAX(CASE WHEN rn=2 THEN operating_margin END) AS om2,
                   MAX(CASE WHEN rn=3 THEN operating_margin END) AS om3,
                   MAX(CASE WHEN rn=4 THEN operating_margin END) AS om4
            FROM r WHERE rn <= 4 GROUP BY symbol
        )
        SELECT symbol, om1, om2, om3, om4 FROM p WHERE cnt = 4 AND min_om >= 10
    """,
    "net_income_outpace_revenue": """
        WITH r AS (
            SELECT symbol, year, quarter, net_income, revenue,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY year DESC, quarter DESC) AS rn
            FROM stock_quarterly_financials WHERE net_income IS NOT NULL AND revenue IS NOT NULL
        ),
        rec AS (
            SELECT r.symbol, r.net_income, r.revenue, p.net_income AS prev_ni, p.revenue AS prev_rev
            FROM r JOIN stock_quarterly_financials p
              ON p.symbol=r.symbol AND p.year=r.year-1 AND p.quarter=r.quarter
             AND p.net_income IS NOT NULL AND p.revenue IS NOT NULL
            WHERE r.rn=1 AND p.net_income<>0 AND p.revenue<>0
        )
        SELECT symbol FROM rec
        WHERE (net_income-prev_ni)/ABS(prev_ni) > (revenue-prev_rev)/ABS(prev_rev)
        ORDER BY symbol
    """,
    "contract_liabilities_growth": """
        WITH r AS (
            SELECT symbol, contract_liabilities,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY year DESC, quarter DESC) AS rn
            FROM stock_quarterly_financials WHERE contract_liabilities IS NOT NULL
        ),
        p AS (
            SELECT symbol, COUNT(*) AS cnt,
                   MAX(CASE WHEN rn=1 THEN contract_liabilities END) AS cl1,
                   MAX(CASE WHEN rn=2 THEN contract_liabilities END) AS cl2,
                   MAX(CASE WHEN rn=3 THEN contract_liabilities END) AS cl3,
                   MAX(CASE WHEN rn=4 THEN contract_liabilities END) AS cl4
            FROM r WHERE rn <= 4 GROUP BY symbol
        )
        SELECT symbol, cl1, cl2, cl3, cl4 FROM p WHERE cnt >= 2 AND cl1 IS NOT NULL AND cl2 IS NOT NULL
    """,
    "revenue_yoy_consecutive": """
        WITH r AS (
            SELECT symbol, revenue_yoy,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY year_month DESC) AS rn
            FROM stock_revenue_monthly WHERE revenue_yoy IS NOT NULL
        ),
        chk AS (
            SELECT symbol, COUNT(*) AS cnt, BOOL_AND(revenue_yoy >= 0) AS all_pass
            FROM r WHERE rn <= 3 GROUP BY symbol
        )
        SELECT symbol FROM chk WHERE cnt = 3 AND all_pass = TRUE ORDER BY symbol
    """,
}

def filter_gross_margin_rising(rows):
    return [row[0] for row in rows
            if len([x for x in row[1:5] if x is not None]) == 4
            and all(float(row[i]) > float(row[i+1]) for i in range(1, 4))]

def filter_operating_margin_rising(rows):
    return [row[0] for row in rows
            if len([x for x in row[1:5] if x is not None]) == 4
            and all(float(row[i]) > float(row[i+1]) for i in range(1, 4))]

def filter_contract_liabilities_growth(rows):
    result = []
    for row in rows:
        cls = [float(row[i]) for i in range(1, 5) if row[i] is not None]
        if len(cls) < 2:
            continue
        cond_b = cls[1] != 0 and (cls[0] - cls[1]) / abs(cls[1]) * 100 >= 20
        cond_a = len(cls) >= 4 and all(cls[i] > cls[i+1] for i in range(3))
        if cond_a or cond_b:
            result.append(row[0])
    return result

PYTHON_FILTERS = {
    "gross_margin_rising": filter_gross_margin_rising,
    "operating_margin_rising": filter_operating_margin_rising,
    "contract_liabilities_growth": filter_contract_liabilities_growth,
}


def reconnect():
    import time
    waits = [10, 30, 60, 120, 300]
    for attempt, wait in enumerate(waits, start=1):
        try:
            conn = psycopg2.connect(**DB_CONN)
            cur = conn.cursor()
            logger.info(f"DB 重連成功（第 {attempt} 次）")
            return conn, cur
        except Exception as e:
            if attempt < len(waits):
                logger.warning(f"重連第 {attempt} 次失敗: {e}，{wait}s 後再試…")
                time.sleep(wait)
            else:
                logger.error(f"重連失敗，已達上限: {e}")
                raise


def run_one(cur, conn, name, sql, now):
    cur.execute(sql)
    rows = cur.fetchall()
    symbols = PYTHON_FILTERS[name](rows) if name in PYTHON_FILTERS else [r[0] for r in rows]
    cur.execute("DELETE FROM screener_cache WHERE screener_type = %s", (name,))
    if symbols:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO screener_cache (screener_type, symbol, updated_at) VALUES %s",
            [(name, sym, now) for sym in symbols],
            page_size=200,
        )
    conn.commit()
    return len(symbols)


def main():
    conn = psycopg2.connect(**DB_CONN)
    cur = conn.cursor()
    now = datetime.now(timezone.utc)
    total_success = total_failed = 0

    for name, sql in SCREENERS.items():
        if conn.closed:
            try:
                conn, cur = reconnect()
            except Exception as e:
                logger.error(f"無法重連，中止: {e}")
                break

        try:
            logger.info(f"執行篩選器：{name}...")
            cnt = run_one(cur, conn, name, sql, now)
            logger.info(f"  ✅ {name}：{cnt} 支")
            total_success += 1

        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            total_failed += 1
            logger.warning(f"  ❌ {name} DB 連線中斷，嘗試重連…")
            try:
                conn, cur = reconnect()
                cnt = run_one(cur, conn, name, sql, now)
                logger.info(f"  ✅ {name}（重試成功）：{cnt} 支")
                total_success += 1
                total_failed -= 1
            except Exception as retry_e:
                logger.error(f"  ❌ {name} 重試仍失敗: {retry_e}")

        except Exception as e:
            total_failed += 1
            logger.error(f"  ❌ {name} 失敗: {e}")
            try:
                conn.rollback()
            except Exception:
                pass

    try:
        cur.close()
        conn.close()
    except Exception:
        pass
    logger.info(f"\n✅ Screener 快取完成：成功={total_success}  失敗={total_failed}  共={len(SCREENERS)}")


if __name__ == "__main__":
    main()
