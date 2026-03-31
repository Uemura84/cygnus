import { useState } from 'react'
import { useI18n } from '../App'
import styles from './Step.module.css'

const CONFIDENCE_STYLE = {
  HIGH:   { bg: '#dcfce7', color: '#166534' },
  MEDIUM: { bg: '#fef9c3', color: '#854d0e' },
  LOW:    { bg: '#f1f5f9', color: '#475569' },
}

const AVAIL_STYLE = {
  'Internal only':        { bg: '#ffedd5', color: '#9a3412' },
  'Partially available':  { bg: '#fef9c3', color: '#854d0e' },
  'Partially in CVM filings, full detail internal': { bg: '#fef9c3', color: '#854d0e' },
  'Internal only — CVM reports only top-level 3.02 COGS': { bg: '#ffedd5', color: '#9a3412' },
  'Internal only — CVM reports consolidated revenue':     { bg: '#ffedd5', color: '#9a3412' },
  'Internal only — may be partially disclosed in explanatory notes': { bg: '#ffedd5', color: '#9a3412' },
  'Internal only — some volume data in quarterly earnings releases': { bg: '#ffedd5', color: '#9a3412' },
  'Internal only — CAPEX total available in CVM cash flow statement': { bg: '#ffedd5', color: '#9a3412' },
}

const PRIORITY_STYLE = {
  CRITICAL: { bg: '#fee2e2', color: '#991b1b' },
  HIGH:     { bg: '#ffedd5', color: '#9a3412' },
  MEDIUM:   { bg: '#fef9c3', color: '#854d0e' },
}

function availStyle(avail) {
  return AVAIL_STYLE[avail] ?? (
    avail?.toLowerCase().includes('internal') ? { bg: '#ffedd5', color: '#9a3412' } :
    avail?.toLowerCase().includes('partial')  ? { bg: '#fef9c3', color: '#854d0e' } :
    { bg: '#f1f5f9', color: '#475569' }
  )
}

