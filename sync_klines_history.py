"""
歷史 K 線一次性同步腳本
從 FinMind TaiwanStockPrice 拉近 2 年日 K，計算技術指標後存入 klines_daily。

支援中斷續跑：已有近 30 天資料的股票自動跳過。
包含個股與 ETF（所有 is_active=TRUE 的股票）。

執行方式：
  python sync_klines_history.py
"""

import asyncio
import logging
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import aiohttp
import pandas as pd
import psycopg2
import psycopg2.extras

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ── 設定 ─────────────────────────────────────────────────────────────────────

DB_CONN = dict(
    host="43.167.191.181",
    port=31218,
    database="zeabur",
    user="root",
    password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh",
)

FINMIND_BASE  = "https://api.finmindtrade.com/api/v4/data"
FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")

START_DATE = (date.today() - timedelta(days=730)).strftime("%Y-%m-%d")  # 約 2 年
DELAY      = 2.5   # 秒，避免觸發速率限制
MAX_RETRY  = 3


# ── FinMind ────────────────────────────────────────────────────────────────────

async def fetch_price(session: aiohttp.ClientSession, symbol: str) -> list[dict]:
    url = (
        f"{FINMIND_BASE}?dataset=TaiwanStockPrice"
        f"&data_id={symbol}&start_date={START_DATE}&token={FINMIND_TOKEN}"
    )
    for attempt in range(MAX_RETRY):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 429:
                    wait = 2 ** attempt * 5
                    logger.warning(f"速率限制 {symbol}，等 {wait}s")
                    await asyncio.sleep(wait)
                    continue
                if resp.status != 200:
                    logger.warning(f"HTTP {resp.status} {symbol}")
                    return []
                d = await resp.json()
                rows = d.get("data", [])
                if not rows and "limit" in d.get("msg", "").lower():
                    wait = 2 ** attempt * 5
                    logger.warning(f"FinMind limit {symbol}，等 {wait}s")
                    await asyncio.sleep(wait)
                    continue
                return rows
        except asyncio.TimeoutError:
            logger.warning(f"Timeout {symbol} (attempt {attempt+1})")
            await asyncio.sleep(2 ** attempt * 3)
        except Exception as e:
            logger.error(f"FinMind error {symbol}: {e}")
            return []
    return []


# ── 技術指標計算（pandas） ────────────────────────────────────────────────────

def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    輸入：已按 date 升序排列的 DataFrame，含 close 欄位
    輸出：加上 sma_20/50/200、rsi_14、macd/signal/histogram
    """
    close = df["close"]

    # SMA
    df["sma_20"]  = close.rolling(20,  min_periods=1).mean().round(2)
    df["sma_50"]  = close.rolling(50,  min_periods=1).mean().round(2)
    df["sma_200"] = close.rolling(200, min_periods=1).mean().round(2)

    # RSI 14（Wilder 平滑法）
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=13, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(com=13, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["rsi_14"] = (100 - 100 / (1 + rs)).round(2)

    # MACD（12/26/9）
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    df["macd"]           = macd.round(4)
    df["macd_signal"]    = signal.round(4)
    df["macd_histogram"] = (macd - signal).round(4)

    return df


def _d(val) -> Decimal | None:
    """float → Decimal，None 安全"""
    if val is None or (isinstance(val, float) and (val != val)):  # NaN check
        return None
    try:
        return Decimal(str(round(float(val), 6)))
    except (InvalidOperation, ValueError):
        return None


# ── 主流程 ────────────────────────────────────────────────────────────────────

async def sync_stock(
    session: aiohttp.ClientSession,
    cur,
    conn,
    symbol: str,
    stock_id: str,
) -> tuple[int, int]:
    """回傳 (inserted, skipped_rows)"""
    rows = await fetch_price(session, symbol)
    if not rows:
        return 0, 0

    # 整理成 DataFrame
    df = pd.DataFrame(rows)
    rename = {
        "date": "date",
        "open": "open",
        "max": "high",
        "min": "low",
        "close": "close",
        "Trading_Volume": "volume",
        "Trading_money": "amount",
        "spread": "change",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    needed = ["date", "open", "high", "low", "close", "volume"]
    for col in needed:
        if col not in df.columns:
            logger.warning(f"{symbol} 缺欄位 {col}，跳過")
            return 0, 0

    df["date"]   = df["date"].astype(str)
    df["open"]   = pd.to_numeric(df["open"],   errors="coerce")
    df["high"]   = pd.to_numeric(df["high"],   errors="coerce")
    df["low"]    = pd.to_numeric(df["low"],    errors="coerce")
    df["close"]  = pd.to_numeric(df["close"],  errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
    df["amount"] = pd.to_numeric(df.get("amount", pd.Series(dtype=float)), errors="coerce").fillna(0).astype(int)
    df["change"] = pd.to_numeric(df.get("change", pd.Series(dtype=float)), errors="coerce")

    # 過濾無效行
    df = df.dropna(subset=["close"])
    df = df.sort_values("date").reset_index(drop=True)

    if df.empty:
        return 0, 0

    # 計算漲跌幅
    df["change_percent"] = (
        df["change"] / (df["close"] - df["change"]) * 100
    ).where((df["close"] - df["change"]) != 0).round(2)

    # 計算技術指標
    df = calc_indicators(df)

    # Upsert
    now = datetime.now(timezone.utc)
    records = []
    for _, r in df.iterrows():
        records.append((
            str(uuid.uuid4()),          # id
            symbol,
            stock_id,
            r["date"],
            _d(r["open"]),  _d(r["high"]), _d(r["low"]), _d(r["close"]),
            int(r["volume"]), int(r["amount"]),
            _d(r.get("change")), _d(r.get("change_percent")),
            _d(r.get("sma_20")), _d(r.get("sma_50")), _d(r.get("sma_200")),
            _d(r.get("rsi_14")),
            _d(r.get("macd")), _d(r.get("macd_signal")), _d(r.get("macd_histogram")),
            now, now,                   # created_at, updated_at
        ))

    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO klines_daily
            (id, symbol, stock_id, date,
             open, high, low, close, volume, amount,
             change, change_percent,
             sma_20, sma_50, sma_200,
             rsi_14, macd, macd_signal, macd_histogram,
             created_at, updated_at)
        VALUES %s
        ON CONFLICT (symbol, date) DO UPDATE SET
            open            = EXCLUDED.open,
            high            = EXCLUDED.high,
            low             = EXCLUDED.low,
            close           = EXCLUDED.close,
            volume          = EXCLUDED.volume,
            amount          = EXCLUDED.amount,
            change          = EXCLUDED.change,
            change_percent  = EXCLUDED.change_percent,
            sma_20          = EXCLUDED.sma_20,
            sma_50          = EXCLUDED.sma_50,
            sma_200         = EXCLUDED.sma_200,
            rsi_14          = EXCLUDED.rsi_14,
            macd            = EXCLUDED.macd,
            macd_signal     = EXCLUDED.macd_signal,
            macd_histogram  = EXCLUDED.macd_histogram,
            updated_at      = EXCLUDED.updated_at
        """,
        records,
        page_size=500,
    )
    conn.commit()
    return len(records), 0


