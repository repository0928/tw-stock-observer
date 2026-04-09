# 🚀 台股觀測站

台灣股票市場監測和投資組合管理平台

## 📋 專案說明

台股觀測站是一個完整的股票市場應用，提供：

- ✅ 實時行情查詢
- ✅ K線技術分析
- ✅ 投資組合管理
- ✅ 自動交易記錄
- ✅ 風險評估分析
- ✅ 價格告警系統

## 🛠️ 技術棧

### 後端
- **框架**: FastAPI
- **資料庫**: PostgreSQL
- **快取**: Redis
- **ORM**: SQLAlchemy 2.0
- **驗證**: Pydantic

### 前端
- **框架**: React 18
- **語言**: TypeScript
- **構建**: Vite
- **樣式**: CSS3

### 基礎設施
- **容器化**: Docker
- **編排**: Docker Compose
- **版本控制**: Git

## 🚀 快速開始

### 方案 1: Docker Compose（推薦）

```bash
# 克隆專案
git clone https://github.com/repository0928/tw-stock-observer.git
cd tw-stock-observer

# 啟動所有服務
docker-compose up -d

# 檢查服務狀態
docker-compose ps
```

訪問：
- 前端：http://localhost:5173
- 後端：http://localhost:8000
- API 文檔：http://localhost:8000/api/docs

### 方案 2: 本地開發

#### 後端

```bash
cd backend

# 建立虛擬環境
python -m venv venv

# 啟動虛擬環境
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# 安裝依賴
pip install -r requirements.txt

# 複製環境設置
cp .env.example .env

# 啟動伺服器
python main.py
```

#### 前端

```bash
cd frontend

# 安裝依賴
npm install

# 複製環境設置
cp .env.example .env

# 啟動開發伺服器
npm run dev
```

## 📚 文件

- [系統架構](./architecture.md) - 詳細的系統設計
- [API 文檔](./api_reference.md) - API 完整參考
- [資料庫設計](./db_schema.sql) - SQL DDL
- [編碼規範](./coding_style.md) - 開發規範
- [部署指南](./DEPLOYMENT_GUIDE.md) - 部署步驟

## 🔧 環境變數

複製 `.env.example` 為 `.env` 並設置：

```
DEBUG=false
ENVIRONMENT=production
DATABASE_URL=postgresql://user:password@host:port/database
REDIS_URL=redis://host:port/0
SECRET_KEY=your-secret-key
```

## 📖 API 端點

### 股票
- `GET /api/v1/stocks` - 獲取股票列表
- `GET /api/v1/stocks/{symbol}/quote` - 獲取行情
- `GET /api/v1/stocks/{symbol}/klines` - 獲取 K線
- `GET /api/v1/stocks/{symbol}/info` - 獲取基本資訊
- `GET /api/v1/stocks/search/{keyword}` - 搜尋股票

### 投資組合（待實現）
- `GET /api/v1/portfolios` - 獲取組合列表
- `POST /api/v1/portfolios` - 建立組合
- `GET /api/v1/portfolios/{id}` - 獲取組合詳情
- `PUT /api/v1/portfolios/{id}` - 更新組合
- `DELETE /api/v1/portfolios/{id}` - 刪除組合

完整 API 文檔見：http://localhost:8000/api/docs

## 🧪 測試

```bash
# 後端測試
cd backend
pytest

# 前端測試
cd frontend
npm test
```

## 📦 部署

### Zeabur

```bash
# 推送到 GitHub
git push origin main

# 在 Zeabur 部署
# 1. 訪問 https://zeabur.com
# 2. 連接 GitHub 倉庫
# 3. 點擊部署
```

### Heroku

```bash
# 登入 Heroku
heroku login

# 建立應用
heroku create tw-stock-observer

# 部署
git push heroku main
```

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

### 開發流程

1. Fork 本倉庫
2. 建立特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交變更 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 開啟 Pull Request

## 📄 授權

MIT License - 見 [LICENSE](./LICENSE) 檔案

## 🙏 致謝

感謝所有開源專案和社區的支持。

## 📞 聯繫

- 提交 Issue: https://github.com/repository0928/tw-stock-observer/issues
- 討論: https://github.com/repository0928/tw-stock-observer/discussions

---

**版本**: 1.0.0  
**最後更新**: 2024年1月  
**維護者**: 台股觀測站開發團隊

祝你使用愉快！🎉
