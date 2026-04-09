# 🚀 台股觀測站 - 最終完整修復指南

## ❌ 當前問題分析

**症狀**：
- ✅ Zeabur 顯示「Running」（運作中）
- ❌ 但訪問 URL 還是 404

**原因**：
Zeabur **無法正確識別前端應用的構建方式**

**解決**：
添加 **zeabur.json** 配置檔案，明確告訴 Zeabur 如何構建

---

# ✅ 立即修復步驟（5分鐘）

## 步驟 1：添加 zeabur.json 檔案

### 在專案根目錄（tw-stock-observer/）添加檔案：`zeabur.json`

**檔案位置**：
```
tw-stock-observer/
├── zeabur.json          ← 新增這個檔案！
├── backend/
├── frontend/
├── docker-compose.yml
└── ...
```

**檔案內容**：

```json
{
  "services": {
    "api": {
      "root": "backend",
      "build": {
        "dockerfile": "Dockerfile"
      }
    },
    "frontend": {
      "root": "frontend",
      "build": {
        "dockerfile": "Dockerfile"
      }
    }
  }
}
```

---

## 步驟 2：簡化前端 Dockerfile

### 更新 `frontend/Dockerfile`

**完整內容**（覆蓋現有的）：

```dockerfile
# 簡化的前端 Dockerfile
FROM node:18-alpine

WORKDIR /app

# 複製 package 檔案
COPY package.json package-lock.json ./

# 安裝依賴
RUN npm install

# 複製源代碼
COPY . .

# 構建
RUN npm run build

# 安裝 serve
RUN npm install -g serve

# 暴露埠口
EXPOSE 3000

# 啟動
CMD ["serve", "-s", "dist", "-l", "3000"]
```

**注意**：埠口改為 **3000**（Zeabur 標準埠口）

---

## 步驟 3：確認 package.json 有 build 指令

### 檢查 `frontend/package.json`

確認有以下內容：

```json
{
  "name": "tw-stock-observer-frontend",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@typescript-eslint/eslint-plugin": "^6.14.0",
    "@typescript-eslint/parser": "^6.14.0",
    "@vitejs/plugin-react": "^4.2.1",
    "eslint": "^8.55.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.5",
    "typescript": "^5.2.2",
    "vite": "^5.0.8"
  }
}
```

如果缺少依賴，複製上面的 package.json

---

## 步驟 4：推送到 GitHub

```bash
cd tw-stock-observer

# 添加所有檔案
git add .

# 提交
git commit -m "fix: add zeabur.json configuration for proper deployment"

# 推送
git push origin main
```

---

## 步驟 5：在 Zeabur 中刪除並重新部署

### 在 Zeabur 儀表板：

1. **刪除當前服務**
   - 點擊 tw-stock-observer-01
   - 進入設定
   - 點擊刪除

2. **重新部署**
   - 點擊「Deploy New Project」
   - 選擇 GitHub
   - 搜尋 tw-stock-observer
   - 點擊 Deploy

3. **等待 5-10 分鐘**
   - Zeabur 會讀取 zeabur.json
   - 正確構建前後端
   - 部署完成

4. **訪問新 URL**
   - 應該是：`https://tw-stock-observer-xx.zeabur.app/`

---

# 📋 完整檢查清單

在推送前確認：

### zeabur.json：
- [ ] 在專案根目錄（tw-stock-observer/）中
- [ ] 內容正確（JSON 格式）

### frontend/Dockerfile：
- [ ] 已更新為簡化版本
- [ ] 埠口改為 3000

### frontend/package.json：
- [ ] 有 `build` 指令
- [ ] 有所有必需的依賴

### GitHub：
- [ ] `git add .`
- [ ] `git commit`
- [ ] `git push origin main`

### Zeabur：
- [ ] 刪除了舊服務
- [ ] 開始新部署
- [ ] 部署完成（顯示 Running）

---

# 🧪 部署完成後驗證

### 1. 訪問應用

新 URL（Zeabur 會給你）：
```
https://tw-stock-observer-xx.zeabur.app/
```

應該看到：
- ✅ 「台股觀測站」標題
- ✅ 搜尋欄
- ✅ 股票卡片列表
- ❌ **不是** 404 或空白

### 2. 打開開發工具

按 `F12`，查看 Console：

應該看到：
```
🔧 應用配置:
當前環境: production
API URL: https://tw-stock-observer-xx.zeabur.app/api
```

### 3. 測試功能

- 點擊股票卡片
- 應該在右側顯示行情資訊

---

# 🆘 如果還是不行

### 檢查 1：查看 Zeabur 部署日誌

1. 進入 Zeabur 儀表板
2. 點擊新服務
3. 查看「Deployments」
4. 點擊最新部署
5. 點擊「Logs」查看日誌

常見錯誤：
```
npm ERR! → npm 依賴問題
Error: Cannot find module → 檔案缺失
```

### 檢查 2：驗證 zeabur.json 格式

確認 JSON 語法正確：

```json
{
  "services": {
    "api": {
      "root": "backend",
      "build": {
        "dockerfile": "Dockerfile"
      }
    },
    "frontend": {
      "root": "frontend",
      "build": {
        "dockerfile": "Dockerfile"
      }
    }
  }
}
```

使用 JSON 驗證工具：https://jsonlint.com/

### 檢查 3：確認 GitHub 上有所有檔案

```bash
git status
```

查看是否有未提交的檔案

---

# ✨ 預期成功結果

當一切正常時，你會看到：

```
🚀 台股觀測站
台灣股票市場監測和投資組合管理平台

[搜尋欄]

股票列表              股票行情
┌───────────┐
│ 2330      │          (點擊股票後)
│ 台積電    │
│ 半導體業  │         2330 - 台積電
└───────────┘         $612.00  +0.82%
                      開盤: $610.00
┌───────────┐         最高: $615.00
│ 2454      │         最低: $608.00
│ 聯發科    │         成交量: 12.35M
└───────────┘
```

---

# 🎯 立即行動

**5 分鐘內完成：**

1. ✅ 添加 zeabur.json
2. ✅ 更新 frontend/Dockerfile
3. ✅ 推送到 GitHub
4. ✅ Zeabur 刪除並重新部署
5. ✅ 訪問應用

---

# 📞 告訴我進度

完成後告訴我：

1. ✅ 是否添加了 zeabur.json？
2. ✅ 是否更新了 Dockerfile？
3. ✅ 是否推送到 GitHub？
4. ✅ Zeabur 是否顯示部署中？
5. ✅ 部署完成後看到什麼？

**我會持續幫助你直到成功！** 🚀💪

