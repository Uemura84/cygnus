import { useState } from 'react'
import { useI18n, useAppState } from '../App'
import FindingChart from '../components/charts/FindingChart'
import RiskGauge from '../components/charts/RiskGauge'
import styles from './Step.module.css'

const SEVERITY_BADGE = { HIGH: styles.badgeHigh, MEDIUM: styles.badgeMedium, LOW: styles.badgeLow, CRITICAL: styles.badgeHigh }
const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
const CONFIDENCE_BADGE = { HIGH: styles.badgeLow, MEDIUM: styles.badgeMedium, LOW: styles.badgeHigh }

const SEVERITY_BORDER = { CRITICAL: '#991b1b', HIGH: '#E24B4A', MEDIUM: '#EF9F27', LOW: 'var(--blue)' }

function formatKey(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatDpValue(val) {
  if (val == null) return '—'
  if (typeof val === 'number') return val % 1 === 0 ? val.toString() : val.toFixed(1)
  return String(val)
}

// Module grouping configuration
const MODULE_ORDER = ['profitability', 'balance_sheet_health', 'cash_flow_quality', 'stacked']

// All module headers use navy. Modules are differentiated by Signal Blue left border opacity.
const MODULE_STYLE = {
  profitability: {
    headerColor: '#fff',
    headerBg: 'var(--navy)',
    headerBorder: 'var(--blue)',         // full opacity — primary module
    accentBorder: 'rgba(30,144,255,1.0)',
  },
  balance_sheet_health: {
    headerColor: '#fff',
    headerBg: 'var(--navy)',
    headerBorder: 'rgba(30,144,255,0.55)', // 55% opacity
    accentBorder: 'rgba(30,144,255,0.55)',
  },
  cash_flow_quality: {
    headerColor: '#fff',
    headerBg: 'var(--navy)',
    headerBorder: 'rgba(30,144,255,0.35)', // 35% opacity
    accentBorder: 'rgba(30,144,255,0.35)',
  },
  stacked: {
    headerColor: '#fff',
    headerBg: 'var(--navy)',
    headerBorder: 'var(--blue)',         // full opacity — diagnoses are prominent
    accentBorder: 'var(--blue)',
  },
}

const CATEGORY_ORDER = ['core', 'supporting', 'contextual', 'anomalies']

const CATEGORY_STYLE = {
  core: { border: '2px solid var(--blue)', background: 'var(--blue-dim)', titleColor: 'var(--blue)' },
  supporting: { border: '1px solid rgba(11,31,58,0.07)', background: '#fff', titleColor: 'var(--charcoal)' },
  contextual: { border: '1px solid rgba(11,31,58,0.07)', background: 'var(--offwhite)', titleColor: 'var(--gray)' },
  anomalies: { border: '1px solid rgba(239,159,39,0.3)', background: 'rgba(239,159,39,0.05)', titleColor: '#EF9F27' },
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

  // Group findings by module
  const byModule = { profitability: [], balance_sheet_health: [], cash_flow_quality: [], stacked: [] }
  if (d?.findings) {
    for (const f of d.findings) {
      const mod = f.module || 'profitability'
      if (mod in byModule) {
        byModule[mod].push(f)
      } else {
        byModule.profitability.push(f)
      }
    }
  }

  // For profitability: sub-group by category (core/supporting/contextual/anomalies)
  const profByCategory = { core: [], supporting: [], contextual: [], anomalies: [] }
  for (const f of byModule.profitability) {
    const cat = findingCategory[f.id] || 'contextual'
    if (cat in profByCategory) {
      profByCategory[cat].push(f)
    } else {
      profByCategory.contextual.push(f)
    }
  }
  for (const cat of CATEGORY_ORDER) {
    profByCategory[cat].sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 4) - (SEVERITY_ORDER[b.severity] ?? 4))
  }

  // For BS and CF: sort by severity only
  byModule.balance_sheet_health.sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 4) - (SEVERITY_ORDER[b.severity] ?? 4))
  byModule.cash_flow_quality.sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 4) - (SEVERITY_ORDER[b.severity] ?? 4))
  byModule.stacked.sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 4) - (SEVERITY_ORDER[b.severity] ?? 4))

  const MODULE_LABEL = {
    profitability: t.step6.module_profitability ?? 'Profitability Analysis',
    balance_sheet_health: t.step6.module_balance_sheet ?? 'Balance Sheet Health',
    cash_flow_quality: t.step6.module_cash_flow ?? 'Cash Flow Quality',
    stacked: t.step6.module_diagnoses ?? 'Cross-Module Diagnoses',
  }

  const MODULE_COUNT_LABEL = {
    profitability: d?.profitability_findings_count,
    balance_sheet_health: d?.bs_findings_count,
    cash_flow_quality: d?.cf_findings_count,
    stacked: d?.stacked_diagnoses_count,
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

          {/* Module counts summary */}
          {(d.bs_findings_count > 0 || d.cf_findings_count > 0 || d.stacked_diagnoses_count > 0) && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
              {d.profitability_findings_count > 0 && (
                <ModuleCountBadge label={MODULE_LABEL.profitability} count={d.profitability_findings_count} opacity={1} />
              )}
              {d.bs_findings_count > 0 && (
                <ModuleCountBadge label={MODULE_LABEL.balance_sheet_health} count={d.bs_findings_count} opacity={0.55} />
              )}
              {d.cf_findings_count > 0 && (
                <ModuleCountBadge label={MODULE_LABEL.cash_flow_quality} count={d.cf_findings_count} opacity={0.35} />
              )}
              {d.stacked_diagnoses_count > 0 && (
                <ModuleCountBadge label={MODULE_LABEL.stacked} count={d.stacked_diagnoses_count} opacity={1} />
              )}
            </div>
          )}

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

          {/* Findings grouped by module */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step6.findings_title}</h3>

            {/* Module 1: Profitability — sub-grouped by category */}
            {byModule.profitability.length > 0 && (
              <ModuleSection
                label={MODULE_LABEL.profitability}
                count={d.profitability_findings_count}
                moduleStyle={MODULE_STYLE.profitability}
              >
                {CATEGORY_ORDER.map((cat) => {
                  const catFindings = profByCategory[cat]
                  if (!catFindings?.length) return null
                  return (
                    <div key={cat} style={{ marginBottom: '20px' }}>
                      <h5 style={{ fontSize: '0.66rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.13em', color: 'var(--blue)', fontFamily: "'JetBrains Mono', monospace", marginBottom: '8px' }}>
                        {CATEGORY_LABEL[cat]}
                      </h5>
                      {catFindings.map((f) => (
                        <FindingCard key={f.id} f={f} cardStyle={CATEGORY_STYLE[cat]} timeSeries={timeSeries} t={t} />
                      ))}
                    </div>
                  )
                })}
              </ModuleSection>
            )}

            {/* Module 2: Balance Sheet Health */}
            {byModule.balance_sheet_health.length > 0 && (
              <ModuleSection
                label={MODULE_LABEL.balance_sheet_health}
                count={d.bs_findings_count}
                moduleStyle={MODULE_STYLE.balance_sheet_health}
              >
                {byModule.balance_sheet_health.map((f) => (
                  <FindingCard key={f.id} f={f} cardStyle={{ border: '1px solid var(--blue-line)', background: '#fff' }} timeSeries={timeSeries} t={t} />
                ))}
              </ModuleSection>
            )}

            {/* Module 3: Cash Flow Quality */}
            {byModule.cash_flow_quality.length > 0 && (
              <ModuleSection
                label={MODULE_LABEL.cash_flow_quality}
                count={d.cf_findings_count}
                moduleStyle={MODULE_STYLE.cash_flow_quality}
              >
                {byModule.cash_flow_quality.map((f) => (
                  <FindingCard key={f.id} f={f} cardStyle={{ border: '1px solid rgba(30,144,255,0.15)', background: '#fff' }} timeSeries={timeSeries} t={t} />
                ))}
              </ModuleSection>
            )}

            {/* Cross-Module Diagnoses (stacked) */}
            {byModule.stacked.length > 0 && (
              <ModuleSection
                label={MODULE_LABEL.stacked}
                count={d.stacked_diagnoses_count}
                moduleStyle={MODULE_STYLE.stacked}
                isdiagnosis
              >
                {byModule.stacked.map((f) => (
                  <DiagnosisCard key={f.id} f={f} t={t} />
                ))}
              </ModuleSection>
            )}

          </div>
        </div>
      )}
    </div>
  )
}

