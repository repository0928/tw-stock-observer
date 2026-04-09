# API 參考文檔 - 台股觀測站

## 1. 內部 API (台股觀測站)

### 1.1 股票服務 API

#### 獲取實時行情
```
GET /api/v1/stocks/{symbol}/quote
```

**參數**:
- `symbol` (string): 股票代碼 (如 "2330")

**範例請求**:
```bash
curl -X GET "http://localhost:8000/api/v1/stocks/2330/quote" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**成功回應 (200)**:
```json
{
  "symbol": "2330",
  "name": "台積電",
  "price": 612.00,
  "change": 5.00,
  "changePercent": 0.82,
  "volume": 12345678,
  "high": 615.00,
  "low": 608.00,
  "open": 610.00,
  "close": 612.00,
  "timestamp": "2024-01-15T14:30:00+08:00",
  "bid": 611.50,
  "ask": 612.50
}
```

**錯誤回應 (404)**:
```json
{
  "error": "Stock not found",
  "code": "STOCK_NOT_FOUND"
}
```

---

#### 獲取 K 線資料
```
GET /api/v1/stocks/{symbol}/klines
```

**查詢參數**:
- `period` (string): 時間週期 - "1m", "5m", "15m", "1h", "1d" (默認: "1d")
- `limit` (integer): 返回筆數 (默認: 100, 最大: 500)
- `start_date` (string): 開始日期 (ISO 8601 格式)
- `end_date` (string): 結束日期 (ISO 8601 格式)

**範例請求**:
```bash
curl -X GET "http://localhost:8000/api/v1/stocks/2330/klines?period=1d&limit=30" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**成功回應 (200)**:
```json
{
  "symbol": "2330",
  "period": "1d",
  "klines": [
    {
      "timestamp": "2024-01-15T00:00:00+08:00",
      "open": 610.00,
      "high": 615.00,
      "low": 608.00,
      "close": 612.00,
      "volume": 12345678,
      "amount": 7500000000
    },
    {
      "timestamp": "2024-01-14T00:00:00+08:00",
      "open": 608.00,
      "high": 613.00,
      "low": 607.00,
      "close": 610.00,
      "volume": 11234567,
      "amount": 6800000000
    }
  ]
}
```

---

#### 獲取股票基本資料
```
GET /api/v1/stocks/{symbol}/info
```

**成功回應 (200)**:
```json
{
  "symbol": "2330",
  "name": "台積電",
  "englishName": "Taiwan Semiconductor Manufacturing Company Limited",
  "sector": "半導體業",
  "industry": "IC設計製造",
  "listingDate": "1994-06-05",
  "capitalStock": 10000000000,
  "shares": 2600000000,
  "chairman": "劉德音",
  "ceo": "魏哲家",
  "revenue": 676000000000,
  "eps": 23.50,
  "peRatio": 26.04,
  "pbRatio": 5.20,
  "website": "https://www.tsmc.com"
}
```

---

### 1.2 投資組合 API

#### 建立投資組合
```
POST /api/v1/portfolios
```

**請求體**:
```json
{
  "name": "我的股票組合",
  "description": "長期投資組合",
  "visibility": "private",
  "budget": 500000,
  "targetReturn": 15.0
}
```

**成功回應 (201)**:
```json
{
  "id": "portfolio_001",
  "userId": "user_123",
  "name": "我的股票組合",
  "description": "長期投資組合",
  "visibility": "private",
  "budget": 500000,
  "currentValue": 0,
  "targetReturn": 15.0,
  "actualReturn": 0,
  "returnPercent": 0,
  "createdAt": "2024-01-15T14:30:00+08:00",
  "updatedAt": "2024-01-15T14:30:00+08:00"
}
```

---

#### 新增股票到投資組合
```
POST /api/v1/portfolios/{portfolioId}/holdings
```

**請求體**:
```json
{
  "symbol": "2330",
  "quantity": 10,
  "purchasePrice": 600.00,
  "purchaseDate": "2024-01-10"
}
```

