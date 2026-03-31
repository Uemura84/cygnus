import { useI18n } from '../App'
import styles from './Step.module.css'

export default function Step8Reporting({ stepState, data }) {
  const t = useI18n()
  const d = data?.data

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step8.title}</h2>
      <p className={styles.description}>{t.step8.description}</p>

      {stepState === 'running' && (
        <div className={styles.running}>{t.step8.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step8.narrative_title}</h3>
            <p style={{ fontSize: '0.9rem', lineHeight: 1.75, color: '#334155' }}>{d.narrative}</p>
          </div>

          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step8.findings_title}</h3>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>{t.step8.finding_rank}</th>
                  <th>{t.step8.finding_label}</th>
                  <th>{t.step8.finding_evidence}</th>
                </tr>
              </thead>
              <tbody>
                {d.key_findings_summary?.map((f) => (
                  <tr key={f.rank}>
                    <td><strong>{f.rank}</strong></td>
                    <td>{f.finding}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>{f.evidence}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {d.data_limitations?.length > 0 && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step8.limitations_title}</h3>
              <ul style={{ paddingLeft: '18px', fontSize: '0.84rem', color: '#64748b', lineHeight: 1.7 }}>
                {d.data_limitations.map((l, i) => <li key={i}>{l}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
