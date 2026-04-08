import { useState } from 'react'
import { useI18n, useAppState, useAppDispatch } from '../App'
import styles from './StepSidebar.module.css'

// ── Custom SVG step icons ─────────────────────────────────────────────────────
// Outline/stroke style, 1.5px, round caps + joins, currentColor controlled via prop.
// Step 7 (accretion disk) and Step 4 data points use fill={color} per spec.

function StepIcon({ step, color = 'currentColor', size = 20 }) {
  const base = {
    viewBox: '0 0 20 20',
    width: size,
    height: size,
    fill: 'none',
    stroke: color,
    strokeWidth: 1.5,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    style: { display: 'block', flexShrink: 0 },
  }

  switch (step) {
    case 1: // Download Data — arrow entering a baseline
      return (
        <svg {...base}>
          <line x1="10" y1="3" x2="10" y2="13" />
          <polyline points="6,10 10,14 14,10" />
          <line x1="4" y1="17" x2="16" y2="17" />
        </svg>
      )

    case 2: // Quality Filters — funnel
      return (
        <svg {...base}>
          <polygon points="3,3 17,3 12,10 12,16 8,16 8,10" />
        </svg>
      )

    case 3: // Statement Mapping — two blocks converging into one
      return (
        <svg {...base}>
          <rect x="2" y="4" width="5" height="5" rx="0.5" />
          <rect x="2" y="11" width="5" height="5" rx="0.5" />
          <rect x="13" y="7" width="5" height="6" rx="0.5" />
          <line x1="7" y1="10" x2="13" y2="10" />
          <polyline points="11,8 13,10 11,12" />
        </svg>
      )

    case 4: // Financial Metrics — trend line with filled data points
      return (
        <svg {...base}>
          <polyline points="3,14 7,8 11,11 15,5 18,7" />
          <circle cx="7"  cy="8"  r="1.2" fill={color} stroke="none" />
          <circle cx="11" cy="11" r="1.2" fill={color} stroke="none" />
          <circle cx="15" cy="5"  r="1.2" fill={color} stroke="none" />
        </svg>
      )

    case 5: // Metric Validation — shield with checkmark
      return (
        <svg {...base}>
          <path d="M10,2 L17,6 L17,11 C17,15 10,18 10,18 C10,18 3,15 3,11 L3,6 Z" />
          <polyline points="7,10 9,12 13,8" />
        </svg>
      )

    case 6: // Pattern Detection — magnifying glass with pulse wave
      return (
        <svg {...base}>
          <circle cx="9" cy="9" r="5.5" />
          <line x1="13.5" y1="13.5" x2="17" y2="17" />
          <polyline points="5.5,9 7,7 9,11 11,8 12.5,9" />
        </svg>
      )

    case 7: // AI Specialist — Cygnus accretion disk mark (brand moment)
      return (
        <svg
          viewBox="0 0 20 20"
          width={size}
          height={size}
          fill="none"
          stroke={color}
          strokeWidth={1.5}
          style={{ display: 'block', flexShrink: 0 }}
        >
          <ellipse cx="10" cy="10" rx="8"   ry="3"   opacity="0.25" />
          <ellipse cx="10" cy="10" rx="5.5" ry="2.2" opacity="0.55" />
          <circle  cx="10" cy="10" r="2"   fill={color} stroke="none" />
        </svg>
      )

    case 8: // Executive Summary — document with hierarchy lines
      return (
        <svg {...base}>
          <rect x="4" y="2" width="12" height="16" rx="1" />
          <line x1="7" y1="6"  x2="13" y2="6"  />
          <line x1="7" y1="9"  x2="15" y2="9"  />
          <line x1="7" y1="12" x2="11" y2="12" />
          <line x1="7" y1="15" x2="14" y2="15" />
        </svg>
      )

    case 9: // Ask the Specialist — chat bubble with text lines
      return (
        <svg {...base}>
          <path d="M4,4 L16,4 C16.5,4 17,4.5 17,5 L17,13 C17,13.5 16.5,14 16,14 L8,14 L5,17 L5,14 L4,14 C3.5,14 3,13.5 3,13 L3,5 C3,4.5 3.5,4 4,4 Z" />
          <line x1="7" y1="8"  x2="13" y2="8"  />
          <line x1="7" y1="11" x2="11" y2="11" />
        </svg>
      )

    default:
      return null
  }
}