**成功回應 (201)**:
```json
{
  "id": "holding_001",
  "portfolioId": "portfolio_001",
  "symbol": "2330",
  "quantity": 10,
  "purchasePrice": 600.00,
  "currentPrice": 612.00,
  "costBasis": 6000.00,
  "currentValue": 6120.00,
  "gain": 120.00,
  "gainPercent": 2.0,
  "purchaseDate": "2024-01-10",
  "updatedAt": "2024-01-15T14:30:00+08:00"
}
```

---

### 1.3 分析 API

#### 計算技術指標
```
POST /api/v1/analysis/indicators
```

**請求體**:
```json
{
  "symbol": "2330",
  "period": "1d",
  "indicators": ["sma", "rsi", "macd", "bollinger"],
  "parameters": {
    "sma_period": 20,
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "bollinger_period": 20,
    "bollinger_stddev": 2
  }
}
```

**成功回應 (200)**:
```json
{
  "symbol": "2330",
  "period": "1d",
  "timestamp": "2024-01-15T14:30:00+08:00",
  "indicators": {
    "sma": {
      "sma_20": 610.50,
      "sma_50": 605.20,
      "sma_200": 598.80
    },
    "rsi": {
      "rsi_14": 65.50
    },
    "macd": {
      "macd": 5.30,
      "signal": 4.80,
      "histogram": 0.50
    },
    "bollinger": {
      "upper": 625.00,
      "middle": 610.50,
      "lower": 596.00
    }
  }
}
```

---

#### 風險分析
```
GET /api/v1/analysis/portfolio/{portfolioId}/risk
```

**查詢參數**:
- `method` (string): 分析方法 - "var" (Value at Risk), "cvar" (Conditional VaR), "sharpe" (Sharpe Ratio)
- `confidence` (float): 信心水平 (0.95 或 0.99)

**成功回應 (200)**:
```json
{
  "portfolioId": "portfolio_001",
  "method": "var",
  "confidence": 0.95,
  "var_daily": 5000.00,
  "cvar_daily": 7500.00,
  "volatility": 0.18,
  "sharpeRatio": 1.25,
  "betaToMarket": 1.10,
  "maxDrawdown": 0.25,
  "description": "該投資組合在95%信心水平下，日最大虧損風險為 NT$5,000"
}
```

---

## 2. TWSE API (台灣證交所)

### 2.1 即時成交行情 API

**官方文檔**: https://opendata.twse.com.tw/

#### 獲取個股行情
```
GET https://opendata.twse.com.tw/api/v1/stockInfo
```

**查詢參數**:
- `stockNo` (string): 股票代號 (如 "2330")

**範例**:
```bash
curl -X GET "https://opendata.twse.com.tw/api/v1/stockInfo?stockNo=2330"
```

**回應範例**:
```json
{
  "msgArray": [
    {
      "n": "台積電",
      "z": "612.00",
      "tlong": "20240115143000",
      "ex": "tse",
      "d": "20240115",
      "it": "04",
      "o": "610.00",
      "h": "615.00",
      "l": "608.00",
      "y": "607.00",
      "t": "12345678",
      "f": "100000",
      "a": "100000",
      "v": "7500000000",
      "ot": "0"
    }
  ],
  "sessionStr": "UserSession",
  "sessionFromTime": 1705318800000,
  "sessionLatestTime": 1705340400000
}
```

**欄位說明**:
| 欄位 | 說明 | 
|------|------|
| n | 股票名稱 |
| z | 成交價 |
| tlong | 時間戳 |
| ex | 交易所 (tse: 上市, otc: 櫃買) |
| d | 日期 |
| o | 開盤價 |
| h | 最高價 |
| l | 最低價 |
| y | 昨收 |
| t | 成交量 |
| v | 成交值 |

---

### 2.2 個股日成交資訊

```
GET https://opendata.twse.com.tw/api/v1/exchangeReport
```

**查詢參數**:
- `date` (string): 日期 (YYYYMMDD 格式，如 "20240115")

