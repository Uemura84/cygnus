import { useI18n } from '../App'
import DataFunnel from '../components/charts/DataFunnel'
import RunStepButton from '../components/RunStepButton'
import styles from './Step.module.css'

const STMT_LABELS = ['DRE', 'BPA', 'BPP', 'DFC']

/**
 * Build funnel data from filter_stages if available, fall back to old DRE-only fields.
 * Funnel starts at company-filtered rows (not all CVM companies).
 */
function buildFunnelData(d, t) {
  if (d.filter_stages) {
    const fs = d.filter_stages
    return [
      { name: fs.company_selected ?? t.step2.raw_rows, value: fs.company_raw?.total },
      { name: t.step2.ordre_exerc_label,               value: fs.ordem?.total },
      { name: t.step2.overlap_label,                   value: fs.overlap?.total },
    ]
  }
  // Legacy fallback (cached responses without filter_stages)
  return [
    { name: t.step2.raw_rows,        value: d.raw_rows },
    { name: t.step2.after_ordem,     value: d.after_ordem_exerc },
    { name: t.step2.after_holding,   value: d.after_holding_exclusion },
  ]
}

export default function Step2Preparation({ stepState, data }) {
  const t = useI18n()
  const d = data?.data
  const fs = d?.filter_stages   // may be null for cached responses

  const funnelData = d ? buildFunnelData(d, t) : []

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step2.title}</h2>
      <p className={styles.description}>{t.step2.description}</p>

      <RunStepButton step={2} />

      {stepState === 'running' && (
        <div className={styles.running}>{t.step2.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>
          <div className={styles.chartCard}>
            <h3 className={styles.chartTitle}>{t.step2.chart_title}</h3>

            {/* Company selection note */}
            {fs?.company_selected && fs?.total_companies != null && (
              <CompanyNote
                template={t.step2.company_selection_note}
                company={fs.company_selected}
                count={fs.total_companies}
              />
            )}

            <DataFunnel filters={funnelData} />
          </div>

          {/* Filter Waterfall Cards */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step2.filter_cards_title}</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>

              {/* 1. ORDEM_EXERC Filter */}
              <FilterCard
                title={t.step2.ordem_exerc_title}
                desc={t.step2.ordem_exerc_desc1}
                subdesc={t.step2.ordem_exerc_desc2}
                before={fs ? fs.company_raw?.total : d.after_dre_filter}
                after={fs  ? fs.ordem?.total       : d.after_ordem_exerc}
                breakdown={fs ? { before: fs.company_raw, after: fs.ordem } : null}
                t={t}
              />

              {/* 2. DFP / ITR Overlap Resolution */}
              <FilterCard
                title={t.step2.dfp_itr_overlap_title}
                desc={t.step2.dfp_itr_overlap_desc}
                before={fs ? fs.ordem?.total   : null}
                after={fs  ? fs.overlap?.total : null}
                breakdown={fs ? { before: fs.ordem, after: fs.overlap } : null}
                t={t}
              />

              {/* 3. YTD-to-Standalone Conversion */}
              <YtdCard t={t} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Renders the company selection note above the funnel.
 * Bolds the company name; rest is IBM Plex Sans 400 slate 13px.
 * Template format: "Selected {company} from {count} listed companies..."
 */
function CompanyNote({ template, company, count }) {
  // Split on {company} and {count} placeholders to bold them inline
  const parts = template
    .replace('{company}', '\x00COMPANY\x00')
    .replace('{count}', '\x00COUNT\x00')
    .split('\x00')

  return (
    <div style={{
      fontFamily: "'IBM Plex Sans', sans-serif",
      fontSize: '13px',
      fontWeight: 400,
      color: 'var(--gray)',
      marginBottom: '12px',
    }}>
      {parts.map((part, i) => {
        if (part === 'COMPANY') return <span key={i} style={{ fontWeight: 500 }}>{company}</span>
        if (part === 'COUNT')   return <span key={i} style={{ fontWeight: 500 }}>{count.toLocaleString()}</span>
        return part
      })}
    </div>
  )
}

function FilterCard({ title, desc, subdesc, before, after, breakdown, t }) {
  const removed = (before ?? 0) - (after ?? 0)
  const pct = before > 0 ? ((removed / before) * 100).toFixed(1) : '—'
  const hasData = before != null && after != null

  return (
    <div style={{
      background: 'var(--offwhite)',
      border: '1px solid rgba(11,31,58,0.07)',
      borderRadius: '8px',
      padding: '14px 16px',
    }}>
      <div style={{
        fontFamily: "'IBM Plex Sans', sans-serif",
        fontSize: '0.85rem',
        fontWeight: 600,
        color: 'var(--navy)',
        marginBottom: '4px',
      }}>{title}</div>
      <div style={{ fontSize: '0.78rem', color: 'var(--gray)', fontFamily: "'IBM Plex Sans', sans-serif", marginBottom: '2px' }}>
        {desc}
      </div>
      {subdesc && (
        <div style={{ fontSize: '0.78rem', color: 'var(--gray)', fontFamily: "'IBM Plex Sans', sans-serif", marginBottom: '8px' }}>
          {subdesc}
        </div>
      )}
      {!subdesc && <div style={{ marginBottom: '8px' }} />}

      {hasData ? (
        <>
          <div style={{ display: 'flex', gap: '20px', alignItems: 'baseline', flexWrap: 'wrap' }}>
            <BeforeAfter label={t.step2.before_label} value={before} />
            <span style={{ color: 'rgba(11,31,58,0.3)', fontSize: '0.78rem' }}>→</span>
            <BeforeAfter label={t.step2.after_label} value={after} highlight />
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: '0.75rem',
              color: 'var(--gray)',
              marginLeft: 'auto',
            }}>−{pct}%</span>
          </div>

          {/* Per-statement breakdown */}
          {breakdown && (
            <div style={{
              marginTop: '8px',
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: '0.69rem',
              color: 'var(--gray)',
              lineHeight: 1.6,
              display: 'flex',
              flexWrap: 'wrap',
              gap: '0 12px',
            }}>
              {STMT_LABELS.map((label, i) => {
                const b = breakdown.before?.[label]
                const a = breakdown.after?.[label]
                if (b == null && a == null) return null
                return (
                  <span key={label}>
                    <span style={{ fontWeight: 700 }}>{label}:</span>{' '}
                    {b?.toLocaleString() ?? '—'} → {a?.toLocaleString() ?? '—'}
                    {i < STMT_LABELS.length - 1 ? '' : ''}
                  </span>
                )
              })}
            </div>
          )}
        </>
      ) : (
        <div style={{ fontSize: '0.78rem', color: 'var(--gray)', fontStyle: 'italic' }}>
          —
        </div>
      )}
    </div>
  )
}

function BeforeAfter({ label, value, highlight }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
      <span style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: '0.65rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: 'var(--teal)',
      }}>{label}</span>
      <span style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: '0.9rem',
        fontWeight: 700,
        color: highlight ? 'var(--navy)' : 'var(--gray)',
      }}>{value?.toLocaleString() ?? '—'}</span>
    </div>
  )
}

