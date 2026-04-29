import React, { useState, useEffect, useCallback, useRef } from 'react'
import './index.css'

// ─── 資料型別 ────────────────────────────────────────────────────────────────

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

// ─── 通用篩選條件型別 ─────────────────────────────────────────────────────────
//
// 新增任何欄位的篩選按鈕時，只需要在 FILTER_GROUPS 加一筆 QuickFilterDef，
// 並在後端 NUMERIC_FILTER_FIELDS 白名單加上欄位名稱。
// FilterCondition / buildUrl / mergeConditions 不需要再改。

type FilterOp = 'min' | 'max' | 'contains' | 'is_true'

interface FilterCondition {
  field: string   // 對應後端 Stock model 的欄位名稱
  op: FilterOp
  value: number | string | boolean
}

// 將條件陣列轉成 URL query string（接在 ? 之後）
function buildUrl(base: string, conditions: FilterCondition[]): string {
  let url = base
  for (const { field, op, value } of conditions) {
    if (op === 'min')      url += `&${field}_min=${value}`
    if (op === 'max')      url += `&${field}_max=${value}`
    if (op === 'contains') url += `&${field}_contains=${encodeURIComponent(String(value))}`
    if (op === 'is_true')  url += `&${field}=true`
  }
  return url
}

// 合併多組條件（AND 疊加，衝突時取最嚴格）
function mergeConditions(conditionSets: FilterCondition[][]): FilterCondition[] {
  // key = `${field}__${op}`，避免同欄位同方向的條件重複
  const map = new Map<string, FilterCondition>()

  for (const set of conditionSets) {
    for (const cond of set) {
      const key = `${cond.field}__${cond.op}`
      const existing = map.get(key)

      if (!existing) {
        map.set(key, { ...cond })
      } else {
        // min 衝突 → 取較大值（較嚴格的下限）
        if (cond.op === 'min' && typeof cond.value === 'number' && typeof existing.value === 'number') {
          existing.value = Math.max(existing.value, cond.value)
        }
        // max 衝突 → 取較小值（較嚴格的上限）
        else if (cond.op === 'max' && typeof cond.value === 'number' && typeof existing.value === 'number') {
          existing.value = Math.min(existing.value, cond.value)
        }
        // 其他 op 後者覆蓋前者
        else {
          map.set(key, { ...cond })
        }
      }
    }
  }

  return Array.from(map.values())
}

// ─── 快捷篩選定義 ─────────────────────────────────────────────────────────────

type QuickFilterKey =
  | 'limit_up' | 'near_limit' | 'rising' | 'falling' | 'limit_down'
  | 'low_pe' | 'low_pb' | 'high_eps'
  | 'profitable' | 'losing' | 'revenue_growth'
  | 'etf' | 'close_at_high'

interface QuickFilterDef {
  key: QuickFilterKey
  label: string
  emoji: string
  tooltip: string
  conditions: FilterCondition[]
  disabled?: boolean
}

// ★ 新增篩選按鈕時，只需在此加一筆 QuickFilterDef。
//   conditions 的 field 必須存在於後端 NUMERIC_FILTER_FIELDS 白名單中。
const FILTER_GROUPS: { label: string; filters: QuickFilterDef[] }[] = [
  {
    label: '漲跌',
    filters: [
      {
        key: 'limit_up', label: '漲停板', emoji: '🚀', tooltip: '漲幅 ≥ 9.5%',
        conditions: [{ field: 'change_percent', op: 'min', value: 9.5 }],
      },
      {
        key: 'near_limit', label: '接近漲停', emoji: '🔥', tooltip: '漲幅 8% ～ 9.49%',
        conditions: [
          { field: 'change_percent', op: 'min', value: 8 },
          { field: 'change_percent', op: 'max', value: 9.49 },
        ],
      },
      {
        key: 'rising', label: '今日上漲', emoji: '📈', tooltip: '漲跌幅 > 0%',
        conditions: [{ field: 'change_percent', op: 'min', value: 0.01 }],
      },
      {
        key: 'falling', label: '今日下跌', emoji: '📉', tooltip: '漲跌幅 < 0%',
        conditions: [{ field: 'change_percent', op: 'max', value: -0.01 }],
      },
      {
        key: 'limit_down', label: '跌停板', emoji: '🔻', tooltip: '漲幅 ≤ −9.5%',
        conditions: [{ field: 'change_percent', op: 'max', value: -9.5 }],
      },
    ],
  },
  {
    label: '估值',
    filters: [
      {
        key: 'low_pe', label: '低本益比', emoji: '💰', tooltip: '本益比 1 ～ 15',
        conditions: [
          { field: 'pe_ratio', op: 'min', value: 1 },
          { field: 'pe_ratio', op: 'max', value: 15 },
        ],
      },
      {
        key: 'low_pb', label: '低淨值比', emoji: '🏦', tooltip: '淨值比 0.01 ～ 1',
        conditions: [
          { field: 'pb_ratio', op: 'min', value: 0.01 },
          { field: 'pb_ratio', op: 'max', value: 1 },
        ],
      },
      {
        key: 'high_eps', label: '高 EPS', emoji: '⭐', tooltip: 'EPS ≥ 5 元',
        conditions: [{ field: 'eps', op: 'min', value: 5 }],
      },
    ],
  },
  {
    label: '獲利',
    filters: [
      {
        key: 'profitable', label: '獲利股', emoji: '✅', tooltip: '淨利 > 0',
        conditions: [{ field: 'net_income', op: 'min', value: 1 }],
      },
      {
        key: 'losing', label: '虧損股', emoji: '❌', tooltip: '淨利 < 0',
        conditions: [{ field: 'net_income', op: 'max', value: -1 }],
      },
      {
        key: 'revenue_growth', label: '營收成長 20%+', emoji: '📊',
        tooltip: '需要歷史營收資料（即將推出）',
        conditions: [],
        disabled: true,
      },
    ],
  },
  {
    label: '其他',
    filters: [
      {
        key: 'etf', label: 'ETF', emoji: '📦', tooltip: '名稱含 "ETF"',
        conditions: [{ field: 'name', op: 'contains', value: 'ETF' }],
      },
      {
        key: 'close_at_high', label: '收在最高', emoji: '🎯', tooltip: '收盤價 = 當日最高價',
        conditions: [{ field: 'close_at_high', op: 'is_true', value: true }],
      },
    ],
  },
]