function ModuleCountBadge({ label, count, opacity = 1 }) {
  const border = opacity < 1 ? `rgba(30,144,255,${opacity})` : 'var(--blue)'
  return (
    <span style={{
      fontSize: '0.72rem',
      fontWeight: 600,
      color: 'var(--blue)',
      background: 'var(--blue-dim)',
      border: `1px solid ${border}`,
      borderRadius: '12px',
      padding: '3px 10px',
      fontFamily: "'JetBrains Mono', monospace",
      opacity: opacity < 1 ? 0.7 + (0.3 * opacity) : 1,
    }}>
      {label}: {count}
    </span>
  )
}

function ModuleSection({ label, count, moduleStyle, isdiagnosis, children }) {
  const [collapsed, setCollapsed] = useState(false)
  return (
    <div style={{ marginBottom: '28px', borderRadius: '8px', overflow: 'hidden', border: '1px solid rgba(11,31,58,0.1)', borderLeft: `4px solid ${moduleStyle.accentBorder}` }}>
      <button
        onClick={() => setCollapsed(v => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          padding: '10px 16px',
          background: moduleStyle.headerBg,
          border: 'none',
          cursor: 'pointer',
          color: moduleStyle.headerColor,
          fontWeight: 700,
          fontSize: '0.82rem',
          textAlign: 'left',
          letterSpacing: isdiagnosis ? '0.03em' : '0',
        }}
      >
        <span>{label} {count != null && <span style={{ fontWeight: 400, opacity: 0.75 }}>({count})</span>}</span>
        <span style={{ fontSize: '0.7rem', opacity: 0.6 }}>{collapsed ? '▶' : '▼'}</span>
      </button>
      {!collapsed && (
        <div style={{ padding: '16px' }}>
          {children}
        </div>
      )}
    </div>
  )
}

