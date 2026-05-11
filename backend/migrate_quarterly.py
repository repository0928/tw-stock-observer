"""
資料庫遷移腳本：季度財務功能
Migration: stock_quarterly_financials table + stocks.inventory_turnover column

執行方式：
  python migrate_quarterly.py

環境變數（需與主應用一致）：
  DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
"""

import asyncio
import logging
import os
import sys

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 資料庫連線 ──────────────────────────────────────────────────────────────
DB_DRIVER   = "postgresql+asyncpg"
DB_USER     = os.getenv("DB_USER",     "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST     = os.getenv("DB_HOST",     "localhost")
DB_PORT     = os.getenv("DB_PORT",     "5432")
DB_NAME     = os.getenv("DB_NAME",     "tw_stock_observer")

DATABASE_URL = f"{DB_DRIVER}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ── SQL 語句 ────────────────────────────────────────────────────────────────

CREATE_QUARTERLY_TABLE = """
CREATE TABLE IF NOT EXISTS stock_quarterly_financials (
    symbol               VARCHAR(10)      NOT NULL,
    year                 INTEGER          NOT NULL,
    quarter              INTEGER          NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    gross_margin         DECIMAL(8, 2),
    net_income           BIGINT,
    revenue              BIGINT,
    contract_liabilities BIGINT,
    inventories          BIGINT,
    updated_at           TIMESTAMPTZ,
    PRIMARY KEY (symbol, year, quarter)
);
"""

CREATE_QUARTERLY_INDEX = """
CREATE INDEX IF NOT EXISTS idx_sqf_symbol_year_q
    ON stock_quarterly_financials (symbol, year DESC, quarter DESC);
"""

ADD_INVENTORY_TURNOVER_COLUMN = """
ALTER TABLE stocks
    ADD COLUMN IF NOT EXISTS inventory_turnover DECIMAL(8, 2);
"""

CREATE_INVENTORY_TURNOVER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_stocks_inventory_turnover
    ON stocks (inventory_turnover)
    WHERE inventory_turnover IS NOT NULL;
"""


async def run_migration():
    engine = create_async_engine(DATABASE_URL, echo=False)

    try:
        async with engine.begin() as conn:
            logger.info("📦 建立 stock_quarterly_financials 資料表...")
            await conn.execute(text(CREATE_QUARTERLY_TABLE))
            logger.info("✅ stock_quarterly_financials 建立完成（或已存在）")

            logger.info("🔍 建立季度表索引...")
            await conn.execute(text(CREATE_QUARTERLY_INDEX))
            logger.info("✅ 索引建立完成")

            logger.info("📊 在 stocks 表新增 inventory_turnover 欄位...")
            await conn.execute(text(ADD_INVENTORY_TURNOVER_COLUMN))
            logger.info("✅ inventory_turnover 欄位新增完成（或已存在）")

            logger.info("🔍 建立 inventory_turnover 索引...")
            await conn.execute(text(CREATE_INVENTORY_TURNOVER_INDEX))
            logger.info("✅ 索引建立完成")

        logger.info("🎉 所有遷移執行完成！")

    except Exception as e:
        logger.error(f"❌ 遷移失敗: {e}")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migration())
