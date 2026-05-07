# 計劃書：月營收備註欄位 + 「需求增加」篩選按鈕

**日期：** 2026-05-01  
**狀態：** 待確認

---

## 一、需求摘要

從公開資訊觀測站（MOPS）月營收報表（`t21sc03`）取得各公司當月備註說明，
新增 `revenue_note` 欄位至資料庫，並在前端加入「需求增加」快速篩選按鈕。

---

## 二、現況分析

| 項目 | 現況 |
|------|------|
| 月營收同步 | `sync_revenue_monthly.py` 透過 TWSE/TPEx openapi 取得年增率、月增率，但**無備註欄位** |
| MOPS CSV | 使用者已確認可從 MOPS 下載 CSV（如 `t21sc03_115_3.csv`），含備註欄位 |
| 備註樣本 | 247 筆含非空備註（以 115/3 月資料為例），含「需求增加」者 20 筆 |
| 後端篩選 | 已有 `STRING_FILTER_FIELDS` 機制，支援 `{field}_contains=關鍵字` 查詢 |
| 前端篩選 | 已有 `contains` FilterOp，可直接新增按鈕 |

---

## 三、執行步驟

### 步驟 1 — 資料庫 Schema 異動

**新增欄位：**
```sql
ALTER TABLE stocks
  ADD COLUMN IF NOT EXISTS revenue_note TEXT;
```

**說明：**
- 型別 `TEXT`，可為 NULL
- 每次同步時覆蓋更新（直接 `UPDATE`，不用 COALESCE）
- 不加索引（備註為模糊搜尋，資料量不大）

---

### 步驟 2 — 新增同步腳本 `sync_revenue_note.py`

**資料來源：** MOPS `t21sc03` 月報（上市公司）

```
POST https://mops.twse.com.tw/server-java/t21sc03
Content-Type: application/x-www-form-urlencoded
Body: STK_YEAR={ROC年份}&NACD=1&QOP=3&SHCO=&Mar_Item={月份}
```

**處理邏輯：**

1. 自動計算當前民國年份與月份（今日若為 5/1，同步上月 = 115/3 月）
2. 下載 MOPS CSV（或解析 HTML table）
3. 讀取欄位：`公司代號`、`備註`
4. 將備註值清理（去除前後空白、將單獨的 `"－"` 或 `"-"` 視為 NULL）
5. 批次 `UPDATE stocks SET revenue_note=..., updated_at=... WHERE symbol=...`

**上櫃：** TPEx 月報目前尚未確認有對應的備註 API；初期先處理上市，上櫃備註留待後續補充。

---

### 步驟 3 — 後端 API 異動（`backend/app/api/v1/stocks.py`）

**1. ORM Model（`backend/app/models.py`）新增欄位：**
```python
revenue_note = Column(Text)   # 月營收備註（含「需求增加」等說明）
```

**2. 加入字串篩選白名單：**
```python
STRING_FILTER_FIELDS = {
    "name", "symbol", "sector", "industry",
    "revenue_note",   # ← 新增
}
```

**3. 確認 `StockResponse` schema 包含 `revenue_note`**（Pydantic schema 需一併新增）

這樣就能用 `?revenue_note_contains=需求增加` 查詢。

---

### 步驟 4 — 前端異動（`frontend/src/App.tsx`）

**A. 新增篩選按鈕**

在「基本面」群組加入：
```typescript
{
  key: 'demand_increase', label: '需求增加', emoji: '📈',
  tooltip: '當月月營收備註含「需求增加」',
  conditions: [{ field: 'revenue_note', op: 'contains', value: '需求增加' }],
},
```

`QuickFilterKey` type 也需加入 `'demand_increase'`。

**B. 新增可顯示欄位**

在欄位選擇器（Column Selector）加入「月營收備註」：
- 欄位 key：`revenue_note`
- 顯示標籤：`月營收備註`
- 預設**不顯示**（選填欄位）
- 最大寬度：300px，`overflow: hidden; text-overflow: ellipsis`（備註文字可能較長）

---

### 步驟 5 — 每月自動化

此腳本屬**月度更新**（每月 1～5 日執行），可整合進現有排程或 Zeabur cron job。

---

## 四、變更檔案清單

| 檔案 | 異動類型 | 說明 |
|------|---------|------|
| `sync_revenue_note.py` | **新增** | 下載 MOPS CSV、更新 revenue_note |
| `backend/app/models.py` | 修改 | 新增 `revenue_note = Column(Text)` |
| `backend/app/api/v1/stocks.py` | 修改 | 加入 `revenue_note` 至 STRING_FILTER_FIELDS 及 StockResponse |
| `frontend/src/App.tsx` | 修改 | 新增「需求增加」按鈕 + 欄位顯示 |
| `migrate_revenue_note.sql` | **新增** | `ALTER TABLE stocks ADD COLUMN IF NOT EXISTS revenue_note TEXT` |

---

## 五、不在此次範圍內

- 上櫃備註同步（TPEx 無對應 JSON API，需另外評估）
- 歷史備註保存（只儲存最新月份，不保留過去備註）
- 備註全文搜尋（只做 LIKE `%contains%`，不做全文索引）

---

## 六、確認後執行順序

```
1. 執行 migrate_revenue_note.sql → 新增 DB 欄位
2. 執行 sync_revenue_note.py    → 填入備註資料
3. 修改 models.py + stocks.py   → 後端支援查詢
4. 修改 App.tsx                 → 前端顯示與按鈕
5. git commit & push → Zeabur 自動重部署
```

---

**請確認後，我再開始執行。**
