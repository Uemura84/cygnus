import { useI18n, useAppState, useAppDispatch } from '../App'
import styles from './StepSidebar.module.css'

const STEP_META = [
  { n: 1, icon: '⬇', labelKey: 'step1.title' },
  { n: 2, icon: '🔧', labelKey: 'step2.title' },
  { n: 3, icon: '🔄', labelKey: 'step3.title' },
  { n: 4, icon: '📈', labelKey: 'step4.title' },
  { n: 5, icon: '🔍', labelKey: 'step5.title' },
  { n: 6, icon: '📊', labelKey: 'step6.title' },
  { n: 7, icon: '🌐', labelKey: 'step7.title' },
  { n: 8, icon: '📝', labelKey: 'step8.title' },
  { n: 9, icon: '🤖', labelKey: 'step9.title' },
]

function getLabel(t, key) {
  const [section, field] = key.split('.')
  return t?.[section]?.[field] ?? key
}

export default function StepSidebar() {
  const t = useI18n()
  const state = useAppState()
  const dispatch = useAppDispatch()

  return (
    <nav className={styles.sidebar}>
      {STEP_META.map(({ n, icon, labelKey }) => {
        const stepState = state.stepStates[n]
        const isCurrent = state.currentStep === n
        const isClickable = stepState === 'complete' || isCurrent

        return (
          <button
            key={n}
            className={`${styles.stepBtn} ${styles[stepState]} ${isCurrent ? styles.current : ''}`}
            onClick={() => isClickable && dispatch({ type: 'NAVIGATE_TO_STEP', step: n })}
            disabled={!isClickable}
            title={getLabel(t, labelKey)}
          >
            <span className={styles.stepNumber}>{n}</span>
            <span className={styles.stepIcon}>{icon}</span>
            <span className={styles.stepLabel}>{getLabel(t, labelKey)}</span>
            {stepState === 'running' && <span className={styles.spinner} />}
            {stepState === 'complete' && <span className={styles.check}>✓</span>}
          </button>
        )
      })}
    </nav>
  )
}
