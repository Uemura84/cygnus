/**
 * Step 4 — Margin Trajectory: dual y-axis.
 * Left axis  (-10% to 40%): Gross Margin + EBIT Margin
 * Right axis (60% to 100%): COGS / Revenue %
 *
 * Props: data — array of { period, Gross_Margin_pct, EBIT_Margin_pct, COGS_pct_Revenue }
 *        labels — { grossMargin, ebitMargin, cogsRevenue, breakeven } i18n strings
 */
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ReferenceLine, ResponsiveContainer,
} from 'recharts'

export default function MarginTrajectory({ data, labels = {} }) {
  if (!data?.length) return null
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 8, right: 64, bottom: 8, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
        <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }} />

        {/* Left axis: Gross + EBIT Margin */}
        <YAxis
          yAxisId="margins"
          unit="%"
          domain={[-10, 40]}
          tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }}
          tickCount={6}
        />
        {/* Right axis: COGS / Revenue */}
        <YAxis
          yAxisId="cogs"
          orientation="right"
          unit="%"
          domain={[60, 100]}
          tick={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }}
          tickCount={5}
        />

        <Tooltip formatter={(v) => `${v?.toFixed(1)}%`} />
        <Legend />

        {/* Breakeven at 0% on left axis */}
        <ReferenceLine
          yAxisId="margins"
          y={0}
          stroke="rgba(11,31,58,0.2)"
          strokeDasharray="4 2"
          strokeWidth={1}
          label={{
            value: labels.breakeven ?? 'Breakeven',
            position: 'insideBottomRight',
            fontSize: 9,
            fill: 'rgba(11,31,58,0.2)',
          }}
        />

        <Line
          yAxisId="margins"
          type="monotone"
          dataKey="Gross_Margin_pct"
          name={labels.grossMargin ?? 'Gross Margin %'}
          stroke="#2E86C1"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
        <Line
          yAxisId="margins"
          type="monotone"
          dataKey="EBIT_Margin_pct"
          name={labels.ebitMargin ?? 'EBIT Margin %'}
          stroke="rgba(46,134,193,0.55)"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
        <Line
          yAxisId="cogs"
          type="monotone"
          dataKey="COGS_pct_Revenue"
          name={labels.cogsRevenue ?? 'COGS / Revenue %'}
          stroke="rgba(192,57,43,0.65)"
          strokeWidth={2.5}
          dot={{ r: 3 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
