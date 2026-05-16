"""
每日 K 線增量同步
每個交易日盤後執行，補入當日 OHLCV 並重算技術指標。

資料來源：
  - 上市：TWSE STOCK_DAY_ALL（批量，一次取全市場）
  - 上櫃：TPEx 批量 API

流程：
  1. 從 TWSE/TPEx 取今日全市場 OHLCV
  2. 對每支有新資料的股票，從 DB 取近 250 筆歷史，重算指標
  3. Upsert 今日一筆進 klines_daily

排程：run_daily.py 每日盤後（17:00 TST）
"""

import logging
import os
import uuid
import requests
import psycopg2
import psycopg2.extras
import pandas as pd
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

DB_CONN = dict(
    host="43.167.191.181",
    port=31218,
    database="zeabur",
    user="root",
    password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh",
)


def _d(val) -> Decimal | None:
    if val is None or (isinstance(val, float) and val != val):
        return None
    try:
        return Decimal(str(round(float(val), 6)))
    except (InvalidOperation, ValueError):
        return None


def _parse(val):
    try:
        v = str(val).replace(",", "").replace("+", "").replace("X", "").strip()
        return float(v) if v not in ("--", "", "N/A") else None
    except Exception:
        return None


# ── 取今日全市場行情 ──────────────────────────────────────────────────────────

def fetch_twse_today() -> dict[str, dict]:
    """回傳 {symbol: {open,high,low,close,volume,amount,change}} 上市"""
    result = {}
    try:
        r = requests.get(
            "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=json",
            timeout=20, verify=False,
        )
        data = r.json()
        trade_date = data.get("date", "")
        for row in data.get("data", []):
            sym = str(row[0]).strip()
            if not sym.isdigit():
                continue
            close  = _parse(row[7])
            if not close:
                continue
            change = _parse(str(row[8]).replace("X", "").replace("+", ""))
            result[sym] = {
                "date":   trade_date[:4] + "-" + trade_date[4:6] + "-" + trade_date[6:],
                "open":   _parse(row[4]),
                "high":   _parse(row[5]),
                "low":    _parse(row[6]),
                "close":  close,
                "volume": int(_parse(row[2]) or 0),
                "amount": int(_parse(row[3]) or 0),
                "change": change,
            }
    except Exception as e:
        logger.error(f"TWSE today 失敗: {e}")
    return result


def fetch_tpex_today() -> dict[str, dict]:
    """回傳 {symbol: {...}} 上櫃"""
    result = {}
    try:
        today = date.today().strftime("%Y/%m/%d")
        r = requests.get(
            f"https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php"
            f"?l=zh-tw&d={today}&se=EW&s=0,asc&o=json",
            timeout=20, verify=False,
        )
        data = r.json()
        for row in data.get("aaData", []):
            sym = str(row[0]).strip()
            if not sym.isdigit():
                continue
            close = _parse(row[2])
            if not close:
                continue
            # TPEx row: [code, name, close, change, open, high, low, vol, amt, ...]
            trade_date = data.get("reportDate", today.replace("/", "-"))
            result[sym] = {
                "date":   trade_date,
                "open":   _parse(row[4]),
                "high":   _parse(row[5]),
                "low":    _parse(row[6]),
                "close":  close,
                "volume": int(float(str(row[7]).replace(",", "") or 0) * 1000),
                "amount": int(float(str(row[8]).replace(",", "") or 0) * 1000),
                "change": _parse(row[3]),
            }
    except Exception as e:
        logger.error(f"TPEx today 失敗: {e}")
    return result


# ── 技術指標重算 ──────────────────────────────────────────────────────────────