async def main():
    conn = psycopg2.connect(**DB_CONN)
    cur  = conn.cursor()

    # 確保有 UNIQUE constraint（若不存在則建立）
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_klines_daily_symbol_date'
            ) THEN
                ALTER TABLE klines_daily
                ADD CONSTRAINT uq_klines_daily_symbol_date
                UNIQUE (symbol, date);
            END IF;
        END$$;
    """)
    conn.commit()
    logger.info("UNIQUE constraint 確認完成")

    # 取所有活躍股票（含 ETF）
    cur.execute("""
        SELECT symbol, id::text
        FROM stocks
        WHERE is_active = TRUE
        ORDER BY symbol
    """)
    stocks = cur.fetchall()
    logger.info(f"共 {len(stocks)} 支股票待同步（含 ETF）")

    # 取已有近 30 天資料的股票（skip 用）
    cur.execute("""
        SELECT DISTINCT symbol
        FROM klines_daily
        WHERE date >= %s
    """, ((date.today() - timedelta(days=30)).strftime("%Y-%m-%d"),))
    done_set = {r[0] for r in cur.fetchall()}
    logger.info(f"已完成 {len(done_set)} 支（近 30 天有資料），將跳過")

    success = failed = skipped = 0

    async with aiohttp.ClientSession() as session:
        for i, (symbol, stock_id) in enumerate(stocks):
            if symbol in done_set:
                skipped += 1
                continue

            if i > 0:
                await asyncio.sleep(DELAY)

            try:
                inserted, _ = await sync_stock(session, cur, conn, symbol, stock_id)
                if inserted:
                    success += 1
                    if success % 20 == 0 or success <= 5:
                        logger.info(
                            f"[{i+1}/{len(stocks)}] {symbol} ✓ {inserted} 筆"
                            f"  (成功={success} 跳過={skipped} 失敗={failed})"
                        )
                else:
                    skipped += 1
                    logger.debug(f"[{i+1}/{len(stocks)}] {symbol} 無資料")
            except Exception as e:
                failed += 1
                logger.error(f"[{i+1}/{len(stocks)}] {symbol} 失敗: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass

    cur.close()
    conn.close()
    logger.info(
        f"\n✅ 歷史 K 線同步完成：成功={success}  跳過={skipped}  失敗={failed}"
    )


if __name__ == "__main__":
    asyncio.run(main())
# test
                except Exception:
                    pass

    cur.close()
    conn.close()
    logger.info(
        f"\n✅ 歷史 K 線同步完成：成功={success}  跳過={skipped}  失敗={failed}"
    )


if __name__ == "__main__":
    asyncio.run(main())
