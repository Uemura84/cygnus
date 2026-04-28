/**
 * Step 6 — Risk score gauge.
 * Custom SVG semi-circle with gradient track + needle.
 * Props: score — number 0–100
 *        level — string e.g. "HIGH"
 */
import styles from './RiskGauge.module.css'

const LEVEL_COLOR = {
  // Legacy levels (backward compat with old caches)
  LOW:      '#0e8f9a',
  MEDIUM:   '#EF9F27',
  HIGH:     '#E24B4A',
  CRITICAL: '#E24B4A',
  // Distress scoring v1.5 bands
  'Healthy':          '#0e8f9a',
  'Stable':           '#0e8f9a',
  'Watchlist':        '#EF9F27',
  'High Risk':        '#E24B4A',
  'Distress':         '#E24B4A',
  'Severe Distress':  '#991b1b',
}

export default function RiskGauge({ score, level }) {
  const pct = Math.min(Math.max(score ?? 0, 0), 100) / 100
  const color = LEVEL_COLOR[level] ?? 'rgba(11,31,58,0.3)'

  // Layout: diameter line sits near the bottom of the SVG so the arc curves upward.
  // Semicircle from (cx-R, cy) to (cx+R, cy) going UP (sweep=1, largeArc=0).
  const cx = 100
  const cy = 105
  const R  = 80
  const arcPath = `M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${cx + R} ${cy}`

  // Needle angle: score 0% → left (θ=π), score 100% → right (θ=0)
  const theta      = Math.PI * (1 - pct)
  const needleTipX = cx + R * Math.cos(theta)
  const needleTipY = cy - R * Math.sin(theta)

  return (
    <div className={styles.wrapper}>
      <svg width="200" height="115" viewBox="0 0 200 115">
        <defs>
          <linearGradient id="riskGaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"   stopColor="#0e8f9a" />
            <stop offset="50%"  stopColor="#EF9F27" />
            <stop offset="100%" stopColor="#E24B4A" />
          </linearGradient>
        </defs>

        {/* Background track */}
        <path
          d={arcPath}
          fill="none"
          stroke="rgba(11,31,58,0.08)"
          strokeWidth={14}
          strokeLinecap="round"
        />
        {/* Gradient color band */}
        <path
          d={arcPath}
          fill="none"
          stroke="url(#riskGaugeGrad)"
          strokeWidth={10}
          strokeLinecap="round"
          opacity={0.9}
        />

        {/* Needle */}
        <line
          x1={cx}         y1={cy}
          x2={needleTipX} y2={needleTipY}
          stroke="rgba(11,31,58,0.25)"
          strokeWidth={2}
          strokeLinecap="round"
        />
        {/* Needle hub */}
        <circle cx={cx} cy={cy} r={4} fill="rgba(11,31,58,0.25)" />
        <circle cx={cx} cy={cy} r={2} fill="var(--offwhite, #f5f7fa)" />

        {/* Score number */}
        <text
          x={cx} y={cy - 18}
          textAnchor="middle"
          fontSize="22"
          fontWeight="700"
          fill={color}
        >
          {Math.round(score ?? 0)}
        </text>
        {/* Level label */}
        <text
          x={cx} y={cy - 4}
          textAnchor="middle"
          fontSize="11"
          fontWeight="600"
          fill="var(--gray, #4a5568)"
        >
          {level}
        </text>
      </svg>
    </div>
  )
}
