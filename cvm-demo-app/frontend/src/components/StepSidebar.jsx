import { useState } from 'react'
import { useI18n, useAppState, useAppDispatch } from '../App'
import styles from './StepSidebar.module.css'

const STEP_META = [
  { n: 1, icon: '⬇', labelKey: 'step1.title', fullKey: 'step1.title_full' },
  { n: 2, icon: '🔧', labelKey: 'step2.title', fullKey: 'step2.title_full' },
  { n: 3, icon: '🔄', labelKey: 'step3.title', fullKey: 'step3.title_full' },
  { n: 4, icon: '📈', labelKey: 'step4.title', fullKey: null },
  { n: 5, icon: '🔍', labelKey: 'step5.title', fullKey: null },
  { n: 6, icon: '📊', labelKey: 'step6.title', fullKey: 'step6.title_full' },
  { n: 7, icon: '🌐', labelKey: 'step7.title', fullKey: 'step7.title_full' },
  { n: 8, icon: '📝', labelKey: 'step8.title', fullKey: null },
  { n: 9, icon: '🤖', labelKey: 'step9.title', fullKey: null },
]

function resolve(t, key) {
  if (!key) return null
  const [section, field] = key.split('.')
  return t?.[section]?.[field] ?? null
}

export default function StepSidebar() {
  const t = useI18n()
  const state = useAppState()
  const dispatch = useAppDispatch()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <nav className={`${styles.sidebar} ${collapsed ? styles.sidebarCollapsed : ''}`}>
      <div className={styles.stepsContainer}>
        {STEP_META.map(({ n, icon, labelKey, fullKey }, i) => {
          const stepState = state.stepStates[n]
          const isCurrent = state.currentStep === n
          const isClickable = stepState === 'complete' || isCurrent
          const label = resolve(t, labelKey) ?? labelKey
          const fullLabel = resolve(t, fullKey) ?? label
          const isLast = i === STEP_META.length - 1

          // Line below this step: solid blue if complete, dashed slate if current/pending
          const lineComplete = stepState === 'complete'

          return (
            <div key={n} className={styles.stepItem}>
              <button
                className={`${styles.stepBtn} ${styles[stepState]} ${isCurrent ? styles.current : ''}`}
                onClick={() => isClickable && dispatch({ type: 'NAVIGATE_TO_STEP', step: n })}
                disabled={!isClickable}
                title={fullLabel}
              >
                <span className={styles.stepNumber}>{n}</span>
                {!collapsed && <span className={styles.stepIcon}>{icon}</span>}
                {!collapsed && <span className={styles.stepLabel}>{label}</span>}
                {stepState === 'running' && <span className={styles.spinner} />}
                {stepState === 'complete' && <span className={styles.check}>✓</span>}
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