def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"]
    df["sma_20"]  = close.rolling(20,  min_periods=1).mean().round(2)
    df["sma_50"]  = close.rolling(50,  min_periods=1).mean().round(2)
    df["sma_200"] = close.rolling(200, min_periods=1).mean().round(2)
    delta    = close.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=13, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(com=13, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["rsi_14"]       = (100 - 100 / (1 + rs)).round(2)
    ema12              = close.ewm(span=12, adjust=False).mean()
    ema26              = close.ewm(span=26, adjust=False).mean()
    macd               = ema12 - ema26
    signal             = macd.ewm(span=9, adjust=False).mean()
    df["macd"]         = macd.round(4)
    df["macd_signal"]  = signal.round(4)
    df["macd_histogram"] = (macd - signal).round(4)
    return df


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    conn = psycopg2.connect(**DB_CONN)
    cur  = conn.cursor()

    # 取所有活躍股票（含 ETF）的 stock_id
    cur.execute("SELECT symbol, id::text FROM stocks WHERE is_active = TRUE")
    stock_map = {r[0]: r[1] for r in cur.fetchall()}
    logger.info(f"活躍股票 {len(stock_map)} 支")

    # 取今日行情
    logger.info("下載今日行情...")
    today_data = {**fetch_twse_today(), **fetch_tpex_today()}
    logger.info(f"取得 {len(today_data)} 支今日行情")

    now     = datetime.now(timezone.utc)
    success = failed = skipped = 0

    for symbol, stock_id in stock_map.items():
        q = today_data.get(symbol)
        if not q or not q.get("close"):
            skipped += 1
            continue

        try:
            # 取近 250 筆歷史（不含今日）
            cur.execute("""
                SELECT date, close FROM klines_daily
                WHERE symbol = %s
                ORDER BY date DESC LIMIT 250
            """, (symbol,))
            hist = cur.fetchall()

            if not hist:
                skipped += 1
                continue  # 沒有歷史資料，等 history sync 完成後再跑

            # 組 DataFrame：歷史 + 今日，升序排列
            hist_df = pd.DataFrame(hist, columns=["date", "close"])
            hist_df["close"] = hist_df["close"].astype(float)
            today_row = pd.DataFrame([{"date": q["date"], "close": float(q["close"])}])
            df = pd.concat([hist_df[::-1], today_row], ignore_index=True)
            df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

            df = calc_indicators(df)
            last = df.iloc[-1]

            # 計算漲跌幅
            change = q.get("change")
            prev_close = float(q["close"]) - change if change is not None else None
            change_pct = round(change / prev_close * 100, 2) if change and prev_close else None

            rec = [(
                str(uuid.uuid4()),
                symbol,
                stock_id,
                q["date"],
                _d(q["open"]),  _d(q["high"]), _d(q["low"]), _d(q["close"]),
                int(q["volume"]), int(q["amount"]),
                _d(change), _d(change_pct),
                _d(last.get("sma_20")), _d(last.get("sma_50")), _d(last.get("sma_200")),
                _d(last.get("rsi_14")),
                _d(last.get("macd")), _d(last.get("macd_signal")), _d(last.get("macd_histogram")),
                now, now,
            )]

            psycopg2.extras.execute_values(cur, """
                INSERT INTO klines_daily
                    (id, symbol, stock_id, date,
                     open, high, low, close, volume, amount,
                     change, change_percent,
                     sma_20, sma_50, sma_200,
                     rsi_14, macd, macd_signal, macd_histogram,
                     created_at, updated_at)
                VALUES %s
                ON CONFLICT (symbol, date) DO UPDATE SET
                    open=EXCLUDED.open, high=EXCLUDED.high,
                    low=EXCLUDED.low,   close=EXCLUDED.close,
                    volume=EXCLUDED.volume, amount=EXCLUDED.amount,
                    change=EXCLUDED.change, change_percent=EXCLUDED.change_percent,
                    sma_20=EXCLUDED.sma_20, sma_50=EXCLUDED.sma_50, sma_200=EXCLUDED.sma_200,
                    rsi_14=EXCLUDED.rsi_14,
                    macd=EXCLUDED.macd, macd_signal=EXCLUDED.macd_signal,
                    macd_histogram=EXCLUDED.macd_histogram,
                    updated_at=EXCLUDED.updated_at
            """, rec)
            conn.commit()
            success += 1

        except Exception as e:
            conn.rollback()
            logger.error(f"{symbol} 失敗: {e}")
            failed += 1

    cur.close()
    conn.close()
    logger.info(f"✅ 每日 K 線同步完成：成功={success}  跳過={skipped}  失敗={failed}")


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    main()
