#!/bin/bash
# 台股觀測站 - 完整設置和部署指南
# Taiwan Stock Observer - Complete Setup and Deployment Guide

# ==================== 第 1 步：安裝工具 ====================

echo "═══════════════════════════════════════════════════════════════"
echo "           台股觀測站 - 完整設置指南"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ==================== 檢查系統 ====================

echo "🔍 檢查已安裝的工具..."
echo ""

# 檢查 Git
if command -v git &> /dev/null; then
    echo "✅ Git: $(git --version)"
else
    echo "❌ Git 未安裝"
    echo "   訪問: https://git-scm.com/download"
fi

# 檢查 Python
if command -v python3 &> /dev/null; then
    echo "✅ Python: $(python3 --version)"
else
    echo "❌ Python 未安裝"
    echo "   訪問: https://www.python.org/downloads"
fi

# 檢查 Node.js
if command -v node &> /dev/null; then
    echo "✅ Node.js: $(node --version)"
else
    echo "❌ Node.js 未安裝"
    echo "   訪問: https://nodejs.org"
fi

# 檢查 Docker
if command -v docker &> /dev/null; then
    echo "✅ Docker: $(docker --version)"
else
    echo "❌ Docker 未安裝"
    echo "   訪問: https://www.docker.com/products/docker-desktop"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ==================== 建立檔案夾結構 ====================

echo "📁 建立專案檔案夾結構..."
echo ""

# 如果已在專案目錄中
if [ ! -d "backend" ]; then
    mkdir -p backend
    echo "✅ 建立 backend 檔案夾"
fi

if [ ! -d "frontend" ]; then
    mkdir -p frontend
    echo "✅ 建立 frontend 檔案夾"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ==================== 後端設置 ====================

echo "🔧 後端設置步驟..."
echo ""
echo "1️⃣ 複製 main.py, config.py, database.py 等到 backend/ 資料夾"
echo "2️⃣ 複製 stock_service.py 到 backend/app/services/ 資料夾"
echo "3️⃣ 複製 stocks.py 到 backend/app/api/v1/ 資料夾"
echo "4️⃣ 複製 requirements.txt 和 Dockerfile.backend 到 backend/ 資料夾"
echo "5️⃣ 複製 db_schema.sql 到 backend/ 資料夾"
echo ""

# ==================== 前端設置 ====================

echo "⚛️  前端設置步驟..."
echo ""
echo "1️⃣ 複製 App.tsx 到 frontend/src/ 資料夾"
echo "2️⃣ 複製 package.json 到 frontend/ 資料夾"
echo "3️⃣ 複製 Dockerfile.backend 改名為 Dockerfile 到 frontend/ 資料夾"
echo ""

# ==================== 版本控制 ====================

echo "📚 版本控制設置..."
echo ""
echo "1️⃣ 初始化 Git：git init"
echo "2️⃣ 複製 .gitignore 到專案根目錄"
echo "3️⃣ 複製 .env.example 到專案根目錄"
echo "4️⃣ 提交代碼："
echo "   $ git add ."
echo "   $ git commit -m 'Initial commit: tw-stock-observer'"
echo ""

# ==================== Docker Compose ====================

echo "🐳 Docker Compose 設置..."
echo ""
echo "1️⃣ 複製 docker-compose.yml 到專案根目錄"
echo "2️⃣ 啟動所有服務："
echo "   $ docker-compose up -d"
echo "3️⃣ 檢查服務狀態："
echo "   $ docker-compose ps"
echo ""

# ==================== GitHub 上傳 ====================

echo "☁️  GitHub 上傳步驟..."
echo ""
echo "1️⃣ 在 GitHub 建立新倉庫："
echo "   https://github.com/new"
echo ""
echo "2️⃣ 倉庫設置："
echo "   - 名稱: tw-stock-observer"
echo "   - 描述: Taiwan Stock Observer Platform"
echo "   - 可見性: Public"
echo ""
echo "3️⃣ 推送代碼（把 repository0928 改成你的用戶名）："
echo ""
echo "   git remote add origin https://github.com/repository0928/tw-stock-observer.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""

# ==================== Zeabur 部署 ====================

echo "🚀 Zeabur 部署步驟..."
echo ""
echo "1️⃣ 訪問 Zeabur："
echo "   https://zeabur.com"
echo ""
echo "2️⃣ 登入/註冊："
echo "   - 使用 GitHub 帳號登入"
echo "   - 授權 Zeabur 訪問你的 GitHub"
echo ""
echo "3️⃣ 部署新專案："
echo "   - 點擊 Deploy New Project"
echo "   - 選擇 GitHub"
echo "   - 搜尋 tw-stock-observer"
echo "   - 點擊部署"
echo ""
echo "4️⃣ 等待部署完成（2-3 分鐘）"
echo ""
echo "5️⃣ 設置環境變數："
echo "   - 進入 Settings"
echo "   - 添加環境變數："
echo "     DEBUG=false"
echo "     ENVIRONMENT=production"
echo "     SECRET_KEY=your-secret-key"
echo ""
echo "6️⃣ 訪問應用："
echo "   https://tw-stock-observer-xxx.zeabur.app"
echo ""

# ==================== 完成檢查清單 ====================

echo "═══════════════════════════════════════════════════════════════"
echo "                   ✅ 完成檢查清單"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "安裝工具："
echo "  ☐ Git"
echo "  ☐ Python 3.10+"
echo "  ☐ Node.js 16+"
echo "  ☐ Docker"
echo ""
echo "建立檔案夾結構："
echo "  ☐ backend/"
echo "  ☐ frontend/"
echo ""
echo "複製檔案："
echo "  ☐ 後端檔案"
echo "  ☐ 前端檔案"
echo "  ☐ 配置檔案 (docker-compose.yml, .env.example, .gitignore)"
echo "  ☐ 文檔檔案 (README.md)"
echo ""
echo "版本控制："
echo "  ☐ git init"
echo "  ☐ git add ."
echo "  ☐ git commit"
echo ""
echo "GitHub 上傳："
echo "  ☐ 在 GitHub 建立倉庫"
echo "  ☐ git push 到 GitHub"
echo ""
echo "Zeabur 部署："
echo "  ☐ 連接 GitHub 倉庫"
echo "  ☐ 點擊部署"
echo "  ☐ 設置環境變數"
echo "  ☐ 訪問應用"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "🎉 祝你成功！"
echo ""
