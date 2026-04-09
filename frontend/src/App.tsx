import React, { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [stocks, setStocks] = useState([])
  const [loading, setLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedStock, setSelectedStock] = useState(null)

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

  // 獲取股票列表
  const fetchStocks = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/v1/stocks`)
      const data = await response.json()
      setStocks(data.stocks || [])
    } catch (error) {
      console.error('獲取股票列表失敗:', error)
    }
    setLoading(false)
  }

  // 搜尋股票
  const searchStocks = async (keyword) => {
    if (!keyword.trim()) {
      fetchStocks()
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/v1/stocks/search/${keyword}`)
      const data = await response.json()
      setStocks(data.stocks || [])
    } catch (error) {
      console.error('搜尋失敗:', error)
    }
    setLoading(false)
  }

  // 獲取股票行情
  const fetchQuote = async (symbol) => {
    try {
      const response = await fetch(`${API_URL}/v1/stocks/${symbol}/quote`)
      const data = await response.json()
      setSelectedStock(data)
    } catch (error) {
      console.error('獲取行情失敗:', error)
    }
  }

  // 初始化
  useEffect(() => {
    fetchStocks()
  }, [])

  // 搜尋處理
  const handleSearch = (e) => {
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
            placeholder="搜尋股票代碼或名稱..."
            value={searchTerm}
            onChange={handleSearch}
          />
        </section>

        {/* 內容區 */}
        <div className="content-container">
          {/* 股票列表 */}
          <section className="stocks-section">
            <h2>股票列表</h2>
            {loading ? (
              <div className="loading">載入中...</div>
            ) : stocks.length > 0 ? (
              <div className="stocks-grid">
                {stocks.map((stock) => (
                  <div
                    key={stock.id}
                    className="stock-card"
                    onClick={() => fetchQuote(stock.symbol)}
                  >
                    <div className="stock-symbol">{stock.symbol}</div>
                    <div className="stock-name">{stock.name}</div>
                    <div className="stock-sector">{stock.sector || '未分類'}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-data">未找到股票</div>
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
                  <span className="price">${selectedStock.price}</span>
                  <span className={`change ${selectedStock.change_percent >= 0 ? 'up' : 'down'}`}>
                    {selectedStock.change_percent >= 0 ? '+' : ''}{selectedStock.change_percent}%
                  </span>
                </div>
                <div className="quote-details">
                  <div className="detail-item">
                    <span className="label">開盤:</span>
                    <span className="value">${selectedStock.open}</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">最高:</span>
                    <span className="value">${selectedStock.high}</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">最低:</span>
                    <span className="value">${selectedStock.low}</span>
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
      </footer>
    </div>
  )
}

export default App
