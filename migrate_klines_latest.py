"""
建立 klines_latest 表，並從 klines_daily 填入每支股票最新 100 筆資料。
執行一次即可，重複執行安全（IF NOT EXISTS / TRUNCATE + INSERT）。

執行方式：
  python migrate_klines_latest.py
"""

import logging
import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_CONN = dict(
    host="43.167.191.181",
    port=31218,
    database="zeabur",
    user="root",
    password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh",
)

KEEP_ROWS = 100  # 每支股票保留最新幾筆

def main():
    conn = psycopg2.connect(**DB_CONN)
    conn.autocommit = False
    cur = conn.cursor()

    # ── Step 1：建表 ────────────────────────────────────────────────────────────
    logger.info("Step 1：建立 klines_latest 表...")
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS klines_latest (
            id              UUID          NOT NULL,
            symbol          VARCHAR(10)   NOT NULL,
            stock_id        UUID,
            date            VARCHAR(10)   NOT NULL,
            open            NUMERIC(12,4),
            high            NUMERIC(12,4),
            low             NUMERIC(12,4),
            close           NUMERIC(12,4),
            volume          BIGINT,
            amount          BIGINT,
            change          NUMERIC(12,4),
            change_percent  NUMERIC(8,2),
            sma_20          NUMERIC(12,2),
            sma_50          NUMERIC(12,2),
            sma_200         NUMERIC(12,2),
            rsi_14          NUMERIC(6,2),
            macd            NUMERIC(12,4),
            macd_signal     NUMERIC(12,4),
            macd_histogram  NUMERIC(12,4),
            created_at      TIMESTAMPTZ,
            updated_at      TIMESTAMPTZ,
            PRIMARY KEY (symbol, date)
        );
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_klines_latest_symbol_date
        ON klines_latest (symbol, date DESC);
    """)
    conn.commit()
    logger.info("  ✅ 表與 index 建立完成")

    # ── Step 2：取得所有 active 股票 ────────────────────────────────────────────
    logger.info("Step 2：取得 active 股票清單...")
    cur.execute("SELECT DISTINCT symbol FROM klines_daily ORDER BY symbol")
    symbols = [r[0] for r in cur.fetchall()]
    logger.info(f"  共 {len(symbols)} 支股票")

    # ── Step 3：批次填入每股最新 100 筆 ─────────────────────────────────────────
    logger.info(f"Step 3：填入每股最新 {KEEP_ROWS} 筆資料...")
    logger.info("  先清空舊資料...")
    cur.execute("TRUNCATE TABLE klines_latest")
    conn.commit()

    batch_size = 50   # 每批處理幾支股票
    inserted_total = 0

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]

        cur.execute(f"""
            INSERT INTO klines_latest
                (id, symbol, stock_id, date,
                 open, high, low, close, volume, amount,
                 change, change_percent,
                 sma_20, sma_50, sma_200,
                 rsi_14, macd, macd_signal, macd_histogram,
                 created_at, updated_at)
            SELECT id, symbol, stock_id, date,
                   open, high, low, close, volume, amount,
                   change, change_percent,
                   sma_20, sma_50, sma_200,
                   rsi_14, macd, macd_signal, macd_histogram,
                   created_at, updated_at
            FROM (
                SELECT *,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
                FROM klines_daily
                WHERE symbol = ANY(%s)
            ) sub
            WHERE rn <= {KEEP_ROWS}
            ON CONFLICT (symbol, date) DO NOTHING
        """, (batch,))

        inserted_total += cur.rowcount
        conn.commit()

        done = min(i + batch_size, len(symbols))
        logger.info(f"  [{done}/{len(symbols)}] 已處理，累計插入 {inserted_total} 筆")

    # ── Step 4：驗證 ────────────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM klines_latest")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT symbol) FROM klines_latest")
    sym_count = cur.fetchone()[0]

    cur.close()
    conn.close()

    logger.info(f"\n✅ klines_latest 填入完成")
    logger.info(f"   股票數：{sym_count}  總筆數：{total}  平均每股：{total // max(sym_count, 1)} 筆")


if __name__ == "__main__":
    main()