**回應範例**:
```json
{
  "fields": ["代號", "名稱", "成交筆數", "成交股數", "成交額", "開盤價", "最高價", "最低價", "收盤價", "漲跌", "漲跌比例"],
  "data": [
    ["2330", "台積電", "12345", "12345678", "7500000000", "610.00", "615.00", "608.00", "612.00", "5.00", "0.82"],
    ...
  ]
}
```

---

## 3. Yahoo Finance API

### 3.1 歷史股價資料

**官方文檔**: https://finance.yahoo.com/

#### 使用 yfinance Python 庫

```python
import yfinance as yf

# 下載單支股票資料
stock = yf.download("2330.TW", start="2024-01-01", end="2024-01-15")

# 下載多支股票
tickers = yf.download(["2330.TW", "2454.TW"], start="2024-01-01")

# 獲取股票資訊
info = yf.Ticker("2330.TW").info
```

**返回欄位**:
- Open: 開盤價
- High: 最高價
- Low: 最低價
- Close: 收盤價
- Adj Close: 調整後收盤價
- Volume: 成交量

---

### 3.2 股票基本資訊

```python
ticker = yf.Ticker("2330.TW")
info = ticker.info

# 常用欄位
print(info['longName'])           # 公司全名
print(info['sector'])              # 產業
print(info['industry'])             # 行業
print(info['marketCap'])            # 市值
print(info['trailingPE'])           # 本益比
print(info['priceToBook'])          # 股價淨值比
print(info['dividendYield'])        # 股息殖利率
```

---

## 4. TaiwanStock (台灣股市資料) API

### 4.1 基本用途

**官方網站**: https://www.twstock.com/

提供台灣股市的完整資料包括：
- 個股日成交資訊
- 技術分析資料
- 籌碼面資訊
- 財報資訊

---

## 5. API 認證與授權

### 5.1 JWT Token 認證

**獲取 Token**:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'
```

**回應**:
```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refreshToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expiresIn": 3600,
  "tokenType": "Bearer"
}
```

**使用 Token**:
```bash
curl -X GET "http://localhost:8000/api/v1/stocks/2330/quote" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

### 5.2 API Key 認證 (備用)

```bash
curl -X GET "http://localhost:8000/api/v1/stocks/2330/quote" \
  -H "X-API-Key: your-api-key-here"
```

---

## 6. 錯誤碼參考

| 狀態碼 | 說明 |
|--------|------|
| 200 | 成功 |
| 201 | 建立成功 |
| 400 | 請求參數錯誤 |
| 401 | 未認證 |
| 403 | 無權限存取 |
| 404 | 資源不存在 |
| 429 | 請求過於頻繁 (Rate Limit) |
| 500 | 伺服器錯誤 |
| 503 | 服務暫時不可用 |

---

## 7. Rate Limiting (請求限流)

### 限流規則
- **未認證使用者**: 100 requests/hour
- **普通認證使用者**: 1000 requests/hour
- **高級用戶**: 10000 requests/hour

### 響應頭
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1705340400
```

---

## 8. 使用示例

### Python 完整示例

```python
import requests
import json
from datetime import datetime, timedelta

class TWStockAPIClient:
    def __init__(self, base_url="http://localhost:8000", token=None):
        self.base_url = base_url
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def get_quote(self, symbol):
        """獲取實時行情"""
        url = f"{self.base_url}/api/v1/stocks/{symbol}/quote"
        response = requests.get(url, headers=self.headers)
        return response.json()
    
    def get_klines(self, symbol, period="1d", limit=30):
        """獲取K線資料"""
        url = f"{self.base_url}/api/v1/stocks/{symbol}/klines"
        params = {"period": period, "limit": limit}
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()
    
    def create_portfolio(self, name, budget):
        """建立投資組合"""
        url = f"{self.base_url}/api/v1/portfolios"
        data = {
            "name": name,
            "budget": budget
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

# 使用示例
client = TWStockAPIClient(token="your-token-here")
quote = client.get_quote("2330")
print(json.dumps(quote, indent=2))
```

---

**最後更新**: 2024年1月 | **維護者**: 台股觀測站開發團隊
