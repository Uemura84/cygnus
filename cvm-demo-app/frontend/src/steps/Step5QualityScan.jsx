import { useState } from 'react'
import { useI18n, useAppState } from '../App'
import styles from './Step.module.css'

const FLAG_BADGE = {
  STATISTICAL_ANOMALY: styles.badgeHigh,
  DATA_ISSUE:          styles.badgeMedium,
  ACCOUNTING_EVENT:    styles.badgeLow,
  INFORMATIONAL:       styles.badgeLow,
}

const SEVERITY_BADGE = {
  HIGH:   styles.badgeHigh,
  MEDIUM: styles.badgeMedium,
  LOW:    styles.badgeLow,
}

/** Convert a bounds section dict → sorted array for BoundsTable. */
function boundsToRows(sectionObj, lang) {
  if (!sectionObj || typeof sectionObj !== 'object') return []
  return Object.entries(sectionObj).map(([metric, entry]) => ({
    metric,
    min: entry.min,
    max: entry.max,
    rationale: lang === 'en' ? (entry.rationale_en ?? '') : (entry.rationale_pt ?? entry.rationale_en ?? ''),
  }))
}


export default function Step5QualityScan({ stepState, data }) {
  const t        = useI18n()
  const appState = useAppState()
  const lang     = appState.language ?? 'en'
  const d        = data?.data

  // LLM-generated plausibility bounds (or default)
  const pb       = d?.plausibility_bounds
  const pbSource = pb?.source ?? 'default'
  const isLLM    = pbSource === 'llm'
  const sectorLabel = lang === 'en'
    ? (pb?.label_en ?? t.step5.sector_default_en)
    : (pb?.label_pt ?? t.step5.sector_default_pt)

  const profBounds = boundsToRows(pb?.profitability, lang)
  const bsBounds   = boundsToRows(pb?.balance_sheet, lang)
  const cfBounds   = boundsToRows(pb?.cash_flow, lang)

  // Per-section counts
  const profTotal   = d?.total_data_points                  ?? 0
  const profFlagged = d?.flagged                            ?? 0
  const bsTotal     = d?.bs_plausibility?.total_data_points ?? 0
  const bsFlagged   = d?.bs_plausibility?.flagged           ?? 0
  const cfTotal     = d?.cf_plausibility?.total_data_points ?? 0
  const cfFlagged   = d?.cf_plausibility?.flagged           ?? 0

  // Overall quality score across all three sections
  const totalAll   = profTotal + bsTotal + cfTotal
  const cleanAll   = (profTotal - profFlagged) + (bsTotal - bsFlagged) + (cfTotal - cfFlagged)
  const overallPct = totalAll > 0
    ? ((cleanAll / totalAll) * 100).toFixed(1)
    : (d?.quality_score != null ? (d.quality_score * 100).toFixed(1) : '—')

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step5.title}</h2>
      <p className={styles.description}>{t.step5.description}</p>

      {stepState === 'running' && (
        <div className={styles.running}>{t.step5.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>

          {/* ── Summary cards ─────────────────────────────────────── */}
          <div className={styles.statsGrid}>
            <SectionStat label={t.step5.profitability_label} points={profTotal} flags={profFlagged} t={t} />
            <SectionStat label={t.step5.bs_label}            points={bsTotal}   flags={bsFlagged}   t={t} />
            <SectionStat label={t.step5.cf_label}            points={cfTotal}   flags={cfFlagged}   t={t} />
            <Stat label={t.step5.quality_score} value={`${overallPct}%`} />
          </div>

          {/* ── Profitability plausibility ─────────────────────────── */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>
              {t.step5.profitability_bounds_title}
              {' '}
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.72rem', color: 'var(--gray)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                ({sectorLabel.toUpperCase()})
              </span>
            </h3>
            <BoundsSourceNote isLLM={isLLM} t={t} />
            <BoundsTable bounds={profBounds} t={t} />
            {d.flags?.length > 0
              ? <FlagsTable flags={d.flags} t={t} />
              : <NoFlags t={t} />
            }
          </div>

          {/* ── Balance sheet plausibility ─────────────────────────── */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>
              {t.step5.bs_bounds_title}
              {' '}
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.72rem', color: 'var(--gray)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                ({sectorLabel.toUpperCase()})
              </span>
            </h3>
            <BoundsSourceNote isLLM={isLLM} t={t} />
            <BoundsTable bounds={bsBounds} t={t} />
            {bsTotal > 0 && (
              d.bs_plausibility.flags?.length > 0
                ? <FlagsTable flags={d.bs_plausibility.flags} t={t} />
                : <NoFlags t={t} />
            )}
          </div>

          {/* ── Cash flow plausibility ────────────────────────────── */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>
              {t.step5.cf_bounds_title}
              {' '}
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.72rem', color: 'var(--gray)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                ({sectorLabel.toUpperCase()})
              </span>
            </h3>
            <BoundsSourceNote isLLM={isLLM} t={t} />
            <BoundsTable bounds={cfBounds} t={t} />
            {cfTotal > 0 && (
              d.cf_plausibility.flags?.length > 0
                ? <FlagsTable flags={d.cf_plausibility.flags} t={t} />
                : <NoFlags t={t} />
            )}
          </div>

          {/* ── Cross-statement consistency ────────────────────────── */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step5.cross_statement_title}</h3>
            <CrossStatementWarnings warnings={d.cross_statement_warnings ?? []} t={t} />
          </div>

        </div>
      )}
    </div>
  )
}

// ── Stat cards ────────────────────────────────────────────────────────────────

function Stat({ label, value }) {
  return (
    <div className={styles.stat}>
      <span className={styles.statLabel}>{label}</span>
      <span className={styles.statValue}>{value}</span>
    </div>
  )
}

function SectionStat({ label, points, flags, t }) {
  const hasFlags = flags > 0
  return (
    <div className={styles.stat}>
      <span className={styles.statLabel}>{label}</span>
      <span className={styles.statValue}>
        {points}{' '}
        <span style={{ fontSize: '0.72rem', fontWeight: 400 }}>{t.step5.points_suffix}</span>
      </span>
      <span style={{
        display: 'block',
        fontSize: '0.72rem',
        fontFamily: "'JetBrains Mono', monospace",
        color: hasFlags ? '#EF9F27' : 'var(--blue)',
        marginTop: 4,
      }}>
        {flags} {t.step5.flags_suffix}
      </span>
    </div>
  )
}

// ── Bounds source note ────────────────────────────────────────────────────────

function BoundsSourceNote({ isLLM, t }) {
  if (isLLM) return null
  return (
    <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: '0.75rem', color: 'var(--gray)', fontStyle: 'italic', marginBottom: 10 }}>
      {t.step5.bounds_default_note}
    </p>
  )
}

