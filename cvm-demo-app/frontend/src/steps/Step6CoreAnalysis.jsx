import { useState } from 'react'
import { useI18n, useAppState } from '../App'
import FindingChart from '../components/charts/FindingChart'
import MacroTimeline from '../components/charts/MacroTimeline'
import RiskGauge from '../components/charts/RiskGauge'
import styles from './Step.module.css'

const SEVERITY_BADGE = { HIGH: styles.badgeHigh, MEDIUM: styles.badgeMedium, LOW: styles.badgeLow }
const SEVERITY_ORDER = { HIGH: 0, MEDIUM: 1, LOW: 2 }
const CONFIDENCE_BADGE = { HIGH: styles.badgeLow, MEDIUM: styles.badgeMedium, LOW: styles.badgeHigh }

function formatKey(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatDpValue(val) {
  if (val == null) return '—'
  if (typeof val === 'number') return val % 1 === 0 ? val.toString() : val.toFixed(1)
  return String(val)
}

const CATEGORY_ORDER = ['core', 'supporting', 'contextual', 'anomalies']

const CATEGORY_STYLE = {
  core: {
    border: '2px solid #2563eb',
    background: '#eff6ff',
    titleColor: '#1d4ed8',
  },
  supporting: {
    border: '1px solid #e2e8f0',
    background: '#fff',
    titleColor: '#334155',
  },
  contextual: {
    border: '1px solid #e2e8f0',
    background: '#f8fafc',
    titleColor: '#64748b',
  },
  anomalies: {
    border: '1px solid #fde68a',
    background: '#fffbeb',
    titleColor: '#92400e',
  },
}

export default function Step6CoreAnalysis({ stepState, data }) {
  const t = useI18n()
  const appState = useAppState()
  const d = data?.data

  const timeSeries = appState.stepData[4]?.data?.time_series ?? []

  // Build id → finding map and id → category map
  const findingById = {}
  const findingCategory = {}
  if (d?.findings) {
    for (const f of d.findings) findingById[f.id] = f
  }
  if (d?.finding_categories) {
    for (const [cat, ids] of Object.entries(d.finding_categories)) {
      for (const id of ids) findingCategory[id] = cat
    }
  }

  // All finding ids not in any category go to contextual
  const allIds = d?.findings?.map(f => f.id) ?? []
  for (const id of allIds) {
    if (!findingCategory[id]) findingCategory[id] = 'contextual'
  }

  // Group findings by category
  const byCategory = { core: [], supporting: [], contextual: [], anomalies: [] }
  if (d?.finding_categories) {
    for (const cat of CATEGORY_ORDER) {
      byCategory[cat] = (d.finding_categories[cat] ?? [])
        .map(id => findingById[id])
        .filter(Boolean)
        .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3))
    }
  } else if (d?.findings) {
    // Fallback: no categories, show all as supporting
    byCategory.supporting = [...d.findings].sort(
      (a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3)
    )
  }

  const CATEGORY_LABEL = {
    core: t.step6.core_findings,
    supporting: t.step6.supporting_evidence,
    contextual: t.step6.macro_context_section,
    anomalies: t.step6.anomalies,
  }

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step6.title}</h2>
      <p className={styles.description}>{t.step6.description}</p>

      {stepState === 'running' && (
        <div className={styles.running}>{t.step6.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>
          {/* Summary bar */}
          <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '20px' }}>
            <div className={styles.statsGrid} style={{ flex: 1 }}>
              <Stat label={t.step6.algorithms_run} value={d.algorithms_run?.length} />
              <Stat label={t.step6.raw_findings} value={d.raw_findings} />
              <Stat label={t.step6.risk_score} value={d.risk_score != null ? d.risk_score.toFixed(1) : '—'} />
              <Stat label={t.step6.risk_level} value={d.risk_level} />
            </div>
            {d.risk_score != null && (
              <RiskGauge score={d.risk_score} level={d.risk_level} />
            )}
          </div>

          {/* Composite signals */}
          {d.composite_signals?.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '20px' }}>
              {d.composite_signals.map((s) => (
                <span
                  key={s.composite_signal_type}
                  className={SEVERITY_BADGE[s.severity]}
                  title={s.explanation}
                >
                  {s.composite_signal_type}
                </span>
              ))}
            </div>
          )}

          {/* Findings by category */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step6.findings_title}</h3>
            {CATEGORY_ORDER.map((cat) => {
              const catFindings = byCategory[cat]
              if (!catFindings?.length) return null
              const cs = CATEGORY_STYLE[cat]
              return (
                <div key={cat} style={{ marginBottom: '24px' }}>
                  <h4 style={{ fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: cs.titleColor, marginBottom: '10px' }}>
                    {CATEGORY_LABEL[cat]}
                  </h4>
                  {catFindings.map((f) => (
                    <FindingCard
                      key={f.id}
                      f={f}
                      cardStyle={cs}
                      timeSeries={timeSeries}
                      t={t}
                    />
                  ))}
                </div>
              )
            })}
          </div>

          {/* Macro timeline */}
          {d.macro_timeline?.length > 0 && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step6.timeline_title}</h3>
              <MacroTimeline
                macroTimeline={d.macro_timeline}
                findings={d.findings ?? []}
                findingCategories={d.finding_categories ?? {}}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function FindingCard({ f, cardStyle, timeSeries, t }) {
  const [showChart, setShowChart] = useState(false)

  return (
    <div style={{
      marginBottom: '12px',
      border: cardStyle.border,
      background: cardStyle.background,
      borderRadius: '8px',
      padding: '14px 16px',
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '6px' }}>
        <span style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: '#94a3b8', flexShrink: 0 }}>{f.id}</span>
        <strong style={{ fontSize: '0.88rem' }}>{f.pattern}</strong>
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
        onClick={() => setShowChart(prev => !prev)}
      >
        {showChart ? t.step6.hide_chart : t.step6.show_chart}
      </button>
      {showChart && (
        <div style={{ marginTop: '12px' }}>
          <FindingChart finding={f} timeSeries={timeSeries} />
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
