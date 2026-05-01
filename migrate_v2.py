"""
資料庫遷移腳本 v2（Phase 2）
新增欄位：margin_long, margin_short, is_attention, is_disposed, is_etf,
          ex_dividend_date, cash_dividend, shares（若尚未存在）
新建表：stock_announcements
ETF 標記：symbol LIKE '00%' → is_etf = TRUE

執行一次即可，IF NOT EXISTS 保證重複執行安全
"""
import psycopg2
import urllib3
urllib3.disable_warnings()

conn = psycopg2.connect(
    host="43.167.191.181",
    port=31218,
    database="zeabur",
    user="root",
    password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh"
)
cur = conn.cursor()

print("=== Phase 2 資料庫遷移 ===\n")

# ── 1. 新增欄位 ──────────────────────────────────────────────
column_migrations = [
    ("shares",           "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS shares BIGINT"),
    ("margin_long",      "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS margin_long INTEGER"),
    ("margin_short",     "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS margin_short INTEGER"),
    ("is_attention",     "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS is_attention BOOLEAN DEFAULT FALSE"),
    ("is_disposed",      "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS is_disposed  BOOLEAN DEFAULT FALSE"),
    ("is_etf",           "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS is_etf        BOOLEAN DEFAULT FALSE"),
    ("ex_dividend_date", "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS ex_dividend_date DATE"),
    ("cash_dividend",    "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS cash_dividend DECIMAL(8,4)"),
    ("eps",              "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS eps DECIMAL(8,2)"),
]

print("【stocks 表 — 新增欄位】")
ok = 0
for col, stmt in column_migrations:
    try:
        cur.execute(stmt)
        print(f"  ✅ {col}")
        ok += 1
    except Exception as e:
        conn.rollback()
        print(f"  ❌ {col}: {e}")

conn.commit()
print(f"  → {ok}/{len(column_migrations)} 個欄位完成\n")


# ── 2. 建立 stock_announcements 表 ───────────────────────────
print("【建立 stock_announcements 表】")
try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_announcements (
            id            SERIAL PRIMARY KEY,
            symbol        VARCHAR(10)  NOT NULL,
            announce_date DATE         NOT NULL,
            subject       TEXT,
            content       TEXT,
            source        VARCHAR(10),
            created_at    TIMESTAMPTZ  DEFAULT NOW(),
            UNIQUE (symbol, announce_date, subject)
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_ann_symbol_date
            ON stock_announcements (symbol, announce_date DESC)
    """)
    conn.commit()
    print("  ✅ stock_announcements 表已建立（含索引）\n")
except Exception as e:
    conn.rollback()
    print(f"  ❌ 建表失敗: {e}\n")


# ── 3. ETF 標記（symbol LIKE '00%'） ─────────────────────────
print("【ETF 標記】")
try:
    cur.execute("UPDATE stocks SET is_etf = TRUE  WHERE symbol LIKE '00%'")
    etf_count = cur.rowcount
    cur.execute("UPDATE stocks SET is_etf = FALSE WHERE symbol NOT LIKE '00%'")
    non_etf_count = cur.rowcount
    conn.commit()
    print(f"  ✅ ETF 標記完成：{etf_count} 檔 ETF，{non_etf_count} 檔非 ETF\n")
except Exception as e:
    conn.rollback()
    print(f"  ❌ ETF 標記失敗: {e}\n")


cur.close()
conn.close()
print("=== 遷移完成！===")