function DiagnosisCard({ f, t }) {
  const [expanded, setExpanded] = useState(true)
  const borderColor = SEVERITY_BORDER[f.severity] || 'var(--blue)'
  const contributing = f.contributing_signals

  return (
    <div style={{
      marginBottom: '12px',
      background: 'var(--blue-dim)',
      border: '1px solid var(--blue-line)',
      borderLeft: `4px solid ${borderColor}`,
      borderRadius: '6px',
      padding: '14px 16px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '0.7rem',
          color: 'var(--blue)',
          background: 'var(--blue-dim)',
          padding: '2px 7px',
          borderRadius: '4px',
          flexShrink: 0,
          letterSpacing: '0.03em',
        }}>{f.id}</span>
        <strong style={{ fontSize: '0.88rem', color: 'var(--navy)' }}>{f.pattern}</strong>
        <span className={SEVERITY_BADGE[f.severity]}>{f.severity}</span>
      </div>

      {/* Description */}
      <p style={{ fontSize: '0.84rem', color: 'var(--charcoal)', marginBottom: '10px', lineHeight: 1.55 }}>{f.description}</p>

      {/* Contributing signals */}
      {contributing && Object.keys(contributing).length > 0 && (
        <div>
          <button
            style={{ fontSize: '0.75rem', color: 'var(--blue)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginBottom: '8px' }}
            onClick={() => setExpanded(v => !v)}
          >
            {expanded
              ? (t.step6.hide_signals ?? '▼ Hide contributing signals')
              : (t.step6.show_signals ?? '▶ Show contributing signals')}
          </button>
          {expanded && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {Object.entries(contributing).map(([moduleName, signals]) =>
                signals.map((s, i) => (
                  <span key={`${moduleName}-${i}`} style={{
                    fontSize: '0.72rem',
                    background: 'var(--blue-dim)',
                    color: 'var(--blue)',
                    border: '1px solid var(--blue-line)',
                    borderRadius: '4px',
                    padding: '2px 8px',
                    fontFamily: "'JetBrains Mono', monospace",
                  }}>
                    {s.code || s.signal} <span style={{ opacity: 0.65 }}>({moduleName})</span>
                  </span>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function FindingCard({ f, cardStyle, timeSeries, t }) {
  const [showChart, setShowChart] = useState(false)
  const borderColor = SEVERITY_BORDER[f.severity] || 'var(--blue)'

  return (
    <div style={{
      marginBottom: '12px',
      background: '#fff',
      border: '1px solid rgba(11,31,58,0.07)',
      borderLeft: `4px solid ${borderColor}`,
      borderRadius: '6px',
      padding: '14px 16px',
      transition: 'box-shadow 0.15s',
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '0.7rem',
          color: 'var(--blue)',
          background: 'var(--blue-dim)',
          padding: '2px 7px',
          borderRadius: '4px',
          flexShrink: 0,
          letterSpacing: '0.03em',
        }}>{f.id}</span>
        <strong style={{ fontSize: '0.88rem' }}>{f.pattern}</strong>
        <span className={SEVERITY_BADGE[f.severity]}>{f.severity}</span>
        {f.confidence && (
          <span className={CONFIDENCE_BADGE[f.confidence]} style={{ opacity: 0.85 }}>
            {t.step6.confidence_label}: {f.confidence}
          </span>
        )}
        {f.period && (
          <span style={{ fontSize: '0.78rem', color: 'var(--gray)', background: 'var(--offwhite)', borderRadius: '4px', padding: '2px 8px' }}>
            {f.period}
          </span>
        )}
      </div>

      {/* Estimated Impact */}
      {f.estimated_impact && (
        <div style={{
          background: 'rgba(239,159,39,0.07)',
          border: '1px solid rgba(239,159,39,0.3)',
          borderRadius: '6px',
          padding: '8px 12px',
          marginBottom: '10px',
        }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#EF9F27' }}>
              {t.materiality?.estimated_impact ?? 'Estimated Impact'}
            </span>
            <strong style={{ fontSize: '1rem', color: 'var(--navy)' }}>{f.estimated_impact.formatted}</strong>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--gray)', marginTop: '2px' }}>
            <span style={{ fontWeight: 600 }}>{t.materiality?.basis ?? 'Basis'}:</span>{' '}
            <span
              title={f.estimated_impact.caveat}
              style={{ cursor: 'help', borderBottom: '1px dotted rgba(239,159,39,0.5)' }}
            >
              {f.estimated_impact.basis}
            </span>
          </div>
        </div>
      )}

      {/* Description */}
      <p style={{ fontSize: '0.84rem', color: 'var(--gray)', marginBottom: '8px', lineHeight: 1.55 }}>{f.description}</p>

      {/* Data points */}
      {f.data_points && Object.keys(f.data_points).length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 20px', marginBottom: '10px' }}>
          {Object.entries(f.data_points)
            .filter(([k]) => k !== 'period')
            .map(([k, v]) => (
              <span key={k} style={{ fontSize: '0.78rem', color: 'var(--gray)' }}>
                <span style={{ color: 'rgba(11,31,58,0.3)' }}>{formatKey(k)}:</span>{' '}
                <strong style={{ color: 'var(--charcoal)' }}>{formatDpValue(v)}</strong>
              </span>
            ))}
        </div>
      )}

      {/* Chart toggle */}
      <button
        style={{ fontSize: '0.78rem', color: 'var(--blue)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
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