// ── Step metadata ─────────────────────────────────────────────────────────────

const STEP_META = [
  { n: 1, labelKey: 'step1.title', fullKey: 'step1.title_full' },
  { n: 2, labelKey: 'step2.title', fullKey: 'step2.title_full' },
  { n: 3, labelKey: 'step3.title', fullKey: 'step3.title_full' },
  { n: 4, labelKey: 'step4.title', fullKey: null },
  { n: 5, labelKey: 'step5.title', fullKey: null },
  { n: 6, labelKey: 'step6.title', fullKey: 'step6.title_full' },
  { n: 7, labelKey: 'step7.title', fullKey: 'step7.title_full' },
  { n: 8, labelKey: 'step8.title', fullKey: null },
  { n: 9, labelKey: 'step9.title', fullKey: null },
]

function resolve(t, key) {
  if (!key) return null
  const [section, field] = key.split('.')
  return t?.[section]?.[field] ?? null
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

export default function StepSidebar() {
  const t = useI18n()
  const state = useAppState()
  const dispatch = useAppDispatch()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <nav className={`${styles.sidebar} ${collapsed ? styles.sidebarCollapsed : ''}`}>

      {/* Logo */}
      <div className={styles.logoArea}>
        {collapsed
          ? <img src="/cygnus-mark.svg"      alt="Cygnus" className={styles.logoMark} />
          : <img src="/cygnus-logo-dark.svg" alt="Cygnus" className={styles.logoFull} />
        }
      </div>

      <div className={styles.stepsContainer}>
        {STEP_META.map(({ n, labelKey, fullKey }, i) => {
          const stepState = state.stepStates[n]
          const isCurrent = state.currentStep === n
          const isClickable = stepState === 'complete' || isCurrent
          const label = resolve(t, labelKey) ?? labelKey
          const fullLabel = resolve(t, fullKey) ?? label
          const isLast = i === STEP_META.length - 1

          // Icon color: Signal Blue for completed/active, Slate 40% for pending
          const iconColor = (stepState === 'complete' || isCurrent)
            ? '#1e90ff'
            : 'rgba(74,85,104,0.4)'

          // Flow line below this step: solid if complete, dashed if current/pending
          const lineComplete = stepState === 'complete'

          return (
            <div key={n} className={styles.stepItem}>
              <button
                className={`${styles.stepBtn} ${styles[stepState]} ${isCurrent ? styles.current : ''}`}
                onClick={() => isClickable && dispatch({ type: 'NAVIGATE_TO_STEP', step: n })}
                disabled={!isClickable}
                title={fullLabel}
              >
                {!collapsed && <span className={styles.stepNumber}>{n}</span>}
                <StepIcon step={n} color={iconColor} size={collapsed ? 24 : 20} />
                {!collapsed && <span className={styles.stepLabel}>{label}</span>}
                {!collapsed && stepState === 'running'  && <span className={styles.spinner} />}
                {!collapsed && stepState === 'complete' && <span className={styles.check}>✓</span>}
              </button>
              {!isLast && (
                <div className={`${styles.flowConnector} ${lineComplete ? styles.lineComplete : styles.linePending}`} />
              )}
            </div>
          )
        })}
      </div>

      {/* Collapse / expand toggle */}
      <button
        className={styles.collapseBtn}
        onClick={() => setCollapsed(c => !c)}
        title={collapsed ? (t.sidebar?.expand ?? 'Expand') : (t.sidebar?.collapse ?? 'Collapse')}
      >
        <span className={styles.collapseChevron}>{collapsed ? '»' : '«'}</span>
        {!collapsed && (
          <span className={styles.collapseLabel}>
            {t.sidebar?.collapse ?? 'Collapse'}
          </span>
        )}
      </button>
    </nav>
  )
}
