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
        {/* Row 1: logo + controls */}
        <div className={styles.headerBar}>
          <img src="/cygnus-logo-dark.svg" alt="Cygnus" className={styles.logo} />
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
        </div>
        {/* Row 2: company context strip */}
        <div className={styles.headerContext}>
          <span className={styles.companyName}>{state.companyName ?? 'BRASKEM S.A.'}</span>
          <span className={styles.contextSep}>—</span>
          <span className={styles.contextLabel}>{t.header.analysis_context ?? 'Financial Signal Analysis'}</span>
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

      {/* Footer — Previous / Next only */}
      <footer className={styles.footer}>
        <button
          className={styles.navBtnPrev}
          disabled={state.currentStep <= 1}
          onClick={() => dispatch({ type: 'NAVIGATE_TO_STEP', step: state.currentStep - 1 })}
        >
          ← {t.nav.previous}
        </button>
        <button
          className={styles.navBtnNext}
          disabled={state.currentStep >= 9}
          onClick={() => dispatch({ type: 'NAVIGATE_TO_STEP', step: state.currentStep + 1 })}
        >
          {t.nav.next} →
        </button>
      </footer>
    </div>
  )
}
