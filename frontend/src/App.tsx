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
  revenue_note?: string | null
  revenue_yoy?: number | string
  revenue_mom?: number | string
  // 三大法人（張）
  foreign_net_buy?: number
  investment_trust_net_buy?: number
  dealer_net_buy?: number
  foreign_consecutive_days?: number
  // 財報
  gross_margin?: number | string
  operating_margin?: number | string
  net_margin?: number | string
  roe?: number | string
  roa?: number | string
  debt_ratio?: number | string
  // 融資/融券
  margin_long?: number
  margin_long_prev?: number
  margin_long_chg_pct?: number | string
  margin_surge?: boolean
  margin_short?: number
  // 標記
  is_attention?: boolean
  is_disposed?: boolean
  is_etf?: boolean
  // 股利
  ex_dividend_date?: string
  cash_dividend?: number | string
  dividend_per_share?: number | string
  // 效率指標
  inventory_turnover?: number | string
  // 基本面進階指標
  core_profit_ratio?: number | string
  roe_quality?: boolean
  free_cash_flow_ps?: number | string
  interest_coverage?: number | string
  // 基本資料（補充）
  listing_date?: string
  capital_stock?: number
  shares?: number
  website?: string
  suspension_reason?: string
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
  | 'high_gross_margin' | 'high_roe' | 'high_roa' | 'low_debt'
  | 'etf' | 'no_etf' | 'close_at_high' | 'high_turnover'
  | 'foreign_buy' | 'trust_buy' | 'high_margin_long'
  | 'is_attention' | 'is_disposed'
  | 'demand_increase'
  | 'gross_margin_rising' | 'net_income_outpace' | 'contract_liabilities_growth'
  | 'high_inventory_turnover'
  | 'roe_quality' | 'core_profit_high'
  | 'foreign_buy_streak' | 'foreign_sell_streak'
  | 'margin_surge_alert'

