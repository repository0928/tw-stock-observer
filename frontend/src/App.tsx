import React, { useState, useEffect } from 'react'
import './index.css'

interface Stock {
  id?: string
  symbol: string
  name: string
  sector?: string
  market_type?: string
  close_price?: number
  open_price?: number
  high_price?: number
  low_price?: number
  change_amount?: number
  change_percent?: number
  volume?: number
  eps?: number
  pe_ratio?: number
  pb_ratio?: number
}

function App() {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')

  const API_URL = window.location.hostname.includes('zeabur.app')
    ? 'https://tw-stock-observer-01-b.zeabur.app/api'
    : 'http://localhost:8000/api'

  const fetchStocks = async (keyword?: string) => {
    setLoading(true)
    setError(null)
    try {
      const url = keyword
        ? `${API_URL}/v1/stocks/search/${encodeURIComponent(keyword)}`
        : `${API_URL}/v1/stocks?limit=500`
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const list = data.stocks || []
      setStocks(list)
    } catch (e) {
      setError(e instanceof Error ? e.message : '載入失敗')
    }
    setLoading(false)
  }

  useEffect(() => { fetchStocks() }, [])

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setSearchTerm(val)
    if (val.length === 0) fetchStocks()
    else if (val.length >= 1) fetchStocks(val)
  }

const fmt = (n?: number | string, digits = 2) => {
  if (n == null) return '--'
  const num = typeof n === 'string' ? parseFloat(n) : n
  return isNaN(num) ? '--' : num.toFixed(digits)
}
const changeColor = (n?: number | string) => {
  if (n == null) return '#aaa'
  const num = typeof n === 'string' ? parseFloat(n) : n
  if (num > 0) return '#ff4d4d'
  if (num < 0) return '#33cc66'
  return '#aaa'
}
  return (
    <div className="app">
      <header className="app-header">
        <h1>🚀 台股觀測站</h1>
        <p>台灣股票市場監測和投資組合管理平台</p>
      </header>

      <main className="app-main">
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginBottom: '1rem' }}>
          <input
            type="text"
            className="search-input"
            placeholder="搜尋股票代碼或名稱..."
            value={searchTerm}
            onChange={handleSearch}
            style={{ flex: 1 }}
          />
          <span style={{ color: '#aaa', fontSize: '0.9rem', whiteSpace: 'nowrap' }}>
            共 {stocks.length} 筆
          </span>
        </div>

        {error && (
          <div style={{ color: '#f44336', padding: '0.5rem', marginBottom: '1rem' }}>
            ⚠️ {error}
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#aaa' }}>⏳ 載入中...</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.9rem',
              background: 'rgba(255,255,255,0.03)',
              borderRadius: '8px',
              overflow: 'hidden',
            }}>
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.08)', color: '#ccc' }}>
                  {['股號','股名','市場','收盤','漲跌','漲跌幅%','開盤','最高','最低','成交量(千)','EPS','本益比','淨值比'].map(h => (
                    <th key={h} style={{ padding: '10px 12px', textAlign: 'right', whiteSpace: 'nowrap', fontWeight: 500 }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {stocks.map((s, i) => (
                  <tr key={s.symbol} style={{
                    background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)',
                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                  }}>
                    <td style={{ padding: '8px 12px', color: '#f90', fontWeight: 600 }}>{s.symbol}</td>
                    <td style={{ padding: '8px 12px', color: '#fff', whiteSpace: 'nowrap' }}>{s.name}</td>
                    <td style={{ padding: '8px 12px', color: '#aaa', textAlign: 'center' }}>
                      <span style={{
                        background: s.market_type === '上市' ? 'rgba(100,149,237,0.2)' : 'rgba(144,238,144,0.2)',
                        color: s.market_type === '上市' ? '#6495ed' : '#90ee90',
                        padding: '2px 6px', borderRadius: '4px', fontSize: '0.8rem'
                      }}>{s.market_type || '--'}</span>
                    </td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', color: changeColor(s.change_amount), fontWeight: 600 }}>
                      {fmt(s.close_price)}
                    </td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', color: changeColor(s.change_amount) }}>
                      {s.change_amount != null ? (s.change_amount > 0 ? '+' : '') + fmt(s.change_amount) : '--'}
                    </td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', color: changeColor(s.change_percent) }}>
                      {s.change_percent != null ? (s.change_percent > 0 ? '+' : '') + fmt(s.change_percent) + '%' : '--'}
                    </td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ccc' }}>{fmt(s.open_price)}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ff6b6b' }}>{fmt(s.high_price)}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', color: '#51cf66' }}>{fmt(s.low_price)}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', color: '#aaa' }}>
                      {s.volume != null ? Math.round(s.volume / 1000).toLocaleString() : '--'}
                    </td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ccc' }}>{fmt(s.eps)}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ccc' }}>{fmt(s.pe_ratio)}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ccc' }}>{fmt(s.pb_ratio)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>

      <footer className="app-footer">
        <p>© 2024 台股觀測站 | 版本 1.0.0</p>
      </footer>
    </div>
  )
}

export default App