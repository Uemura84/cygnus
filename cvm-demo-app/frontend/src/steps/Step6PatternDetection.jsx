import { useState } from 'react'
import { useI18n, useAppState } from '../App'
import FindingChart from '../components/charts/FindingChart'
import styles from './Step.module.css'

const SEVERITY_ORDER = { HIGH: 0, MEDIUM: 1, LOW: 2 }
const SEVERITY_BADGE = { HIGH: styles.badgeHigh, MEDIUM: styles.badgeMedium, LOW: styles.badgeLow }
const CONFIDENCE_BADGE = { HIGH: styles.badgeLow, MEDIUM: styles.badgeMedium, LOW: styles.badgeHigh }

function formatKey(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatDpValue(val) {
  if (val == null) return '—'
  if (typeof val === 'number') return val % 1 === 0 ? val.toString() : val.toFixed(1)
  return String(val)
}

export default function Step6PatternDetection({ stepState, data }) {
  const t = useI18n()
  const appState = useAppState()
  const d = data?.data
  const [expanded, setExpanded] = useState(null)

  const timeSeries = appState.stepData[4]?.data?.time_series ?? []

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step6.title}</h2>
      <p className={styles.description}>{t.step6.description}</p>

      {stepState === 'running' && (
        <div className={styles.running}>{t.step6.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>
          <div className={styles.statsGrid}>
            <Stat label={t.step6.algorithms_run} value={d.algorithms_run?.length} />
            <Stat label={t.step6.raw_findings} value={d.raw_findings} />
          </div>

          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step6.findings_title}</h3>
            {[...(d.findings ?? [])].sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3)).map((f) => (
              <div key={f.id} style={{ marginBottom: '20px', borderBottom: '1px solid #f1f5f9', paddingBottom: '20px' }}>

                {/* Header row */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
                  <span style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: '#94a3b8', flexShrink: 0 }}>{f.id}</span>
                  <strong style={{ fontSize: '0.9rem', marginRight: '4px' }}>{f.pattern}</strong>
                  <span className={SEVERITY_BADGE[f.severity]}>{f.severity}</span>
                  {f.confidence && (
                    <span className={CONFIDENCE_BADGE[f.confidence]} style={{ opacity: 0.85 }}>
                      {t.step6.confidence_label}: {f.confidence}
                    </span>
                  )}
                  {f.period && (
                    <span style={{ fontSize: '0.78rem', color: '#64748b', background: '#f1f5f9', borderRadius: '4px', padding: '2px 8px' }}>
                      {f.period}
                    </span>
                  )}
                </div>

                {/* Description */}
                <p style={{ fontSize: '0.84rem', color: '#475569', marginBottom: '8px', lineHeight: 1.55 }}>{f.description}</p>

                {/* Data points */}
                {f.data_points && Object.keys(f.data_points).length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 20px', marginBottom: '10px' }}>
                    {Object.entries(f.data_points)
                      .filter(([k]) => k !== 'period')
                      .map(([k, v]) => (
                        <span key={k} style={{ fontSize: '0.78rem', color: '#64748b' }}>
                          <span style={{ color: '#94a3b8' }}>{formatKey(k)}:</span>{' '}
                          <strong style={{ color: '#334155' }}>{formatDpValue(v)}</strong>
                        </span>
                      ))}
                  </div>
                )}

                {/* Chart toggle */}
                <button
                  style={{ fontSize: '0.78rem', color: '#2563eb', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                  onClick={() => setExpanded(expanded === f.id ? null : f.id)}
                >
                  {expanded === f.id ? t.step6.hide_chart : t.step6.show_chart}
                </button>
                {expanded === f.id && (
                  <div style={{ marginTop: '12px' }}>
                    <FindingChart finding={f} timeSeries={timeSeries} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div className={styles.stat}>
      <span className={styles.statLabel}>{label}</span>
      <span className={styles.statValue}>{value}</span>
    </div>
  )
}
