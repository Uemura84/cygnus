import { useI18n, useAppState, useAppDispatch } from '../App'
import StepSidebar from './StepSidebar'
import StepContent from './StepContent'
import LanguageToggle from './LanguageToggle'
import CompanySelector from './CompanySelector'
import styles from './StepWizard.module.css'

export default function StepWizard() {
  const t = useI18n()
  const state = useAppState()
  const dispatch = useAppDispatch()

  function handleCacheToggle() {
    dispatch({ type: 'TOGGLE_CACHE' })
    fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cache_mode: !state.cacheMode }),
    }).catch(() => {})
  }

  return (
    <div className={styles.wrapper}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <img src="/cygnus-logo-dark.svg" alt="Cygnus" className={styles.logo} />
          <span className={styles.subtitle}>
            {(t.header.subtitle_template ?? t.header.subtitle).replace('{company}', state.companyName ?? 'BRASKEM S.A.')}
          </span>
        </div>
        <div className={styles.headerRight}>
          <CompanySelector />
          <LanguageToggle />
          <button
            className={`${styles.toggle} ${state.cacheMode ? styles.toggleActive : ''}`}
            onClick={handleCacheToggle}
          >
            {state.cacheMode ? t.header.cache_toggle_cache : t.header.cache_toggle_live}
          </button>
        </div>
      </header>

      {/* Body */}
      <div className={styles.body}>
        <StepSidebar />
        <main className={styles.main}>
          {state.cacheMode && (
            <div className={styles.cacheBanner}>{t.cache_banner}</div>
          )}
          <StepContent />
        </main>
      </div>

      {/* Footer */}
      <footer className={styles.footer}>
        <button
          className={styles.navBtn}
          disabled={state.currentStep <= 1}
          onClick={() => dispatch({ type: 'NAVIGATE_TO_STEP', step: state.currentStep - 1 })}
        >
          ← {t.nav.previous}
        </button>
        <div className={styles.footerRight}>
          {state.currentStep !== 7 && state.currentStep !== 8 && state.currentStep !== 9 && <RunStepButton />}
          <button
            className={styles.navBtn}
            disabled={state.currentStep >= 9}
            onClick={() => dispatch({ type: 'NAVIGATE_TO_STEP', step: state.currentStep + 1 })}
          >
            {t.nav.next} →
          </button>
        </div>
      </footer>
    </div>
  )
}

function RunStepButton() {
  const t = useI18n()
  const state = useAppState()
  const dispatch = useAppDispatch()

  const step = state.currentStep
  const stepState = state.stepStates[step]
  const isRunning = stepState === 'running'

  async function handleRun() {
    dispatch({ type: 'SET_STEP_RUNNING', step })
    try {
      const res = await fetch(`/api/step/${step}`, { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      dispatch({ type: 'SET_STEP_COMPLETE', step, data: json })
    } catch (err) {
      console.error('Step failed:', err)
      dispatch({ type: 'SET_STEP_ERROR', step })
    }
  }

  return (
    <button
      className={`${styles.navBtn} ${styles.runBtn}`}
      onClick={handleRun}
      disabled={isRunning}
    >
      {isRunning ? t.nav.running : `${t.nav.run_step} →`}
    </button>
  )
}
