import React, { useState, useEffect, useCallback } from 'react'
import './index.css'

interface Stock {
  id?: string
  symbol: string
  name: string
  sector?: string
  market_type?: string
  close_price?: number | string
  open_price?: number | string
  high_price?: number | string
  low_price?: number | string
  change_amount?: number | string
  change_percent?: number | string
  volume?: number
  eps?: number | string
  pe_ratio?: number | string
  pb_ratio?: number | string
}

const API_URL = window.location.hostname.includes('zeabur.app')
  ? 'https://tw-stock-observer-01-b.zeabur.app/api'
  : 'http://localhost:8000/api'

const PAGE_SIZE = 50

function App() {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [marketFilter, setMarketFilter] = useState('')
  const [sectorFilter, setSectorFilter] = useState('')
  const [sectors, setSectors] = useState<string[]>([])

  // 載入產業列表
  useEffect(() => {
    fetch(`${API_URL}/v1/stocks/sectors`)
      .then(r => r.json())
      .then(d => setSectors(d.sectors || []))
      .catch(() => {})
  }, [])

  const fetchStocks = useCallback(async (p: number, keyword?: string, market?: string, sector?: string) => {
    setLoading(true)
    setError(null)
    try {
      let url: string
      if (keyword) {
        url = `${API_URL}/v1/stocks/search/${encodeURIComponent(keyword)}`
      } else {
        const skip = (p - 1) * PAGE_SIZE
        url = `${API_URL}/v1/stocks?skip=${skip}&limit=${PAGE_SIZE}`
        if (market) url += `&market_type=${encodeURIComponent(market)}`
        if (sector) url += `&sector=${encodeURIComponent(sector)}`
      }
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const list = data.stocks || []
      setStocks(list)
      setTotal(keyword ? list.length : (data.total || 0))
    } catch (e) {
      setError(e instanceof Error ? e.message : '載入失敗')
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    fetchStocks(1, '', marketFilter, sectorFilter)
  }, [])

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setSearchTerm(val)
    setPage(1)
    if (val.length === 0) fetchStocks(1, '', marketFilter, sectorFilter)
    else fetchStocks(1, val)
  }

  const handleMarketFilter = (market: string) => {
    setMarketFilter(market)
    setPage(1)
    setSearchTerm('')
    fetchStocks(1, '', market, sectorFilter)
  }

  const handleSectorFilter = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const sector = e.target.value
    setSectorFilter(sector)
    setPage(1)
    setSearchTerm('')
    fetchStocks(1, '', marketFilter, sector)
  }

  const handlePage = (newPage: number) => {
    setPage(newPage)
    fetchStocks(newPage, searchTerm || '', marketFilter, sectorFilter)
    window.scrollTo(0, 0)
  }

  const fmt = (n?: number | string, digits = 2) => {
    if (n == null) return '--'
    const num = typeof n === 'string' ? parseFloat(n) : n
    return isNaN(num) ? '--' : num.toFixed(digits)
  }

  const fmtChange = (n?: number | string) => {
    if (n == null) return '--'
    const num = typeof n === 'string' ? parseFloat(n) : n
    if (isNaN(num)) return '--'
    return (num > 0 ? '+' : '') + num.toFixed(2)
  }

  const changeColor = (n?: number | string) => {
    if (n == null) return '#aaa'
    const num = typeof n === 'string' ? parseFloat(n) : n
    if (num > 0) return '#ff4d4d'
    if (num < 0) return '#33cc66'
    return '#aaa'
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const btnStyle = (active: boolean) => ({
    padding: '6px 14px',
    background: active ? '#f90' : 'rgba(255,255,255,0.08)',
    color: active ? '#000' : '#ccc',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: active ? 700 : 400,
    fontSize: '0.85rem',
    transition: 'all 0.2s',
  })

  return (
    <div className="app">
      <header className="app-header">
        <h1>🚀 台股觀測站</h1>
        <p>台灣股票市場監測和投資組合管理平台</p>
      </header>

      <main className="app-main">
        {/* 搜尋與篩選列 */}
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <input
            type="text"
            className="search-input"
            placeholder="搜尋股票代碼或名稱..."
            value={searchTerm}
            onChange={handleSearch}
            style={{ flex: 1, minWidth: '200px' }}
          />

          {/* 市場篩選 */}
          <div style={{ display: 'flex', gap: '0.4rem' }}>
            <button style={btnStyle(marketFilter === '')} onClick={() => handleMarketFilter('')}>全部</button>
            <button style={btnStyle(marketFilter === '上市')} onClick={() => handleMarketFilter('上市')}>上市</button>
            <button style={btnStyle(marketFilter === '上櫃')} onClick={() => handleMarketFilter('上櫃')}>上櫃</button>
          </div>

          {/* 產業篩選 */}
          <select
            value={sectorFilter}
            onChange={handleSectorFilter}
            style={{
              padding: '6px 10px',
              background: 'rgba(255,255,255,0.08)',
              color: '#ccc',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: '6px',
              fontSize: '0.85rem',
              cursor: 'pointer',
            }}
          >
            <option value="">所有產業</option>
            {sectors.map(s => <option key={s} value={s}>{s}</option>)}
          </select>

          <span style={{ color: '#aaa', fontSize: '0.9rem', whiteSpace: 'nowrap' }}>
            共 {total} 筆
          </span>
        </div>

        {error && (
          <div style={{ color: '#f44336', padding: '0.5rem', marginBottom: '1rem' }}>⚠️ {error}</div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#aaa' }}>⏳ 載入中...</div>
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table style={{
                width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem',
                background: 'rgba(255,255,255,0.03)', borderRadius: '8px', overflow: 'hidden',
              }}>
                <thead>
                  <tr style={{ background: 'rgba(255,255,255,0.08)', color: '#ccc' }}>
                    {['股號','股名','市場','產業','收盤','漲跌','漲跌幅%','開盤','最高','最低','成交量(千)','EPS','本益比','淨值比'].map(h => (
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
                      <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                        <span style={{
                          background: s.market_type === '上市' ? 'rgba(100,149,237,0.2)' : 'rgba(144,238,144,0.2)',
                          color: s.market_type === '上市' ? '#6495ed' : '#90ee90',
                          padding: '2px 6px', borderRadius: '4px', fontSize: '0.8rem'
                        }}>{s.market_type || '--'}</span>
                      </td>
                      <td style={{ padding: '8px 12px', color: '#aaa', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>{s.sector || '--'}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: changeColor(s.change_amount), fontWeight: 600 }}>
                        {fmt(s.close_price)}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: changeColor(s.change_amount) }}>
                        {fmtChange(s.change_amount)}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: changeColor(s.change_percent) }}>
                        {s.change_percent != null ? fmtChange(s.change_percent) + '%' : '--'}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ccc' }}>{fmt(s.open_price)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ff6b6b' }}>{fmt(s.high_price)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#51cf66' }}>{fmt(s.low_price)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#aaa' }}>
                        {s.volume != null ? Math.round(Number(s.volume) / 1000).toLocaleString() : '--'}
                      </td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ccc' }}>{fmt(s.eps)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ccc' }}>{fmt(s.pe_ratio)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ccc' }}>{fmt(s.pb_ratio)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {!searchTerm && totalPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem', marginTop: '1.5rem' }}>
                <button onClick={() => handlePage(1)} disabled={page === 1}
                  style={{ padding: '6px 12px', background: 'rgba(255,255,255,0.1)', color: '#fff', border: 'none', borderRadius: '4px', cursor: page === 1 ? 'not-allowed' : 'pointer', opacity: page === 1 ? 0.4 : 1 }}>«</button>
                <button onClick={() => handlePage(page - 1)} disabled={page === 1}
                  style={{ padding: '6px 12px', background: 'rgba(255,255,255,0.1)', color: '#fff', border: 'none', borderRadius: '4px', cursor: page === 1 ? 'not-allowed' : 'pointer', opacity: page === 1 ? 0.4 : 1 }}>‹</button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let start = Math.max(1, page - 2)
                  if (start + 4 > totalPages) start = Math.max(1, totalPages - 4)
                  const p = start + i
                  if (p > totalPages) return null
                  return (
                    <button key={p} onClick={() => handlePage(p)}
                      style={{ padding: '6px 12px', background: p === page ? '#f90' : 'rgba(255,255,255,0.1)', color: p === page ? '#000' : '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: p === page ? 700 : 400 }}>
                      {p}
                    </button>
                  )
                })}
                <button onClick={() => handlePage(page + 1)} disabled={page === totalPages}
                  style={{ padding: '6px 12px', background: 'rgba(255,255,255,0.1)', color: '#fff', border: 'none', borderRadius: '4px', cursor: page === totalPages ? 'not-allowed' : 'pointer', opacity: page === totalPages ? 0.4 : 1 }}>›</button>
                <button onClick={() => handlePage(totalPages)} disabled={page === totalPages}
                  style={{ padding: '6px 12px', background: 'rgba(255,255,255,0.1)', color: '#fff', border: 'none', borderRadius: '4px', cursor: page === totalPages ? 'not-allowed' : 'pointer', opacity: page === totalPages ? 0.4 : 1 }}>»</button>
                <span style={{ color: '#aaa', fontSize: '0.85rem' }}>第 {page} / {totalPages} 頁</span>
              </div>
            )}
          </>
        )}
      </main>

      <footer className="app-footer">
        <p>© 2024 台股觀測站 | 版本 1.0.0</p>
      </footer>
    </div>
  )
}

export default App