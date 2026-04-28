import React, { useState, useEffect, useCallback, useRef } from 'react'
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
  revenue?: number | string
  net_income?: number | string
  trade_date?: string
}

const API_URL = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000/api'

const PAGE_SIZE = 50

const COLUMNS = [
  { label: '股號', key: 'symbol' },
  { label: '股名', key: 'name' },
  { label: '市場', key: 'market_type' },
  { label: '產業', key: 'sector' },
  { label: '日期', key: 'trade_date' },
  { label: '收盤', key: 'close_price' },
  { label: '漲跌', key: 'change_amount' },
  { label: '漲跌幅%', key: 'change_percent' },
  { label: '開盤', key: 'open_price' },
  { label: '最高', key: 'high_price' },
  { label: '最低', key: 'low_price' },
  { label: '成交量(千)', key: 'volume' },
  { label: 'EPS', key: 'eps' },
  { label: '本益比', key: 'pe_ratio' },
  { label: '淨值比', key: 'pb_ratio' },
  { label: '營收(千)', key: 'revenue' },
  { label: '淨利(千)', key: 'net_income' },
]

// 快捷篩選定義
type QuickFilter = 'etf' | 'limit_up' | 'revenue_growth'
const QUICK_FILTERS: { key: QuickFilter; label: string; emoji: string; tooltip: string }[] = [
  { key: 'etf', label: 'ETF', emoji: '📦', tooltip: '篩選 ETF 商品（名稱含 ETF）' },
  { key: 'limit_up', label: '漲停板', emoji: '🚀', tooltip: '篩選漲幅 ≥ 9.5% 的漲停股' },
  { key: 'revenue_growth', label: '營收成長 20%+', emoji: '📈', tooltip: '需要歷史營收資料（尚未支援）' },
]

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
  const [sortKey, setSortKey] = useState<string>('')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [tradeDate, setTradeDate] = useState<string>('')
  const [quickFilter, setQuickFilter] = useState<QuickFilter | ''>('')
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    fetch(`${API_URL}/v1/stocks/sectors`)
      .then(r => r.json())
      .then(d => setSectors(d.sectors || []))
      .catch(() => {})
  }, [])

  const fetchStocks = useCallback(async (
    p: number,
    keyword?: string,
    market?: string,
    sector?: string,
    nameContains?: string,
    minChangePct?: number,
  ) => {
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
        if (nameContains) url += `&name_contains=${encodeURIComponent(nameContains)}`
        if (minChangePct !== undefined) url += `&min_change_percent=${minChangePct}`
      }
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const list = data.stocks || []
      setStocks(list)
      setTotal(keyword ? list.length : (data.total || 0))
      if (list.length > 0 && list[0].trade_date) setTradeDate(list[0].trade_date)
    } catch (e) {
      setError(e instanceof Error ? e.message : '載入失敗')
    }
    setLoading(false)
  }, [])

  useEffect(() => { fetchStocks(1) }, [])

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setSearchTerm(val)
    setPage(1)
    setSortKey('')
    setQuickFilter('')
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => {
      if (val.length === 0) fetchStocks(1, '', marketFilter, sectorFilter)
      else fetchStocks(1, val)
    }, 300)
  }

  const handleMarketFilter = (market: string) => {
    setMarketFilter(market)
    setPage(1)
    setSearchTerm('')
    setSortKey('')
    const nameContains = quickFilter === 'etf' ? 'ETF' : undefined
    const minChangePct = quickFilter === 'limit_up' ? 9.5 : undefined
    fetchStocks(1, '', market, sectorFilter, nameContains, minChangePct)
  }

  const handleSectorFilter = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const sector = e.target.value
    setSectorFilter(sector)
    setPage(1)
    setSearchTerm('')
    setSortKey('')
    const nameContains = quickFilter === 'etf' ? 'ETF' : undefined
    const minChangePct = quickFilter === 'limit_up' ? 9.5 : undefined
    fetchStocks(1, '', marketFilter, sector, nameContains, minChangePct)
  }

  const handlePage = (newPage: number) => {
    setPage(newPage)
    const nameContains = quickFilter === 'etf' ? 'ETF' : undefined
    const minChangePct = quickFilter === 'limit_up' ? 9.5 : undefined
    fetchStocks(newPage, searchTerm || '', marketFilter, sectorFilter, nameContains, minChangePct)
    window.scrollTo(0, 0)
  }

  const handleQuickFilter = (filter: QuickFilter) => {
    if (filter === 'revenue_growth') return // 尚未支援
    const next = quickFilter === filter ? '' : filter
    setQuickFilter(next)
    setPage(1)
    setSearchTerm('')
    setSortKey('')
    const nameContains = next === 'etf' ? 'ETF' : undefined
    const minChangePct = next === 'limit_up' ? 9.5 : undefined
    fetchStocks(1, '', marketFilter, sectorFilter, nameContains, minChangePct)
  }

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
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

  const fmtThousands = (n?: number | string) => {
    if (n == null) return '--'
    const num = typeof n === 'string' ? parseFloat(n) : Number(n)
    if (isNaN(num)) return '--'
    return Math.round(num / 1000).toLocaleString()
  }

  // 格式化日期：2024-01-15 → 01/15
  const fmtDate = (d?: string) => {
    if (!d) return '--'
    const parts = d.split('-')
    if (parts.length === 3) return `${parts[1]}/${parts[2]}`
    return d
  }

  const changeColor = (n?: number | string) => {
    if (n == null) return '#aaa'
    const num = typeof n === 'string' ? parseFloat(n) : n
    if (num > 0) return '#ff4d4d'
    if (num < 0) return '#33cc66'
    return '#aaa'
  }

  const netIncomeColor = (n?: number | string) => {
    if (n == null) return '#aaa'
    const num = typeof n === 'string' ? parseFloat(n) : Number(n)
    if (isNaN(num)) return '#aaa'
    if (num > 0) return '#51cf66'
    if (num < 0) return '#ff6b6b'
    return '#aaa'
  }

  const sortedStocks = [...stocks].sort((a, b) => {
    if (!sortKey) return 0
    const va = a[sortKey as keyof Stock]
    const vb = b[sortKey as keyof Stock]
    if (va == null && vb == null) return 0
    if (va == null) return 1
    if (vb == null) return -1
    const na = typeof va === 'string' ? parseFloat(va) : Number(va)
    const nb = typeof vb === 'string' ? parseFloat(vb) : Number(vb)
    if (!isNaN(na) && !isNaN(nb)) return sortDir === 'asc' ? na - nb : nb - na
    return sortDir === 'asc'
      ? String(va).localeCompare(String(vb))
      : String(vb).localeCompare(String(va))
  })

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const btnStyle = (active: boolean) => ({
    padding: '6px 14px',
    background: active ? '#f90' : 'rgba(255,255,255,0.08)',
    color: active ? '#000' : '#ccc',
    border: 'none', borderRadius: '6px', cursor: 'pointer',
    fontWeight: active ? 700 : 400, fontSize: '0.85rem',
  })

  const quickBtnStyle = (key: QuickFilter, active: boolean) => {
    const disabled = key === 'revenue_growth'
    return {
      padding: '6px 14px',
      background: active ? '#7c3aed' : disabled ? 'rgba(255,255,255,0.04)' : 'rgba(124,58,237,0.15)',
      color: active ? '#fff' : disabled ? '#555' : '#a78bfa',
      border: active ? 'none' : `1px solid ${disabled ? 'rgba(255,255,255,0.07)' : 'rgba(124,58,237,0.35)'}`,
      borderRadius: '6px',
      cursor: disabled ? 'not-allowed' : 'pointer',
      fontWeight: active ? 700 : 400,
      fontSize: '0.85rem',
      opacity: disabled ? 0.5 : 1,
    } as React.CSSProperties
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>🚀 台股觀測站</h1>
        <p>台灣股票市場監測和投資組合管理平台</p>
      </header>

      <main className="app-main">
        {/* 搜尋列與市場篩選 */}
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '0.6rem', flexWrap: 'wrap' }}>
          <input
            type="text" className="search-input"
            placeholder="搜尋股票代碼或名稱..."
            value={searchTerm} onChange={handleSearch}
            style={{ flex: 1, minWidth: '200px' }}
          />
          <div style={{ display: 'flex', gap: '0.4rem' }}>
            <button style={btnStyle(marketFilter === '')} onClick={() => handleMarketFilter('')}>全部</button>
            <button style={btnStyle(marketFilter === '上市')} onClick={() => handleMarketFilter('上市')}>上市</button>
            <button style={btnStyle(marketFilter === '上櫃')} onClick={() => handleMarketFilter('上櫃')}>上櫃</button>
          </div>
          <select value={sectorFilter} onChange={handleSectorFilter}
            style={{ padding: '6px 10px', background: 'rgba(255,255,255,0.08)', color: '#ccc', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '6px', fontSize: '0.85rem' }}>
            <option value="">所有產業</option>
            {sectors.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <span style={{ color: '#aaa', fontSize: '0.9rem', whiteSpace: 'nowrap' }}>共 {total} 筆</span>
          {tradeDate && (
            <span style={{ color: '#666', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>
              資料日期：{tradeDate}
            </span>
          )}
        </div>

        {/* 快捷篩選按鈕列 */}
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <span style={{ color: '#666', fontSize: '0.8rem', whiteSpace: 'nowrap' }}>快捷篩選：</span>
          {QUICK_FILTERS.map(({ key, label, emoji, tooltip }) => (
            <button
              key={key}
              title={tooltip}
              style={quickBtnStyle(key, quickFilter === key)}
              onClick={() => handleQuickFilter(key)}
            >
              {emoji} {label}
              {key === 'revenue_growth' && (
                <span style={{ marginLeft: '4px', fontSize: '0.7rem', opacity: 0.7 }}>（即將推出）</span>
              )}
            </button>
          ))}
          {quickFilter && (
            <button
              onClick={() => handleQuickFilter(quickFilter as QuickFilter)}
              style={{ padding: '4px 10px', background: 'transparent', color: '#888', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.78rem' }}
            >
              ✕ 清除篩選
            </button>
          )}
        </div>

        {error && (
          <div style={{ color: '#f44336', padding: '0.75rem 1rem', marginBottom: '1rem', background: 'rgba(244,67,54,0.08)', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            ⚠️ {error}
            <button onClick={() => fetchStocks(page, searchTerm || '', marketFilter, sectorFilter)}
              style={{ marginLeft: 'auto', padding: '4px 10px', background: 'rgba(244,67,54,0.2)', color: '#f44336', border: '1px solid rgba(244,67,54,0.4)', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}>
              重試
            </button>
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#aaa' }}>⏳ 載入中...</div>
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem', background: 'rgba(255,255,255,0.03)', borderRadius: '8px', overflow: 'hidden' }}>
                <thead>
                  <tr style={{ background: 'rgba(255,255,255,0.08)' }}>
                    {COLUMNS.map(({ label, key }) => (
                      <th key={key} onClick={() => handleSort(key)}
                        title={sortKey === key ? '排序僅限本頁資料' : '點擊排序（僅限本頁）'}
                        style={{ padding: '10px 12px', textAlign: 'right', whiteSpace: 'nowrap', fontWeight: 500, cursor: 'pointer', userSelect: 'none', color: sortKey === key ? '#f90' : '#ccc' }}>
                        {label} {sortKey === key ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedStocks.length === 0 && (
                    <tr>
                      <td colSpan={COLUMNS.length} style={{ padding: '3rem', textAlign: 'center', color: '#666' }}>
                        <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🔍</div>
                        <div>{searchTerm ? `找不到符合「${searchTerm}」的股票` : quickFilter ? '目前沒有符合條件的股票' : '目前沒有資料'}</div>
                      </td>
                    </tr>
                  )}
                  {sortedStocks.map((s, i) => (
                    <tr key={s.symbol} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <td style={{ padding: '8px 12px', color: '#f90', fontWeight: 600 }}>{s.symbol}</td>
                      <td style={{ padding: '8px 12px', color: '#fff', whiteSpace: 'nowrap' }}>{s.name}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                        <span style={{ background: s.market_type === '上市' ? 'rgba(100,149,237,0.2)' : 'rgba(144,238,144,0.2)', color: s.market_type === '上市' ? '#6495ed' : '#90ee90', padding: '2px 6px', borderRadius: '4px', fontSize: '0.8rem' }}>
                          {s.market_type || '--'}
                        </span>
                      </td>
                      <td style={{ padding: '8px 12px', color: '#aaa', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>{s.sector || '--'}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#666', fontSize: '0.82rem', whiteSpace: 'nowrap' }}>{fmtDate(s.trade_date)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: changeColor(s.change_amount), fontWeight: 600 }}>{fmt(s.close_price)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: changeColor(s.change_amount) }}>{fmtChange(s.change_amount)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: changeColor(s.change_percent) }}>{s.change_percent != null ? fmtChange(s.change_percent) + '%' : '--'}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ccc' }}>{fmt(s.open_price)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ff6b6b' }}>{fmt(s.high_price)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#51cf66' }}>{fmt(s.low_price)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#aaa' }}>{fmtThousands(s.volume)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ccc' }}>{fmt(s.eps)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ccc' }}>{fmt(s.pe_ratio)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ccc' }}>{fmt(s.pb_ratio)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#ccc' }}>{fmtThousands(s.revenue)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: netIncomeColor(s.net_income) }}>{fmtThousands(s.net_income)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {sortKey && sortedStocks.length > 0 && (
              <div style={{ textAlign: 'center', marginTop: '0.5rem', color: '#666', fontSize: '0.8rem' }}>
                ℹ️ 排序僅作用於本頁 {sortedStocks.length} 筆，完整排序請至下一版本支援
              </div>
            )}

            {!searchTerm && totalPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem', marginTop: '1.5rem' }}>
                <button onClick={() => handlePage(1)} disabled={page === 1} style={{ padding: '6px 12px', background: 'rgba(255,255,255,0.1)', color: '#fff', border: 'none', borderRadius: '4px', cursor: page === 1 ? 'not-allowed' : 'pointer', opacity: page === 1 ? 0.4 : 1 }}>«</button>
                <button onClick={() => handlePage(page - 1)} disabled={page === 1} style={{ padding: '6px 12px', background: 'rgba(255,255,255,0.1)', color: '#fff', border: 'none', borderRadius: '4px', cursor: page === 1 ? 'not-allowed' : 'pointer', opacity: page === 1 ? 0.4 : 1 }}>‹</button>
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
                <button onClick={() => handlePage(page + 1)} disabled={page === totalPages} style={{ padding: '6px 12px', background: 'rgba(255,255,255,0.1)', color: '#fff', border: 'none', borderRadius: '4px', cursor: page === totalPages ? 'not-allowed' : 'pointer', opacity: page === totalPages ? 0.4 : 1 }}>›</button>
                <button onClick={() => handlePage(totalPages)} disabled={page === totalPages} style={{ padding: '6px 12px', background: 'rgba(255,255,255,0.1)', color: '#fff', border: 'none', borderRadius: '4px', cursor: page === totalPages ? 'not-allowed' : 'pointer', opacity: page === totalPages ? 0.4 : 1 }}>»</button>
                <span style={{ color: '#aaa', fontSize: '0.85rem' }}>第 {page} / {totalPages} 頁</span>
              </div>
            )}
          </>
        )}
      </main>

      <footer className="app-footer">
        <p>© {new Date().getFullYear()} 台股觀測站 | 版本 1.0.0</p>
      </footer>
    </div>
  )
}

export default App
