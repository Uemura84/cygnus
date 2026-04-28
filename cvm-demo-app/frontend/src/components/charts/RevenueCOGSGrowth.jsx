/**
 * Step 4 — Revenue vs. COGS (absolute BRL amounts).
 *
 * Two bars per year: Revenue (Signal Blue) and COGS (Signal Blue 50%).
 * The gap between them is gross profit — narrows → margin compression.
 * A line traces gross profit (gap) to make the compression undeniable.
 *
 * Props:
 *   data   — array of { period, revenue_abs, cogs_abs } (BRL thousands)
 *   labels — { revenue, cogs, grossProfit, stickiness } i18n strings
 */
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine, ResponsiveContainer,
} from 'recharts'

// Auto-scale BRL thousands → B or M
function detectScale(data) {
  let maxK = 0
  for (const r of data) {
    if (r.revenue_abs != null) maxK = Math.max(maxK, r.revenue_abs)
    if (r.cogs_abs    != null) maxK = Math.max(maxK, r.cogs_abs)
  }
  return maxK / 1000 >= 1000
    ? { divisor: 1_000_000, suffix: 'B' }
    : { divisor: 1_000,     suffix: 'M' }
}

function fmtBrl(v, scale) {
  if (v == null) return '—'
  const scaled = v / scale.divisor
  return `R$${Math.abs(scaled).toFixed(1)}${scale.suffix}`
}

export default function RevenueCOGSGrowth({ data, labels = {} }) {
  const base = data?.filter(r => r.revenue_abs != null) ?? []
  if (!base.length) return null

  const scale = detectScale(base)

  const chartData = base.map(r => ({
    period:      r.period?.slice(0, 4) ?? r.period,
    revenue:     r.revenue_abs != null ? r.revenue_abs / scale.divisor : null,
    cogs:        r.cogs_abs    != null ? r.cogs_abs    / scale.divisor : null,
    gross_profit: (r.revenue_abs != null && r.cogs_abs != null)
      ? (r.revenue_abs - r.cogs_abs) / scale.divisor
      : null,
    // Keep raw BRL-K values for tooltip
    _rev_raw:  r.revenue_abs,
    _cogs_raw: r.cogs_abs,
  }))

  const tickFmt = v => {
    const abs = Math.abs(v)
    if (abs >= 100) return v.toFixed(0) + scale.suffix
    if (abs >= 10)  return v.toFixed(1) + scale.suffix
    return v.toFixed(2) + scale.suffix
  }

  return (
    <ResponsiveContainer width="100%" height={290}>
      <ComposedChart data={chartData} margin={{ top: 48, right: 24, bottom: 8, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" vertical={false} />
        <XAxis
          dataKey="period"
          tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={tickFmt}
          tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          formatter={(v, name, props) => {
            const r = props.payload
            if (name === (labels.grossProfit ?? 'Gross Profit')) {
              return [fmtBrl(v * scale.divisor, scale), name]
            }
            if (name === (labels.revenue ?? 'Revenue')) return [fmtBrl(r._rev_raw,  scale), name]
            if (name === (labels.cogs    ?? 'COGS'))    return [fmtBrl(r._cogs_raw, scale), name]
            return [v != null ? v.toFixed(2) + scale.suffix : '—', name]
          }}
        />
        <Legend />
        <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" />

<Bar dataKey="revenue" name={labels.revenue ?? 'Revenue'} fill="#2E86C1"             radius={[3, 3, 0, 0]}
          label={{ position: 'top', formatter: v => v != null ? fmtBrl(v * scale.divisor, scale) : '', fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", fill: '#2E86C1' }}
        />
        <Bar dataKey="cogs"    name={labels.cogs    ?? 'COGS'}    fill="rgba(192,57,43,0.65)" radius={[3, 3, 0, 0]}
          label={{ position: 'top', formatter: v => v != null ? fmtBrl(v * scale.divisor, scale) : '', fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", fill: 'rgba(192,57,43,0.85)' }}
        />

        {/* Gross profit gap line — compression becomes visually undeniable */}
        <Line
          type="monotone"
          dataKey="gross_profit"
          name={labels.grossProfit ?? 'Gross Profit'}
          stroke="#0b1f3a"
          strokeWidth={2}
          dot={{ r: 3, fill: '#0b1f3a' }}
          connectNulls
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
