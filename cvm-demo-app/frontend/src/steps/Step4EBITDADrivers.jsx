import { useI18n } from '../App'
import MarginTrajectory from '../components/charts/MarginTrajectory'
import RevenueCOGSGrowth from '../components/charts/RevenueCOGSGrowth'
import styles from './Step.module.css'

const ROWS = [
  { key: 'Revenue_YoY_pct',   labelKey: 'revenue_yoy_label',   descKey: 'revenue_yoy_desc',   isYoY: true },
  { key: 'COGS_YoY_pct',      labelKey: 'cogs_yoy_label',      descKey: 'cogs_yoy_desc',      isYoY: true },
  { key: 'Gross_Margin_pct',  labelKey: 'gross_margin_label',  descKey: 'gross_margin_desc',  isYoY: false },
  { key: 'EBIT_Margin_pct',   labelKey: 'ebit_margin_label',   descKey: 'ebit_margin_desc',   isYoY: false },
  { key: 'EBITDA_Margin_pct', labelKey: 'ebitda_margin_label', descKey: 'ebitda_margin_desc', isYoY: false },
  { key: 'COGS_pct_Revenue',  labelKey: 'cogs_revenue_label',  descKey: 'cogs_revenue_desc',  isYoY: false },
  { key: 'SGA_pct_Revenue',   labelKey: 'sga_revenue_label',   descKey: 'sga_revenue_desc',   isYoY: false },
]

function fmt(v, isYoY) {
  if (v == null) return '—'
  const prefix = isYoY && v > 0 ? '+' : ''
  return prefix + v.toFixed(1) + '%'
}

export default function Step4EBITDADrivers({ stepState, data }) {
  const t = useI18n()
  const d = data?.data

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step4.title}</h2>
      <p className={styles.description}>{t.step4.description}</p>

      {stepState === 'running' && (
        <div className={styles.running}>{t.step4.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>
          <div className={styles.statsGrid}>
            <Stat label={t.step4.periods_label} value={d.periods} />
            <Stat label={t.step4.metrics_computed} value={d.metrics_computed?.length} />
          </div>

          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step4.table_title}</h3>
            <div style={{ overflowX: 'auto' }}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left' }}>Metric</th>
                    {d.time_series.map((row) => (
                      <th key={row.period} style={{ textAlign: 'right' }}>
                        {row.period.slice(0, 4)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map(({ key, labelKey, descKey, isYoY }) => (
                    <tr key={key}>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <span className={styles.tooltip} data-tooltip={t.step4[descKey]}>{t.step4[labelKey]}</span>
                      </td>
                      {d.time_series.map((row) => (
                        <td key={row.period} style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: '0.85rem' }}>
                          {fmt(row[key], isYoY)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className={styles.chartCard}>
            <h3 className={styles.chartTitle}>{t.step4.chart_margin_title}</h3>
            <MarginTrajectory
              data={d.time_series}
              labels={{
                grossMargin: t.step4.gross_margin_label,
                ebitMargin: t.step4.ebit_margin_label,
                cogsRevenue: t.step4.cogs_revenue_label,
                breakeven: t.charts?.breakeven,
              }}
            />
          </div>

          <div className={styles.chartCard}>
            <h3 className={styles.chartTitle}>{t.step4.chart_growth_title}</h3>
            <RevenueCOGSGrowth
              data={d.time_series}
              labels={{
                revenue: t.step4.revenue_yoy_label,
                cogs: t.step4.cogs_yoy_label,
                divergenceGap: t.charts?.divergence_gap,
                stickiness: t.charts?.cost_stickiness,
              }}
            />
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
