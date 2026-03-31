import { useI18n } from '../App'
import styles from './Step.module.css'

// indent: visual indentation level (0 = top-level, 1 = sub-item)
// isSubtotal: bold row with top border — marks a computed line
const IS_STYLE = {
  "Receita de Venda de Bens e/ou Serviços":                          { indent: 0, isSubtotal: false },
  "Custo dos Bens e/ou Serviços Vendidos":                           { indent: 1, isSubtotal: false },
  "Resultado Bruto":                                                  { indent: 0, isSubtotal: true  },
  "Despesas com Vendas":                                             { indent: 1, isSubtotal: false },
  "Despesas Gerais e Administrativas":                               { indent: 1, isSubtotal: false },
  "Resultado Antes do Resultado Financeiro e dos Tributos (EBIT)":   { indent: 0, isSubtotal: true  },
  "Resultado Financeiro":                                            { indent: 1, isSubtotal: false },
  "Resultado Antes dos Tributos sobre o Lucro":                      { indent: 0, isSubtotal: true  },
  "Imposto de Renda e Contribuição Social sobre o Lucro":            { indent: 1, isSubtotal: false },
  "Lucro/Prejuízo Consolidado do Período":                           { indent: 0, isSubtotal: true  },
}

export default function Step3Transformation({ stepState, data }) {
  const t = useI18n()
  const d = data?.data

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step3.title}</h2>
      <p className={styles.description}>{t.step3.description}</p>

      {stepState === 'running' && (
        <div className={styles.running}>{t.step3.running_message}</div>
      )}

      {stepState === 'complete' && d && (
        <div className={styles.results}>
          <div className={styles.statsGrid}>
            <Stat label={t.step3.before_dedup} value={d.before_dedup?.toLocaleString()} />
            <Stat label={t.step3.after_dedup} value={d.after_dedup?.toLocaleString()} />
            <Stat label={t.step3.duplicates_removed} value={d.duplicates_removed?.toLocaleString()} />
            <Stat label={t.step3.ytd_conversions} value={d.itr_standalone_rows?.toLocaleString()} />
          </div>

          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step3.dedup_rules_title}</h3>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>{t.step3.dedup_rule}</th>
                  <th>{t.step3.dedup_description}</th>
                </tr>
              </thead>
              <tbody>
                {t.step3.dedup_rules_list.map((r) => (
                  <tr key={r.rule}>
                    <td><strong>{r.rule}</strong></td>
                    <td>{r.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {d.income_statement?.length > 0 && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step3.is_table_title}</h3>
              <div style={{ overflowX: 'auto' }}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'left' }}>Account</th>
                      {Object.keys(d.income_statement[0].values).map((yr) => (
                        <th key={yr} style={{ textAlign: 'right' }}>{yr}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {d.income_statement.map((row) => {
                      const { indent = 0, isSubtotal = false } = IS_STYLE[row.description] ?? {}
                      const label = t.step3.is_account_labels[row.description] ?? row.description
                      const borderTop = isSubtotal ? '2px solid #e2e8f0' : undefined
                      return (
                        <tr key={row.description}>
                          <td style={{
                            whiteSpace: 'nowrap',
                            paddingLeft: `${12 + indent * 20}px`,
                            fontWeight: isSubtotal ? 700 : 400,
                            color: isSubtotal ? '#1a1a2e' : '#475569',
                            borderTop,
                          }}>
                            {label}
                          </td>
                          {Object.values(row.values).map((val, i) => (
                            <td key={i} style={{
                              textAlign: 'right',
                              fontFamily: 'monospace',
                              fontSize: '0.85rem',
                              fontWeight: isSubtotal ? 700 : 400,
                              color: isSubtotal ? '#1a1a2e' : '#475569',
                              borderTop,
                            }}>
                              {val == null ? '—' : val.toLocaleString()}
                            </td>
                          ))}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {d.ytd_example && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step3.example_title}</h3>
              <p style={{ fontSize: '0.85rem', color: '#475569' }}>{d.ytd_example.note}</p>
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
