/**
 * WaterfallChart — reusable bridge/waterfall chart.
 *
 * Props:
 *   data: Array of { name: string, value: number, type: "total" | "change" }
 *   unit: string  (e.g. "%" or " B")
 *   height: number (default 300)
 *   showConnectors: boolean (default true)
 *   showLabels: boolean (default true)
 *
 * Visual:
 *   - "total" bars: Signal Blue, anchored at zero
 *   - positive "change" bars: Signal Blue 70%, floating
 *   - negative "change" bars: Amber (#EF9F27) 70%, floating
 *   - thin dashed gray connector lines between bars
 */

import { useMemo } from 'react'
import {
  ResponsiveContainer,
  BarChart, Bar, Cell,
  XAxis, YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Customized,
} from 'recharts'

const BLUE_TOTAL   = '#2E86C1'
const BLUE_POS     = 'rgba(46,134,193,0.70)'
const COST_RED     = 'rgba(192,57,43,0.65)'  // negative change bars

// ── Data preparation ─────────────────────────────────────────────────────────

function prepareChartData(items) {
  let running = 0
  return items.map((item) => {
    const isTotal    = item.type === 'total'
    const isNegative = item.value < 0

    let base, barVal, runningBefore, runningAfter

    if (isTotal) {
      runningBefore = running
      runningAfter  = item.value   // reset to absolute
      // For negative totals: invisible bar from totalValue → 0 (abs fills upward to 0)
      base   = item.value < 0 ? item.value : 0
      barVal = Math.abs(item.value)
      running = item.value
    } else {
      runningBefore = running
      runningAfter  = running + item.value
      // Position invisible spacer at the lower of (before, after)
      base   = isNegative ? runningAfter : running
      barVal = Math.abs(item.value)
      running += item.value
    }

    return {
      name:          item.name,
      base,
      barVal,
      isTotal,
      isNegative,
      originalValue: item.value,
      runningBefore,
      runningAfter,
    }
  })
}

// ── Connector lines via Customized ───────────────────────────────────────────

function ConnectorLines({ xAxisMap, yAxisMap, chartData }) {
  try {
    const xAxis = Object.values(xAxisMap || {})[0]
    const yAxis = Object.values(yAxisMap || {})[0]
    if (!xAxis?.scale || !yAxis?.scale) return null

    const xScale = xAxis.scale
    const yScale = yAxis.scale
    const bw     = xScale.bandwidth ? xScale.bandwidth() : 40

    return (
      <g>
        {chartData.map((d, i) => {
          if (i >= chartData.length - 1) return null
          const next = chartData[i + 1]
          const x1 = xScale(d.name) + bw
          const x2 = xScale(next.name)
          const y  = yScale(d.runningAfter)
          if (x1 == null || x2 == null || isNaN(y)) return null
          return (
            <line
              key={i}
              x1={x1} y1={y}
              x2={x2} y2={y}
              stroke="rgba(11,31,58,0.22)"
              strokeWidth={1}
              strokeDasharray="4 3"
            />
          )
        })}
      </g>
    )
  } catch {
    return null
  }
}

// ── Bar label ────────────────────────────────────────────────────────────────

function makeBarLabel(chartData, unit) {
  return function BarLabel({ x, y, width, height, index }) {
    const d = chartData[index]
    if (!d || width < 12) return null

    // For negative-value items: label goes below the bar bottom
    // For positive-value items: label goes above the bar top
    const labelY = d.originalValue < 0 ? y + height + 13 : y - 5
    const color  = d.isTotal ? BLUE_TOTAL
                 : d.isNegative ? COST_RED
                 : BLUE_POS

    const absStr = Math.abs(d.originalValue).toFixed(1)
    const sign   = d.isTotal ? (d.originalValue < 0 ? '−' : '') : (d.isNegative ? '−' : '+')
    const text   = `${sign}${absStr}${unit}`

    return (
      <text
        x={x + width / 2}
        y={labelY}
        fill={color}
        fontSize={10}
        fontFamily="'IBM Plex Mono', monospace"
        textAnchor="middle"
      >
        {text}
      </text>
    )
  }
}

// ── Tooltip ──────────────────────────────────────────────────────────────────

