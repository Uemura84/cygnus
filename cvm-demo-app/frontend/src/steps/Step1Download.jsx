import { useI18n } from '../App'
import styles from './Step.module.css'

export default function Step1Download({ stepState, data }) {
  const t = useI18n()
  const d = data?.data

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step1.title}</h2>
      <p className={styles.description}>{t.step1.description}</p>

      {stepState === 'running' && (
        <div className={styles.running}>{t.step1.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>
          {d.source === 'cache' && (
            <div className={styles.cacheBadge}>{t.step1.cache_indicator}</div>
          )}
          <div className={styles.statsGrid}>
            <Stat label={t.step1.summary_company} value={d.company} />
            <Stat label={t.step1.summary_dfp_rows} value={d.dfp_rows?.toLocaleString()} />
            <Stat label={t.step1.summary_itr_rows} value={d.itr_rows?.toLocaleString()} />
            <Stat label={t.step1.summary_total_rows} value={d.total_rows?.toLocaleString()} />
            <Stat
              label={t.step1.summary_date_range}
              value={`${d.date_range?.start} → ${d.date_range?.end}`}
            />
          </div>

          {d.files_downloaded?.length > 0 && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step1.summary_files}</h3>
              <ul className={styles.fileList}>
                {d.files_downloaded.map((f) => <li key={f}>{f}</li>)}
              </ul>
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
