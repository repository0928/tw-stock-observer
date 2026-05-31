"""
為 klines_daily 加上 (symbol, date DESC) 複合 index。
執行一次即可，重複執行安全（IF NOT EXISTS）。
"""

import psycopg2

DB_CONN = dict(
    host="43.167.191.181",
    port=31218,
    database="zeabur",
    user="root",
    password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh",
)

def main():
    print("連線到資料庫...")
    conn = psycopg2.connect(**DB_CONN)
    conn.autocommit = True  # CREATE INDEX 不需要 transaction
    cur = conn.cursor()

    print("建立 index（約需 30-60 秒，請稍候）...")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_klines_daily_symbol_date
        ON klines_daily (symbol, date DESC);
    """)
    print("✅ idx_klines_daily_symbol_date 建立完成")

    # 順便確認 index 存在
    cur.execute("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'klines_daily';
    """)
    rows = cur.fetchall()
    print(f"\nklines_daily 目前的 indexes（共 {len(rows)} 個）：")
    for name, defn in rows:
        print(f"  {name}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