export default function Step7Hypotheses({ stepState, data }) {
  const t = useI18n()
  const d = data?.data
  // First 3 expanded by default
  const [expanded, setExpanded] = useState(new Set(['H1', 'H2', 'H3']))

  function toggle(id) {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step7.title}</h2>
      <p className={styles.description}>{t.step7.description}</p>

      {stepState === 'running' && (
        <div className={styles.running}>{t.step7.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>

          {/* Primary finding banner */}
          {d.primary_finding?.pattern && (
            <div style={{ background: '#eff6ff', border: '2px solid #2563eb', borderRadius: '8px', padding: '14px 18px', marginBottom: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px', flexWrap: 'wrap', marginBottom: '6px' }}>
                <span style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#1d4ed8' }}>
                  {t.step7.primary_finding}
                </span>
                <strong style={{ fontSize: '0.95rem', color: '#1e293b' }}>{d.primary_finding.pattern}</strong>
                {d.primary_finding.magnitude && (
                  <span style={{ fontFamily: 'monospace', fontSize: '0.85rem', color: '#dc2626', fontWeight: 700 }}>
                    {d.primary_finding.magnitude}
                  </span>
                )}
              </div>
              {d.primary_finding.description && (
                <p style={{ fontSize: '0.84rem', color: '#334155', lineHeight: 1.55, margin: 0 }}>{d.primary_finding.description}</p>
              )}
            </div>
          )}

          {/* Hypotheses */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step7.hypotheses}</h3>
            {t.step7.source_note && (
              <p style={{ fontSize: '0.75rem', color: '#94a3b8', fontStyle: 'italic', margin: '-6px 0 14px' }}>
                {t.step7.source_note}
              </p>
            )}
            {d.hypotheses?.map((h) => {
              const confStyle = CONFIDENCE_STYLE[h.confidence] ?? CONFIDENCE_STYLE.LOW
              const isOpen = expanded.has(h.id)
              return (
                <div key={h.id} style={{ marginBottom: '10px', border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden' }}>
                  {/* Collapsed header */}
                  <button
                    onClick={() => toggle(h.id)}
                    style={{
                      width: '100%', display: 'flex', alignItems: 'center', gap: '10px',
                      padding: '12px 16px', background: isOpen ? '#f8fafc' : '#fff',
                      border: 'none', cursor: 'pointer', textAlign: 'left',
                    }}
                  >
                    <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: '#94a3b8', flexShrink: 0 }}>{h.id}</span>
                    <span style={{ flex: 1, fontSize: '0.88rem', fontWeight: 600, color: '#1e293b' }}>{h.theory}</span>
                    <span style={{ background: confStyle.bg, color: confStyle.color, borderRadius: '4px', padding: '2px 8px', fontSize: '0.72rem', fontWeight: 700, flexShrink: 0 }}>
                      {h.confidence}
                    </span>
                    <span style={{ color: '#94a3b8', fontSize: '0.75rem', flexShrink: 0 }}>{isOpen ? '▲' : '▼'}</span>
                  </button>

                  {/* Expanded body */}
                  {isOpen && (
                    <div style={{ padding: '0 16px 16px', borderTop: '1px solid #f1f5f9' }}>
                      <p style={{ fontSize: '0.84rem', color: '#334155', lineHeight: 1.65, marginTop: '12px', marginBottom: '12px' }}>{h.mechanism}</p>

                      <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', marginBottom: h.supporting_findings?.length ? '10px' : 0 }}>
                        <div style={{ minWidth: '140px' }}>
                          <span style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b' }}>
                            {t.step7.data_needed}
                          </span>
                          <p style={{ margin: '4px 0 0', fontSize: '0.82rem', color: '#334155', lineHeight: 1.4 }}>{h.data_needed}</p>
                        </div>
                        <div style={{ flexShrink: 0 }}>
                          <span style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b', display: 'block', marginBottom: '4px' }}>
                            {t.step7.data_availability}
                          </span>
                          {(() => {
                            const as = availStyle(h.data_availability)
                            const label = h.data_availability?.includes('Partially') ? t.step7.partially_available : t.step7.internal_only
                            return (
                              <span style={{ background: as.bg, color: as.color, borderRadius: '4px', padding: '2px 8px', fontSize: '0.78rem', fontWeight: 600 }}>
                                {label}
                              </span>
                            )
                          })()}
                        </div>
                      </div>

                      {h.supporting_findings?.length > 0 && (
                        <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '8px' }}>
                          <span style={{ fontWeight: 600 }}>{t.step7.supporting_findings}:</span>{' '}
                          {h.supporting_findings.join(', ')}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* Data Readiness Gap */}
          {d.data_readiness_gap?.length > 0 && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step7.data_readiness}</h3>
              <div style={{ overflowX: 'auto' }}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'left' }}>{t.step7.data_needed}</th>
                      <th style={{ textAlign: 'left' }}>Source</th>
                      <th style={{ textAlign: 'center' }}>{t.step7.data_availability}</th>
                      <th style={{ textAlign: 'center' }}>Priority</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.data_readiness_gap.map((q, i) => {
                      const ps = PRIORITY_STYLE[q.priority] ?? PRIORITY_STYLE.MEDIUM
                      const as = availStyle(q.availability)
                      return (
                        <tr key={i}>
                          <td style={{ fontSize: '0.82rem' }}>{q.question}</td>
                          <td style={{ fontSize: '0.78rem', color: '#64748b', fontFamily: 'monospace' }}>{q.source}</td>
                          <td style={{ textAlign: 'center' }}>
                            <span style={{ background: as.bg, color: as.color, borderRadius: '4px', padding: '2px 8px', fontSize: '0.72rem', fontWeight: 600, whiteSpace: 'nowrap' }}>
                              {q.availability?.includes('Partially') ? t.step7.partially_available : t.step7.internal_only}
                            </span>
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <span style={{ background: ps.bg, color: ps.color, borderRadius: '4px', padding: '2px 8px', fontSize: '0.72rem', fontWeight: 700 }}>
                              {q.priority}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
