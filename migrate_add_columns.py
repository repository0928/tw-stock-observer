"""
資料庫遷移腳本：為 stocks 表加入 12 個新欄位
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

migrations = [
    # 月營收
    ("revenue_yoy",               "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS revenue_yoy DECIMAL(8,2)"),
    ("revenue_mom",               "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS revenue_mom DECIMAL(8,2)"),
    # 三大法人（單位：張）
    ("foreign_net_buy",           "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS foreign_net_buy BIGINT"),
    ("investment_trust_net_buy",  "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS investment_trust_net_buy BIGINT"),
    ("dealer_net_buy",            "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS dealer_net_buy BIGINT"),
    # 技術
    ("turnover_rate",             "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS turnover_rate DECIMAL(8,4)"),
    # 財報
    ("gross_margin",              "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS gross_margin DECIMAL(8,2)"),
    ("operating_margin",          "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS operating_margin DECIMAL(8,2)"),
    ("net_margin",                "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS net_margin DECIMAL(8,2)"),
    ("roe",                       "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS roe DECIMAL(8,2)"),
    ("roa",                       "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS roa DECIMAL(8,2)"),
    ("debt_ratio",                "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS debt_ratio DECIMAL(8,2)"),
    # dividend_yield 已存在，確保有此欄位
    ("dividend_yield",            "ALTER TABLE stocks ADD COLUMN IF NOT EXISTS dividend_yield DECIMAL(6,2)"),
]

print("開始執行資料庫遷移...")
ok = 0
for col, stmt in migrations:
    try:
        cur.execute(stmt)
        print(f"  ✅ {col}")
        ok += 1
    except Exception as e:
        print(f"  ❌ {col}: {e}")

conn.commit()
cur.close()
conn.close()
print(f"\n完成：{ok}/{len(migrations)} 個欄位")
