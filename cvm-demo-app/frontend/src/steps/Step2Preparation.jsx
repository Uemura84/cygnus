import { useI18n } from '../App'
import DataFunnel from '../components/charts/DataFunnel'
import styles from './Step.module.css'

export default function Step2Preparation({ stepState, data }) {
  const t = useI18n()
  const d = data?.data

  const funnelData = d ? [
    { name: t.step2.raw_rows, value: d.raw_rows },
    { name: t.step2.after_dre, value: d.after_dre_filter },
    { name: t.step2.after_ordem, value: d.after_ordem_exerc },
    { name: t.step2.after_holding, value: d.after_holding_exclusion },
  ] : []

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step2.title}</h2>
      <p className={styles.description}>{t.step2.description}</p>

      {stepState === 'running' && (
        <div className={styles.running}>{t.step2.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>
          <div className={styles.chartCard}>
            <h3 className={styles.chartTitle}>{t.step2.chart_title}</h3>
            <DataFunnel filters={funnelData} />
          </div>

          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step2.filter_name}</h3>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>{t.step2.filter_name}</th>
                  <th>{t.step2.filter_removed}</th>
                  <th>{t.step2.filter_reason}</th>
                </tr>
              </thead>
              <tbody>
                {d.filters_applied?.map((f) => (
                  <tr key={f.name}>
                    <td>{f.name}</td>
                    <td>{f.removed?.toLocaleString()}</td>
                    <td>{f.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
