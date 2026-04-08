/**
 * Step 6 — Supporting chart for a single finding, with pattern-specific annotations.
 * Props: finding — finding object with pattern, metric, data_points, period
 *        timeSeries — array of { period, [metric]: value } from step 4 state
 */
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ReferenceArea, ResponsiveContainer,
} from 'recharts'
import { useI18n } from '../../App'

export default function FindingChart({ finding, timeSeries }) {
  const t = useI18n()
  if (!finding) return null
  if (!timeSeries?.length) {
    return (
      <div style={{ padding: '12px', background: 'var(--offwhite)', borderRadius: '6px', fontSize: '0.8rem', color: 'var(--gray)', textAlign: 'center' }}>
        Run Step 4 to see trend chart
      </div>
    )
  }

  const { metric, pattern, data_points: dp = {}, period } = finding
  const tc = t.charts ?? {}

  if (pattern === 'Cost composition drift') {
    return <CostDriftChart timeSeries={timeSeries} dp={dp} tc={tc} />
  }
  if (pattern === 'Margin compression') {
    return <MarginCompressionChart timeSeries={timeSeries} metric={metric} dp={dp} tc={tc} />
  }
  if (pattern === 'Revenue-cost decoupling') {
    return <RevenueCostDecouplingChart timeSeries={timeSeries} dp={dp} period={period} tc={tc} />
  }
  return <DefaultChart timeSeries={timeSeries} metric={metric} />
}

// ---------------------------------------------------------------------------
// Cost Composition Drift
// ---------------------------------------------------------------------------
function CostDriftChart({ timeSeries, dp, tc }) {
  const hasAvgs = dp.first_half_avg != null && dp.second_half_avg != null
  const period2022 = timeSeries.find(r => r.period?.startsWith('2022'))?.period
  const lastPeriod  = timeSeries[timeSeries.length - 1]?.period

  return (
    <ResponsiveContainer width="100%" height={210}>
      <LineChart data={timeSeries} margin={{ top: 22, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
        <XAxis dataKey="period" tick={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} />
        <YAxis unit="%" domain={[60, 'auto']} tick={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} />
        <Tooltip formatter={(v) => `${v?.toFixed(1)}%`} />

        {/* Structural deterioration shading (2022 onward) */}
        {period2022 && lastPeriod && (
          <ReferenceArea
            x1={period2022} x2={lastPeriod}
            fill="#E24B4A" fillOpacity={0.06}
            label={{ value: tc.structural_deterioration ?? 'Structural deterioration', position: 'insideTopLeft', fontSize: 9, fill: '#E24B4A' }}
          />
        )}

        {/* Revenue = COGS breakeven at 100% */}
        <ReferenceLine
          y={100} stroke="#E24B4A" strokeDasharray="3 2" strokeWidth={1}
          label={{ value: tc.revenue_equals_cogs ?? 'Revenue = COGS', position: 'insideTopRight', fontSize: 9, fill: '#E24B4A' }}
        />

        {/* First-half and second-half average lines */}
        {hasAvgs && (
          <>
            <ReferenceLine
              y={dp.first_half_avg} stroke="#1e90ff" strokeDasharray="6 3"
              label={{ value: `${tc.first_half_avg ?? '1st half avg'}: ${dp.first_half_avg?.toFixed(1)}%`, position: 'insideBottomLeft', fontSize: 10, fill: '#1e90ff' }}
            />
            <ReferenceLine
              y={dp.second_half_avg} stroke="#E24B4A" strokeDasharray="6 3"
              label={{ value: `${tc.second_half_avg ?? '2nd half avg'}: ${dp.second_half_avg?.toFixed(1)}%`, position: 'insideTopRight', fontSize: 10, fill: '#E24B4A' }}
            />
          </>
        )}

        <Line type="monotone" dataKey="COGS_pct_Revenue" stroke="#1e90ff" strokeWidth={2} dot={{ r: 3 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}

// ---------------------------------------------------------------------------
// Margin Compression
// ---------------------------------------------------------------------------
function MarginCompressionChart({ timeSeries, metric, dp, tc }) {
  const annualChange = dp.annual_change_pp
  const lastPeriod   = timeSeries[timeSeries.length - 1]?.period

  return (
    <ResponsiveContainer width="100%" height={210}>
      <LineChart data={timeSeries} margin={{ top: 8, right: 60, bottom: 8, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
        <XAxis dataKey="period" tick={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} />
        <YAxis unit="%" tick={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} domain={['auto', 'auto']} />
        <Tooltip formatter={(v) => `${v?.toFixed(1)}%`} />

        {/* Breakeven at 0% */}
        <ReferenceLine
          y={0} stroke="rgba(11,31,58,0.2)" strokeDasharray="4 3" strokeWidth={1}
          label={{ value: tc.breakeven ?? 'Breakeven', position: 'insideBottomRight', fontSize: 10, fill: 'rgba(11,31,58,0.3)' }}
        />

        {/* Compression rate label near last period */}
        {annualChange != null && lastPeriod && (
          <ReferenceLine
            x={lastPeriod} stroke="transparent"
            label={{ value: `${annualChange.toFixed(1)}pp${tc.per_year ?? '/year'}`, position: 'insideTopRight', fontSize: 10, fill: '#E24B4A', fontWeight: 'bold' }}
          />
        )}

        <Line type="monotone" dataKey={metric} stroke="#1e90ff" strokeWidth={2} dot={{ r: 3 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}

// ---------------------------------------------------------------------------
// Revenue-Cost Decoupling
// ---------------------------------------------------------------------------
function RevenueCostDecouplingChart({ timeSeries, dp, period, tc }) {
  const divergence = dp.divergence_pp

  return (
    <ResponsiveContainer width="100%" height={210}>
      <LineChart data={timeSeries} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
        <XAxis dataKey="period" tick={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} />
        <YAxis unit="%" tick={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} domain={['auto', 'auto']} />
        <Tooltip formatter={(v) => `${v?.toFixed(1)}%`} />

        {/* Zero reference */}
        <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" strokeDasharray="3 3" strokeWidth={1} />

        {/* Highlight the period with worst decoupling */}
        {period && (
          <ReferenceLine
            x={period} stroke="#EF9F27" strokeWidth={2} strokeDasharray="4 2"
            label={divergence != null ? {
              value: `${Math.abs(divergence).toFixed(1)}pp ${tc.divergence ?? 'divergence'}`,
              position: 'insideTopRight',
              fontSize: 10,
              fill: '#E24B4A',
            } : undefined}
          />
        )}

        <Line type="monotone" dataKey="Revenue_YoY_pct" name="Revenue YoY%" stroke="#1e90ff" strokeWidth={2} dot={{ r: 3 }} />
        <Line type="monotone" dataKey="COGS_YoY_pct" name="COGS YoY%" stroke="#E24B4A" strokeWidth={2} dot={{ r: 3 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}

// ---------------------------------------------------------------------------
// Default (statistical anomaly, YoY comparison, peer divergence, etc.)
// ---------------------------------------------------------------------------
function DefaultChart({ timeSeries, metric }) {
  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={timeSeries} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
        <XAxis dataKey="period" tick={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} />
        <YAxis unit="%" tick={{ fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} domain={['auto', 'auto']} />
        <Tooltip formatter={(v) => `${v?.toFixed(1)}%`} />
        <Line type="monotone" dataKey={metric} stroke="#1e90ff" strokeWidth={2} dot={{ r: 3 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}
