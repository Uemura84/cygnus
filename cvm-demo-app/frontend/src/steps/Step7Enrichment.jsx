import { useI18n } from '../App'
import MacroTimeline from '../components/charts/MacroTimeline'
import RiskGauge from '../components/charts/RiskGauge'
import styles from './Step.module.css'

const SEVERITY_BADGE = { HIGH: styles.badgeHigh, MEDIUM: styles.badgeMedium, LOW: styles.badgeLow }

export default function Step7Enrichment({ stepState, data }) {
  const t = useI18n()
  const d = data?.data

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step7.title}</h2>
      <p className={styles.description}>{t.step7.description}</p>

      {stepState === 'running' && (
        <div className={styles.running}>{t.step7.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <div className={styles.statsGrid} style={{ flex: 1 }}>
              <Stat label={t.step7.findings_enriched} value={d.findings_enriched} />
              <Stat label={t.step7.macro_annotations} value={d.macro_annotations_added} />
              <Stat label={t.step7.risk_score} value={d.risk_score} />
              <Stat label={t.step7.risk_level} value={d.risk_level} />
            </div>
            <RiskGauge score={d.risk_score} level={d.risk_level} />
          </div>

          {d.composite_signals?.length > 0 && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step7.composite_signals}</h3>
              {d.composite_signals.map((s) => (
                <div key={s.composite_signal_type} style={{ marginBottom: '12px' }}>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
                    <strong style={{ fontSize: '0.88rem', fontFamily: 'monospace' }}>{s.composite_signal_type}</strong>
                    <span className={SEVERITY_BADGE[s.severity]}>{s.severity}</span>
                    <span style={{ fontSize: '0.76rem', color: '#64748b' }}>{t.step7.signal_confidence}: {s.confidence}</span>
                  </div>
                  <p style={{ fontSize: '0.83rem', color: '#475569' }}>{s.explanation}</p>
                </div>
              ))}
            </div>
          )}

          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step7.timeline_title}</h3>
            <MacroTimeline macroTimeline={d.macro_timeline} findings={[]} />
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
