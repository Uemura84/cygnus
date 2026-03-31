/**
 * Step 4 — Revenue vs. COGS YoY growth bar chart with divergence indicator.
 * A thin third bar shows the gap (Revenue YoY − COGS YoY):
 *   green = revenue outpaced COGS (good)
 *   red   = COGS grew faster than revenue (bad)
 *
 * COGS sign convention: positive = costs increased (backend uses abs()).
 * So gap = Revenue_YoY_pct − COGS_YoY_pct:
 *   positive → revenue grew faster (green)
 *   negative → COGS grew faster   (red)
 *
 * Props: data — array of { period, Revenue_YoY_pct, COGS_YoY_pct }
 *        labels — { revenue, cogs, divergenceGap, stickiness } i18n strings
 */
import {
  BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine, ResponsiveContainer,
} from 'recharts'

export default function RevenueCOGSGrowth({ data, labels = {} }) {
  const base = data?.filter((d) => d.Revenue_YoY_pct != null) ?? []
  if (!base.length) return null

  // Compute divergence gap per period
  const chartData = base.map((d) => ({
    ...d,
    Gap_pct:
      d.Revenue_YoY_pct != null && d.COGS_YoY_pct != null
        ? +(d.Revenue_YoY_pct - d.COGS_YoY_pct).toFixed(1)
        : null,
  }))

  // Find 2022 row for "cost stickiness" annotation
  const row2022 = chartData.find((d) => d.period?.startsWith('2022'))
  const stickLabel =
    row2022 && row2022.COGS_YoY_pct != null && row2022.Revenue_YoY_pct != null
      ? `${labels.stickiness ?? 'Cost stickiness'} — COGS ${row2022.COGS_YoY_pct >= 0 ? '+' : ''}${row2022.COGS_YoY_pct.toFixed(1)}%, Rev ${row2022.Revenue_YoY_pct.toFixed(1)}%`
      : null

  return (
    <ResponsiveContainer width="100%" height={290}>
      <BarChart data={chartData} margin={{ top: 36, right: 24, bottom: 8, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="period" tick={{ fontSize: 11 }} />
        <YAxis unit="%" tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v) => `${v?.toFixed(1)}%`} />
        <Legend />
        <ReferenceLine y={0} stroke="#94a3b8" />

        {/* Cost stickiness annotation on the 2022 bars */}
        {stickLabel && row2022?.period && (
          <ReferenceLine
            x={row2022.period}
            stroke="#f59e0b"
            strokeDasharray="3 2"
            strokeWidth={1.5}
            label={{
              value: stickLabel,
              position: 'top',
              fontSize: 8.5,
              fill: '#b45309',
              offset: 8,
            }}
          />
        )}

        <Bar
          dataKey="Revenue_YoY_pct"
          name={labels.revenue ?? 'Revenue YoY %'}
          fill="#3b82f6"
          radius={[3, 3, 0, 0]}
        />
        <Bar
          dataKey="COGS_YoY_pct"
          name={labels.cogs ?? 'COGS YoY %'}
          fill="#ef4444"
          radius={[3, 3, 0, 0]}
        />

        {/* Divergence gap: thin bars colored by direction */}
        <Bar
          dataKey="Gap_pct"
          name={labels.divergenceGap ?? 'Gap'}
          maxBarSize={8}
          radius={[2, 2, 0, 0]}
        >
          {chartData.map((entry, i) => (
            <Cell
              key={i}
              fill={
                entry.Gap_pct == null
                  ? 'transparent'
                  : entry.Gap_pct >= 0
                  ? '#16a34a'
                  : '#dc2626'
              }
              fillOpacity={0.75}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
