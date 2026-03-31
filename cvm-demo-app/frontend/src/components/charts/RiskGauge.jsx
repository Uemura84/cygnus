/**
 * Step 6 — Risk score gauge.
 * Custom SVG semi-circle with gradient track + needle.
 * Props: score — number 0–100
 *        level — string e.g. "HIGH"
 */
import styles from './RiskGauge.module.css'

const LEVEL_COLOR = {
  LOW:      '#16a34a',
  MEDIUM:   '#f59e0b',
  HIGH:     '#ea580c',
  CRITICAL: '#dc2626',
}

export default function RiskGauge({ score, level }) {
  const pct = Math.min(Math.max(score ?? 0, 0), 100) / 100
  const color = LEVEL_COLOR[level] ?? '#94a3b8'

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
          {/* Horizontal gradient: green (left/0) → yellow (center/50) → red (right/100) */}
          <linearGradient id="riskGaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"   stopColor="#16a34a" />
            <stop offset="50%"  stopColor="#f59e0b" />
            <stop offset="100%" stopColor="#dc2626" />
          </linearGradient>
        </defs>

        {/* Background track */}
        <path
          d={arcPath}
          fill="none"
          stroke="#e2e8f0"
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
          stroke="#1e293b"
          strokeWidth={2.5}
          strokeLinecap="round"
        />
        {/* Needle hub */}
        <circle cx={cx} cy={cy} r={5} fill="#1e293b" />
        <circle cx={cx} cy={cy} r={2.5} fill="#f8fafc" />

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
          fill="#64748b"
        >
          {level}
        </text>
      </svg>
    </div>
  )
}
