# 台股觀測站 Phase 2 開發計畫

> 更新日期：2026-04-30  
> 前置狀態：Phase 1 已完成（13 欄位 migration、sync_quotes/institutional/revenue_monthly/financials/pe、App.tsx 30 欄 rewrite）

---

## 一、目前資料庫欄位狀態

### stocks 表（現有）

| 欄位 | 說明 | 同步來源 |
|---|---|---|
| symbol, name, market, industry | 基本資料 | sync_stocks.py |
| close, volume, change_pct | 行情 | sync_quotes.py |
| turnover_rate | 週轉率（需 shares 才能算） | sync_quotes.py |
| pe_ratio, pb_ratio, dividend_yield | 估值 | sync_pe.py |
| revenue_yoy, revenue_mom | 月營收年增/月增 | sync_revenue_monthly.py ✅ |
| foreign_net_buy, investment_trust_net_buy, dealer_net_buy | 三大法人（張） | sync_institutional.py（上市✅ 上櫃❌） |
| gross_margin, operating_margin, net_margin, eps | 財報（上市✅ 上櫃❌） | sync_financials.py |
| roe, roa, debt_ratio | ROE/ROA/負債比（目前無 API） | — |

---

## 二、Phase 2 工作項目

### 📌 Group A：修補 TPEx 缺口（改現有腳本，不加欄位）

**A1 — sync_institutional.py 補上櫃三大法人**

- API：`https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading`
- 欄位：`SecuritiesCompanyCode`、`ForeignInvestorsNetBuyOrSellShares`、`InvestmentTrustNetBuyOrSellShares`、`DealerNetBuyOrSellShares`
- 單位：已是「張」，不需除 1000
- 改動：替換原本 try-fallback 邏輯，直接用上面 URL

**A2 — sync_financials.py 補上櫃利潤率 + EPS**

- 利潤率 API：`https://www.tpex.org.tw/openapi/v1/mopsfin_187ap17_O`
  - 欄位名稱待確認（Swagger 僅列路徑，需實際探測）
- EPS API：`https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap14_O`
  - 欄位名稱待確認
- 改動：在現有腳本末尾加上「上櫃財報」區塊，邏輯與上市相同

---

### 📌 Group B：基本資料同步（優先！解鎖週轉率）

**B1 — sync_basic_info.py（新建）**

目的：補齊 `shares`（流通股數），讓 `turnover_rate = volume / shares * 100` 能正確計算。同時更新 `industry`、`market`。

| 市場 | API |
|---|---|
| 上市 | `https://openapi.twse.com.tw/v1/opendata/t51sb01` |
| 上櫃 | `https://www.tpex.org.tw/openapi/v1/tpex_mainboard_basic_info`（Swagger 確認） |

欄位對應（上市 t51sb01）：

| API 欄位 | DB 欄位 |
|---|---|
| 公司代號 | symbol |
| 上市股數（千股） | shares（需 ×1000 轉成股） |
| 產業別 | industry |

更新策略：`UPDATE stocks SET shares=..., industry=..., updated_at=... WHERE symbol=...`

執行完後立刻重跑 `sync_quotes.py`，turnover_rate 即自動補齊。

---

### 📌 Group C：融資／融券餘額

**新增 DB 欄位（stocks 表）：**

```sql
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS margin_long  INTEGER;  -- 融資餘額（張）
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS margin_short INTEGER;  -- 融券餘額（張）
```

**C1 — sync_margin.py（新建）**

| 市場 | API |
|---|---|
| 上市 | `https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&selectType=ALL` |
| 上櫃 | `https://www.tpex.org.tw/openapi/v1/tpex_margin_trading_balance`（Swagger 確認） |

上市 MI_MARGN 欄位：
- `data[n][0]` = 股票代號
- `data[n][3]` = 融資買進（股，需/1000→張）... 實際需探測欄位定義

---

### 📌 Group D：注意／處置標記

**新增 DB 欄位（stocks 表）：**

```sql
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS is_attention BOOLEAN DEFAULT FALSE;
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS is_disposed  BOOLEAN DEFAULT FALSE;
```

**D1 — sync_attention.py（新建）**

| 市場/類型 | API |
|---|---|
| 上市 注意股票 | `https://openapi.twse.com.tw/v1/announcement/attention`（Swagger 有） |
| 上市 處置股票 | `https://openapi.twse.com.tw/v1/announcement/disposition`（Swagger 有） |
| 上櫃 注意股票 | TPEx Swagger 確認中 |

邏輯：
1. 先 `UPDATE stocks SET is_attention=FALSE, is_disposed=FALSE`（全清）
2. 再針對出現在 attention list 的 symbol 設為 TRUE
3. 再針對 disposition list 設為 TRUE

**前端顯示：** 股名旁加 badge（注意=黃色、處置=紅色）

---

### 📌 Group E：重大訊息（新表 + 後端 API + 前端檢視）

**新建 DB 表：**

