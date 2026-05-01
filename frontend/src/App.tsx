import React, { useState, useEffect, useCallback, useRef } from 'react'
import './index.css'

// ─── 資料型別 ────────────────────────────────────────────────────────────────

interface Stock {
  id?: string
  symbol: string
  name: string
  sector?: string
  market_type?: string
  // 行情
  close_price?: number | string
  open_price?: number | string
  high_price?: number | string
  low_price?: number | string
  change_amount?: number | string
  change_percent?: number | string
  volume?: number
  turnover_rate?: number | string
  trade_date?: string
  // 估值
  eps?: number | string
  pe_ratio?: number | string
  pb_ratio?: number | string
  dividend_yield?: number | string
  // 損益
  revenue?: number | string
  net_income?: number | string
  // 月營收
  revenue_yoy?: number | string
  revenue_mom?: number | string
  // 三大法人（張）
  foreign_net_buy?: number
  investment_trust_net_buy?: number
  dealer_net_buy?: number
  // 財報
  gross_margin?: number | string
  operating_margin?: number | string
  net_margin?: number | string
  roe?: number | string
  roa?: number | string
  debt_ratio?: number | string
  // 融資/融券
  margin_long?: number
  margin_short?: number
  // 標記
  is_attention?: boolean
  is_disposed?: boolean
  is_etf?: boolean
  // 股利
  ex_dividend_date?: string
  cash_dividend?: number | string
}

// ─── 通用篩選條件型別 ─────────────────────────────────────────────────────────

type FilterOp = 'min' | 'max' | 'contains' | 'is_true' | 'is_false'

interface FilterCondition {
  field: string
  op: FilterOp
  value: number | string | boolean
}

function buildUrl(base: string, conditions: FilterCondition[]): string {
  let url = base
  for (const { field, op, value } of conditions) {
    if (op === 'min')      url += `&${field}_min=${value}`
    if (op === 'max')      url += `&${field}_max=${value}`
    if (op === 'contains') url += `&${field}_contains=${encodeURIComponent(String(value))}`
    if (op === 'is_true')  url += `&${field}=true`
    if (op === 'is_false') url += `&${field}=false`
  }
  return url
}