function WaterfallTooltip({ active, payload, label, chartData, unit }) {
  if (!active || !payload?.length) return null
  const d = chartData.find(x => x.name === label)
  if (!d) return null

  const absStr  = Math.abs(d.originalValue).toFixed(1)
  const sign    = d.isTotal ? (d.originalValue < 0 ? '−' : '') : (d.isNegative ? '−' : '+')
  const valStr  = `${sign}${absStr}${unit}`
  const rtAfter = `${d.runningAfter >= 0 ? '' : '−'}${Math.abs(d.runningAfter).toFixed(1)}${unit}`

  return (
    <div style={{
      background: '#fff',
      border: '1px solid rgba(11,31,58,0.12)',
      borderRadius: 6,
      padding: '8px 12px',
      fontSize: 12,
      fontFamily: "'IBM Plex Sans', sans-serif",
    }}>
      <div style={{ fontWeight: 700, marginBottom: 4, color: 'var(--navy)' }}>{label}</div>
      <div style={{ color: d.isNegative ? COST_RED : BLUE_TOTAL, fontFamily: "'IBM Plex Mono', monospace" }}>
        {valStr}
      </div>
      {!d.isTotal && (
        <div style={{ color: 'var(--gray)', fontSize: 11, marginTop: 2 }}>
          Running total: {rtAfter}
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function WaterfallChart({
  data,
  unit = '',
  height = 300,
  showConnectors = true,
  showLabels = true,
}) {
  const chartData = useMemo(() => prepareChartData(data), [data])

  // Y-axis domain with 15% padding
  const allLevels = chartData.flatMap(d => [d.base, d.base + d.barVal, 0])
  const rawMin = Math.min(...allLevels)
  const rawMax = Math.max(...allLevels)
  const pad    = (rawMax - rawMin) * 0.18 || 1
  const yMin   = rawMin - pad
  const yMax   = rawMax + pad

  const BarLabelComponent = useMemo(
    () => showLabels ? makeBarLabel(chartData, unit) : undefined,
    [chartData, unit, showLabels]
  )

  const ConnectorComponent = useMemo(() => {
    if (!showConnectors) return undefined
    return (props) => <ConnectorLines {...props} chartData={chartData} />
  }, [chartData, showConnectors])

  const TooltipContent = useMemo(() => {
    return (props) => <WaterfallTooltip {...props} chartData={chartData} unit={unit} />
  }, [chartData, unit])

  const tickFmt = (v) => {
    const abs = Math.abs(v)
    if (abs >= 100) return v.toFixed(0)
    if (abs >= 10)  return v.toFixed(1)
    return v.toFixed(2)
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={chartData}
        margin={{ top: 24, right: 20, left: 8, bottom: 4 }}
        barCategoryGap="28%"
      >
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" vertical={false} />
        <XAxis
          dataKey="name"
          tick={{ fontSize: 10, fontFamily: "'IBM Plex Mono', monospace", fill: 'var(--charcoal)' }}
          tickLine={false}
        />
        <YAxis
          domain={[yMin, yMax]}
          tickFormatter={tickFmt}
          tick={{ fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" }}
          tickLine={false}
          axisLine={false}
          unit={unit}
        />
        <Tooltip content={TooltipContent} cursor={{ fill: 'rgba(11,31,58,0.04)' }} />
        <ReferenceLine y={0} stroke="rgba(11,31,58,0.25)" strokeWidth={1} />

        {/* Invisible spacer bar — positions the visible bar at the correct height */}
        <Bar
          dataKey="base"
          stackId="wf"
          fill="transparent"
          isAnimationActive={false}
          legendType="none"
        />

        {/* Visible colored bar */}
        <Bar
          dataKey="barVal"
          stackId="wf"
          isAnimationActive={false}
          legendType="none"
          label={BarLabelComponent}
          radius={[2, 2, 0, 0]}
        >
          {chartData.map((d, i) => (
            <Cell
              key={i}
              fill={
                d.isTotal    ? BLUE_TOTAL :
                d.isNegative ? COST_RED   :
                               BLUE_POS
              }
            />
          ))}
        </Bar>

        {/* Connector lines between bars */}
        {showConnectors && ConnectorComponent && (
          <Customized component={ConnectorComponent} />
        )}
      </BarChart>
    </ResponsiveContainer>
  )
}
