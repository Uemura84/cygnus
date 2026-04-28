import { useState, useMemo } from 'react'
import {
  ResponsiveContainer,
  LineChart, Line, Area,
  BarChart, Bar, Cell,
  ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from 'recharts'

// ─── Cygnus chart palette ─────────────────────────────────────────────────────
const FINANCIAL_BLUE      = '#2E86C1'
const FINANCIAL_BLUE_70   = 'rgba(46,134,193,0.70)'
const FINANCIAL_BLUE_55   = 'rgba(46,134,193,0.55)'
const NAVY_50             = 'rgba(11,31,58,0.50)'
const COST_RED            = 'rgba(192,57,43,0.65)'  // costs, expenses, negative values
import { useI18n } from '../App'
import RevenueCOGSGrowth from '../components/charts/RevenueCOGSGrowth'
import WaterfallChart from '../components/charts/WaterfallChart'
import RunStepButton from '../components/RunStepButton'
import styles from './Step.module.css'

// ─── Formatting helpers ───────────────────────────────────────────────────────

function fmt(v, isYoY) {
  if (v == null) return '—'
  const prefix = isYoY && v > 0 ? '+' : ''
  return prefix + v.toFixed(1) + '%'
}

function shortPeriod(p) {
  return p ? p.slice(0, 4) : p
}

function fmtK(v) {
  if (v == null) return '—'
  const abs = Math.abs(v)
  if (abs >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M'
  if (abs >= 1_000) return (v / 1_000).toFixed(0) + 'K'
  return v.toFixed(0)
}

function fmtBrlM(v) {
  if (v == null) return '—'
  const m = v / 1000
  const abs = Math.abs(m)
  if (abs >= 1000) return (m / 1000).toFixed(1) + 'B'
  if (abs >= 1) return m.toFixed(0) + 'M'
  return m.toFixed(1) + 'M'
}

// ─── Bridge helpers ───────────────────────────────────────────────────────────

/** Auto-detect BRL scale from bridge data (values in BRL thousands). */
function bridgeScale(bridgeData) {
  const vals = bridgeData.map(d => Math.abs(d.value ?? 0)).filter(v => isFinite(v))
  const maxK = vals.length ? Math.max(...vals) : 0
  return maxK / 1000 >= 1000
    ? { divisor: 1_000_000, unit: ' B' }
    : { divisor: 1_000,     unit: ' M' }
}

/** Translate backend bridge label keys → display strings. */
function bridgeLabel(key, t) {
  if (key.startsWith('peak_'))     return `${t.step4.bridge_peak ?? 'Peak'} (${key.slice(5)})`
  if (key.startsWith('current_'))  return `${t.step4.bridge_current ?? 'Current'} (${key.slice(8)})`
  if (key.startsWith('total_va_')) return `Total VA (${key.slice(9)})`
  return t.step4[`bridge_${key}`] ?? key.replace(/_/g, ' ')
}

/**
 * Convert backend bridge object to WaterfallChart data array.
 * Optionally scales BRL-thousands values by divisor.
 */
function buildWaterfallData(bridge, t, divisor = 1) {
  if (!bridge || bridge.start_value == null) return null
  const items = [
    { name: bridgeLabel(bridge.start_label, t), value: bridge.start_value / divisor, type: 'total' },
    ...bridge.factors.map(f => ({
      name:  t.step4[`bridge_${f.name}`] ?? f.name.replace(/_/g, ' '),
      value: f.value / divisor,
      type:  'change',
    })),
    { name: bridgeLabel(bridge.end_label, t), value: bridge.end_value / divisor, type: 'total' },
  ]
  // If start OR end is null (cash bridge with no BS data), filter those out
  return items.filter(item => item.value != null && !isNaN(item.value))
}

// ─── Table row definitions ────────────────────────────────────────────────────

const ROWS = [
  { key: 'Revenue_YoY_pct',   labelKey: 'revenue_yoy_label',   descKey: 'revenue_yoy_desc',   isYoY: true },
  { key: 'COGS_YoY_pct',      labelKey: 'cogs_yoy_label',      descKey: 'cogs_yoy_desc',      isYoY: true },
  { key: 'Gross_Margin_pct',  labelKey: 'gross_margin_label',  descKey: 'gross_margin_desc',  isYoY: false },
  { key: 'EBIT_Margin_pct',   labelKey: 'ebit_margin_label',   descKey: 'ebit_margin_desc',   isYoY: false },
  { key: 'EBITDA_Margin_pct', labelKey: 'ebitda_margin_label', descKey: 'ebitda_margin_desc', isYoY: false },
  { key: 'COGS_pct_Revenue',  labelKey: 'cogs_revenue_label',  descKey: 'cogs_revenue_desc',  isYoY: false },
  { key: 'SGA_pct_Revenue',   labelKey: 'sga_revenue_label',   descKey: 'sga_revenue_desc',   isYoY: false },
]

const BS_TABLE_ROWS = [
  { key: 'debt_to_ebitda',   labelKey: 'debt_to_ebitda_label',   descKey: 'debt_to_ebitda_desc',   fmt: v => v != null ? v.toFixed(2) + '×' : '—' },
  { key: 'current_ratio',    labelKey: 'current_ratio_label',    descKey: 'current_ratio_desc',    fmt: v => v != null ? v.toFixed(2) + '×' : '—' },
  { key: 'quick_ratio',      labelKey: 'quick_ratio_label',      descKey: 'quick_ratio_desc',      fmt: v => v != null ? v.toFixed(2) + '×' : '—' },
  { key: 'return_on_assets', labelKey: 'return_on_assets_label', descKey: 'return_on_assets_desc', fmt: v => v != null ? v.toFixed(1) + '%' : '—' },
  { key: 'return_on_equity', labelKey: 'return_on_equity_label', descKey: 'return_on_equity_desc', fmt: v => v != null ? v.toFixed(1) + '%' : '—' },
  { key: 'net_debt',         labelKey: 'net_debt_brlm_label',    descKey: 'net_debt_brlm_desc',    fmt: fmtBrlM },
]

const CF_TABLE_ROWS = [
  { key: 'operating_cash_flow', labelKey: 'ocf_label',              descKey: 'ocf_desc',              fmt: fmtBrlM },
  { key: 'free_cash_flow',      labelKey: 'fcf_brlm_label',         descKey: 'fcf_brlm_desc',         fmt: fmtBrlM },
  { key: 'ocf_to_net_income',   labelKey: 'ocf_to_ni_label',        descKey: 'ocf_to_ni_desc',        fmt: v => v != null ? v.toFixed(2) + '×' : '—' },
  { key: 'capex_to_revenue',    labelKey: 'capex_to_revenue_label', descKey: 'capex_to_revenue_desc', fmt: v => v != null ? v.toFixed(1) + '%' : '—' },
]

const DVA_TABLE_ROWS = [
  { key: 'total_to_distribute', labelKey: 'dva_total_label',        fmt: fmtBrlM },
  { key: 'employees',           labelKey: 'dva_employees_label',    fmt: fmtBrlM },
  { key: 'government',          labelKey: 'dva_government_label',   fmt: fmtBrlM },
  { key: 'lenders',             labelKey: 'dva_lenders_label',      fmt: fmtBrlM },
  { key: 'shareholders',        labelKey: 'dva_shareholders_label', fmt: fmtBrlM },
]

// ─── Shared sub-components ────────────────────────────────────────────────────

function MetricTable({ rows, data, t }) {
  if (!data?.length) return null
  return (
    <div style={{ overflowX: 'auto', marginBottom: 16 }}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>{t.step4.table_metric_header ?? 'Metric'}</th>
            {data.map(r => (
              <th key={r.period} style={{ textAlign: 'right' }}>{shortPeriod(r.period)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ key, labelKey, descKey, fmt }) => (
            <tr key={key}>
              <td style={{ whiteSpace: 'nowrap' }}>
                {descKey
                  ? <span className={styles.tooltip} data-tooltip={t.step4[descKey]}>{t.step4[labelKey]}</span>
                  : (t.step4[labelKey] ?? key)
                }
              </td>
              {data.map(r => (
                <td key={r.period} style={{ textAlign: 'right', fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.85rem' }}>
                  {fmt(r[key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Numbered section header with an analytical question and optional LLM headline. */
function SectionHeader({ number, question, headline }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 20, marginTop: 36 }}>
      <span style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 28,
        fontWeight: 700,
        color: '#0e8f9a',
        lineHeight: 1,
        flexShrink: 0,
      }}>{number}</span>
      <div>
        <div style={{
          fontFamily: "'IBM Plex Sans', sans-serif",
          fontSize: 20,
          fontWeight: 700,
          color: 'var(--navy)',
          lineHeight: 1.2,
        }}>{question}</div>
        {headline && (
          <div style={{
            fontFamily: "'IBM Plex Sans', sans-serif",
            fontSize: '0.82rem',
            color: 'var(--gray)',
            marginTop: 4,
            fontStyle: 'italic',
          }}>{headline}</div>
        )}
      </div>
    </div>
  )
}

/** Collapsible wrapper — hides content behind a toggle. */
function CollapsibleSection({ label, children }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginTop: 12 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          background: 'none',
          border: '1px solid rgba(11,31,58,0.15)',
          borderRadius: 6,
          padding: '5px 14px',
          fontSize: '0.78rem',
          fontFamily: "'IBM Plex Mono', monospace",
          color: 'var(--gray)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <span style={{ transition: 'transform 0.2s', display: 'inline-block', transform: open ? 'rotate(90deg)' : 'none' }}>▶</span>
        {label}
      </button>
      {open && <div style={{ marginTop: 8 }}>{children}</div>}
    </div>
  )
}

// ─── DVA chart helpers ────────────────────────────────────────────────────────

// Stack order bottom → top: Employees, Government, Shareholders, Lenders
// Shareholders sit adjacent to zero so their positive↔negative swing reads continuously.
const DVA_FIELDS = [
  { orig: 'employees',    pct: 'employees_share_pct',    pos: 'employees_pos',    neg: 'employees_neg',    labelKey: 'dva_employees_label',    color: '#2E86C1' },
  { orig: 'government',   pct: 'government_share_pct',   pos: 'government_pos',   neg: 'government_neg',   labelKey: 'dva_government_label',   color: '#EF9F27' },
  { orig: 'shareholders', pct: 'shareholders_share_pct', pos: 'shareholders_pos', neg: 'shareholders_neg', labelKey: 'dva_shareholders_label', color: '#7EC8E3' },
  { orig: 'lenders',      pct: 'lenders_share_pct',      pos: 'lenders_pos',      neg: 'lenders_neg',      labelKey: 'dva_lenders_label',      color: '#0b1f3a' },
]

function detectDvaScale(series) {
  let maxAbsK = 0
  for (const r of series) {
    for (const { orig } of DVA_FIELDS) {
      const v = r[orig]
      if (v != null) maxAbsK = Math.max(maxAbsK, Math.abs(v))
    }
  }
  return maxAbsK / 1000 >= 1000
    ? { divisor: 1_000_000, unit: ' B' }
    : { divisor: 1_000,     unit: ' M' }
}

function DvaDistributionTooltip({ active, payload, label, t, scale }) {
  if (!active || !payload?.length) return null
  const data = payload[0]?.payload
  return (
    <div style={{ background: '#fff', border: '1px solid rgba(11,31,58,0.12)', borderRadius: 6, padding: '8px 12px', fontSize: 12, fontFamily: "'IBM Plex Sans', sans-serif" }}>
      <div style={{ fontWeight: 700, marginBottom: 4, color: 'var(--navy)' }}>{label}</div>
      {DVA_FIELDS.map(({ orig, pct, labelKey }) => {
        const brl = data?.[orig]
        const pctVal = data?.[pct]
        if (brl == null) return null
        const pctStr = pctVal != null ? ` (${pctVal.toFixed(1)}%)` : ''
        return (
          <div key={orig} style={{ color: 'var(--charcoal)' }}>
            {t.step4[labelKey] ?? labelKey}:{' '}
            <strong>{brl.toFixed(1)}{scale.unit}</strong>
            <span style={{ color: 'var(--gray)', fontSize: 11 }}>{pctStr}</span>
          </div>
        )
      })}
    </div>
  )
}

// ─── Section-specific chart components ───────────────────────────────────────

function LiquidityChart({ data, interp, t }) {
  return (
    <div className={styles.chartCard}>
      <h4 className={styles.chartTitle}>{t.step4.chart_liquidity_title}</h4>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
          <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <YAxis tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <Tooltip formatter={v => v != null ? v.toFixed(2) : '—'} />
          <Legend />
          <ReferenceLine y={1} stroke="rgba(192,57,43,0.65)" strokeWidth={1.5} strokeDasharray="4 3"
            label={{ value: '1.0×', position: 'right', fontSize: 10, fill: 'rgba(192,57,43,0.65)', fontFamily: "'IBM Plex Mono', monospace" }}
          />
          <Line type="monotone" dataKey="current_ratio" name={t.step4.current_ratio_label} stroke={FINANCIAL_BLUE}    dot strokeWidth={2} connectNulls />
          <Line type="monotone" dataKey="quick_ratio"   name={t.step4.quick_ratio_label}   stroke={FINANCIAL_BLUE_55} dot strokeWidth={2} connectNulls />
        </LineChart>
      </ResponsiveContainer>
      {interp.liquidity && <p className={styles.chartCaption}>{interp.liquidity}</p>}
    </div>
  )
}

function NetDebtChart({ data, interp, t }) {
  return (
    <div className={styles.chartCard}>
      <h4 className={styles.chartTitle}>{t.step4.chart_net_debt_title}</h4>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 20, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
          <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <YAxis tickFormatter={fmtK} tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <Tooltip formatter={v => v != null ? fmtK(v) : '—'} />
          <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" />
          <Bar dataKey="net_debt" name={t.step4.net_debt_label} fill={NAVY_50}
            label={{
              position: 'top',
              formatter: v => v != null ? fmtBrlM(v) : '',
              fontSize: 9,
              fontFamily: "'IBM Plex Mono', monospace",
              fill: 'var(--charcoal)',
            }}
          />
        </BarChart>
      </ResponsiveContainer>
      {interp.net_debt && <p className={styles.chartCaption}>{interp.net_debt}</p>}
    </div>
  )
}

function WorkingCapitalChart({ data, tsData, interp, t }) {
  const INVENTORY_BLUE = 'rgba(46,134,193,0.50)'
  const PAYABLES_RED   = 'rgba(192,57,43,0.65)'

  const chartData = data.map(r => {
    const yr = (r.period || '').slice(0, 4)
    const tsRow = (tsData || []).find(t => (t.period || '').slice(0, 4) === yr)
    const rev = tsRow?.revenue_abs
    const wcRevPct = (r.working_capital != null && rev) ? (r.working_capital / rev * 100) : null
    return {
      period: r.period,
      ar: r.accounts_receivable,
      inventory: r.inventories,
      ap_neg: r.accounts_payable != null ? -r.accounts_payable : null,
      wc: r.working_capital,
      wc_neg: r.working_capital != null && r.working_capital < 0 ? r.working_capital : 0,
      wc_rev_pct: wcRevPct,
    }
  })

  // WC/Revenue with prior-period comparison
  const latest = chartData[chartData.length - 1]
  const prior  = chartData.length >= 3 ? chartData[chartData.length - 3] : null
  let wcRevLine = null
  if (latest?.wc_rev_pct != null) {
    const label = t.step4.wc_to_revenue ?? 'WC / Revenue'
    let str = `${label}: ${latest.wc_rev_pct >= 0 ? '+' : ''}${latest.wc_rev_pct.toFixed(1)}%`
    if (prior?.wc_rev_pct != null) {
      str += `  (was ${prior.wc_rev_pct >= 0 ? '+' : ''}${prior.wc_rev_pct.toFixed(1)}% in ${prior.period})`
    }
    wcRevLine = str
  }

  const tickStyle = { fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }

  return (
    <div className={styles.chartCard}>
      <h4 className={styles.chartTitle}>{t.step4.chart_working_capital_title}</h4>
      {wcRevLine && (
        <p style={{
          fontSize: 11, fontFamily: "'IBM Plex Mono', monospace",
          color: '#475569', fontWeight: 600, margin: '0 0 4px 0',
        }}>
          {wcRevLine}
        </p>
      )}

      {/* ── Top panel: Net WC line ── */}
      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={chartData} margin={{ top: 12, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
          <XAxis dataKey="period" tick={tickStyle} hide />
          <YAxis tickFormatter={v => fmtBrlM(v)} tick={tickStyle} />
          <Tooltip formatter={v => v != null ? fmtBrlM(v) : '—'} />
          <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" />
          <Area
            type="monotone" dataKey="wc_neg" fill="rgba(192,57,43,0.08)"
            stroke="none" baseLine={0} isAnimationActive={false}
          />
          <Line
            type="monotone" dataKey="wc"
            name={t.step4.working_capital_label ?? 'Net WC'}
            stroke="#0b1f3a" strokeWidth={3}
            dot={{ r: 4, fill: '#0b1f3a', stroke: '#fff', strokeWidth: 2 }}
            connectNulls
            label={({ x, y, index, value }) => {
              if (index !== chartData.length - 1 || value == null) return null
              return (
                <text
                  x={x} y={value < 0 ? y + 16 : y - 10}
                  textAnchor="middle" fontSize={10} fontWeight="bold"
                  fontFamily="'IBM Plex Mono', monospace" fill="#0b1f3a"
                >
                  {fmtBrlM(value)}
                </text>
              )
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* ── Bottom panel: Component decomposition ── */}
      <ResponsiveContainer width="100%" height={140}>
        <BarChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
          <XAxis dataKey="period" tick={tickStyle} />
          <YAxis tickFormatter={v => fmtBrlM(v)} tick={tickStyle} />
          <Tooltip formatter={(v, name) => {
            const abs = v != null ? fmtBrlM(Math.abs(v)) : '—'
            return name === (t.step4.ap_label ?? 'Payables') ? `−${abs}` : abs
          }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" />
          <Bar dataKey="ar"        name={t.step4.ar_label ?? 'Receivables'} stackId="pos" fill={FINANCIAL_BLUE} />
          <Bar dataKey="inventory" name={t.step4.inventory_label ?? 'Inventory'} stackId="pos" fill={INVENTORY_BLUE} />
          <Bar dataKey="ap_neg"    name={t.step4.ap_label ?? 'Payables'} stackId="neg" fill={PAYABLES_RED} />
        </BarChart>
      </ResponsiveContainer>

      {interp.working_capital && <p className={styles.chartCaption}>{interp.working_capital}</p>}
    </div>
  )
}

function ROAChart({ data, interp, t }) {
  return (
    <div className={styles.chartCard}>
      <h4 className={styles.chartTitle}>{t.step4.chart_roa_title}</h4>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
          <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <YAxis unit="%" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <Tooltip formatter={v => v != null ? v.toFixed(1) + '%' : '—'} />
          <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" strokeDasharray="4 4" />
          <Line type="monotone" dataKey="return_on_assets" name={t.step4.return_on_assets_label} stroke={FINANCIAL_BLUE} dot strokeWidth={2} connectNulls />
        </LineChart>
      </ResponsiveContainer>
      {interp.roa && <p className={styles.chartCaption}>{interp.roa}</p>}
    </div>
  )
}

// ─── FRE Debt Maturity Chart ──────────────────────────────────────────────────

const BUCKET_KEYS   = ['lt_1yr', 'yr_1_2', 'yr_2_3', 'yr_3_5', 'gt_5yr', 'undetermined']
const BUCKET_COLORS = [
  'rgba(192,57,43,0.75)',   // lt_1yr  — red (urgent)
  'rgba(211,84,0,0.65)',    // yr_1_2  — orange
  FINANCIAL_BLUE_70,           // yr_2_3
  FINANCIAL_BLUE_55,           // yr_3_5
  'rgba(14,143,154,0.30)',  // gt_5yr  — light blue
  'rgba(11,31,58,0.15)',    // undetermined — grey
]

function DebtMaturityChart({ maturity, t }) {
  if (!maturity) return null

  const chartData = BUCKET_KEYS.map((k, i) => ({
    bucket: t.step4[`bucket_${k}`] ?? k,
    amount: maturity.buckets[k]?.amount ?? 0,
    pct:    maturity.buckets[k]?.pct ?? 0,
    color:  BUCKET_COLORS[i],
  })).filter(r => r.amount > 0)

  const periodLabel = (t.step4.fre_data_period ?? 'FRE {year}').replace('{year}', maturity.reference_period)
  const showWarning = maturity.near_term_pct > 40

  return (
    <div className={styles.chartCard}>
      <h4 className={styles.chartTitle}>
        {t.step4.chart_debt_maturity_title ?? 'Debt Maturity Profile (FRE)'}
        <span style={{ fontSize: '0.72rem', fontFamily: "'IBM Plex Mono', monospace", color: 'var(--gray)', fontWeight: 400, marginLeft: '8px' }}>
          {periodLabel}
        </span>
      </h4>
      {showWarning && (
        <div style={{ display: 'inline-block', background: 'rgba(192,57,43,0.10)', border: '1px solid rgba(192,57,43,0.35)', borderRadius: '4px', padding: '2px 8px', marginBottom: '10px', fontSize: '0.75rem', fontFamily: "'IBM Plex Sans', sans-serif", fontWeight: 600, color: 'rgba(192,57,43,0.9)' }}>
          {t.step4.annotation_refinancing ?? 'Refinancing concentration'} — {maturity.near_term_pct}%
        </div>
      )}
      <ResponsiveContainer width="100%" height={Math.max(120, chartData.length * 36 + 20)}>
        <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 60, left: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" horizontal={false} />
          <XAxis type="number" tickFormatter={fmtK} tick={{ fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" }} />
          <YAxis type="category" dataKey="bucket" width={56} tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <Tooltip formatter={(v, _n, props) => [`${fmtBrlM(v)}  (${props.payload?.pct}%)`, '']} />
          <Bar dataKey="amount" radius={[0, 3, 3, 0]}
            label={{ position: 'right', formatter: v => fmtBrlM(v), fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", fill: 'var(--charcoal)' }}
          >
            {chartData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ─── FRE Debt Currency Chart ──────────────────────────────────────────────────

const CURRENCY_COLORS = [FINANCIAL_BLUE, FINANCIAL_BLUE_70, FINANCIAL_BLUE_55, 'rgba(11,31,58,0.30)']

function DebtCurrencyChart({ currency, t }) {
  if (!currency) return null

  const chartData = Object.entries(currency.currencies).map(([cur, info], i) => ({
    currency: cur,
    amount:   info.amount,
    pct:      info.pct,
    color:    CURRENCY_COLORS[i] ?? CURRENCY_COLORS[CURRENCY_COLORS.length - 1],
  }))

  const periodLabel = (t.step4.fre_data_period ?? 'FRE {year}').replace('{year}', currency.reference_period)
  const showWarning = currency.fx_pct > 30

  return (
    <div className={styles.chartCard}>
      <h4 className={styles.chartTitle}>
        {t.step4.chart_debt_currency_title ?? 'Debt by Currency (FRE)'}
        <span style={{ fontSize: '0.72rem', fontFamily: "'IBM Plex Mono', monospace", color: 'var(--gray)', fontWeight: 400, marginLeft: '8px' }}>
          {periodLabel}
        </span>
      </h4>
      {showWarning && (
        <div style={{ display: 'inline-block', background: 'rgba(211,84,0,0.10)', border: '1px solid rgba(211,84,0,0.35)', borderRadius: '4px', padding: '2px 8px', marginBottom: '10px', fontSize: '0.75rem', fontFamily: "'IBM Plex Sans', sans-serif", fontWeight: 600, color: 'rgba(211,84,0,0.9)' }}>
          {t.step4.annotation_fx_exposure ?? 'FX exposure'} — {currency.fx_pct}%
        </div>
      )}
      <ResponsiveContainer width="100%" height={Math.max(80, chartData.length * 36 + 20)}>
        <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 60, left: 8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" horizontal={false} />
          <XAxis type="number" tickFormatter={fmtK} tick={{ fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" }} />
          <YAxis type="category" dataKey="currency" width={36} tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <Tooltip formatter={(v, _n, props) => [`${fmtBrlM(v)}  (${props.payload?.pct}%)`, '']} />
          <Bar dataKey="amount" radius={[0, 3, 3, 0]}
            label={{ position: 'right', formatter: v => fmtBrlM(v), fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", fill: 'var(--charcoal)' }}
          >
            {chartData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ─── FRE Auditor Info Card ────────────────────────────────────────────────────

function AuditorCard({ auditor, t }) {
  if (!auditor) return null

  const total = (auditor.audit_fees ?? 0) + (auditor.non_audit_fees ?? 0)
  const auditPct  = total > 0 ? Math.round((auditor.audit_fees ?? 0) / total * 100) : null
  const otherPct  = total > 0 ? Math.round((auditor.non_audit_fees ?? 0) / total * 100) : null
  const flagRatio = (auditor.non_audit_ratio ?? 0) > 0.5

  return (
    <div className={styles.chartCard}>
      <h4 className={styles.chartTitle}>
        {t.step4.fre_auditor_card_title ?? 'Auditor'}
        <span style={{ fontSize: '0.72rem', fontFamily: "'IBM Plex Mono', monospace", color: 'var(--gray)', fontWeight: 400, marginLeft: '8px' }}>
          {(t.step4.fre_data_period ?? 'FRE {year}').replace('{year}', auditor.period)}
        </span>
      </h4>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '12px', alignItems: 'start' }}>
        {/* Left: firm name + tenure */}
        <div>
          <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontWeight: 600, fontSize: '0.95rem', color: 'var(--navy)', marginBottom: '4px' }}>
            {auditor.firm_name}
          </div>
          <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.78rem', color: 'var(--gray)' }}>
            {t.step4.tenure_years_label ?? 'Tenure'}: <strong style={{ color: 'var(--charcoal)' }}>{auditor.tenure_years} yr</strong>
          </div>
        </div>

        {/* Right: fee ratio indicator */}
        {auditPct != null && (
          <div style={{ textAlign: 'right' }}>
            {flagRatio && (
              <div style={{ fontSize: '0.72rem', fontFamily: "'IBM Plex Sans', sans-serif", fontWeight: 600, color: 'rgba(211,84,0,0.9)', background: 'rgba(211,84,0,0.08)', border: '1px solid rgba(211,84,0,0.25)', borderRadius: '4px', padding: '1px 6px', marginBottom: '6px', whiteSpace: 'nowrap' }}>
                {t.step4.annotation_non_audit ?? 'Non-audit fees > 50% of audit'}
              </div>
            )}
            <div style={{ fontSize: '0.72rem', color: 'var(--gray)', fontFamily: "'IBM Plex Sans', sans-serif", marginBottom: '4px' }}>
              {t.step4.non_audit_ratio_label ?? 'Non-audit ratio'}: <strong style={{ fontFamily: "'IBM Plex Mono', monospace", color: 'var(--charcoal)' }}>{auditor.non_audit_ratio?.toFixed(2)}</strong>
            </div>
          </div>
        )}
      </div>

      {/* Fee bar */}
      {auditPct != null && (
        <div style={{ marginTop: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', fontFamily: "'IBM Plex Sans', sans-serif", color: 'var(--gray)', marginBottom: '4px' }}>
            <span>{t.step4.audit_fees_label ?? 'Audit fees'}: <strong style={{ fontFamily: "'IBM Plex Mono', monospace", color: 'var(--charcoal)' }}>{fmtBrlM(auditor.audit_fees)}</strong></span>
            <span>{t.step4.non_audit_fees_label ?? 'Non-audit fees'}: <strong style={{ fontFamily: "'IBM Plex Mono', monospace", color: 'var(--charcoal)' }}>{fmtBrlM(auditor.non_audit_fees)}</strong></span>
          </div>
          <div style={{ height: '8px', borderRadius: '4px', background: 'rgba(11,31,58,0.07)', overflow: 'hidden', display: 'flex' }}>
            <div style={{ width: `${auditPct}%`, background: FINANCIAL_BLUE, borderRadius: '4px 0 0 4px' }} />
            <div style={{ width: `${otherPct}%`, background: flagRatio ? 'rgba(211,84,0,0.55)' : FINANCIAL_BLUE_55, borderRadius: '0 4px 4px 0' }} />
          </div>
          <div style={{ display: 'flex', gap: '12px', marginTop: '5px', fontSize: '0.68rem', fontFamily: "'IBM Plex Mono', monospace", color: 'var(--gray)' }}>
            <span style={{ color: FINANCIAL_BLUE }}>■ {t.step4.audit_fees_label ?? 'Audit'} {auditPct}%</span>
            <span style={{ color: flagRatio ? 'rgba(211,84,0,0.9)' : FINANCIAL_BLUE_55 }}>■ {t.step4.non_audit_fees_label ?? 'Non-audit'} {otherPct}%</span>
          </div>
        </div>
      )}
    </div>
  )
}

function FCFChart({ data, interp, t }) {
  return (
    <div className={styles.chartCard}>
      <h4 className={styles.chartTitle}>{t.step4.chart_fcf_title}</h4>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={data} margin={{ top: 20, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
          <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <YAxis tickFormatter={fmtK} tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <Tooltip formatter={v => v != null ? fmtK(v) : '—'} />
          <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" />
          <Bar dataKey="free_cash_flow" name={t.step4.fcf_label}
            label={{
              position: 'top',
              formatter: v => v != null ? fmtBrlM(v) : '',
              fontSize: 9,
              fontFamily: "'IBM Plex Mono', monospace",
              fill: 'var(--charcoal)',
            }}
          >
            {data.map((r, i) => (
              <Cell key={i} fill={(r.free_cash_flow ?? 0) >= 0 ? FINANCIAL_BLUE : COST_RED} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
      {interp.fcf && <p className={styles.chartCaption}>{interp.fcf}</p>}
    </div>
  )
}

function CapexChart({ data, interp, t }) {
  return (
    <div className={styles.chartCard}>
      <h4 className={styles.chartTitle}>{t.step4.chart_capex_title}</h4>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
          <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <YAxis yAxisId="left"  unit="%" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <Tooltip />
          <Legend />
          <Bar   yAxisId="left"  dataKey="capex_to_revenue"      name={t.step4.capex_to_revenue_label} fill={FINANCIAL_BLUE} />
          <Line  yAxisId="right" type="monotone" dataKey="capex_to_depreciation" name={t.step4.capex_to_da_label} stroke={FINANCIAL_BLUE_55} dot strokeWidth={2} connectNulls />
        </ComposedChart>
      </ResponsiveContainer>
      {interp.capex && <p className={styles.chartCaption}>{interp.capex}</p>}
    </div>
  )
}

function CashConversionCycleChart({ data, interp, t }) {
  const INVENTORY_BLUE = 'rgba(46,134,193,0.50)'
  const PAYABLES_RED   = 'rgba(192,57,43,0.60)'

  const tickStyle = { fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }

  return (
    <div className={styles.chartCard}>
      <h4 className={styles.chartTitle}>{t.step4.chart_ccc_title}</h4>
      <p style={{
        fontSize: 11, fontFamily: "'IBM Plex Mono', monospace",
        color: '#475569', fontStyle: 'italic', margin: '0 0 4px 0',
      }}>
        {t.step4.ccc_formula ?? 'CCC = Receivable + Inventory \u2212 Payable'}
      </p>

      {/* ── Top panel: CCC line alone ── */}
      <ResponsiveContainer width="100%" height={170}>
        <LineChart data={data} margin={{ top: 12, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
          <XAxis dataKey="period" tick={tickStyle} hide />
          <YAxis tick={tickStyle} domain={['auto', 'auto']} />
          <Tooltip formatter={v => v != null ? v.toFixed(0) + 'd' : '—'} />
          <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" />
          <Line
            type="linear" dataKey="cash_conversion_cycle"
            name={t.step4.ccc_label}
            stroke="#0b1f3a" strokeWidth={3}
            dot={{ r: 4, fill: '#0b1f3a', stroke: '#fff', strokeWidth: 2 }}
            connectNulls
            label={({ x, y, index, value }) => {
              if (value == null) return null
              return (
                <text
                  x={x} y={y - 10}
                  textAnchor="middle" fontSize={9} fontWeight="bold"
                  fontFamily="'IBM Plex Mono', monospace" fill="#0b1f3a"
                >
                  {Math.round(value)}d
                </text>
              )
            }}
          />
        </LineChart>
      </ResponsiveContainer>

      {/* ── Bottom panel: Component lines ── */}
      <ResponsiveContainer width="100%" height={140}>
        <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
          <XAxis dataKey="period" tick={tickStyle} />
          <YAxis tick={tickStyle} />
          <Tooltip formatter={v => v != null ? v.toFixed(0) + 'd' : '—'} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" />
          <Line type="linear" dataKey="receivable_days" name={t.step4.receivable_days_label}
            stroke={FINANCIAL_BLUE} strokeWidth={1.5} connectNulls
            dot={{ r: 3, fill: '#fff', stroke: FINANCIAL_BLUE, strokeWidth: 1 }} />
          <Line type="linear" dataKey="inventory_days" name={t.step4.inventory_days_label}
            stroke={INVENTORY_BLUE} strokeWidth={1.5} connectNulls
            dot={{ r: 3, fill: '#fff', stroke: INVENTORY_BLUE, strokeWidth: 1 }} />
          <Line type="linear" dataKey="payable_days" name={t.step4.payable_days_label}
            stroke={PAYABLES_RED} strokeWidth={1.5} connectNulls
            dot={{ r: 3, fill: '#fff', stroke: PAYABLES_RED, strokeWidth: 1 }} />
        </LineChart>
      </ResponsiveContainer>

      {interp.ccc && <p className={styles.chartCaption}>{interp.ccc}</p>}
    </div>
  )
}

function DvaDistributionChart({ series, t, interp = {} }) {
  if (!series?.length) return null
  const scale  = detectDvaScale(series)
  const hasNeg = series.some(r => DVA_FIELDS.some(f => (r[f.orig] ?? 0) < 0))
  const chartData = series.map(r => {
    const point = { period: shortPeriod(r.period) }
    for (const { orig, pos, neg, pct } of DVA_FIELDS) {
      const raw    = r[orig]
      const scaled = raw != null ? raw / scale.divisor : null
      point[pos]  = scaled != null ? Math.max(0, scaled) : null
      point[neg]  = scaled != null ? Math.min(0, scaled) : null
      point[orig] = scaled
      point[pct]  = r[pct]
    }
    point.total_va = r.total_to_distribute != null ? r.total_to_distribute / scale.divisor : null
    return point
  })
  return (
    <div className={styles.chartCard}>
      <h4 className={styles.chartTitle}>{t.step4.dva_chart_dist_title ?? 'Value Distribution by Stakeholder'}</h4>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={chartData} margin={{ top: 20, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
          <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <YAxis unit={scale.unit} tickFormatter={v => v.toFixed(v % 1 === 0 ? 0 : 1)} tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <Tooltip content={<DvaDistributionTooltip t={t} scale={scale} />} />
          <Legend />
          <ReferenceLine y={0} stroke="rgba(11,31,58,0.25)" strokeWidth={1} />
          {DVA_FIELDS.map(f => (
            <Bar key={f.pos} dataKey={f.pos} name={t.step4[f.labelKey] ?? f.pos} stackId="pos" fill={f.color} />
          ))}
          {hasNeg && [...DVA_FIELDS].reverse().map(f => (
            <Bar key={f.neg} dataKey={f.neg} stackId="neg" fill={f.color} legendType="none" name={f.neg} opacity={0.6} />
          ))}
          <Line
            type="monotone"
            dataKey="total_va"
            name={t.step4.dva_total_label ?? 'Total VA'}
            stroke="rgba(11,31,58,0.70)"
            strokeWidth={2}
            strokeDasharray="4 3"
            dot={{ r: 3, fill: '#0b1f3a' }}
            connectNulls
            legendType="line"
            label={{
              position: 'top',
              formatter: v => v != null ? fmtBrlM(v * scale.divisor) : '',
              fontSize: 9,
              fontFamily: "'IBM Plex Mono', monospace",
              fill: 'rgba(11,31,58,0.70)',
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
      {hasNeg && (
        <p style={{ fontSize: '0.72rem', color: 'var(--gray)', marginTop: '4px', fontStyle: 'italic' }}>
          ▼ {t.step4.dva_neg_note ?? 'Below zero — value absorbed exceeds value created for that stakeholder'}
        </p>
      )}
      {interp.dva_dist && <p className={styles.chartCaption}>{interp.dva_dist}</p>}
    </div>
  )
}

function DvaVaMarginChart({ series, t, interp = {} }) {
  if (!series?.length) return null
  const chartData = series.map(r => ({ period: shortPeriod(r.period), va_margin_pct: r.va_margin_pct }))
  return (
    <div className={styles.chartCard}>
      <h4 className={styles.chartTitle}>{t.step4.dva_chart_va_margin_title ?? 'VA Margin (%)'}</h4>
      <ResponsiveContainer width="100%" height={150}>
        <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
          <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <YAxis unit="%" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />
          <Tooltip formatter={v => v != null ? [v.toFixed(1) + '%', t.step4.dva_va_margin_label ?? 'VA Margin'] : '—'} />
          <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" />
          <Line type="monotone" dataKey="va_margin_pct" name={t.step4.dva_va_margin_label ?? 'VA Margin'} stroke={FINANCIAL_BLUE} dot strokeWidth={2} connectNulls />
        </LineChart>
      </ResponsiveContainer>
      {interp.dva_va_margin && <p className={styles.chartCaption}>{interp.dva_va_margin}</p>}
    </div>
  )
}

// ─── Section 1 charts ─────────────────────────────────────────────────────────

function MarginTrendChart({ data, interp, t }) {
  // Filter to annual rows only and map to short period keys
  const chartData = data
    .filter(r => r.period && r.period.length >= 4)
    .map(r => ({ period: r.period.slice(0, 4), Gross_Margin_pct: r.Gross_Margin_pct, EBIT_Margin_pct: r.EBIT_Margin_pct }))

  if (!chartData.length) return null

  const allVals = chartData.flatMap(r => [r.Gross_Margin_pct, r.EBIT_Margin_pct]).filter(v => v != null)
  const rawMin  = Math.min(...allVals, 0)
  const rawMax  = Math.max(...allVals)
  const pad     = (rawMax - rawMin) * 0.12 || 2
  const yDomain = [Math.floor(rawMin - pad), Math.ceil(rawMax + pad)]

  return (
    <div className={styles.chartCard}>
      <h4 className={styles.chartTitle}>{t.step4.chart_margin_trend_title ?? 'Margin Trend'}</h4>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" vertical={false} />
          <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} tickLine={false} />
          <YAxis domain={yDomain} unit="%" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} tickLine={false} axisLine={false} />
          <Tooltip formatter={v => v != null ? v.toFixed(1) + '%' : '—'} />
          <Legend />
          <ReferenceLine y={0} stroke="rgba(11,31,58,0.25)" strokeDasharray="4 4" strokeWidth={1} />
          <Line type="monotone" dataKey="Gross_Margin_pct" name={t.step4.gross_margin_label} stroke="#2E86C1"         strokeWidth={2} dot connectNulls />
          <Line type="monotone" dataKey="EBIT_Margin_pct"  name={t.step4.ebit_margin_label}  stroke="rgba(46,134,193,0.55)" strokeWidth={2} dot connectNulls />
        </LineChart>
      </ResponsiveContainer>
      {interp.margin_trend && <p className={styles.chartCaption}>{interp.margin_trend}</p>}
    </div>
  )
}


// ─── DRA Table ────────────────────────────────────────────────────────────────

const DRA_ROWS = [
  { key: 'net_income',                 labelKey: 'dra_net_income_label',  fmt: fmtBrlM },
  { key: 'oci_total',                  labelKey: 'dra_oci_label',         fmt: fmtBrlM },
  { key: 'total_comprehensive_income', labelKey: 'dra_total_ci_label',    fmt: fmtBrlM },
  { key: 'comprehensive_income_ratio', labelKey: 'dra_ci_ratio_label',    fmt: v => v != null ? v.toFixed(3) + '×' : '—' },
  { key: 'oci_pct_net_income',         labelKey: 'dra_oci_pct_label',     fmt: v => v != null ? v.toFixed(1) + '%' : '—' },
]

function DraTable({ series, t }) {
  if (!series?.length) return null
  return (
    <div style={{ overflowX: 'auto', marginBottom: 8, marginTop: 12 }}>
      <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--teal)', marginBottom: 8 }}>
        {t.step4.dra_section_title ?? 'Comprehensive Income (DRA)'}
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>{t.step4.table_metric_header ?? 'Metric'}</th>
            {series.map(r => (
              <th key={r.period} style={{ textAlign: 'right' }}>{shortPeriod(r.period)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {DRA_ROWS.map(({ key, labelKey, fmt }) => (
            <tr key={key}>
              <td style={{ whiteSpace: 'nowrap' }}>{t.step4[labelKey] ?? key}</td>
              {series.map(r => (
                <td key={r.period} style={{ textAlign: 'right', fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.85rem' }}>
                  {fmt(r[key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function Step4EBITDADrivers({ stepState, data }) {
  const t = useI18n()
  const d = data?.data

  const bsSeries = d?.balance_sheet_series ?? []
  const cfSeries = d?.cash_flow_series ?? []
  const interp   = d?.chart_interpretations ?? {}
  const headlines = d?.section_headlines ?? {}

  const bsData = bsSeries.filter(r => r.granularity === 'annual').map(r => ({ ...r, period: shortPeriod(r.period) }))
  const cfData = cfSeries.filter(r => r.granularity === 'annual').map(r => ({ ...r, period: shortPeriod(r.period) }))

  // Bridge chart data — built once, scaled to BRL B or M as needed
  const marginBridgeData = useMemo(() => {
    const b = d?.margin_bridge
    if (!b) return null
    const items = buildWaterfallData(b, t, 1)  // already in %
    return items?.length >= 3 ? items : null
  }, [d?.margin_bridge, t])

  const equityBridgeData = useMemo(() => {
    const b = d?.equity_bridge
    if (!b) return null
    const sc = bridgeScale([
      { value: b.start_value ?? 0 },
      { value: b.end_value ?? 0 },
      ...b.factors,
    ])
    const items = buildWaterfallData(b, t, sc.divisor)
    return items?.length >= 2 ? { items, unit: sc.unit } : null
  }, [d?.equity_bridge, t])

  const cashflowBridgeData = useMemo(() => {
    const b = d?.cashflow_bridge
    if (!b || b.start_value == null || b.end_value == null) return null
    const sc = bridgeScale([
      { value: b.start_value },
      { value: b.end_value },
      ...b.factors,
    ])
    const items = buildWaterfallData(b, t, sc.divisor)
    return items?.length >= 2 ? { items, unit: sc.unit } : null
  }, [d?.cashflow_bridge, t])

  const dvaBridgeData = useMemo(() => {
    const b = d?.dva_bridge
    if (!b) return null
    const sc = bridgeScale([
      { value: b.start_value ?? 0 },
      { value: b.end_value ?? 0 },
      ...b.factors,
    ])
    const items = buildWaterfallData(b, t, sc.divisor)
    return items?.length >= 2 ? { items, unit: sc.unit } : null
  }, [d?.dva_bridge, t])

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step4.title}</h2>
      <p className={styles.description}>{t.step4.description}</p>

      <RunStepButton step={4} />

      {stepState === 'running' && (
        <div className={styles.running}>{t.step4.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>
          {/* ══════════════════════════════════════════════════════════
               SECTION 1 — Is This Company Profitable?
          ══════════════════════════════════════════════════════════ */}
          <SectionHeader
            number="1"
            question={t.step4.section1_question ?? 'Is This Company Profitable?'}
            headline={headlines.section1}
          />
          <div className={styles.section}>
            {/* Profitability metrics table */}
            <div style={{ overflowX: 'auto', marginBottom: 16 }}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left' }}>{t.step4.table_title}</th>
                    {d.time_series.map(row => (
                      <th key={row.period} style={{ textAlign: 'right' }}>{row.period.slice(0, 4)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map(({ key, labelKey, descKey, isYoY }) => (
                    <tr key={key}>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <span className={styles.tooltip} data-tooltip={t.step4[descKey]}>{t.step4[labelKey]}</span>
                      </td>
                      {d.time_series.map(row => (
                        <td key={row.period} style={{ textAlign: 'right', fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.85rem' }}>
                          {fmt(row[key], isYoY)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Margin Trend — 2 lines: Gross Margin % and EBIT Margin % */}
            <MarginTrendChart data={d.time_series} interp={interp} t={t} />

            {/* Revenue vs COGS (absolute BRL) */}
            <div className={styles.chartCard}>
              <h4 className={styles.chartTitle}>{t.step4.chart_growth_title}</h4>
              <RevenueCOGSGrowth
                data={d.time_series}
                labels={{
                  revenue:     t.step4.revenue_abs_label  ?? 'Revenue',
                  cogs:        t.step4.cogs_abs_label     ?? 'COGS',
                  grossProfit: t.step4.gross_profit_label ?? 'Gross Profit',
                }}
              />
              {interp.revenue_cogs_growth && <p className={styles.chartCaption}>{interp.revenue_cogs_growth}</p>}
            </div>

            {/* Margin Bridge */}
            {marginBridgeData && (
              <div className={styles.chartCard}>
                <h4 className={styles.chartTitle}>{t.step4.chart_margin_bridge_title ?? 'Margin Bridge: Peak → Current'}</h4>
                <WaterfallChart data={marginBridgeData} unit="%" height={280} />
                {interp.margin_bridge && <p className={styles.chartCaption}>{interp.margin_bridge}</p>}
              </div>
            )}
          </div>

          {/* ══════════════════════════════════════════════════════════
               SECTION 2 — Can It Survive?
          ══════════════════════════════════════════════════════════ */}
          <SectionHeader
            number="2"
            question={t.step4.section2_question ?? 'Can It Survive?'}
            headline={headlines.section2}
          />
          <div className={styles.section}>
            {bsData.length === 0 ? (
              <p style={{ color: 'var(--gray)', fontSize: '0.875rem' }}>{t.step4.bs_unavailable}</p>
            ) : (
              <>
                <MetricTable rows={BS_TABLE_ROWS} data={bsData} t={t} />
                <LiquidityChart    data={bsData} interp={interp} t={t} />
                <NetDebtChart      data={bsData} interp={interp} t={t} />
                <DebtMaturityChart maturity={d.fre_debt_maturity} t={t} />
                <DebtCurrencyChart currency={d.fre_debt_currency} t={t} />
                <AuditorCard       auditor={d.fre_auditor_card}   t={t} />
                <WorkingCapitalChart data={bsData} tsData={d.time_series} interp={interp} t={t} />
                <CashConversionCycleChart data={bsData} interp={interp} t={t} />
                <ROAChart          data={bsData} interp={interp} t={t} />
              </>
            )}

            {/* Equity Bridge from DMPL */}
            {equityBridgeData && (
              <div className={styles.chartCard}>
                <h4 className={styles.chartTitle}>
                  {t.step4.chart_equity_bridge_title
                    ? t.step4.chart_equity_bridge_title.replace('{year}', d.equity_bridge?.year ?? '')
                    : `Equity Bridge (${d.equity_bridge?.year ?? ''})`}
                </h4>
                <WaterfallChart data={equityBridgeData.items} unit={equityBridgeData.unit} height={280} />
                {interp.equity_bridge && <p className={styles.chartCaption}>{interp.equity_bridge}</p>}
              </div>
            )}

            {/* DRA Comprehensive Income table */}
            {d.dra_series?.length > 0 && <DraTable series={d.dra_series} t={t} />}
          </div>

          {/* ══════════════════════════════════════════════════════════
               SECTION 3 — Does It Generate Cash?
          ══════════════════════════════════════════════════════════ */}
          <SectionHeader
            number="3"
            question={t.step4.section3_question ?? 'Does It Generate Cash?'}
            headline={headlines.section3}
          />
          <div className={styles.section}>
            {cfData.length === 0 ? (
              <p style={{ color: 'var(--gray)', fontSize: '0.875rem' }}>{t.step4.cf_unavailable}</p>
            ) : (
              <>
                <MetricTable rows={CF_TABLE_ROWS} data={cfData} t={t} />

                {/* Cash Flow Bridge (replaces O/I/F grouped bar) */}
                {cashflowBridgeData ? (
                  <div className={styles.chartCard}>
                    <h4 className={styles.chartTitle}>
                      {t.step4.chart_cf_bridge_title
                        ? t.step4.chart_cf_bridge_title.replace('{year}', d.cashflow_bridge?.year ?? '')
                        : `Cash Flow Bridge (${d.cashflow_bridge?.year ?? ''})`}
                    </h4>
                    <WaterfallChart data={cashflowBridgeData.items} unit={cashflowBridgeData.unit} height={280} />
                    {interp.cf_bridge && <p className={styles.chartCaption}>{interp.cf_bridge}</p>}
                  </div>
                ) : null}

                <FCFChart   data={cfData} interp={interp} t={t} />
                <CapexChart data={cfData} interp={interp} t={t} />

                {/* CCC chart moved to Section 2 alongside Working Capital */}
              </>
            )}
          </div>

          {/* ══════════════════════════════════════════════════════════
               SECTION 4 — Who Captures the Value?
          ══════════════════════════════════════════════════════════ */}
          {d.dva_series?.length > 0 && (
            <>
              <SectionHeader
                number="4"
                question={t.step4.section4_question ?? 'Who Captures the Value?'}
                headline={headlines.section4}
              />
              <div className={styles.section}>
                {/* DVA distribution table */}
                <div style={{ overflowX: 'auto', marginBottom: 16 }}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: 'left' }}>{t.step4.table_metric_header ?? 'Metric'}</th>
                        {d.dva_series.map(r => (
                          <th key={r.period} style={{ textAlign: 'right' }}>{shortPeriod(r.period)}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {DVA_TABLE_ROWS.map(({ key, labelKey, fmt }) => (
                        <tr key={key}>
                          <td style={{ whiteSpace: 'nowrap' }}>{t.step4[labelKey] ?? key}</td>
                          {d.dva_series.map(r => (
                            <td key={r.period} style={{ textAlign: 'right', fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.85rem' }}>
                              {fmt(r[key])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <DvaDistributionChart series={d.dva_series} t={t} interp={interp} />

                {/* Value Distribution Bridge */}
                {dvaBridgeData && (
                  <div className={styles.chartCard}>
                    <h4 className={styles.chartTitle}>{t.step4.chart_dva_bridge_title ?? 'Value Distribution Bridge: Peak → Current'}</h4>
                    <WaterfallChart data={dvaBridgeData.items} unit={dvaBridgeData.unit} height={280} />
                    {interp.dva_bridge && <p className={styles.chartCaption}>{interp.dva_bridge}</p>}
                  </div>
                )}

                <DvaVaMarginChart series={d.dva_series} t={t} interp={interp} />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
