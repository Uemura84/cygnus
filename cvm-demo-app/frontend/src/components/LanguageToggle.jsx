import { useI18n, useAppState, useAppDispatch } from '../App'
import styles from './LanguageToggle.module.css'

export default function LanguageToggle() {
  const t = useI18n()
  const state = useAppState()
  const dispatch = useAppDispatch()

  function handleToggle() {
    dispatch({ type: 'TOGGLE_LANGUAGE' })
    const newLang = state.language === 'en' ? 'pt-br' : 'en'
    fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ language: newLang }),
    }).catch(() => {})
  }

  return (
    <button className={styles.btn} onClick={handleToggle}>
      {t.header.lang_toggle}
    </button>
  )
}
