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

interface FilterParams {
  nameContains?: string
  minChangePct?: number
  maxChangePct?: number
  minPeRatio?: number
  maxPeRatio?: number
  minPbRatio?: number
  maxPbRatio?: number
  minEps?: number
  minNetIncome?: number
  maxNetIncome?: number
  closeAtHigh?: boolean
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

type QuickFilterKey =
  | 'limit_up' | 'near_limit' | 'rising' | 'falling' | 'limit_down'
  | 'low_pe' | 'low_pb' | 'high_eps'
  | 'profitable' | 'losing'
  | 'etf' | 'close_at_high'
  | 'revenue_growth'

interface QuickFilterDef {
  key: QuickFilterKey
  label: string
  emoji: string
  tooltip: string
  params: FilterParams
  disabled?: boolean
}

const FILTER_GROUPS: { label: string; filters: QuickFilterDef[] }[] = [
  {
    label: '漲跌',
    filters: [
      { key: 'limit_up',    label: '漲停板',   emoji: '🚀', tooltip: '漲幅 ≥ 9.5%',              params: { minChangePct: 9.5 } },
      { key: 'near_limit',  label: '接近漲停', emoji: '🔥', tooltip: '漲幅 8% ～ 9.49%',          params: { minChangePct: 8, maxChangePct: 9.49 } },
      { key: 'rising',      label: '今日上漲', emoji: '📈', tooltip: '漲跌幅 > 0%',              params: { minChangePct: 0.01 } },
      { key: 'falling',     label: '今日下跌', emoji: '📉', tooltip: '漲跌幅 < 0%',              params: { maxChangePct: -0.01 } },
      { key: 'limit_down',  label: '跌停板',   emoji: '🔻', tooltip: '漲幅 ≤ −9.5%',             params: { maxChangePct: -9.5 } },
    ],
  },
  {
    label: '估值',
    filters: [
      { key: 'low_pe',   label: '低本益比', emoji: '💰', tooltip: '本益比 1 ～ 15',   params: { minPeRatio: 1, maxPeRatio: 15 } },
      { key: 'low_pb',   label: '低淨值比', emoji: '🏦', tooltip: '淨值比 0.01 ～ 1', params: { minPbRatio: 0.01, maxPbRatio: 1 } },
      { key: 'high_eps', label: '高 EPS',   emoji: '⭐', tooltip: 'EPS ≥ 5 元',       params: { minEps: 5 } },
    ],
  },
  {
    label: '獲利',
    filters: [
      { key: 'profitable', label: '獲利股',   emoji: '✅', tooltip: '淨利 > 0',            params: { minNetIncome: 1 } },
      { key: 'losing',     label: '虧損股',   emoji: '❌', tooltip: '淨利 < 0',            params: { maxNetIncome: -1 } },
      { key: 'revenue_growth', label: '營收成長 20%+', emoji: '📊', tooltip: '需要歷史營收資料（即將推出）', params: {}, disabled: true },
    ],
  },
  {
    label: '其他',
    filters: [
      { key: 'etf',          label: 'ETF',      emoji: '📦', tooltip: '名稱含 "ETF"',       params: { nameContains: 'ETF' } },
      { key: 'close_at_high', label: '收在最高', emoji: '🎯', tooltip: '收盤價 = 當日最高價', params: { closeAtHigh: true } },
    ],
  },
]

const ALL_FILTERS = FILTER_GROUPS.flatMap(g => g.filters)

function buildUrl(base: string, fp: FilterParams): string {
  let url = base
  if (fp.nameContains)        url += `&name_contains=${encodeURIComponent(fp.nameContains)}`
  if (fp.minChangePct != null) url += `&min_change_percent=${fp.minChangePct}`
  if (fp.maxChangePct != null) url += `&max_change_percent=${fp.maxChangePct}`
  if (fp.minPeRatio != null)   url += `&min_pe_ratio=${fp.minPeRatio}`
  if (fp.maxPeRatio != null)   url += `&max_pe_ratio=${fp.maxPeRatio}`
  if (fp.minPbRatio != null)   url += `&min_pb_ratio=${fp.minPbRatio}`
  if (fp.maxPbRatio != null)   url += `&max_pb_ratio=${fp.maxPbRatio}`
  if (fp.minEps != null)       url += `&min_eps=${fp.minEps}`
  if (fp.minNetIncome != null) url += `&min_net_income=${fp.minNetIncome}`
  if (fp.maxNetIncome != null) url += `&max_net_income=${fp.maxNetIncome}`
  if (fp.closeAtHigh)          url += `&close_at_high=true`
  return url
}

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
  const [activeFilter, setActiveFilter] = useState<QuickFilterKey | ''>('')
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const currentFilterParams = (): FilterParams => {
    if (!activeFilter) return {}
    return ALL_FILTERS.find(f => f.key === activeFilter)?.params || {}
  }

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
    fp: FilterParams = {},
  ) => {
    setLoading(true)
    setError(null)
    try {
      let url: string
      if (keyword) {
        url = `${API_URL}/v1/stocks/search/${encodeURIComponent(keyword)}`
      } else {
        const skip = (p - 1) * PAGE_SIZE
        let base = `${API_URL}/v1/stocks?skip=${skip}&limit=${PAGE_SIZE}`
        if (market) base += `&market_type=${encodeURIComponent(market)}`
        if (sector) base += `&sector=${encodeURIComponent(sector)}`
        url = buildUrl(base, fp)
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
    setActiveFilter('')
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
    fetchStocks(1, '', market, sectorFilter, currentFilterParams())
  }

  const handleSectorFilter = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const sector = e.target.value
    setSectorFilter(sector)
    setPage(1)
    setSearchTerm('')
    setSortKey('')
    fetchStocks(1, '', marketFilter, sector, currentFilterParams())
  }

  const handlePage = (newPage: number) => {
    setPage(newPage)
    fetchStocks(newPage, '', marketFilter, sectorFilter, currentFilterParams())
    window.scrollTo(0, 0)
  }

  const handleQuickFilter = (key: QuickFilterKey) => {
    const def = ALL_FILTERS.find(f => f.key === key)
    if (!def || def.disabled) return
    const next = activeFilter === key ? '' : key
    setActiveFilter(next)
    setPage(1)
    setSearchTerm('')
    setSortKey('')
    const fp = next ? (def.params) : {}
    fetchStocks(1, '', marketFilter, sectorFilter, fp)
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

  const qBtnStyle = (def: QuickFilterDef) => {
    const active = activeFilter === def.key
    const disabled = !!def.disabled
    return {
      padding: '4px 11px',
      background: active
        ? 'rgba(124,58,237,0.85)'
        : disabled
          ? 'rgba(255,255,255,0.03)'
          : 'rgba(255,255,255,0.06)',
      color: active ? '#fff' : disabled ? '#444' : '#bbb',
      border: `1px solid ${active ? 'rgba(124,58,237,0.6)' : disabled ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.1)'}`,
      borderRadius: '5px',
      cursor: disabled ? 'not-allowed' : 'pointer',
      fontSize: '0.82rem',
      opacity: disabled ? 0.5 : 1,
      whiteSpace: 'nowrap' as const,
      transition: 'background 0.15s',
    }
  }

  const pageBtnStyle = (disabled: boolean) => ({
    padding: '6px 12px',
    background: 'rgba(255,255,255,0.1)',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.4 : 1,
  })

  const activeFilterDef = ALL_FILTERS.find(f => f.key === activeFilter)

  return (
    <div className="app">
      <header className="app-header">
        <h1>🚀 台股觀測站</h1>
        <p>台灣股票市場監測和投資組合管理平台</p>
      </header>

      <main className="app-main">
        {/* 搜尋列與市場篩選 */}
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
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
            <span style={{ color: '#666', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>資料日期：{tradeDate}</span>
          )}
        </div>

        {/* 快捷篩選 — 分組 */}
        <div style={{ marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {FILTER_GROUPS.map(group => (
            <div key={group.label} style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span style={{ color: '#555', fontSize: '0.75rem', minWidth: '30px', textAlign: 'right', flexShrink: 0 }}>
                {group.label}
              </span>
              <div style={{ width: '1px', height: '14px', background: 'rgba(255,255,255,0.1)', flexShrink: 0 }} />
              {group.filters.map(def => (
                <button
                  key={def.key}
                  title={def.tooltip}
                  style={qBtnStyle(def)}
                  onClick={() => handleQuickFilter(def.key)}
                >
                  {def.emoji} {def.label}
                  {def.disabled && <span style={{ marginLeft: '3px', fontSize: '0.7rem', opacity: 0.6 }}>（即將推出）</span>}
                </button>
              ))}
            </div>
          ))}

          {/* 已套用篩選提示 */}
          {activeFilterDef && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
              <span style={{ fontSize: '0.8rem', color: '#a78bfa' }}>
                已篩選：{activeFilterDef.emoji} {activeFilterDef.label}（{activeFilterDef.tooltip}）
              </span>
              <button
                onClick={() => handleQuickFilter(activeFilter as QuickFilterKey)}
                style={{ padding: '2px 8px', background: 'transparent', color: '#666', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem' }}
              >
                ✕ 清除
              </button>
            </div>
          )}
        </div>

        {error && (
          <div style={{ color: '#f44336', padding: '0.75rem 1rem', marginBottom: '1rem', background: 'rgba(244,67,54,0.08)', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            ⚠️ {error}
            <button onClick={() => fetchStocks(page, '', marketFilter, sectorFilter, currentFilterParams())}
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
                        <div>
                          {searchTerm
                            ? `找不到符合「${searchTerm}」的股票`
                            : activeFilterDef
                              ? `目前沒有符合「${activeFilterDef.label}」條件的股票`
                              : '目前沒有資料'}
                        </div>
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
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#555', fontSize: '0.82rem', whiteSpace: 'nowrap' }}>{fmtDate(s.trade_date)}</td>
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
                ℹ️ 排序僅作用於本頁 {sortedStocks.length} 筆
              </div>
            )}

            {!searchTerm && totalPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem', marginTop: '1.5rem' }}>
                <button onClick={() => handlePage(1)} disabled={page === 1} style={pageBtnStyle(page === 1)}>«</button>
                <button onClick={() => handlePage(page - 1)} disabled={page === 1} style={pageBtnStyle(page === 1)}>‹</button>
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
                <button onClick={() => handlePage(page + 1)} disabled={page === totalPages} style={pageBtnStyle(page === totalPages)}>›</button>
                <button onClick={() => handlePage(totalPages)} disabled={page === totalPages} style={pageBtnStyle(page === totalPages)}>»</button>
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