// 呼叫 screener API 的篩選 key 與對應端點
const SCREENER_ENDPOINT_MAP: Partial<Record<QuickFilterKey, string>> = {
  gross_margin_rising:          'gross-margin-rising',
  net_income_outpace:           'net-income-outpace-revenue',
  contract_liabilities_growth:  'contract-liabilities-growth',
  roe_quality:                  'roe-quality',
  core_profit_high:             'core-profit',
}

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
        key: 'gross_margin_rising', label: '毛利率逐季↑', emoji: '📈', tooltip: '最近 4 季毛利率均 ≥ 30% 且逐季遞增',
        conditions: [],
      },
      {
        key: 'net_income_outpace', label: '淨利增幅>營收', emoji: '🔍', tooltip: '最新季淨利年增率 > 營收年增率（利潤率擴張）',
        conditions: [],
      },
      {
        key: 'contract_liabilities_growth', label: '合約負債增加', emoji: '📦', tooltip: '合約負債連續 3 季增加，或單季 QoQ ≥ 20%',
        conditions: [],
      },
      {
        key: 'high_inventory_turnover', label: '高存貨周轉', emoji: '⚡', tooltip: '年化存貨周轉率 ≥ 4 次（近四季 TTM）',
        conditions: [{ field: 'inventory_turnover', op: 'min', value: 4 }],
      },
      {
        key: 'high_roe', label: '高 ROE', emoji: '📐', tooltip: 'ROE ≥ 15%',
        conditions: [{ field: 'roe', op: 'min', value: 15 }],
      },
      {
        key: 'roe_quality', label: 'ROE 品質股', emoji: '🏆', tooltip: 'ROE≥15% 且 營益率≥10% 且 毛利率≥30%（多維度交叉驗證高品質獲利）',
        conditions: [],
      },
      {
        key: 'core_profit_high', label: '本業獲利佔比≥80%', emoji: '🎯', tooltip: '本業獲利佔比（營業利益/稅後淨利）≥80%，排除靠業外灌水的公司',
        conditions: [],
      },
      {
        key: 'high_roa', label: '高 ROA', emoji: '💎', tooltip: 'ROA ≥ 8%',
        conditions: [{ field: 'roa', op: 'min', value: 8 }],
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
      {
        key: 'demand_increase', label: '需求增加', emoji: '📈', tooltip: '當月月營收備註含「需求增加」',
        conditions: [{ field: 'revenue_note', op: 'contains', value: '需求增加' }],
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
        key: 'foreign_buy_streak', label: '外資連買 5+ 天', emoji: '📈', tooltip: '外資連續買超 ≥ 5 個交易日，趨勢成形',
        conditions: [{ field: 'foreign_consecutive_days', op: 'min', value: 5 }],
      },
      {
        key: 'foreign_sell_streak', label: '外資連賣 5+ 天', emoji: '📉', tooltip: '外資連續賣超 ≥ 5 個交易日（數值 ≤ -5）',
        conditions: [{ field: 'foreign_consecutive_days', op: 'max', value: -5 }],
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
        key: 'margin_surge_alert', label: '融資急增⚠️', emoji: '🚨', tooltip: '融資餘額單日暴增 ≥ 20%（散戶追價警訊，波段末段信號）',
        conditions: [{ field: 'margin_surge', op: 'is_true', value: true }],
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
  { label: '上市日期',   key: 'listing_date',            group: '基本', defaultVisible: false },
  { label: '資本額',     key: 'capital_stock',           group: '基本', defaultVisible: false },
  { label: '發行股數',   key: 'shares',                  group: '基本', defaultVisible: false },
  { label: '公司網站',   key: 'website',                 group: '基本', defaultVisible: false },
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
  { label: '月營收備註', key: 'revenue_note',           group: '月營收', defaultVisible: false },
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
  { label: '存貨周轉',  key: 'inventory_turnover',      group: '財報', defaultVisible: false },
  { label: '本業獲利%', key: 'core_profit_ratio',        group: '財報', defaultVisible: false },
  { label: 'ROE品質',   key: 'roe_quality',              group: '財報', defaultVisible: false },
  // 籌碼
  { label: '外資連續天', key: 'foreign_consecutive_days', group: '籌碼', defaultVisible: false },
  { label: '融資(張)',   key: 'margin_long',              group: '籌碼', defaultVisible: false },
  { label: '融資增幅%', key: 'margin_long_chg_pct',      group: '籌碼', defaultVisible: false },
  { label: '融券(張)',  key: 'margin_short',              group: '籌碼', defaultVisible: false },
  // 股利
  { label: '除息日',     key: 'ex_dividend_date',        group: '股利', defaultVisible: false },
  { label: '現金股利',   key: 'cash_dividend',           group: '股利', defaultVisible: false },
  { label: '每股股利',   key: 'dividend_per_share',      group: '股利', defaultVisible: false },
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

// ─── 大盤指數型別 ──────────────────────────────────────────────────────────────

interface MarketIndex {
  name: string
  code: string
  price: number | null
  change: number | null
  change_pct: number | null
}

// ─── 總體經濟指標型別 ──────────────────────────────────────────────────────────

interface MacroIndicator {
  name: string
  code: string
  price: number | null
  change: number | null
  change_pct: number | null
  unit?: string
  hint?: string
  link?: string
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

  // ── Screener 狀態（symbol 白名單篩選） ────────────────────────────────────
  const [screenerMap, setScreenerMap] = useState<Map<QuickFilterKey, Set<string>>>(new Map())
  const [screenerLoading, setScreenerLoading] = useState(false)

  const fetchScreenerResults = useCallback(async (key: QuickFilterKey, endpoint: string) => {
    setScreenerLoading(true)
    try {
      const res = await fetch(`${API_URL}/v1/stocks/screener/${endpoint}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const symbols: string[] = data.symbols || []

      // 更新 screenerMap
      const nextMap = new Map(screenerMap)
      nextMap.set(key, new Set(symbols))
      setScreenerMap(nextMap)

      // 計算所有 screener 的交集
      let intersection: string[] = symbols
      for (const [k, symbolSet] of nextMap.entries()) {
        if (k === key) continue
        intersection = intersection.filter(s => symbolSet.has(s))
      }

      // 直接用 symbols 撈後端，不依賴本地分頁的 stocks 陣列
      if (intersection.length > 0) {
        const symbolsParam = intersection.join(',')
        const r2 = await fetch(`${API_URL}/v1/stocks?symbols=${encodeURIComponent(symbolsParam)}&limit=500`)
        if (r2.ok) {
          const d2 = await r2.json()
          setStocks(d2.stocks || [])
          setTotal(d2.total || d2.stocks?.length || 0)
        }
      } else {
        setStocks([])
        setTotal(0)
      }
    } catch (e) {
      console.error(`screener ${endpoint} failed:`, e)
    }
    setScreenerLoading(false)
  }, [screenerMap])

  // ── 大盤指數 ──────────────────────────────────────────────────────────────
  const [marketIndices, setMarketIndices] = useState<MarketIndex[]>([])
  const [indicesLoading, setIndicesLoading] = useState(true)

  useEffect(() => {
    const fetchIndices = async () => {
      setIndicesLoading(true)
      try {
        const res = await fetch(`${API_URL}/v1/market/indices`)
        if (res.ok) {
          const data = await res.json()
          setMarketIndices(data.indices || [])
        }
      } catch {}
      setIndicesLoading(false)
    }
    fetchIndices()
    // 每 60 秒刷新一次
    const timer = setInterval(fetchIndices, 60_000)
    return () => clearInterval(timer)
  }, [])

  // ── 七大面向說明頁開關 ────────────────────────────────────────────────────
  const [showGuide, setShowGuide] = useState(false)

  // ── 總體經濟指標 ──────────────────────────────────────────────────────────
  const [macroIndicators, setMacroIndicators] = useState<MacroIndicator[]>([])
  const [macroLoading, setMacroLoading] = useState(true)

  useEffect(() => {
    const fetchMacro = async () => {
      setMacroLoading(true)
      try {
        const res = await fetch(`${API_URL}/v1/market/macro`)
        if (res.ok) {
          const data = await res.json()
          setMacroIndicators(data.indicators || [])
        }
      } catch {}
      setMacroLoading(false)
    }
    fetchMacro()
    // 每 5 分鐘刷新一次（總體數據變動頻率低）
    const timer = setInterval(fetchMacro, 300_000)
    return () => clearInterval(timer)
  }, [])

  // ── 月營收歷史 Sparkline ──────────────────────────────────────────────────
  interface RevenuePoint { year_month: string; revenue_yoy: number | null; revenue_mom: number | null }
  const [sparkData, setSparkData] = useState<Map<string, RevenuePoint[]>>(new Map())

  const fetchRevenueHistory = useCallback(async (symbol: string) => {
    if (sparkData.has(symbol)) return
    try {
      const res = await fetch(`${API_URL}/v1/stocks/${symbol}/revenue-history?months=6`)
      if (res.ok) {
        const data = await res.json()
        setSparkData(prev => new Map(prev).set(symbol, data.history || []))
      }
    } catch {}
  }, [sparkData])

  const renderSparkline = (points: RevenuePoint[]) => {
    if (!points || points.length < 2) return null
    const vals = points.map(p => p.revenue_yoy ?? 0)
    const min = Math.min(...vals, 0)
    const max = Math.max(...vals, 0)
    const range = max - min || 1
    const w = 56, h = 22, pad = 2
    const x = (i: number) => pad + (i / (vals.length - 1)) * (w - pad * 2)
    const y = (v: number) => h - pad - ((v - min) / range) * (h - pad * 2)
    const pts = vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
    const lastVal = vals[vals.length - 1]
    const color = lastVal > 0 ? '#51cf66' : lastVal < 0 ? '#ff6b6b' : '#aaa'
    const zeroY = y(0)
    return (
      <svg width={w} height={h} style={{ display: 'inline-block', verticalAlign: 'middle' }}>
        {min < 0 && max > 0 && (
          <line x1={pad} y1={zeroY} x2={w - pad} y2={zeroY} stroke="rgba(255,255,255,0.1)" strokeWidth={0.5} />
        )}
        <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={x(vals.length - 1)} cy={y(lastVal)} r={2.5} fill={color} />
      </svg>
    )
  }

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
    sby?: string,
    sdir?: 'asc' | 'desc',
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
          + (market ? `&market_type=${encodeURIComponent(market)}` : '')
          + (sector ? `&sector=${encodeURIComponent(sector)}` : '')
        if (sby) base += `&sort_by=${sby}&sort_order=${sdir ?? 'desc'}`
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
    fetchStocks(newPage, '', marketFilter, sectorFilter, getActiveConditions(activeFilters), sortKey || undefined, sortDir)
    window.scrollTo(0, 0)
  }

  const handleQuickFilter = (key: QuickFilterKey) => {
    const def = ALL_FILTERS.find(f => f.key === key)
    if (!def || def.disabled) return

    const screenerEndpoint = SCREENER_ENDPOINT_MAP[key]
    const isScreenerKey = !!screenerEndpoint

    setActiveFilters(prev => {
      const next = new Set(prev)
      if (next.has(key)) {
        // 取消：移除篩選，若是 screener key 也清掉 map 裡的 set
        next.delete(key)
        if (isScreenerKey) {
          setScreenerMap(sm => {
            const nsm = new Map(sm)
            nsm.delete(key)
            return nsm
          })
        }
      } else {
        next.add(key)
        // 若是 screener key，非同步呼叫 screener API
        if (isScreenerKey) {
          fetchScreenerResults(key, screenerEndpoint!)
        }
      }
      // 一般 conditions（高存貨周轉率本身也有 conditions，照常傳給後端）
      const conditions = getActiveConditions(next)
      setPage(1)
      setSearchTerm('')
      setSortKey('')
      fetchStocks(1, '', marketFilter, sectorFilter, conditions)
      return next
    })
  }

  const handleClearFilter = (key: QuickFilterKey) => {
    if (SCREENER_ENDPOINT_MAP[key]) {
      setScreenerMap(sm => { const nsm = new Map(sm); nsm.delete(key); return nsm })
    }
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
    setScreenerMap(new Map())
    setActiveFilters(new Set())
    setPage(1)
    fetchStocks(1, '', marketFilter, sectorFilter, [])
  }

  const handleSort = (key: string) => {
    const newDir = sortKey === key ? (sortDir === 'asc' ? 'desc' : 'asc') : 'desc'
    const newKey = key
    setSortKey(newKey)
    setSortDir(newDir)
    setPage(1)
    fetchStocks(1, searchTerm, marketFilter, sectorFilter, getActiveConditions(activeFilters), newKey, newDir)
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
      case 'symbol': return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
          <span style={{ color: '#f90', fontWeight: 600 }}>{s.symbol}</span>
          <span style={{ display: 'inline-flex', gap: '3px' }}>
            <a href={`https://tw.tradingview.com/chart/?symbol=TWSE%3A${s.symbol}`} target="_blank" rel="noreferrer"
              title="TradingView 技術面" style={{ fontSize: '0.65rem', padding: '1px 5px', background: 'rgba(56,139,253,0.15)', color: '#6ea8fe', border: '1px solid rgba(56,139,253,0.25)', borderRadius: '3px', textDecoration: 'none', lineHeight: 1.5 }}>TV</a>
            <a href={`https://goodinfo.tw/tw/StockInfo.asp?STOCK_ID=${s.symbol}`} target="_blank" rel="noreferrer"
              title="Goodinfo 基本面" style={{ fontSize: '0.65rem', padding: '1px 5px', background: 'rgba(81,207,102,0.15)', color: '#69db7c', border: '1px solid rgba(81,207,102,0.25)', borderRadius: '3px', textDecoration: 'none', lineHeight: 1.5 }}>GI</a>
            <a href={`https://mops.twse.com.tw/mops/web/t05st09?STK_NO=${s.symbol}`} target="_blank" rel="noreferrer"
              title="MOPS 公開資訊觀測站" style={{ fontSize: '0.65rem', padding: '1px 5px', background: 'rgba(255,193,7,0.15)', color: '#ffd43b', border: '1px solid rgba(255,193,7,0.25)', borderRadius: '3px', textDecoration: 'none', lineHeight: 1.5 }}>MO</a>
          </span>
        </span>
      )
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
      case 'revenue_yoy': {
        const history = sparkData.get(s.symbol)
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}
            onMouseEnter={() => fetchRevenueHistory(s.symbol)}>
            <span style={{ color: yoyColor(s.revenue_yoy) }}>{fmt(s.revenue_yoy)}</span>
            {history && history.length >= 2 && renderSparkline(history)}
          </span>
        )
      }
      case 'revenue_mom':  return <span style={{ color: yoyColor(s.revenue_mom) }}>{fmt(s.revenue_mom)}</span>
      case 'revenue_note': return <span style={{ color: '#aaa', fontSize: '0.8rem', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }} title={s.revenue_note ?? ''}>{s.revenue_note ?? '—'}</span>
      case 'foreign_net_buy':         return <span style={{ color: instColor(s.foreign_net_buy) }}>{fmtInt(s.foreign_net_buy)}</span>
      case 'investment_trust_net_buy':return <span style={{ color: instColor(s.investment_trust_net_buy) }}>{fmtInt(s.investment_trust_net_buy)}</span>
      case 'dealer_net_buy':          return <span style={{ color: instColor(s.dealer_net_buy) }}>{fmtInt(s.dealer_net_buy)}</span>
      case 'gross_margin':    return <span style={{ color: '#ccc' }}>{fmt(s.gross_margin)}</span>
      case 'operating_margin':return <span style={{ color: '#ccc' }}>{fmt(s.operating_margin)}</span>
      case 'net_margin':      return <span style={{ color: '#ccc' }}>{fmt(s.net_margin)}</span>
      case 'roe':             return <span style={{ color: '#ccc' }}>{fmt(s.roe)}</span>
      case 'roa':             return <span style={{ color: '#ccc' }}>{fmt(s.roa)}</span>
      case 'debt_ratio':          return <span style={{ color: '#ccc' }}>{fmt(s.debt_ratio)}</span>
      case 'inventory_turnover':  return <span style={{ color: s.inventory_turnover != null && Number(s.inventory_turnover) >= 4 ? '#51cf66' : '#ccc' }}>{s.inventory_turnover != null ? fmt(s.inventory_turnover, 1) + ' 次' : '--'}</span>
      case 'core_profit_ratio': {
        const v = s.core_profit_ratio != null ? Number(s.core_profit_ratio) : null
        const color = v == null ? '#aaa' : v >= 80 ? '#51cf66' : v >= 60 ? '#ffd43b' : '#ff6b6b'
        return <span style={{ color }}>{v != null ? v.toFixed(1) + '%' : '--'}</span>
      }
      case 'roe_quality': return (
        s.roe_quality
          ? <span style={{ fontSize: '0.75rem', padding: '2px 7px', background: 'rgba(255,215,0,0.15)', color: '#ffd43b', border: '1px solid rgba(255,215,0,0.3)', borderRadius: '4px' }}>🏆品質</span>
          : <span style={{ color: '#444' }}>--</span>
      )
      case 'foreign_consecutive_days': {
        const d = s.foreign_consecutive_days
        if (d == null) return <span style={{ color: '#444' }}>--</span>
        const isBuy = d > 0
        const abs = Math.abs(d)
        const intensity = Math.min(abs / 10, 1)
        const baseColor = isBuy ? `rgba(81,207,102,${0.3 + intensity * 0.7})` : `rgba(255,107,107,${0.3 + intensity * 0.7})`
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px', padding: '2px 7px', background: isBuy ? 'rgba(81,207,102,0.12)' : 'rgba(255,107,107,0.12)', borderRadius: '4px', color: baseColor, fontWeight: abs >= 5 ? 700 : 400, fontSize: '0.83rem' }}>
            {isBuy ? '▲' : '▼'}{abs}天
          </span>
        )
      }
      case 'margin_long': {
        const surge = s.margin_surge
        return (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ color: s.margin_long != null && s.margin_long > 0 ? '#ffc107' : '#aaa' }}>{fmtInt(s.margin_long)}</span>
            {surge && <span style={{ fontSize: '0.68rem', padding: '1px 5px', background: 'rgba(255,107,107,0.2)', color: '#ff6b6b', border: '1px solid rgba(255,107,107,0.4)', borderRadius: '3px' }}>急增⚠</span>}
          </span>
        )
      }
      case 'margin_long_chg_pct': {
        const v = s.margin_long_chg_pct != null ? Number(s.margin_long_chg_pct) : null
        const isSurge = v != null && v >= 20
        return <span style={{ color: v == null ? '#aaa' : isSurge ? '#ff6b6b' : v > 0 ? '#ffc107' : '#51cf66', fontWeight: isSurge ? 700 : 400 }}>{v != null ? (v > 0 ? '+' : '') + v.toFixed(1) + '%' : '--'}</span>
      }
      case 'margin_short':    return <span style={{ color: s.margin_short != null && s.margin_short > 0 ? '#ff6b6b' : '#aaa' }}>{fmtInt(s.margin_short)}</span>
      case 'ex_dividend_date':   return <span style={{ color: '#51cf66', fontSize: '0.83rem' }}>{s.ex_dividend_date || '--'}</span>
      case 'cash_dividend':      return <span style={{ color: '#51cf66' }}>{fmt(s.cash_dividend, 2)}</span>
      case 'dividend_per_share': return <span style={{ color: '#51cf66' }}>{fmt(s.dividend_per_share, 2)}</span>
      case 'listing_date':       return <span style={{ color: '#aaa', fontSize: '0.83rem' }}>{s.listing_date || '--'}</span>
      case 'capital_stock':      return <span style={{ color: '#ccc' }}>{s.capital_stock != null ? (s.capital_stock / 1e8).toFixed(2) + ' 億' : '--'}</span>
      case 'shares':             return <span style={{ color: '#ccc' }}>{s.shares != null ? (s.shares / 1e3).toLocaleString() + ' 千' : '--'}</span>
      case 'website':            return s.website ? <a href={s.website} target="_blank" rel="noreferrer" style={{ color: '#6495ed', fontSize: '0.82rem' }}>官網</a> : <span style={{ color: '#555' }}>--</span>
      default:                   return '--'
    }
  }

  // screener 白名單：多個 screener 結果取交集（AND 邏輯）
  const displayedStocks = screenerMap.size === 0
    ? stocks
    : stocks.filter(s => {
        for (const symbolSet of screenerMap.values()) {
          if (!symbolSet.has(s.symbol)) return false
        }
        return true
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
      <header className="app-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div>
          <h1>🚀 台股觀測站</h1>
          <p>台灣股票市場監測和投資組合管理平台</p>
        </div>
        <button
          onClick={() => setShowGuide(g => !g)}
          style={{
            padding: '7px 16px',
            background: showGuide ? 'rgba(255,153,0,0.2)' : 'rgba(255,255,255,0.08)',
            color: showGuide ? '#f90' : '#aaa',
            border: `1px solid ${showGuide ? 'rgba(255,153,0,0.4)' : 'rgba(255,255,255,0.15)'}`,
            borderRadius: '8px', cursor: 'pointer', fontSize: '0.85rem',
          }}>
          📖 選股七大面向
        </button>
      </header>

      <main className="app-main">

        {/* ── 七大面向說明頁 ── */}
        {showGuide && (
          <div style={{ marginBottom: '1.5rem', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,153,0,0.2)', borderRadius: '12px', padding: '1.25rem 1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <span style={{ color: '#f90', fontWeight: 600, fontSize: '1rem' }}>主動選股七大面向指南</span>
              <span style={{ color: '#555', fontSize: '0.78rem' }}>建立多維度確認系統・提高勝率</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.75rem' }}>
              {[
                { num: '1', title: '基本面', subtitle: '看錢怎麼賺、流去哪', color: '#51cf66', items: ['ROE 連續 3 年 > 15%（效率，非槓桿虛胖）', '自由現金流長期為正（造血能力）', '本業收入佔比 > 80%（EPS 純度）', '利息保障倍數 > 個位數（還債底氣）', '營益率走勢向上（裡子，照妖鏡）'], sources: ['MOPS', 'Goodinfo', 'CMoney', '財報狗'] },
                { num: '2', title: '技術面', subtitle: '找買點，抓趨勢', color: '#6495ed', items: ['MACD 背離判斷動能衰竭', '布林通道找極端進場點', '均線多頭排列，縮量拉回買', '帶量突破壓力區'], sources: ['TradingView', 'XQ全球贏家', 'CMoney K線'] },
                { num: '3', title: '籌碼面', subtitle: '看主力動向', color: '#ffd43b', items: ['籌碼集中度上升＋家數差為負', '大股東持股穩定增加', '特定分點券商節奏追蹤', '外資連續 2-3 週買超趨勢'], sources: ['Goodinfo', 'CMoney 籌碼K線', '玩股網'] },
                { num: '4', title: '總體經濟面', subtitle: '決定持股水位', color: '#cc5de8', items: ['景氣燈號：綠燈↑ 藍燈↓（上方儀表板）', '美債10Y：快速升壓縮本益比（上方）', 'VIX 恐慌指數：極端值是撿屍機會（上方）', '台幣匯率：升值代表外資流入（上方）'], sources: ['國發會', 'Investing.com', 'TradingView', '央行'] },
                { num: '5', title: '產業面', subtitle: '找領先訊號', color: '#ff922b', items: ['存貨周轉天數↓代表需求強勁', 'BB Ratio > 1 半導體訂單擴張', '合約負債逐季上升（在手訂單能見度）', '月營收年增率連續 3-6 月趨勢（本站 Sparkline）', '龍頭先動才是真循環'], sources: ['MOPS', 'Goodinfo', 'SEMI 官網', '財報狗'] },
                { num: '6', title: '市場情緒與資金面', subtitle: '反向指標是好朋友', color: '#f03e3e', items: ['融資暴增 = 散戶追價，波段末段警訊（本站⚠️）', '融資斷頭殺出 = 籌碼清洗機會', '外資連續 2-3 週買超趨勢（本站▲▼天）', '外資買超但大盤不漲 = 內資倒貨警惕'], sources: ['Goodinfo', 'CMoney', 'TWSE'] },
                { num: '7', title: '風控', subtitle: '活下來最重要', color: '#868e96', items: ['跌破買進理由，立刻砍單', '研究越深越危險：反問「誰在賣給我？」', '停損紀律 > 部位控管 > 風報比', '90% 指數（0050）+ 10% 個股配置'], sources: [] },
              ].map(dim => (
                <div key={dim.num} style={{ background: 'rgba(255,255,255,0.04)', border: `1px solid rgba(255,255,255,0.08)`, borderRadius: '10px', padding: '0.85rem 1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                    <span style={{ width: '22px', height: '22px', borderRadius: '50%', background: dim.color + '33', border: `1px solid ${dim.color}66`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.72rem', color: dim.color, fontWeight: 700, flexShrink: 0 }}>{dim.num}</span>
                    <span style={{ color: dim.color, fontWeight: 600, fontSize: '0.9rem' }}>{dim.title}</span>
                    <span style={{ color: '#555', fontSize: '0.73rem' }}>{dim.subtitle}</span>
                  </div>
                  <ul style={{ margin: 0, paddingLeft: '14px', listStyle: 'none' }}>
                    {dim.items.map((item, i) => (
                      <li key={i} style={{ fontSize: '0.77rem', color: '#888', lineHeight: 1.6, paddingLeft: '6px', position: 'relative' }}>
                        <span style={{ position: 'absolute', left: '-6px', color: dim.color + '88' }}>•</span>
                        {item}
                      </li>
                    ))}
                  </ul>
                  {dim.sources.length > 0 && (
                    <div style={{ marginTop: '8px', fontSize: '0.7rem', color: '#444' }}>
                      資料來源：{dim.sources.join('・')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── 大盤指數顯示專區 ── */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '0.75rem',
          marginBottom: '1.25rem',
        }}>
          {indicesLoading
            ? [1,2,3,4].map(i => (
                <div key={i} style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '12px', padding: '16px 20px',
                  display: 'flex', flexDirection: 'column', gap: '6px',
                  minHeight: '90px', animation: 'pulse 1.5s infinite',
                }} />
              ))
            : marketIndices.map((idx) => {
                const isUp = (idx.change ?? 0) > 0
                const isDown = (idx.change ?? 0) < 0
                const color = isUp ? '#4ade80' : isDown ? '#f87171' : '#9ca3af'
                const bgColor = isUp
                  ? 'rgba(74,222,128,0.07)'
                  : isDown ? 'rgba(248,113,113,0.07)' : 'rgba(255,255,255,0.04)'
                const sign = isUp ? '+' : ''
                return (
                  <div key={idx.code} style={{
                    background: bgColor,
                    border: `1px solid ${isUp ? 'rgba(74,222,128,0.2)' : isDown ? 'rgba(248,113,113,0.2)' : 'rgba(255,255,255,0.08)'}`,
                    borderRadius: '12px', padding: '16px 20px',
                    display: 'flex', flexDirection: 'column', gap: '4px',
                  }}>
                    <div style={{ fontSize: '0.78rem', color: '#9ca3af', fontWeight: 500, letterSpacing: '0.02em' }}>
                      {idx.name}
                    </div>
                    <div style={{ fontSize: '1.65rem', fontWeight: 700, color: '#fff', letterSpacing: '-0.02em', lineHeight: 1.1 }}>
                      {idx.price != null ? idx.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '---'}
                    </div>
                    <div style={{ fontSize: '0.88rem', color, fontWeight: 600 }}>
                      {idx.change != null
                        ? `${sign}${idx.change.toFixed(2)}　${sign}${idx.change_pct?.toFixed(2)}%`
                        : '---'}
                    </div>
                  </div>
                )
              })
          }
        </div>

        {/* ── 總體經濟儀表板 ── */}
        <div style={{ marginBottom: '1.25rem' }}>
          <div style={{ fontSize: '0.73rem', color: '#555', marginBottom: '0.5rem', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>📊 總體經濟面</span>
            <span style={{ color: '#444' }}>—</span>
            <span style={{ color: '#444' }}>決定持股水位的四大參考指標</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem' }}>
            {macroLoading
              ? [1,2,3,4].map(i => (
                  <div key={i} style={{
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.06)',
                    borderRadius: '12px', padding: '14px 18px',
                    minHeight: '82px', animation: 'pulse 1.5s infinite',
                  }} />
                ))
              : macroIndicators.map((ind) => {
                  const isBCSI = ind.code === 'BCSI'
                  const isUSDTWD = ind.code === 'USDTWD'
                  const chg = ind.change ?? 0
                  // 台幣匯率：數值下降（台幣升值）= 利多 → 綠色
                  const isPositive = isUSDTWD ? chg < 0 : chg > 0
                  const isNegative = isUSDTWD ? chg > 0 : chg < 0
                  const color = isBCSI ? '#9ca3af' : isPositive ? '#4ade80' : isNegative ? '#f87171' : '#9ca3af'
                  const borderColor = isBCSI ? 'rgba(255,255,255,0.08)' : isPositive ? 'rgba(74,222,128,0.2)' : isNegative ? 'rgba(248,113,113,0.2)' : 'rgba(255,255,255,0.08)'
                  const bgColor = isBCSI ? 'rgba(255,255,255,0.03)' : isPositive ? 'rgba(74,222,128,0.06)' : isNegative ? 'rgba(248,113,113,0.06)' : 'rgba(255,255,255,0.03)'
                  const sign = (ind.change ?? 0) > 0 ? '+' : ''
                  const decimals = ind.code === 'USDTWD' ? 3 : ind.code === 'US10Y' ? 3 : 2
                  return (
                    <div key={ind.code} style={{
                      background: bgColor,
                      border: `1px solid ${borderColor}`,
                      borderRadius: '12px', padding: '14px 18px',
                      display: 'flex', flexDirection: 'column', gap: '4px',
                    }}>
                      <div style={{ fontSize: '0.75rem', color: '#9ca3af', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '4px' }}>
                        {ind.name}
                        {ind.unit && !isBCSI && (
                          <span style={{ opacity: 0.5, fontSize: '0.68rem' }}>({ind.unit})</span>
                        )}
                      </div>
                      {isBCSI ? (
                        <>
                          <div style={{ fontSize: '0.82rem', color: '#555', margin: '2px 0' }}>每月更新，點擊查看</div>
                          {ind.link && (
                            <a href={ind.link} target="_blank" rel="noreferrer"
                              style={{ fontSize: '0.8rem', color: '#6495ed', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '3px' }}>
                              🔗 國發會景氣燈號 →
                            </a>
                          )}
                        </>
                      ) : (
                        <>
                          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#fff', lineHeight: 1.15 }}>
                            {ind.price != null ? ind.price.toFixed(decimals) : '---'}
                          </div>
                          <div style={{ fontSize: '0.82rem', color, fontWeight: 600 }}>
                            {ind.change != null
                              ? `${sign}${ind.change.toFixed(decimals)}　${sign}${ind.change_pct?.toFixed(2)}%`
                              : '---'}
                          </div>
                        </>
                      )}
                      {ind.hint && (
                        <div style={{ fontSize: '0.7rem', color: '#444', marginTop: '1px' }}>{ind.hint}</div>
                      )}
                    </div>
                  )
                })
            }
          </div>
        </div>

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

        {/* ── Screener 載入提示 ── */}
        {screenerLoading && (
          <div style={{ color: '#aaa', padding: '6px 12px', marginBottom: '6px', background: 'rgba(124,58,237,0.08)', border: '1px solid rgba(124,58,237,0.2)', borderRadius: '6px', fontSize: '0.83rem' }}>
            ⏳ 正在從篩選器載入符合條件的股票名單…
          </div>
        )}

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
              <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: '0.9rem', background: 'rgba(255,255,255,0.03)', borderRadius: '8px' }}>
                <thead>
                  <tr style={{ background: '#1e1e38' }}>
                    {visibleCols.map(({ label, key }) => {
                      const isSymbol = key === 'symbol'
                      const isName   = key === 'name'
                      const stickyStyle: React.CSSProperties = isSymbol
                        ? { position: 'sticky', left: 0, zIndex: 3, background: '#1e1e38', minWidth: 130, boxShadow: isName ? undefined : '2px 0 4px rgba(0,0,0,0.4)' }
                        : isName
                        ? { position: 'sticky', left: 130, zIndex: 3, background: '#1e1e38', minWidth: 100, boxShadow: '2px 0 4px rgba(0,0,0,0.4)' }
                        : {}
                      return (
                        <th key={key} onClick={() => handleSort(key)}
                          title="點擊排序（僅限本頁）"
                          style={{ padding: '10px 12px', textAlign: isSymbol || isName ? 'left' : 'right', whiteSpace: 'nowrap', fontWeight: 500, cursor: 'pointer', userSelect: 'none', color: sortKey === key ? '#f90' : '#ccc', borderBottom: '1px solid rgba(255,255,255,0.08)', ...stickyStyle }}>
                          {label} {sortKey === key ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                        </th>
                      )
                    })}
                  </tr>
                </thead>
                <tbody>
                  {displayedStocks.length === 0 && (
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
                  {displayedStocks.map((s, i) => {
                    const rowBg = i % 2 === 0 ? '#16213e' : '#1a1a32'
                    return (
                      <tr key={s.symbol} style={{ background: rowBg }}>
                        {visibleCols.map(({ key }) => {
                          const isSymbol = key === 'symbol'
                          const isName   = key === 'name'
                          const stickyStyle: React.CSSProperties = isSymbol
                            ? { position: 'sticky', left: 0, zIndex: 2, background: rowBg, boxShadow: '2px 0 4px rgba(0,0,0,0.3)' }
                            : isName
                            ? { position: 'sticky', left: 130, zIndex: 2, background: rowBg, boxShadow: '2px 0 4px rgba(0,0,0,0.3)' }
                            : {}
                          return (
                            <td key={key} style={{ padding: '8px 12px', textAlign: isSymbol || isName || key === 'market_type' || key === 'sector' ? 'left' : 'right', borderBottom: '1px solid rgba(255,255,255,0.05)', whiteSpace: 'nowrap', ...stickyStyle }}>
                              {renderCell(s, key)}
                            </td>
                          )
                        })}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>


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