// ── Plausibility display helpers ──────────────────────────────────────────────

function BoundsTable({ bounds, t }) {
  if (!bounds?.length) return null
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th>{t.step5.bounds_metric}</th>
          <th style={{ textAlign: 'center' }}>{t.step5.bounds_min}</th>
          <th style={{ textAlign: 'center' }}>{t.step5.bounds_max}</th>
          <th>{t.step5.bounds_rationale}</th>
        </tr>
      </thead>
      <tbody>
        {bounds.map((b) => (
          <tr key={b.metric}>
            <td style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{b.metric}</td>
            <td style={{ textAlign: 'center', fontFamily: 'monospace' }}>{b.min}</td>
            <td style={{ textAlign: 'center', fontFamily: 'monospace' }}>{b.max}</td>
            <td style={{ fontSize: '0.82rem', color: 'var(--gray)' }}>{b.rationale}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function FlagsTable({ flags, t }) {
  return (
    <div style={{ marginTop: 14 }}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>{t.step5.flag_period}</th>
            <th>{t.step5.flag_metric}</th>
            <th>{t.step5.flag_value}</th>
            <th>{t.step5.flag_type}</th>
            <th>{t.step5.flag_reason}</th>
            <th>{t.step5.flag_confidence}</th>
          </tr>
        </thead>
        <tbody>
          {flags.map((f, i) => (
            <tr key={i}>
              <td style={{ whiteSpace: 'nowrap' }}>{f.period}</td>
              <td style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{f.metric}</td>
              <td style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{f.value}</td>
              <td>
                <span className={FLAG_BADGE[f.flag] ?? SEVERITY_BADGE[f.severity] ?? styles.badgeLow}>
                  {f.flag}
                </span>
              </td>
              <td style={{ fontSize: '0.82rem', color: 'var(--gray)' }}>{f.reason}</td>
              <td>{f.confidence}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function NoFlags({ t }) {
  return (
    <p style={{ color: 'var(--blue)', fontSize: '0.82rem', marginTop: 12 }}>
      {t.step5.no_flags}
    </p>
  )
}

// ── Cross-statement section ───────────────────────────────────────────────────

function CrossStatementWarnings({ warnings, t }) {
  if (!warnings || warnings.length === 0) {
    return (
      <p style={{ color: 'var(--blue)', fontSize: '0.875rem' }}>
        {t.step5.cross_statement_none}
      </p>
    )
  }

  // Group by check type
  const grouped = {}
  for (const w of warnings) {
    const key = w.check || 'unknown'
    if (!grouped[key]) grouped[key] = { warnings: [], severities: {} }
    grouped[key].warnings.push(w)
    grouped[key].severities[w.severity] = (grouped[key].severities[w.severity] || 0) + 1
  }

  const criticalCount = warnings.filter(w => w.severity === 'HIGH').length
  const checkCount    = Object.keys(grouped).length

  return (
    <div>
      {/* Summary bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        padding: '10px 14px',
        background: criticalCount > 0 ? 'rgba(226,75,74,0.06)' : 'var(--blue-dim)',
        border: `1px solid ${criticalCount > 0 ? 'rgba(226,75,74,0.2)' : 'var(--blue-line)'}`,
        borderRadius: '6px',
        marginBottom: '14px',
        fontSize: '0.82rem',
        flexWrap: 'wrap',
      }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--blue)', fontWeight: 600 }}>
          {checkCount} {t.step5.cross_check_types ?? 'check types'}
        </span>
        <span style={{ color: 'var(--gray)' }}>
          {warnings.length} {t.step5.cross_periods_examined ?? 'warnings'}
        </span>
        <span style={{ color: criticalCount > 0 ? '#E24B4A' : 'var(--blue)', fontWeight: 600 }}>
          {criticalCount > 0
            ? `${criticalCount} HIGH severity`
            : (t.step5.cross_no_critical ?? '0 critical')}
        </span>
      </div>

      {Object.entries(grouped).map(([checkKey, group]) => (
        <CheckGroup key={checkKey} checkKey={checkKey} group={group} t={t} />
      ))}
    </div>
  )
}

function CheckGroup({ checkKey, group, t }) {
  const severityKeys    = Object.keys(group.severities)
  const allSameSeverity = severityKeys.length === 1
  const uniformSeverity = allSameSeverity ? severityKeys[0] : null
  const hasHigh         = !!group.severities['HIGH']

  // Numeric gap values for avg/range summary
  const gapValues = group.warnings
    .map(w => w.diff_abs ?? w.gap_pct)
    .filter(v => v != null && isFinite(Number(v)))
    .map(Number)
  const avgGap = gapValues.length
    ? gapValues.reduce((a, b) => a + b, 0) / gapValues.length
    : null
  const minGap = gapValues.length ? Math.min(...gapValues) : null
  const maxGap = gapValues.length ? Math.max(...gapValues) : null

  const checkLabel  = t.step5[`cross_check_${checkKey}`] ?? checkKey.replace(/_/g, ' ')
  const contextNote = t.step5[`cross_note_${checkKey}`]  ?? ''
  const total       = group.warnings.length

  // All hooks must be called unconditionally (Rules of Hooks)
  const isHigh = uniformSeverity === 'HIGH'
  const [showDetail, setShowDetail] = useState(isHigh)  // HIGH defaults open
  const [expanded,   setExpanded]   = useState(true)    // mixed-severity always starts open

  // ── Collapsed summary card when all warnings share the same severity ───────
  if (allSameSeverity) {
    return (
      <div style={{
        marginBottom: '8px',
        border: `1px solid ${isHigh ? 'rgba(226,75,74,0.2)' : 'rgba(11,31,58,0.07)'}`,
        borderRadius: '6px',
        overflow: 'hidden',
      }}>
        <div style={{ padding: '12px 14px', background: isHigh ? 'rgba(226,75,74,0.04)' : 'var(--offwhite)' }}>
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: 8, flexWrap: 'wrap' }}>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem', color: 'var(--blue)', fontWeight: 600 }}>
              {checkLabel}
            </span>
            <span style={{ fontSize: '0.72rem', color: 'var(--gray)', background: 'var(--blue-dim)', borderRadius: '10px', padding: '1px 8px', fontFamily: "'JetBrains Mono', monospace" }}>
              {total} period{total !== 1 ? 's' : ''}
            </span>
            <span className={SEVERITY_BADGE[uniformSeverity] ?? styles.badgeLow}>
              All {uniformSeverity}
            </span>
          </div>

          {/* Gap summary */}
          {avgGap != null && (
            <div style={{ fontSize: '0.78rem', color: 'var(--gray)', marginBottom: 6 }}>
              {t.step5.avg_gap}: {avgGap.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              {minGap != null && maxGap != null && minGap !== maxGap && (
                <> ({t.step5.gap_range}: {minGap.toLocaleString(undefined, { maximumFractionDigits: 0 })} – {maxGap.toLocaleString(undefined, { maximumFractionDigits: 0 })})</>
              )}
            </div>
          )}

          {/* Contextual note */}
          {contextNote && (
            <div style={{ fontSize: '0.78rem', color: 'var(--gray)', fontStyle: 'italic', marginBottom: 10 }}>
              {contextNote}
            </div>
          )}

          {/* Toggle */}
          <button
            onClick={() => setShowDetail(v => !v)}
            style={{ background: 'none', border: 'none', color: 'var(--blue)', fontSize: '0.75rem', cursor: 'pointer', padding: 0, fontFamily: "'JetBrains Mono', monospace" }}
          >
            {showDetail ? '▼' : '▶'}{' '}
            {showDetail ? (t.step5.hide_periods ?? 'Hide individual periods') : (t.step5.show_periods ?? 'Show individual periods')}
          </button>
        </div>

        {showDetail && (
          <table className={styles.table} style={{ marginBottom: 0 }}>
            <thead>
              <tr>
                <th>{t.step5.flag_period}</th>
                <th>{t.step5.flag_type}</th>
                <th>{t.step5.flag_reason}</th>
              </tr>
            </thead>
            <tbody>
              {group.warnings.map((w, i) => (
                <tr key={i}>
                  <td style={{ whiteSpace: 'nowrap', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.78rem' }}>{w.period}</td>
                  <td><span className={SEVERITY_BADGE[w.severity] ?? styles.badgeLow}>{w.severity}</span></td>
                  <td style={{ fontSize: '0.82rem', color: 'var(--gray)' }}>{w.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    )
  }

  // ── Mixed-severity expandable group ──────────────────────────────────────
  return (
    <div style={{ marginBottom: '8px', border: `1px solid ${hasHigh ? 'rgba(226,75,74,0.2)' : 'rgba(11,31,58,0.07)'}`, borderRadius: '6px', overflow: 'hidden' }}>
      <button
        onClick={() => setExpanded(v => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          padding: '10px 14px',
          background: hasHigh ? 'rgba(226,75,74,0.04)' : 'var(--offwhite)',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
          gap: '10px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem', color: 'var(--blue)', fontWeight: 600 }}>
            {checkLabel}
          </span>
          <span style={{ fontSize: '0.72rem', color: 'var(--gray)', background: 'var(--blue-dim)', borderRadius: '10px', padding: '1px 8px', fontFamily: "'JetBrains Mono', monospace" }}>
            {total} period{total !== 1 ? 's' : ''}
          </span>
          {hasHigh && <span className={SEVERITY_BADGE.HIGH}>HIGH</span>}
        </div>
        <span style={{ fontSize: '0.65rem', color: 'var(--gray)', opacity: 0.6 }}>{expanded ? '▼' : '▶'}</span>
      </button>

      {expanded && (
        <table className={styles.table} style={{ marginBottom: 0 }}>
          <thead>
            <tr>
              <th>{t.step5.flag_period}</th>
              <th>{t.step5.flag_type}</th>
              <th>{t.step5.flag_reason}</th>
            </tr>
          </thead>
          <tbody>
            {group.warnings.map((w, i) => (
              <tr key={i}>
                <td style={{ whiteSpace: 'nowrap', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.78rem' }}>{w.period}</td>
                <td><span className={SEVERITY_BADGE[w.severity] ?? styles.badgeLow}>{w.severity}</span></td>
                <td style={{ fontSize: '0.82rem', color: 'var(--gray)' }}>{w.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
