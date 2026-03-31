/**
 * Step 6 — Visual horizontal timeline: macro events (top lane) vs findings (bottom lane).
 * Props:
 *   macroTimeline    — array of { period: "YYYY-HN", event: string }
 *   findings         — array of enriched finding objects
 *   findingCategories — { core: [...ids], supporting: [...ids], contextual: [...ids], anomalies: [...ids] }
 */
import { useState, useRef } from 'react'
import { useI18n } from '../../App'
import styles from './MacroTimeline.module.css'

// --- Layout constants ---
const SVG_W = 1000
const SVG_H = 280
const LEFT = 80
const RIGHT = 20
const PLOT_W = SVG_W - LEFT - RIGHT   // 900px
const STEP_W = PLOT_W / 10            // 90px per half-year (2020-H1 … 2025-H1 = 11 points, 10 gaps)
const AXIS_Y = 140
const MACRO_Y = 62                    // macro event circle center
const FIND_Y = 210                    // finding circle center

const YEARS = [2020, 2021, 2022, 2023, 2024, 2025]

// --- Event styling ---
const EVENT_CATEGORIES = {
  '2020-H1': 'crisis',
  '2020-H2': 'recovery',
  '2021-H1': 'recovery',
  '2021-H2': 'peak',
  '2022-H1': 'crisis',
  '2022-H2': 'tightening',
  '2023-H1': 'pressure',
  '2023-H2': 'pressure',
  '2024-H1': 'pressure',
  '2024-H2': 'trough',
  '2025-H1': 'neutral',
}

const CATEGORY_COLORS = {
  crisis:     '#dc3545',
  recovery:   '#28a745',
  peak:       '#1a7a34',
  tightening: '#007bff',
  pressure:   '#6c8ebf',
  trough:     '#6c757d',
  neutral:    '#adb5bd',
}

// --- Finding styling by category ---
const FINDING_COLORS = {
  core:       { stroke: '#2563eb', fill: '#eff6ff' },
  supporting: { stroke: '#16a34a', fill: '#f0fdf4' },
  contextual: { stroke: '#6b7280', fill: '#f9fafb' },
  anomalies:  { stroke: '#d97706', fill: '#fffbeb' },
}

// --- Helpers ---
function periodToX(period) {
  const m = period?.match(/^(\d{4})-H([12])$/)
  if (!m) return null
  const idx = (parseInt(m[1]) - 2020) * 2 + (parseInt(m[2]) - 1)
  return LEFT + idx * STEP_W
}

function parseFindingPeriod(period) {
  if (!period) return null
  // "2022-12-31"
  const dateMatch = period.match(/^(\d{4})-(\d{2})-\d{2}$/)
  if (dateMatch) {
    const month = parseInt(dateMatch[2])
    return `${dateMatch[1]}-${month <= 6 ? 'H1' : 'H2'}`
  }
  // "Q2 2022"
  const qMatch = period.match(/Q(\d)\s+(\d{4})/)
  if (qMatch) {
    return `${qMatch[2]}-${parseInt(qMatch[1]) <= 2 ? 'H1' : 'H2'}`
  }
  // Already "YYYY-HN"
  if (/^\d{4}-H[12]$/.test(period)) return period
  return null
}