function YtdCard({ t }) {
  return (
    <div style={{
      background: 'var(--offwhite)',
      border: '1px solid rgba(11,31,58,0.07)',
      borderRadius: '8px',
      padding: '14px 16px',
    }}>
      <div style={{
        fontFamily: "'IBM Plex Sans', sans-serif",
        fontSize: '0.85rem',
        fontWeight: 600,
        color: 'var(--navy)',
        marginBottom: '4px',
      }}>{t.step2.ytd_conversion_title}</div>
      <div style={{ fontSize: '0.78rem', color: 'var(--gray)', fontFamily: "'IBM Plex Sans', sans-serif", marginBottom: '10px' }}>
        {t.step2.ytd_conversion_desc}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <TagRow label={t.step2.applied_to}     tags={['DRE', 'DFC']} color="var(--teal)" bg="rgba(14,143,154,0.08)" />
        <TagRow label={t.step2.not_applied_to} tags={['BPA', 'BPP']} color="var(--gray)" bg="rgba(11,31,58,0.06)" />
      </div>
      <div style={{ fontSize: '0.75rem', color: 'var(--gray)', fontFamily: "'IBM Plex Sans', sans-serif", marginTop: '8px', fontStyle: 'italic' }}>
        {t.step2.balance_sheet_note}
      </div>
    </div>
  )
}

function TagRow({ label, tags, color, bg }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
      <span style={{ fontSize: '0.75rem', color: 'var(--gray)', fontFamily: "'IBM Plex Sans', sans-serif", minWidth: '90px' }}>
        {label}:
      </span>
      {tags.map((tag) => (
        <span key={tag} style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: '0.72rem',
          fontWeight: 700,
          color,
          background: bg,
          borderRadius: '4px',
          padding: '2px 7px',
        }}>{tag}</span>
      ))}
    </div>
  )
}
