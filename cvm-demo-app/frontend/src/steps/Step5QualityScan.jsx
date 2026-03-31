import { useI18n } from '../App'
import styles from './Step.module.css'

const FLAG_BADGE = {
  STATISTICAL_ANOMALY: styles.badgeHigh,
  DATA_ISSUE: styles.badgeMedium,
  ACCOUNTING_EVENT: styles.badgeLow,
}


export default function Step5QualityScan({ stepState, data }) {
  const t = useI18n()
  const d = data?.data

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step5.title}</h2>
      <p className={styles.description}>{t.step5.description}</p>

      {stepState === 'running' && (
        <div className={styles.running}>{t.step5.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>
          <div className={styles.statsGrid}>
            <Stat label={t.step5.total_points} value={d.total_data_points} />
            <Stat label={t.step5.clean} value={d.clean} />
            <Stat label={t.step5.flagged} value={d.flagged} />
            <Stat label={t.step5.quality_score} value={`${(d.quality_score * 100).toFixed(0)}%`} />
          </div>

          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step5.bounds_title}</h3>
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
                {t.step5.bounds.map((b) => (
                  <tr key={b.metric}>
                    <td style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{b.metric}</td>
                    <td style={{ textAlign: 'center', fontFamily: 'monospace' }}>{b.min}</td>
                    <td style={{ textAlign: 'center', fontFamily: 'monospace' }}>{b.max}</td>
                    <td style={{ fontSize: '0.82rem', color: '#475569' }}>{b.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {d.flags?.length > 0 && (
            <div className={styles.section}>
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
                  {d.flags.map((f, i) => (
                    <tr key={i}>
                      <td>{f.period}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{f.metric}</td>
                      <td>{f.value}</td>
                      <td><span className={FLAG_BADGE[f.flag] ?? styles.badgeLow}>{f.flag}</span></td>
                      <td>{f.reason}</td>
                      <td>{f.confidence}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
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