export default function MacroTimeline({ macroTimeline, findings, findingCategories }) {
  const t = useI18n()
  const tc = t.charts ?? {}
  const [tooltip, setTooltip] = useState(null)
  const containerRef = useRef(null)

  if (!macroTimeline?.length) return null

  // Build finding → category map
  const findingCatMap = {}
  for (const [cat, ids] of Object.entries(findingCategories ?? {})) {
    for (const id of ids) findingCatMap[id] = cat
  }

  // Ensure each finding has an id
  const shapedFindings = (findings ?? []).map((f, i) => ({
    ...f,
    id: f.id ?? `F${String(i + 1).padStart(3, '0')}`,
  }))

  // Split into trend findings (no parseable period) and period findings
  const trendFindings = []
  const periodFindings = []
  shapedFindings.forEach((f) => {
    const hp = parseFindingPeriod(f.period)
    if (hp) periodFindings.push({ ...f, halfPeriod: hp })
    else trendFindings.push(f)
  })

  const shortLabel = (period) => {
    const key = `macro_short_${period.replace('-', '_')}`
    return tc[key] ?? period
  }

  const showTooltip = (type, data, e) => {
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return
    setTooltip({ type, data, x: e.clientX - rect.left, y: e.clientY - rect.top })
  }
  const hideTooltip = () => setTooltip(null)

  const xStart = LEFT
  const xEnd = LEFT + PLOT_W

  return (
    <div ref={containerRef} className={styles.container}>
      <svg
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        className={styles.svg}
        onMouseLeave={hideTooltip}
        aria-label={tc.macro_timeline_title ?? 'Findings vs. Macro Context'}
      >
        {/* Lane labels */}
        <text x={LEFT - 8} y={MACRO_Y + 4} textAnchor="end" fontSize={9} fill="#94a3b8" fontWeight="600" letterSpacing="0.5">
          {tc.macro_events_lane ?? 'MACRO EVENTS'}
        </text>
        <text x={LEFT - 8} y={FIND_Y + 4} textAnchor="end" fontSize={9} fill="#94a3b8" fontWeight="600" letterSpacing="0.5">
          {tc.findings_lane ?? 'FINDINGS'}
        </text>

        {/* === CENTRAL AXIS === */}
        <line
          x1={LEFT - 4} y1={AXIS_Y}
          x2={xEnd + 4} y2={AXIS_Y}
          stroke="#cbd5e1" strokeWidth={1.5}
        />

        {/* Year ticks + labels + half-year ticks */}
        {YEARS.map((year) => {
          const xYear = periodToX(`${year}-H1`)
          const xHalf = year < 2025 ? periodToX(`${year}-H2`) : null
          return (
            <g key={year}>
              <line x1={xYear} y1={AXIS_Y - 6} x2={xYear} y2={AXIS_Y + 6} stroke="#94a3b8" strokeWidth={1.5} />
              <text x={xYear} y={AXIS_Y + 20} textAnchor="middle" fontSize={11} fill="#475569" fontWeight="700">
                {year}
              </text>
              {xHalf && (
                <line x1={xHalf} y1={AXIS_Y - 3} x2={xHalf} y2={AXIS_Y + 3} stroke="#cbd5e1" strokeWidth={1} />
              )}
            </g>
          )
        })}

        {/* === TOP LANE: MACRO EVENTS === */}
        {macroTimeline.map((item, idx) => {
          const x = periodToX(item.period)
          if (x == null) return null
          const color = CATEGORY_COLORS[EVENT_CATEGORIES[item.period] ?? 'neutral']
          const label = shortLabel(item.period)
          const words = label.split(' ')
          const half = Math.ceil(words.length / 2)
          const line1 = words.slice(0, half).join(' ')
          const line2 = words.slice(half).join(' ')
          // Alternate label height to reduce overlap for adjacent events
          const labelBaseY = idx % 2 === 0 ? MACRO_Y - 36 : MACRO_Y - 22

          return (
            <g
              key={item.period}
              onMouseEnter={(e) => showTooltip('macro', item, e)}
              onMouseLeave={hideTooltip}
              style={{ cursor: 'default' }}
            >
              {/* Dashed connector: marker → axis */}
              <line
                x1={x} y1={MACRO_Y + 7}
                x2={x} y2={AXIS_Y - 5}
                stroke={color} strokeWidth={1}
                strokeDasharray="3 3" opacity={0.5}
              />
              {/* Event circle */}
              <circle cx={x} cy={MACRO_Y} r={6} fill={color} opacity={0.85} />
              {/* Short label (1 or 2 lines) */}
              <text x={x} y={labelBaseY} textAnchor="middle" fontSize={9} fill={color} fontWeight="600">
                {line1}
              </text>
              {line2 && (
                <text x={x} y={labelBaseY + 11} textAnchor="middle" fontSize={9} fill={color} fontWeight="600">
                  {line2}
                </text>
              )}
            </g>
          )
        })}

        {/* === BOTTOM LANE: TREND FINDINGS (full-width bars) === */}
        {trendFindings.map((f, i) => {
          const cat = findingCatMap[f.id] ?? 'core'
          const { stroke, fill } = FINDING_COLORS[cat] ?? FINDING_COLORS.core
          const barCenterY = FIND_Y + i * 16

          return (
            <g
              key={f.id}
              onMouseEnter={(e) => showTooltip('finding', f, e)}
              onMouseLeave={hideTooltip}
              style={{ cursor: 'pointer' }}
            >
              <rect
                x={xStart} y={barCenterY - 5}
                width={PLOT_W} height={10}
                rx={4} ry={4}
                fill={fill} stroke={stroke} strokeWidth={1.5} opacity={0.8}
              />
              <text x={xStart + 6} y={barCenterY + 3.5} fontSize={8} fill={stroke} fontWeight="700">
                {f.id}{f.pattern ? `: ${f.pattern}` : ''}
              </text>
            </g>
          )
        })}

        {/* === BOTTOM LANE: PERIOD FINDINGS (dots) === */}
        {periodFindings.map((f) => {
          const x = periodToX(f.halfPeriod)
          if (x == null) return null
          const cat = findingCatMap[f.id] ?? 'core'
          const { stroke, fill } = FINDING_COLORS[cat] ?? FINDING_COLORS.core
          const patternShort = (f.pattern ?? '').split(' ').slice(0, 2).join(' ')

          return (
            <g
              key={f.id}
              onMouseEnter={(e) => showTooltip('finding', f, e)}
              onMouseLeave={hideTooltip}
              style={{ cursor: 'pointer' }}
            >
              {/* Dashed connector: axis → marker */}
              <line
                x1={x} y1={AXIS_Y + 5}
                x2={x} y2={FIND_Y - 9}
                stroke={stroke} strokeWidth={1}
                strokeDasharray="3 3" opacity={0.4}
              />
              {/* Finding circle */}
              <circle cx={x} cy={FIND_Y} r={8} fill={fill} stroke={stroke} strokeWidth={2} />
              <text x={x} y={FIND_Y + 3.5} textAnchor="middle" fontSize={7.5} fill={stroke} fontWeight="700">
                {f.id}
              </text>
              {/* Short pattern label below dot */}
              <text x={x} y={FIND_Y + 21} textAnchor="middle" fontSize={8} fill="#64748b">
                {patternShort}
              </text>
            </g>
          )
        })}

        {/* Trend-finding legend note (bottom-left) */}
        {trendFindings.length > 0 && (
          <text x={xStart} y={SVG_H - 6} fontSize={8} fill="#94a3b8" fontStyle="italic">
            {tc.trend_finding ?? 'Trend (full period)'}
          </text>
        )}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className={styles.tooltip}
          style={{ left: tooltip.x + 14, top: tooltip.y - 16 }}
        >
          {tooltip.type === 'macro' ? (
            <>
              <div className={styles.tooltipPeriod}>{tooltip.data.period}</div>
              <div className={styles.tooltipText}>{tooltip.data.event}</div>
            </>
          ) : (
            <>
              <div className={styles.tooltipPeriod}>
                {tooltip.data.id}{tooltip.data.pattern ? ` — ${tooltip.data.pattern}` : ''}
              </div>
              {tooltip.data.period && (
                <div className={styles.tooltipText}>{tooltip.data.period}</div>
              )}
              {tooltip.data.description && (
                <div className={styles.tooltipText}>{tooltip.data.description}</div>
              )}
              {tooltip.data.macro_context && typeof tooltip.data.macro_context === 'string' && (
                <div className={styles.tooltipMacro}>{tooltip.data.macro_context}</div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
