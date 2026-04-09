#!/bin/bash
# 台股觀測站 - 前端修復指南
# Fix Frontend Deployment Issue

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          台股觀測站 - 前端部署修復指南                         ║"
echo "║          Frontend Deployment Fix Guide                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# ==================== 問題說明 ====================

echo "❌ 當前問題："
echo "   應用顯示 404 錯誤"
echo "   前端未正確部署"
echo ""

echo "✅ 解決方案："
echo "   添加缺失的前端配置檔案"
echo "   重新推送到 GitHub"
echo "   Zeabur 自動重新部署"
echo ""

# ==================== 步驟 1：更新本地檔案 ====================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "步驟 1：下載並添加缺失的前端檔案"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "需要添加以下檔案到 frontend/ 目錄："
echo ""
echo "1. frontend/src/main.tsx"
echo "2. frontend/src/index.css"
echo "3. frontend/index.html"
echo "4. frontend/vite.config.ts"
echo "5. frontend/tsconfig.json"
echo "6. frontend/tsconfig.node.json"
echo "7. frontend/Dockerfile (改名自 Dockerfile.frontend)"
echo "8. frontend/.env.example"
echo ""

echo "📥 下載位置："
echo "   所有這些檔案都在 /mnt/user-data/outputs/ 中"
echo ""

echo "📂 完整的前端檔案夾結構應該是："
echo ""
echo "frontend/"
echo "├── src/"
echo "│   ├── App.tsx"
echo "│   ├── main.tsx              ← 新增"
echo "│   └── index.css             ← 新增"
echo "├── index.html                ← 新增"
echo "├── package.json              ✓ 已有"
echo "├── tsconfig.json             ← 新增"
echo "├── tsconfig.node.json        ← 新增"
echo "├── vite.config.ts            ← 新增"
echo "├── Dockerfile                ← 新增"
echo "└── .env.example              ← 新增"
echo ""

# ==================== 步驟 2：推送到 GitHub ====================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "步驟 2：推送更新到 GitHub"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "在命令列執行以下命令："
echo ""
echo "  cd tw-stock-observer"
echo "  git add ."
echo "  git commit -m 'fix: add missing frontend configuration files'"
echo "  git push origin main"
echo ""

echo "⏳ 等待 Git 推送完成"
echo ""

# ==================== 步驟 3：Zeabur 自動部署 ====================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "步驟 3：Zeabur 自動部署"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "✅ 自動發生的事情："
echo "1. GitHub 會檢測到你的推送"
echo "2. Zeabur 會自動觸發新的部署"
echo "3. Zeabur 會重新構建前端"
echo "4. 大約 3-5 分鐘後部署完成"
echo ""

echo "🔍 監控部署進度："
echo "1. 進入 Zeabur 儀表板"
echo "2. 查看 \"Deployments\" 部分"
echo "3. 應該看到新的部署記錄"
echo "4. 狀態從 \"Deploying\" 變為 \"Running\""
echo ""

# ==================== 步驟 4：驗證部署成功 ====================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "步驟 4：驗證部署成功"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "⏱️ 等待 3-5 分鐘後，訪問你的應用 URL："
echo ""
echo "  https://tw-stock-observer-v1.zeabur.app"
echo ""

echo "你應該會看到："
echo "✅ 「台股觀測站」標題"
echo "✅ 搜尋欄"
echo "✅ 股票列表卡片"
echo "✅ 應用正常運行"
echo ""

# ==================== 故障排除 ====================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "故障排除"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "❓ 如果還是 404 錯誤："
echo ""
echo "1. 檢查所有檔案是否都正確添加"
echo "   $ git status"
echo ""
echo "2. 檢查 package.json 是否正確"
echo "   應該包含 'react', 'react-dom', '@vitejs/plugin-react'"
echo ""
echo "3. 檢查 Dockerfile 是否存在"
echo "   檔案名應為 'Dockerfile'，不是 'Dockerfile.frontend'"
echo ""
echo "4. 手動在 Zeabur 重新部署"
echo "   - 進入 Zeabur 儀表板"
echo "   - 找到 tw-stock-observer 服務"
echo "   - 點擊「重新部署」或「Restart」"
echo ""

echo "❓ 如果看到其他錯誤："
echo ""
echo "1. 查看 Zeabur 的構建日誌"
echo "   - Deployments → 點擊失敗的部署 → 查看日誌"
echo ""
echo "2. 常見錯誤："
echo "   - 'Cannot find module' → 檢查 package.json"
echo "   - 'TypeScript error' → 檢查 tsconfig.json"
echo "   - 'Port already in use' → Zeabur 會自動處理"
echo ""

# ==================== 完成清單 ====================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 完成檢查清單"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "前端檔案："
echo "  ☐ frontend/src/App.tsx"
echo "  ☐ frontend/src/main.tsx"
echo "  ☐ frontend/src/index.css"
echo "  ☐ frontend/index.html"
echo ""

echo "配置檔案："
echo "  ☐ frontend/package.json"
echo "  ☐ frontend/vite.config.ts"
echo "  ☐ frontend/tsconfig.json"
echo "  ☐ frontend/tsconfig.node.json"
echo "  ☐ frontend/Dockerfile"
echo "  ☐ frontend/.env.example"
echo ""

echo "GitHub："
echo "  ☐ git add ."
echo "  ☐ git commit"
echo "  ☐ git push origin main"
echo ""

echo "Zeabur："
echo "  ☐ 檢查新的部署記錄"
echo "  ☐ 等待部署完成 (3-5 分鐘)"
echo "  ☐ 訪問應用 URL"
echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  🎉 祝你成功！                                 ║"
echo "║                                                                ║"
echo "║    如有任何問題，查看 Zeabur 部署日誌尋找具體錯誤信息          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
