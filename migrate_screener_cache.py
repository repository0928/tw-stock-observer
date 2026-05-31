"""
建立 screener_cache 表。
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
    conn.autocommit = True
    cur = conn.cursor()

    print("建立 screener_cache 表...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS screener_cache (
            screener_type VARCHAR(50)  NOT NULL,
            symbol        VARCHAR(10)  NOT NULL,
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            PRIMARY KEY (screener_type, symbol)
        );
    """)
    print("✅ screener_cache 表建立完成")

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_screener_cache_type
        ON screener_cache (screener_type);
    """)
    print("✅ index 建立完成")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
