import React, { useState, useEffect } from 'react'
import './index.css'

interface Stock {
  id?: string
  symbol: string
  name: string
  sector?: string
}

interface Quote {
  symbol: string
  name: string
  price: number
  change: number
  change_percent: number
  volume: number
  high: number
  low: number
  open: number
  close: number
  timestamp: string
  bid?: number
  ask?: number
}

function App() {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedStock, setSelectedStock] = useState<Quote | null>(null)

  // 動態決定 API URL
  const getApiUrl = () => {
    // 開發環境
    if (import.meta.env.DEV) {
      return import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
    }
    
    // 生產環境 - 從當前域名推斷
    const protocol = window.location.protocol
    const hostname = window.location.hostname
    
    // 如果是 Zeabur，替換為後端 URL
    if (hostname.includes('zeabur.app')) {
      // 從前端 URL 推斷後端 URL
      // 假設後端也在同一個 Zeabur 項目中
      // 可以使用相同的域名但走不同的埠或路徑
      return `${protocol}//tw-stock-observer-v1.zeabur.app/api`
    }
    
    // 其他情況下使用相同的主機名
    return `${protocol}//${hostname}/api`
  }

  const API_URL = getApiUrl()

  console.log('🔧 應用配置:')
  console.log('當前環境:', import.meta.env.MODE)
  console.log('API URL:', API_URL)
  console.log('主機名:', window.location.hostname)

  // 獲取股票列表
  const fetchStocks = async () => {
    setLoading(true)
    setError(null)
    try {
      console.log('📡 正在從以下地址獲取股票列表:', `${API_URL}/v1/stocks`)
      const response = await fetch(`${API_URL}/v1/stocks`, {
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      })
      
      if (!response.ok) {
        throw new Error(`API 請求失敗: ${response.status} ${response.statusText}`)
      }
      
      const data = await response.json()
      console.log('✅ 成功獲取股票列表:', data)
      
      // 處理不同的 API 回應格式
      const stocksList = data.stocks || data.items || data || []
      setStocks(Array.isArray(stocksList) ? stocksList : [])
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : '未知錯誤'
      console.error('❌ 獲取股票列表失敗:', errorMsg)
      setError(`無法載入股票列表: ${errorMsg}`)
      setStocks([])
    }
    setLoading(false)
  }

  // 搜尋股票
  const searchStocks = async (keyword: string) => {
    if (!keyword.trim()) {
      fetchStocks()
      return
    }

    setLoading(true)
    setError(null)
    try {
      console.log('🔍 搜尋股票:', keyword)
      const response = await fetch(`${API_URL}/v1/stocks/search/${encodeURIComponent(keyword)}`, {
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      })
      
      if (!response.ok) {
        throw new Error(`搜尋失敗: ${response.status}`)
      }
      
      const data = await response.json()
      console.log('✅ 搜尋結果:', data)
      
      const stocksList = data.stocks || data.items || []
      setStocks(Array.isArray(stocksList) ? stocksList : [])
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : '未知錯誤'
      console.error('❌ 搜尋失敗:', errorMsg)
      setError(`搜尋失敗: ${errorMsg}`)
    }
    setLoading(false)
  }

  // 獲取股票行情
  const fetchQuote = async (symbol: string) => {
    try {
      console.log('📊 正在獲取行情:', symbol)
      const response = await fetch(`${API_URL}/v1/stocks/${symbol}/quote`, {
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      })
      
      if (!response.ok) {
        throw new Error(`獲取行情失敗: ${response.status}`)
      }
      
      const data = await response.json()
      console.log('✅ 行情數據:', data)
      
      // 轉換數字格式
      const quote: Quote = {
        symbol: data.symbol || symbol,
        name: data.name || symbol,
        price: parseFloat(data.price || 0),
        change: parseFloat(data.change || 0),
        change_percent: parseFloat(data.change_percent || 0),
        volume: parseInt(data.volume || 0),
        high: parseFloat(data.high || 0),
        low: parseFloat(data.low || 0),
        open: parseFloat(data.open || 0),
        close: parseFloat(data.close || 0),
        timestamp: data.timestamp || new Date().toISOString(),
        bid: data.bid ? parseFloat(data.bid) : undefined,
        ask: data.ask ? parseFloat(data.ask) : undefined,
      }
      
      setSelectedStock(quote)
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : '未知錯誤'
      console.error('❌ 獲取行情失敗:', errorMsg)
      setError(`無法獲取行情: ${errorMsg}`)
    }
  }

  // 初始化 - 載入股票列表
  useEffect(() => {
    fetchStocks()
  }, [])

  // 搜尋處理
  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(e.target.value)
    searchStocks(e.target.value)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>🚀 台股觀測站</h1>
        <p>台灣股票市場監測和投資組合管理平台</p>
      </header>

      <main className="app-main">
        {/* 搜尋欄 */}
        <section className="search-section">
          <input
            type="text"
            className="search-input"
            placeholder="搜尋股票代碼或名稱... (例如: 2330)"
            value={searchTerm}
            onChange={handleSearch}
          />
        </section>

        {/* 錯誤提示 */}
        {error && (
          <div style={{
            background: 'rgba(244, 67, 54, 0.1)',
            border: '1px solid rgba(244, 67, 54, 0.3)',
            color: '#f44336',
            padding: '1rem',
            borderRadius: '8px',
            marginBottom: '1rem',
          }}>
            ⚠️ {error}
          </div>
        )}

        {/* 內容區 */}
        <div className="content-container">
          {/* 股票列表 */}
          <section className="stocks-section">
            <h2>股票列表</h2>
            {loading ? (
              <div className="loading">⏳ 載入中...</div>
            ) : stocks.length > 0 ? (
              <div className="stocks-grid">
                {stocks.map((stock) => (
                  <div
                    key={stock.id || stock.symbol}
                    className="stock-card"
                    onClick={() => fetchQuote(stock.symbol)}
                    style={{ cursor: 'pointer' }}
                  >
                    <div className="stock-symbol">{stock.symbol}</div>
                    <div className="stock-name">{stock.name}</div>
                    <div className="stock-sector">{stock.sector || '未分類'}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-data">
                {searchTerm ? '未找到符合的股票' : '尚無股票資料'}
              </div>
            )}
          </section>

          {/* 行情詳情 */}
          {selectedStock && (
            <section className="quote-section">
              <h2>股票行情</h2>
              <div className="quote-card">
                <div className="quote-header">
                  <h3>{selectedStock.symbol} - {selectedStock.name}</h3>
                </div>
                <div className="quote-price">
                  <span className="price">${selectedStock.price.toFixed(2)}</span>
                  <span className={`change ${selectedStock.change_percent >= 0 ? 'up' : 'down'}`}>
                    {selectedStock.change_percent >= 0 ? '+' : ''}{selectedStock.change_percent.toFixed(2)}%
                  </span>
                </div>
                <div className="quote-details">
                  <div className="detail-item">
                    <span className="label">開盤:</span>
                    <span className="value">${selectedStock.open.toFixed(2)}</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">最高:</span>
                    <span className="value">${selectedStock.high.toFixed(2)}</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">最低:</span>
                    <span className="value">${selectedStock.low.toFixed(2)}</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">成交量:</span>
                    <span className="value">{(selectedStock.volume / 1000000).toFixed(2)}M</span>
                  </div>
                </div>
              </div>
            </section>
          )}
        </div>
      </main>

      <footer className="app-footer">
        <p>© 2024 台股觀測站 | 版本 1.0.0</p>
        <p style={{ fontSize: '0.8rem', marginTop: '0.5rem', opacity: 0.7 }}>
          API 地址: {API_URL}
        </p>
      </footer>
    </div>
  )
}

export default App