```sql
CREATE TABLE IF NOT EXISTS stock_announcements (
    id           SERIAL PRIMARY KEY,
    symbol       VARCHAR(10) NOT NULL,
    announce_date DATE NOT NULL,
    subject      TEXT,
    content      TEXT,
    source       VARCHAR(10),  -- 'TWSE' or 'TPEx'
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (symbol, announce_date, subject)
);
CREATE INDEX IF NOT EXISTS idx_ann_symbol_date ON stock_announcements(symbol, announce_date DESC);
```

**E1 — sync_announcements.py（新建）**

| 市場 | API |
|---|---|
| 上市 | `https://openapi.twse.com.tw/v1/opendata/t187ap04_L`（重大訊息） |
| 上櫃 | `https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O`（Swagger 確認） |

策略：`INSERT ... ON CONFLICT (symbol, announce_date, subject) DO NOTHING`（歷史累積，不覆蓋）

**E2 — 後端 API（backend/app/routers/stocks.py）**

新增端點：
```
GET /stocks/{symbol}/announcements?limit=20
```
回傳：`[{id, announce_date, subject, content, source}, ...]`

**E3 — 前端（App.tsx）**

點擊股名或新增「📢」icon，展開 modal 顯示該股最近 20 筆重大訊息。

---

### 📌 Group F：股利分派

**新增 DB 欄位（stocks 表）：**

```sql
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS ex_dividend_date DATE;
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS cash_dividend    DECIMAL(8,4);
```

**F1 — sync_dividend.py（新建）**

| 市場 | API |
|---|---|
| 上市 | `https://openapi.twse.com.tw/v1/opendata/t187ap06_L`（上市公司股利分派情形） |
| 上櫃 | Swagger 確認中 |

---

## 三、執行順序

```
Step 1  migrate_v2.py          ← 一次加完所有新欄位（含 is_etf）+ 建新表 + 標記 ETF
Step 2  sync_basic_info.py     ← PRIORITY：補 shares，解鎖週轉率
Step 3  sync_quotes.py 重跑    ← turnover_rate 從此有值
Step 4  A1 + A2               ← 修 sync_institutional + sync_financials（補上櫃）
Step 5  sync_margin.py         ← 融資/融券
Step 6  sync_attention.py      ← 注意/處置
Step 7  sync_announcements.py  ← 重大訊息
Step 8  sync_dividend.py       ← 股利
Step 9  後端：model + API       ← StockAnnouncement model + /announcements endpoint
Step 10 前端：App.tsx 更新      ← 新欄位顯示 + badges + announcements modal
Step 11 驗證 + commit + 部署
```

---

## 四、需要探測的 API（先跑探測腳本確認欄位）

以下 URL 在 Swagger 有記錄，但實際欄位名稱未確認，執行前會先 probe：

| 腳本 | 需探測的 URL |
|---|---|
| A2 sync_financials | `mopsfin_187ap17_O`, `mopsfin_t187ap14_O` |
| B1 sync_basic_info | `t51sb01`, `tpex_mainboard_basic_info` |
| C1 sync_margin | `MI_MARGN`, `tpex_margin_trading_balance` |
| D1 sync_attention | `announcement/attention`, `announcement/disposition` |
| E1 sync_announcements | `t187ap04_L`, `mopsfin_t187ap04_O` |
| F1 sync_dividend | `t187ap06_L` |

探測腳本（debug_phase2.py）會一次印出所有 URL 的欄位，再依實際欄位名稱寫同步邏輯。

---

## 五、前端新增項目一覽

| 功能 | 說明 |
|---|---|
| 融資/融券 欄位 | margin_long / margin_short，可加入欄位切換 |
| 注意/處置 badge | 股名旁顯示 ⚠️注意 / 🔴處置 小標籤 |
| 股利資訊 欄位 | ex_dividend_date / cash_dividend |
| 重大訊息 modal | 點擊股票展開，顯示最近 20 筆訊息 |
| 新篩選器 | 有重大訊息、注意股排除/包含、高融資 |

---

## 六、ETF 標籤

台股中股票代碼以 `00` 開頭者（如 0050、0056、00878 等）均為 ETF，需在系統中加以標示。

**新增 DB 欄位（stocks 表）：**

```sql
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS is_etf BOOLEAN DEFAULT FALSE;
```

**標記邏輯（加入 migrate_v2.py 或獨立一行 SQL）：**

```sql
UPDATE stocks SET is_etf = TRUE  WHERE symbol LIKE '00%';
UPDATE stocks SET is_etf = FALSE WHERE symbol NOT LIKE '00%';
```

日後 `sync_stocks.py` 在新增股票時也應同步設定：
```python
is_etf = symbol.startswith("00")
```

**前端顯示：**
- 股名旁加 `ETF` 藍色小 badge（與注意/處置 badge 同樣風格）
- 篩選器增加「只看 ETF」/ 「排除 ETF」切換按鈕

---

## 八、不在本次範圍

- ROE / ROA / 負債比：TWSE openapi 目前無對應端點，暫不處理
- K 線圖 / 技術分析
- 使用者登入 / 投資組合
