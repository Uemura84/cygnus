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
      <div className={styles.body}>
        <StepSidebar />

        {/* Content column: context row + scrollable main + footer */}
        <div className={styles.contentCol}>
          <main className={styles.main}>

            {/* Context row — scrolls with content */}
            <div className={styles.contextRow}>
              <div className={styles.contextLeft}>
                <span className={styles.companyName}>
                  {state.companyName ?? 'BRASKEM S.A.'}
                </span>
                <span className={styles.contextSep}>—</span>
                <span className={styles.contextLabel}>
                  {t.header?.analysis_context ?? 'Financial Signal Analysis'}
                </span>
              </div>
              <div className={styles.contextRight}>
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

            {state.cacheMode && (
              <div className={styles.cacheBanner}>{t.cache_banner}</div>
            )}

            <div className={styles.stepArea}>
              <StepContent />
            </div>
          </main>

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
      </div>
    </div>
  )
}
