import { useEffect, useRef, useState } from 'react'
import { useI18n, useAppState, useAppDispatch } from '../App'
import styles from './CompanySelector.module.css'

export default function CompanySelector() {
  const t = useI18n()
  const state = useAppState()
  const dispatch = useAppDispatch()

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const debounceRef = useRef(null)
  const inputRef = useRef(null)
  const containerRef = useRef(null)

  const cs = t.company_selector ?? {}

  // Close on outside click
  useEffect(() => {
    function handleClick(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  // Focus input when opened
  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus()
      setQuery('')
      setResults([])
    }
  }, [open])

  // Debounced search
  useEffect(() => {
    if (!open) return
    clearTimeout(debounceRef.current)
    if (!query.trim()) {
      setResults([])
      setLoading(false)
      return
    }
    setLoading(true)
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`/api/companies/search?q=${encodeURIComponent(query)}`)
        const json = await res.json()
        setResults(json.results ?? [])
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => clearTimeout(debounceRef.current)
  }, [query, open])

  // Dismiss toast after 4 seconds
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 4000)
    return () => clearTimeout(t)
  }, [toast])

  async function handleSelect(company) {
    setOpen(false)
    if (company.name === state.companyName) return

    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company_name: company.name }),
      })
    } catch {
      // proceed optimistically — backend will catch up on next step run
    }

    dispatch({ type: 'SET_COMPANY', companyName: company.name })
    dispatch({ type: 'RESET_PIPELINE' })

    const msg = (cs.company_changed ?? 'Company changed to {company}. Run the pipeline from Step 1.')
      .replace('{company}', company.name)
    setToast(msg)
  }

  const displayName = state.companyName
    ? state.companyName.split(' ')[0].charAt(0).toUpperCase() +
      state.companyName.split(' ')[0].slice(1).toLowerCase()
    : '—'

  return (
    <div className={styles.wrapper} ref={containerRef}>
      {/* Trigger button */}
      <button
        className={styles.trigger}
        onClick={() => setOpen((o) => !o)}
        title={cs.change_company ?? 'Change company'}
      >
        <span className={styles.triggerIcon}>🔍</span>
        <span className={styles.triggerName}>{displayName}</span>
        <span className={styles.triggerArrow}>{open ? '▲' : '▼'}</span>
      </button>

      {/* Dropdown */}
      {open && (
        <div className={styles.dropdown}>
          <input
            ref={inputRef}
            type="text"
            className={styles.searchInput}
            placeholder={cs.search_placeholder ?? 'Search company...'}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />

          <div className={styles.resultList}>
            {loading && (
              <div className={styles.hint}>{cs.loading ?? 'Loading...'}</div>
            )}
            {!loading && query && results.length === 0 && (
              <div className={styles.hint}>{cs.no_results ?? 'No companies found'}</div>
            )}
            {!loading && !query && (
              <div className={styles.hint} style={{ fontStyle: 'italic' }}>
                {cs.search_placeholder ?? 'Search company...'}
              </div>
            )}
            {results.map((r) => (
              <button
                key={r.cvm_code || r.name}
                className={`${styles.resultItem} ${r.name === state.companyName ? styles.resultItemActive : ''}`}
                onClick={() => handleSelect(r)}
              >
                <span className={styles.resultName}>{r.name}</span>
                {r.sector && r.sector !== 'Unknown' ? (
                  <span className={styles.sectorBadge}>{r.sector}</span>
                ) : (
                  <span className={styles.sectorBadgeAi}>{cs.sector_detected_by_ai ?? 'Sector: AI'}</span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Toast notification */}
      {toast && (
        <div className={styles.toast}>{toast}</div>
      )}
    </div>
  )
}