const ALL_FILTERS: QuickFilterDef[] = FILTER_GROUPS.flatMap(g => g.filters)

// ─── 常數 ────────────────────────────────────────────────────────────────────

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

// ─── 主元件 ──────────────────────────────────────────────────────────────────

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
  // ── 多選篩選 state ──
  const [activeFilters, setActiveFilters] = useState<Set<QuickFilterKey>>(new Set())
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 從已選的 filter keys 取得合併後的條件陣列
  const getActiveConditions = useCallback((keys: Set<QuickFilterKey>): FilterCondition[] => {
    const sets = Array.from(keys)
      .map(k => ALL_FILTERS.find(f => f.key === k))
      .filter((f): f is QuickFilterDef => !!f && !f.disabled)
      .map(f => f.conditions)
    return mergeConditions(sets)
  }, [])

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
    conditions: FilterCondition[] = [],
  ) => {
    setLoading(true)
    setError(null)
    try {
      let url: string
      if (keyword) {
        url = `${API_URL}/v1/stocks/search/${encodeURIComponent(keyword)}`
      } else {
        const skip = (p - 1) * PAGE_SIZE
        const base = `${API_URL}/v1/stocks?skip=${skip}&limit=${PAGE_SIZE}`
          + (market ? `&market_type=${encodeURIComponent(market)}` : '')
          + (sector ? `&sector=${encodeURIComponent(sector)}` : '')
        url = buildUrl(base, conditions)
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

  // ── Event handlers ────────────────────────────────────────────────────────

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setSearchTerm(val)
    setPage(1)
    setSortKey('')
    setActiveFilters(new Set())
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
    fetchStocks(1, '', market, sectorFilter, getActiveConditions(activeFilters))
  }

  const handleSectorFilter = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const sector = e.target.value
    setSectorFilter(sector)
    setPage(1)
    setSearchTerm('')
    setSortKey('')
    fetchStocks(1, '', marketFilter, sector, getActiveConditions(activeFilters))
  }

  const handlePage = (newPage: number) => {
    setPage(newPage)
    fetchStocks(newPage, '', marketFilter, sectorFilter, getActiveConditions(activeFilters))
    window.scrollTo(0, 0)
  }

  const handleQuickFilter = (key: QuickFilterKey) => {
    const def = ALL_FILTERS.find(f => f.key === key)
    if (!def || def.disabled) return

    setActiveFilters(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      // 非同步取得新 conditions 後 fetch
      const conditions = getActiveConditions(next)
      setPage(1)
      setSearchTerm('')
      setSortKey('')
      fetchStocks(1, '', marketFilter, sectorFilter, conditions)
      return next
    })
  }

  const handleClearFilter = (key: QuickFilterKey) => {
    setActiveFilters(prev => {
      const next = new Set(prev)
      next.delete(key)
      const conditions = getActiveConditions(next)
      setPage(1)
      fetchStocks(1, '', marketFilter, sectorFilter, conditions)
      return next
    })
  }

  const handleClearAll = () => {
    setActiveFilters(new Set())
    setPage(1)
    fetchStocks(1, '', marketFilter, sectorFilter, [])
  }

  const handleSort = (key: string) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  // ── 格式化工具 ────────────────────────────────────────────────────────────

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
    const p = d.split('-')
    return p.length === 3 ? `${p[1]}/${p[2]}` : d
  }

  const changeColor = (n?: number | string) => {
    const num = typeof n === 'string' ? parseFloat(n) : Number(n)
    if (isNaN(num) || n == null) return '#aaa'
    return num > 0 ? '#ff4d4d' : num < 0 ? '#33cc66' : '#aaa'
  }

  const netIncomeColor = (n?: number | string) => {
    const num = typeof n === 'string' ? parseFloat(n) : Number(n)
    if (isNaN(num) || n == null) return '#aaa'
    return num > 0 ? '#51cf66' : num < 0 ? '#ff6b6b' : '#aaa'
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
  const activeFilterDefs = ALL_FILTERS.filter(f => activeFilters.has(f.key))

  // ── 樣式工具 ──────────────────────────────────────────────────────────────

  const btnStyle = (active: boolean): React.CSSProperties => ({
    padding: '6px 14px',
    background: active ? '#f90' : 'rgba(255,255,255,0.08)',
    color: active ? '#000' : '#ccc',
    border: 'none', borderRadius: '6px', cursor: 'pointer',
    fontWeight: active ? 700 : 400, fontSize: '0.85rem',
  })

  const qBtnStyle = (def: QuickFilterDef): React.CSSProperties => {
    const active = activeFilters.has(def.key)
    const disabled = !!def.disabled
    return {
      padding: '4px 11px',
      background: active
        ? 'rgba(124,58,237,0.85)'
        : disabled ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.06)',
      color: active ? '#fff' : disabled ? '#444' : '#bbb',
      border: `1px solid ${active
        ? 'rgba(124,58,237,0.6)'
        : disabled ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.1)'}`,
      borderRadius: '5px',
      cursor: disabled ? 'not-allowed' : 'pointer',
      fontSize: '0.82rem',
      opacity: disabled ? 0.5 : 1,
      whiteSpace: 'nowrap',
    }
  }

  const pageBtnStyle = (disabled: boolean): React.CSSProperties => ({
    padding: '6px 12px',
    background: 'rgba(255,255,255,0.1)',
    color: '#fff', border: 'none', borderRadius: '4px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.4 : 1,
  })

  // ── 渲染 ──────────────────────────────────────────────────────────────────

  return (
    <div className="app">
      <header className="app-header">
        <h1>🚀 台股觀測站</h1>
        <p>台灣股票市場監測和投資組合管理平台</p>
      </header>

      <main className="app-main">

        {/* ── 搜尋列 + 市場 / 產業篩選 ── */}
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

        {/* ── 快捷篩選按鈕（分組，可多選）── */}
        <div style={{ marginBottom: '0.75rem', display: 'flex', flexDirection: 'column', gap: '5px' }}>
          {FILTER_GROUPS.map(group => (
            <div key={group.label} style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <span style={{ color: '#444', fontSize: '0.73rem', minWidth: '30px', textAlign: 'right', flexShrink: 0 }}>
                {group.label}
              </span>
              <div style={{ width: '1px', height: '14px', background: 'rgba(255,255,255,0.08)', flexShrink: 0 }} />
              {group.filters.map(def => (
                <button key={def.key} title={def.tooltip} style={qBtnStyle(def)} onClick={() => handleQuickFilter(def.key)}>
                  {def.emoji} {def.label}
                  {def.disabled && <span style={{ marginLeft: '3px', fontSize: '0.68rem', opacity: 0.55 }}>（即將推出）</span>}
                </button>
              ))}
            </div>
          ))}

          {/* ── 已選篩選標籤列 ── */}
          {activeFilterDefs.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginTop: '4px', paddingLeft: '38px' }}>
              <span style={{ color: '#555', fontSize: '0.73rem' }}>已選：</span>
              {activeFilterDefs.map(def => (
                <span key={def.key} style={{
                  display: 'inline-flex', alignItems: 'center', gap: '4px',
                  padding: '2px 8px', background: 'rgba(124,58,237,0.2)',
                  border: '1px solid rgba(124,58,237,0.4)',
                  borderRadius: '4px', fontSize: '0.78rem', color: '#c4b5fd',
                }}>
                  {def.emoji} {def.label}
                  <span
                    onClick={() => handleClearFilter(def.key)}
                    style={{ cursor: 'pointer', opacity: 0.7, marginLeft: '2px', fontSize: '0.7rem' }}
                    title="移除此篩選"
                  >✕</span>
                </span>
              ))}
              <button onClick={handleClearAll}
                style={{ padding: '2px 8px', background: 'transparent', color: '#555', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '4px', cursor: 'pointer', fontSize: '0.73rem' }}>
                清除全部
              </button>
            </div>
          )}
        </div>

        {/* ── 錯誤訊息 ── */}
        {error && (
          <div style={{ color: '#f44336', padding: '0.75rem 1rem', marginBottom: '1rem', background: 'rgba(244,67,54,0.08)', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            ⚠️ {error}
            <button
              onClick={() => fetchStocks(page, '', marketFilter, sectorFilter, getActiveConditions(activeFilters))}
              style={{ marginLeft: 'auto', padding: '4px 10px', background: 'rgba(244,67,54,0.2)', color: '#f44336', border: '1px solid rgba(244,67,54,0.4)', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}>
              重試
            </button>
          </div>
        )}

        {/* ── 主表格 ── */}
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
                        title="點擊排序（僅限本頁）"
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
                            : activeFilterDefs.length > 0
                              ? `目前沒有同時符合所有篩選條件的股票`
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
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: '#555', fontSize: '0.82rem' }}>{fmtDate(s.trade_date)}</td>
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

            {/* ── 翻頁 ── */}
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