function mergeConditions(conditionSets: FilterCondition[][]): FilterCondition[] {
  const map = new Map<string, FilterCondition>()
  for (const set of conditionSets) {
    for (const cond of set) {
      const key = `${cond.field}__${cond.op}`
      const existing = map.get(key)
      if (!existing) {
        map.set(key, { ...cond })
      } else {
        if (cond.op === 'min' && typeof cond.value === 'number' && typeof existing.value === 'number') {
          existing.value = Math.max(existing.value, cond.value)
        } else if (cond.op === 'max' && typeof cond.value === 'number' && typeof existing.value === 'number') {
          existing.value = Math.min(existing.value, cond.value)
        } else {
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
  | 'low_pe' | 'low_pb' | 'high_eps' | 'high_dividend'
  | 'profitable' | 'losing' | 'revenue_growth'
  | 'high_gross_margin' | 'high_roe' | 'low_debt'
  | 'etf' | 'no_etf' | 'close_at_high' | 'high_turnover'
  | 'foreign_buy' | 'trust_buy' | 'high_margin_long'
  | 'is_attention' | 'is_disposed'

interface QuickFilterDef {
  key: QuickFilterKey
  label: string
  emoji: string
  tooltip: string
  conditions: FilterCondition[]
  disabled?: boolean
}

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
      {
        key: 'high_dividend', label: '高殖利率', emoji: '💸', tooltip: '殖利率 ≥ 4%',
        conditions: [{ field: 'dividend_yield', op: 'min', value: 4 }],
      },
    ],
  },
  {
    label: '獲利',
    filters: [
      {
        key: 'high_gross_margin', label: '高毛利率', emoji: '🏭', tooltip: '毛利率 ≥ 30%',
        conditions: [{ field: 'gross_margin', op: 'min', value: 30 }],
      },
      {
        key: 'high_roe', label: '高 ROE', emoji: '📐', tooltip: 'ROE ≥ 15%',
        conditions: [{ field: 'roe', op: 'min', value: 15 }],
      },
      {
        key: 'low_debt', label: '低負債', emoji: '🛡️', tooltip: '負債比率 ≤ 40%',
        conditions: [{ field: 'debt_ratio', op: 'max', value: 40 }],
      },
      {
        key: 'profitable', label: '獲利股', emoji: '✅', tooltip: '淨利 > 0',
        conditions: [{ field: 'net_income', op: 'min', value: 1 }],
      },
      {
        key: 'losing', label: '虧損股', emoji: '❌', tooltip: '淨利 < 0',
        conditions: [{ field: 'net_income', op: 'max', value: -1 }],
      },
      {
        key: 'revenue_growth', label: '營收成長 20%+', emoji: '📊', tooltip: '月營收年增率 ≥ 20%',
        conditions: [{ field: 'revenue_yoy', op: 'min', value: 20 }],
      },
    ],
  },
  {
    label: '籌碼',
    filters: [
      {
        key: 'foreign_buy', label: '外資大買', emoji: '🌏', tooltip: '外資買超 ≥ 1000 張',
        conditions: [{ field: 'foreign_net_buy', op: 'min', value: 1000 }],
      },
      {
        key: 'trust_buy', label: '投信大買', emoji: '🏛️', tooltip: '投信買超 ≥ 100 張',
        conditions: [{ field: 'investment_trust_net_buy', op: 'min', value: 100 }],
      },
      {
        key: 'high_margin_long', label: '高融資', emoji: '💳', tooltip: '融資餘額 ≥ 1000 張',
        conditions: [{ field: 'margin_long', op: 'min', value: 1000 }],
      },
      {
        key: 'high_turnover', label: '高週轉率', emoji: '🔄', tooltip: '週轉率 ≥ 5%',
        conditions: [{ field: 'turnover_rate', op: 'min', value: 5 }],
      },
    ],
  },
  {
    label: '風險',
    filters: [
      {
        key: 'is_attention', label: '注意股', emoji: '⚠️', tooltip: '列入注意交易股票',
        conditions: [{ field: 'is_attention', op: 'is_true', value: true }],
      },
      {
        key: 'is_disposed', label: '處置股', emoji: '🔴', tooltip: '列入處置股票',
        conditions: [{ field: 'is_disposed', op: 'is_true', value: true }],
      },
    ],
  },
  {
    label: '其他',
    filters: [
      {
        key: 'etf', label: '只看 ETF', emoji: '📦', tooltip: '只顯示 ETF（代號 00 開頭）',
        conditions: [{ field: 'is_etf', op: 'is_true', value: true }],
      },
      {
        key: 'no_etf', label: '排除 ETF', emoji: '🚫', tooltip: '排除 ETF，只看個股',
        conditions: [{ field: 'is_etf', op: 'is_false', value: false }],
      },
      {
        key: 'close_at_high', label: '收在最高', emoji: '🎯', tooltip: '收盤價 = 當日最高價',
        conditions: [{ field: 'close_at_high', op: 'is_true', value: true }],
      },
    ],
  },
]

const ALL_FILTERS: QuickFilterDef[] = FILTER_GROUPS.flatMap(g => g.filters)

// ─── 欄位定義 ─────────────────────────────────────────────────────────────────

interface ColumnDef {
  label: string
  key: string
  group: string
  defaultVisible: boolean
}

const COLUMN_DEFS: ColumnDef[] = [
  // 基本
  { label: '股號',       key: 'symbol',                  group: '基本', defaultVisible: true  },
  { label: '股名',       key: 'name',                    group: '基本', defaultVisible: true  },
  { label: '市場',       key: 'market_type',             group: '基本', defaultVisible: true  },
  { label: '產業',       key: 'sector',                  group: '基本', defaultVisible: true  },
  // 行情
  { label: '日期',       key: 'trade_date',              group: '行情', defaultVisible: true  },
  { label: '收盤',       key: 'close_price',             group: '行情', defaultVisible: true  },
  { label: '漲跌',       key: 'change_amount',           group: '行情', defaultVisible: true  },
  { label: '漲跌幅%',   key: 'change_percent',          group: '行情', defaultVisible: true  },
  { label: '開盤',       key: 'open_price',              group: '行情', defaultVisible: false },
  { label: '最高',       key: 'high_price',              group: '行情', defaultVisible: false },
  { label: '最低',       key: 'low_price',               group: '行情', defaultVisible: false },
  { label: '成交量(千)', key: 'volume',                  group: '行情', defaultVisible: true  },
  { label: '週轉率%',   key: 'turnover_rate',           group: '行情', defaultVisible: false },
  // 估值
  { label: 'EPS',        key: 'eps',                     group: '估值', defaultVisible: true  },
  { label: '本益比',     key: 'pe_ratio',                group: '估值', defaultVisible: true  },
  { label: '淨值比',     key: 'pb_ratio',                group: '估值', defaultVisible: true  },
  { label: '殖利率%',   key: 'dividend_yield',          group: '估值', defaultVisible: false },
  // 損益
  { label: '營收(千)',   key: 'revenue',                 group: '損益', defaultVisible: false },
  { label: '淨利(千)',   key: 'net_income',              group: '損益', defaultVisible: false },
  // 月營收
  { label: '月營收年增%', key: 'revenue_yoy',           group: '月營收', defaultVisible: false },
  { label: '月營收月增%', key: 'revenue_mom',           group: '月營收', defaultVisible: false },
  // 三大法人
  { label: '外資(張)',   key: 'foreign_net_buy',         group: '法人', defaultVisible: false },
  { label: '投信(張)',   key: 'investment_trust_net_buy', group: '法人', defaultVisible: false },
  { label: '自營(張)',   key: 'dealer_net_buy',          group: '法人', defaultVisible: false },
  // 財報
  { label: '毛利率%',   key: 'gross_margin',            group: '財報', defaultVisible: false },
  { label: '營業利益%', key: 'operating_margin',        group: '財報', defaultVisible: false },
  { label: '淨利率%',   key: 'net_margin',              group: '財報', defaultVisible: false },
  { label: 'ROE%',       key: 'roe',                     group: '財報', defaultVisible: false },
  { label: 'ROA%',       key: 'roa',                     group: '財報', defaultVisible: false },
  { label: '負債比%',   key: 'debt_ratio',              group: '財報', defaultVisible: false },
  // 籌碼
  { label: '融資(張)',   key: 'margin_long',             group: '籌碼', defaultVisible: false },
  { label: '融券(張)',   key: 'margin_short',            group: '籌碼', defaultVisible: false },
  // 股利
  { label: '除息日',     key: 'ex_dividend_date',        group: '股利', defaultVisible: false },
  { label: '現金股利',   key: 'cash_dividend',           group: '股利', defaultVisible: false },
]

const COLUMN_GROUPS = Array.from(new Set(COLUMN_DEFS.map(c => c.group)))

const DEFAULT_VISIBLE = new Set(COLUMN_DEFS.filter(c => c.defaultVisible).map(c => c.key))

function loadVisibleColumns(): Set<string> {
  try {
    const saved = localStorage.getItem('tw_stock_visible_cols')
    if (saved) {
      const arr = JSON.parse(saved) as string[]
      if (Array.isArray(arr) && arr.length > 0) return new Set(arr)
    }
  } catch {}
  return new Set(DEFAULT_VISIBLE)
}

function saveVisibleColumns(cols: Set<string>) {
  try {
    localStorage.setItem('tw_stock_visible_cols', JSON.stringify(Array.from(cols)))
  } catch {}
}

// ─── 常數 ────────────────────────────────────────────────────────────────────

const API_URL = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000/api'
const PAGE_SIZE = 50

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
  const [activeFilters, setActiveFilters] = useState<Set<QuickFilterKey>>(new Set())
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(loadVisibleColumns)
  const [showColPanel, setShowColPanel] = useState(false)
  const colPanelRef = useRef<HTMLDivElement>(null)
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── 重大訊息 modal ────────────────────────────────────────────────────────
  interface Announcement { id: number; announce_date: string; subject: string; content: string; source: string }
  const [annModal, setAnnModal] = useState<{ symbol: string; name: string } | null>(null)
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [annLoading, setAnnLoading] = useState(false)

  const openAnnouncements = useCallback(async (symbol: string, name: string) => {
    setAnnModal({ symbol, name })
    setAnnouncements([])
    setAnnLoading(true)
    try {
      const res = await fetch(`${API_URL}/v1/stocks/${symbol}/announcements?limit=20`)
      if (res.ok) setAnnouncements(await res.json())
    } catch {}
    setAnnLoading(false)
  }, [])

  // 點擊面板外部關閉
  useEffect(() => {
    if (!showColPanel) return
    const handler = (e: MouseEvent) => {
      if (colPanelRef.current && !colPanelRef.current.contains(e.target as Node)) {
        setShowColPanel(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showColPanel])

  const toggleColumn = (key: string) => {
    setVisibleColumns(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      saveVisibleColumns(next)
      return next
    })
  }

  const resetColumns = () => {
    setVisibleColumns(new Set(DEFAULT_VISIBLE))
    saveVisibleColumns(DEFAULT_VISIBLE)
  }

  // 當前顯示的欄位（保持原始順序）
  const visibleCols = COLUMN_DEFS.filter(c => visibleColumns.has(c.key))

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

  const fmtInt = (n?: number) => {
    if (n == null) return '--'
    return n.toLocaleString()
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

  const yoyColor = (n?: number | string) => {
    const num = typeof n === 'string' ? parseFloat(n) : Number(n)
    if (isNaN(num) || n == null) return '#aaa'
    return num > 0 ? '#51cf66' : num < 0 ? '#ff6b6b' : '#aaa'
  }

  const instColor = (n?: number) => {
    if (n == null) return '#aaa'
    return n > 0 ? '#51cf66' : n < 0 ? '#ff6b6b' : '#aaa'
  }

  // 取得某欄位的 cell 內容
  const renderCell = (s: Stock, key: string): React.ReactNode => {
    switch (key) {
      case 'symbol':       return <span style={{ color: '#f90', fontWeight: 600 }}>{s.symbol}</span>
      case 'name':         return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', whiteSpace: 'nowrap' }}>
          <span
            style={{ color: '#fff', cursor: 'pointer', textDecoration: 'underline dotted', textUnderlineOffset: '3px' }}
            title="查看重大訊息"
            onClick={() => openAnnouncements(s.symbol, s.name)}>
            {s.name}
          </span>
          {s.is_etf && <span style={{ fontSize: '0.68rem', padding: '1px 5px', background: 'rgba(56,139,253,0.2)', color: '#6ea8fe', border: '1px solid rgba(56,139,253,0.35)', borderRadius: '3px', lineHeight: 1.4 }}>ETF</span>}
          {s.is_attention && <span style={{ fontSize: '0.68rem', padding: '1px 5px', background: 'rgba(255,193,7,0.15)', color: '#ffc107', border: '1px solid rgba(255,193,7,0.35)', borderRadius: '3px', lineHeight: 1.4 }}>⚠️注意</span>}
          {s.is_disposed  && <span style={{ fontSize: '0.68rem', padding: '1px 5px', background: 'rgba(220,53,69,0.15)', color: '#ff6b6b', border: '1px solid rgba(220,53,69,0.35)', borderRadius: '3px', lineHeight: 1.4 }}>🔴處置</span>}
        </span>
      )
      case 'market_type':  return (
        <span style={{
          background: s.market_type === '上市' ? 'rgba(100,149,237,0.2)' : 'rgba(144,238,144,0.2)',
          color: s.market_type === '上市' ? '#6495ed' : '#90ee90',
          padding: '2px 6px', borderRadius: '4px', fontSize: '0.8rem',
        }}>{s.market_type || '--'}</span>
      )
      case 'sector':       return <span style={{ color: '#aaa', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>{s.sector || '--'}</span>
      case 'trade_date':   return <span style={{ color: '#555', fontSize: '0.82rem' }}>{fmtDate(s.trade_date)}</span>
      case 'close_price':  return <span style={{ color: changeColor(s.change_amount), fontWeight: 600 }}>{fmt(s.close_price)}</span>
      case 'change_amount':return <span style={{ color: changeColor(s.change_amount) }}>{fmtChange(s.change_amount)}</span>
      case 'change_percent':return <span style={{ color: changeColor(s.change_percent) }}>{s.change_percent != null ? fmtChange(s.change_percent) + '%' : '--'}</span>
      case 'open_price':   return <span style={{ color: '#ccc' }}>{fmt(s.open_price)}</span>
      case 'high_price':   return <span style={{ color: '#ff6b6b' }}>{fmt(s.high_price)}</span>
      case 'low_price':    return <span style={{ color: '#51cf66' }}>{fmt(s.low_price)}</span>
      case 'volume':       return <span style={{ color: '#aaa' }}>{fmtThousands(s.volume)}</span>
      case 'turnover_rate':return <span style={{ color: '#aaa' }}>{fmt(s.turnover_rate, 2)}</span>
      case 'eps':          return <span style={{ color: '#ccc' }}>{fmt(s.eps)}</span>
      case 'pe_ratio':     return <span style={{ color: '#ccc' }}>{fmt(s.pe_ratio)}</span>
      case 'pb_ratio':     return <span style={{ color: '#ccc' }}>{fmt(s.pb_ratio)}</span>
      case 'dividend_yield':return <span style={{ color: '#51cf66' }}>{fmt(s.dividend_yield)}</span>
      case 'revenue':      return <span style={{ color: '#ccc' }}>{fmtThousands(s.revenue)}</span>
      case 'net_income':   return <span style={{ color: netIncomeColor(s.net_income) }}>{fmtThousands(s.net_income)}</span>
      case 'revenue_yoy':  return <span style={{ color: yoyColor(s.revenue_yoy) }}>{fmt(s.revenue_yoy)}</span>
      case 'revenue_mom':  return <span style={{ color: yoyColor(s.revenue_mom) }}>{fmt(s.revenue_mom)}</span>
      case 'foreign_net_buy':         return <span style={{ color: instColor(s.foreign_net_buy) }}>{fmtInt(s.foreign_net_buy)}</span>
      case 'investment_trust_net_buy':return <span style={{ color: instColor(s.investment_trust_net_buy) }}>{fmtInt(s.investment_trust_net_buy)}</span>
      case 'dealer_net_buy':          return <span style={{ color: instColor(s.dealer_net_buy) }}>{fmtInt(s.dealer_net_buy)}</span>
      case 'gross_margin':    return <span style={{ color: '#ccc' }}>{fmt(s.gross_margin)}</span>
      case 'operating_margin':return <span style={{ color: '#ccc' }}>{fmt(s.operating_margin)}</span>
      case 'net_margin':      return <span style={{ color: '#ccc' }}>{fmt(s.net_margin)}</span>
      case 'roe':             return <span style={{ color: '#ccc' }}>{fmt(s.roe)}</span>
      case 'roa':             return <span style={{ color: '#ccc' }}>{fmt(s.roa)}</span>
      case 'debt_ratio':      return <span style={{ color: '#ccc' }}>{fmt(s.debt_ratio)}</span>
      case 'margin_long':     return <span style={{ color: s.margin_long != null && s.margin_long > 0 ? '#ffc107' : '#aaa' }}>{fmtInt(s.margin_long)}</span>
      case 'margin_short':    return <span style={{ color: s.margin_short != null && s.margin_short > 0 ? '#ff6b6b' : '#aaa' }}>{fmtInt(s.margin_short)}</span>
      case 'ex_dividend_date':return <span style={{ color: '#51cf66', fontSize: '0.83rem' }}>{s.ex_dividend_date || '--'}</span>
      case 'cash_dividend':   return <span style={{ color: '#51cf66' }}>{fmt(s.cash_dividend, 2)}</span>
      default:                return '--'
    }
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

  // ── 樣式 ──────────────────────────────────────────────────────────────────

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
      background: active ? 'rgba(124,58,237,0.85)' : disabled ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.06)',
      color: active ? '#fff' : disabled ? '#444' : '#bbb',
      border: `1px solid ${active ? 'rgba(124,58,237,0.6)' : disabled ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.1)'}`,
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

        {/* ── 搜尋列 + 市場 / 產業篩選 + 欄位開關 ── */}
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

          {/* 欄位開關按鈕 */}
          <div ref={colPanelRef} style={{ position: 'relative' }}>
            <button
              onClick={() => setShowColPanel(p => !p)}
              title="欄位顯示設定"
              style={{
                padding: '6px 12px', background: showColPanel ? 'rgba(255,153,0,0.2)' : 'rgba(255,255,255,0.08)',
                color: showColPanel ? '#f90' : '#ccc',
                border: `1px solid ${showColPanel ? 'rgba(255,153,0,0.5)' : 'rgba(255,255,255,0.15)'}`,
                borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem',
              }}>
              ⚙️ 欄位
            </button>

            {showColPanel && (
              <div style={{
                position: 'absolute', top: 'calc(100% + 6px)', right: 0,
                background: '#1e2030', border: '1px solid rgba(255,255,255,0.15)',
                borderRadius: '8px', padding: '12px 14px', zIndex: 100,
                minWidth: '340px', maxHeight: '480px', overflowY: 'auto',
                boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <span style={{ color: '#ccc', fontWeight: 600, fontSize: '0.88rem' }}>欄位顯示設定</span>
                  <button onClick={resetColumns}
                    style={{ padding: '2px 8px', background: 'transparent', color: '#666', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '4px', cursor: 'pointer', fontSize: '0.73rem' }}>
                    還原預設
                  </button>
                </div>
                {COLUMN_GROUPS.map(group => (
                  <div key={group} style={{ marginBottom: '10px' }}>
                    <div style={{ color: '#666', fontSize: '0.73rem', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{group}</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                      {COLUMN_DEFS.filter(c => c.group === group).map(col => {
                        const checked = visibleColumns.has(col.key)
                        const isLocked = col.key === 'symbol' || col.key === 'name'
                        return (
                          <label key={col.key} style={{
                            display: 'flex', alignItems: 'center', gap: '5px',
                            padding: '3px 8px',
                            background: checked ? 'rgba(255,153,0,0.12)' : 'rgba(255,255,255,0.04)',
                            border: `1px solid ${checked ? 'rgba(255,153,0,0.3)' : 'rgba(255,255,255,0.06)'}`,
                            borderRadius: '4px', cursor: isLocked ? 'default' : 'pointer',
                            fontSize: '0.8rem', color: checked ? '#f90' : '#777',
                            userSelect: 'none',
                          }}>
                            <input
                              type="checkbox" checked={checked} disabled={isLocked}
                              onChange={() => !isLocked && toggleColumn(col.key)}
                              style={{ accentColor: '#f90', cursor: isLocked ? 'default' : 'pointer', width: '12px', height: '12px' }}
                            />
                            {col.label}
                          </label>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <span style={{ color: '#aaa', fontSize: '0.9rem', whiteSpace: 'nowrap' }}>共 {total} 筆</span>
          {tradeDate && (
            <span style={{ color: '#666', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>資料日期：{tradeDate}</span>
          )}
        </div>

        {/* ── 快捷篩選按鈕 ── */}
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

          {/* 已選篩選標籤列 */}
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
                  <span onClick={() => handleClearFilter(def.key)}
                    style={{ cursor: 'pointer', opacity: 0.7, marginLeft: '2px', fontSize: '0.7rem' }} title="移除此篩選">✕</span>
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
                    {visibleCols.map(({ label, key }) => (
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
                      <td colSpan={visibleCols.length} style={{ padding: '3rem', textAlign: 'center', color: '#666' }}>
                        <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🔍</div>
                        <div>
                          {searchTerm
                            ? `找不到符合「${searchTerm}」的股票`
                            : activeFilterDefs.length > 0
                              ? '目前沒有同時符合所有篩選條件的股票'
                              : '目前沒有資料'}
                        </div>
                      </td>
                    </tr>
                  )}
                  {sortedStocks.map((s, i) => (
                    <tr key={s.symbol} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      {visibleCols.map(({ key }) => (
                        <td key={key} style={{ padding: '8px 12px', textAlign: key === 'symbol' || key === 'name' || key === 'market_type' || key === 'sector' ? 'left' : 'right' }}>
                          {renderCell(s, key)}
                        </td>
                      ))}
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
        <p>© {new Date().getFullYear()} 台股觀測站 | 版本 2.0.0</p>
      </footer>

      {/* ── 重大訊息 Modal ── */}
      {annModal && (
        <div
          onClick={() => setAnnModal(null)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: '20px',
          }}>
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: '#1a1d2e', border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: '10px', padding: '20px 24px', width: '100%', maxWidth: '680px',
              maxHeight: '80vh', display: 'flex', flexDirection: 'column',
              boxShadow: '0 12px 48px rgba(0,0,0,0.6)',
            }}>
            {/* 標題列 */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div>
                <span style={{ color: '#f90', fontWeight: 700, marginRight: '8px' }}>{annModal.symbol}</span>
                <span style={{ color: '#fff', fontWeight: 600 }}>{annModal.name}</span>
                <span style={{ color: '#555', fontSize: '0.82rem', marginLeft: '8px' }}>重大訊息</span>
              </div>
              <button
                onClick={() => setAnnModal(null)}
                style={{ background: 'transparent', border: 'none', color: '#666', cursor: 'pointer', fontSize: '1.2rem', lineHeight: 1, padding: '2px 6px' }}>
                ✕
              </button>
            </div>

            {/* 訊息列表 */}
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {annLoading && (
                <div style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>⏳ 載入中...</div>
              )}
              {!annLoading && announcements.length === 0 && (
                <div style={{ textAlign: 'center', padding: '2rem', color: '#555' }}>
                  <div style={{ fontSize: '1.5rem', marginBottom: '6px' }}>📭</div>
                  尚無重大訊息記錄
                </div>
              )}
              {announcements.map(ann => (
                <div key={ann.id} style={{
                  padding: '12px 14px', marginBottom: '8px',
                  background: 'rgba(255,255,255,0.04)', borderRadius: '6px',
                  borderLeft: `3px solid ${ann.source === 'TWSE' ? '#6495ed' : '#90ee90'}`,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ color: '#aaa', fontSize: '0.78rem' }}>{ann.announce_date}</span>
                    <span style={{
                      fontSize: '0.7rem', padding: '1px 6px',
                      background: ann.source === 'TWSE' ? 'rgba(100,149,237,0.15)' : 'rgba(144,238,144,0.12)',
                      color: ann.source === 'TWSE' ? '#6495ed' : '#90ee90',
                      border: `1px solid ${ann.source === 'TWSE' ? 'rgba(100,149,237,0.3)' : 'rgba(144,238,144,0.2)'}`,
                      borderRadius: '3px',
                    }}>{ann.source}</span>
                  </div>
                  <div style={{ color: '#ddd', fontSize: '0.88rem', fontWeight: 500 }}>{ann.subject || '（無主旨）'}</div>
                  {ann.content && (
                    <div style={{ color: '#888', fontSize: '0.8rem', marginTop: '5px', lineHeight: 1.5,
                      maxHeight: '80px', overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
                      {ann.content}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
