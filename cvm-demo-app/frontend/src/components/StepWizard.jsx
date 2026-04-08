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

      {/* Footer — Previous / Next only */}
      <footer className={styles.footer}>
        <button
          className={styles.navBtn}
          disabled={state.currentStep <= 1}
          onClick={() => dispatch({ type: 'NAVIGATE_TO_STEP', step: state.currentStep - 1 })}
        >
          ← {t.nav.previous}
        </button>
        <button
          className={styles.navBtn}
          disabled={state.currentStep >= 9}
          onClick={() => dispatch({ type: 'NAVIGATE_TO_STEP', step: state.currentStep + 1 })}
        >
          {t.nav.next} →
        </button>
      </footer>
    </div>
  )
}
