import { useI18n } from '../App'
import RunStepButton from '../components/RunStepButton'
import styles from './Step.module.css'

const STMT_LABEL_KEYS = {
  dre: 'stmt_dre',
  bpa: 'stmt_bpa',
  bpp: 'stmt_bpp',
  dfc: 'stmt_dfc',
}

export default function Step1Download({ stepState, data }) {
  const t = useI18n()
  const d = data?.data

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step1.title}</h2>
      <p className={styles.description}>{t.step1.description}</p>

      <RunStepButton step={1} />

      {stepState === 'running' && (
        <div className={styles.running}>{t.step1.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>
          {d.source === 'cache' && (
            <div className={styles.cacheBadge}>{t.step1.cache_indicator}</div>
          )}

          {/* Top summary: company + date range */}
          <div className={styles.statsGrid}>
            <Stat label={t.step1.summary_company} value={d.company} />
            <Stat
              label={t.step1.summary_date_range}
              value={`${d.date_range?.start} → ${d.date_range?.end}`}
            />
          </div>

          {/* Files downloaded */}
          {d.files_downloaded?.length > 0 && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step1.summary_files}</h3>
              <ul className={styles.fileList}>
                {d.files_downloaded.map((f) => <li key={f}>{f}</li>)}
              </ul>
            </div>
          )}

          {/* Statements Found table */}
          {d.statements_found?.length > 0 && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step1.statements_found_title}</h3>
              <div style={{ overflowX: 'auto' }}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'left' }}>{t.step1.stmt_col_statement}</th>
                      <th style={{ textAlign: 'right' }}>{t.step1.stmt_col_dfp_files}</th>
                      <th style={{ textAlign: 'right' }}>{t.step1.stmt_col_itr_files}</th>
                      <th style={{ textAlign: 'right' }}>{t.step1.stmt_col_total_rows}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.statements_found.map((row) => (
                      <tr key={row.type}>
                        <td style={{ fontFamily: "'DM Sans', sans-serif", fontWeight: 500 }}>
                          {t.step1[STMT_LABEL_KEYS[row.type]] ?? row.type.toUpperCase()}
                        </td>
                        <td style={{ textAlign: 'right', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem' }}>
                          {row.dfp_files}
                        </td>
                        <td style={{ textAlign: 'right', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem' }}>
                          {row.itr_files}
                        </td>
                        <td style={{ textAlign: 'right', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem', fontWeight: 700, color: 'var(--navy)' }}>
                          {row.total_rows?.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
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
