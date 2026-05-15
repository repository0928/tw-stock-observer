"""
資料庫遷移：stock_quarterly_financials 新增 operating_margin 欄位

新增欄位：
  - operating_margin : 季度營業利益率(%) = OperatingIncome / Revenue * 100

執行方式：
  python migrate_op_margin_quarterly.py
"""
import psycopg2

conn = psycopg2.connect(
    host="43.167.191.181",
    port=31218,
    database="zeabur",
    user="root",
    password="EKo96Bj0UOc4zP2Jp53I1Rtv8H7fmrgh"
)
cur = conn.cursor()

migrations = [
    (
        "stock_quarterly_financials 加入 operating_margin",
        "ALTER TABLE stock_quarterly_financials ADD COLUMN IF NOT EXISTS operating_margin DECIMAL(8,2)",
    ),
    (
        "建立 operating_margin 索引",
        "CREATE INDEX IF NOT EXISTS idx_sqf_op_margin ON stock_quarterly_financials(symbol, operating_margin) WHERE operating_margin IS NOT NULL",
    ),
]

for name, sql in migrations:
    try:
        cur.execute(sql)
        conn.commit()
        print(f"✅ {name}")
    except Exception as e:
        conn.rollback()
        print(f"❌ {name}: {e}")

cur.close()
conn.close()
print("\n🎉 quarterly operating_margin 欄位遷移完成")
