import { useState } from 'react'
import { useI18n } from '../App'
import styles from './Step.module.css'

const CATEGORY_BADGE = {
  core:       { bg: '#dbeafe', color: '#1d4ed8', label: 'Core' },
  supporting: { bg: '#dcfce7', color: '#166534', label: 'Supporting' },
  contextual: { bg: '#f1f5f9', color: '#64748b', label: 'Context' },
  anomalies:  { bg: '#fef9c3', color: '#854d0e', label: 'Anomaly' },
}

const ARC_KEYS = [
  { key: 'setup',       labelKey: 'story_setup',       icon: '📊' },
  { key: 'evidence',    labelKey: 'story_evidence',    icon: '📉' },
  { key: 'inflection',  labelKey: 'story_inflection',  icon: '⚠️' },
  { key: 'implication', labelKey: 'story_implication', icon: '🔭' },
  { key: 'question',    labelKey: 'story_question',    icon: '❓' },
]

export default function Step8Summary({ stepState, data }) {
  const t = useI18n()
  const d = data?.data
  const [limitationsOpen, setLimitationsOpen] = useState(false)

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step8.title}</h2>
      <p className={styles.description}>{t.step8.description}</p>

      {stepState === 'running' && (
        <div className={styles.running}>{t.step8.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>

          {/* Headline */}
          {d.headline && (
            <div style={{ marginBottom: '24px', padding: '16px 20px', background: '#1e293b', borderRadius: '10px' }}>
              <div style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#94a3b8', marginBottom: '6px' }}>
                {t.step8.headline_label}
              </div>
              <p style={{ fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc', lineHeight: 1.4, margin: 0 }}>{d.headline}</p>
            </div>
          )}

          {/* Story arc */}
          {d.story_arc && (
            <div className={styles.section}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {ARC_KEYS.map(({ key, labelKey, icon }) => {
                  const text = d.story_arc[key]
                  if (!text) return null
                  return (
                    <div key={key} style={{ display: 'flex', gap: '14px', alignItems: 'flex-start', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '14px 16px' }}>
                      <span style={{ fontSize: '1.1rem', flexShrink: 0, marginTop: '1px' }}>{icon}</span>
                      <div>
                        <div style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: '#64748b', marginBottom: '4px' }}>
                          {t.step8[labelKey]}
                        </div>
                        <p style={{ fontSize: '0.87rem', color: '#334155', lineHeight: 1.65, margin: 0 }}>{text}</p>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Key findings table */}
          {d.key_findings_summary?.length > 0 && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step8.key_findings}</h3>
              <div style={{ overflowX: 'auto' }}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'center', width: '48px' }}>{t.step8.finding_rank}</th>
                      <th>{t.step8.finding_category}</th>
                      <th>{t.step8.finding_label}</th>
                      <th>{t.step8.finding_evidence}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.key_findings_summary.map((f) => {
                      const cat = CATEGORY_BADGE[f.category] ?? CATEGORY_BADGE.contextual
                      return (
                        <tr key={f.rank}>
                          <td style={{ textAlign: 'center', fontWeight: 700 }}>{f.rank}</td>
                          <td>
                            <span style={{ background: cat.bg, color: cat.color, borderRadius: '4px', padding: '2px 8px', fontSize: '0.72rem', fontWeight: 700 }}>
                              {cat.label}
                            </span>
                          </td>
                          <td style={{ fontSize: '0.84rem' }}>{f.finding}</td>
                          <td style={{ fontSize: '0.82rem', color: '#475569' }}>{f.evidence}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Transition to offer */}
          {d.transition_to_offer && (
            <div style={{ background: '#eff6ff', border: '2px solid #2563eb', borderRadius: '10px', padding: '18px 20px', marginBottom: '20px' }}>
              <div style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#1d4ed8', marginBottom: '8px' }}>
                {t.step8.transition_label}
              </div>
              <p style={{ fontSize: '0.9rem', color: '#1e40af', lineHeight: 1.65, margin: 0 }}>{d.transition_to_offer}</p>
            </div>
          )}

          {/* Data limitations (collapsible) */}
          {d.data_limitations?.length > 0 && (
            <div className={styles.section}>
              <button
                style={{ fontSize: '0.78rem', color: '#64748b', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                onClick={() => setLimitationsOpen(o => !o)}
              >
                {limitationsOpen ? '▲' : '▼'} {t.step8.data_limitations}
              </button>
              {limitationsOpen && (
                <ul style={{ paddingLeft: '18px', marginTop: '10px', fontSize: '0.82rem', color: '#64748b', lineHeight: 1.7 }}>
                  {d.data_limitations.map((l, i) => <li key={i}>{l}</li>)}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
