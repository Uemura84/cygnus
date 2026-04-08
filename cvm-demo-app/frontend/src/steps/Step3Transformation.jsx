import { useI18n } from '../App'
import styles from './Step.module.css'

const CF_SUB_ACCOUNT_KEYS = [
  'depreciation_amortization',
  'capex',
  'acquisitions',
  'debt_issuance',
  'debt_repayment',
  'dividends_paid',
]

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
          {/* Data Sources Overview — three statement types side by side */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step3.data_sources_title}</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              <StatementCard
                label={t.step3.income_statement_label}
                sublabel={t.step3.dre_label}
                t={t}
                rows={[
                  { key: t.step3.records_loaded, val: d.before_dedup?.toLocaleString() },
                  { key: t.step3.records_after_filter, val: d.after_dedup?.toLocaleString() },
                  { key: t.step3.annual_periods, val: d.doc_types?.DFP?.toLocaleString() ?? '—' },
                  { key: t.step3.quarterly_periods, val: d.doc_types?.ITR?.toLocaleString() ?? '—' },
                ]}
              />
              <StatementCard
                label={t.step3.balance_sheet_label}
                sublabel={t.step3.bpa_bpp_label}
                t={t}
                unavailable={!d.bs_stats}
                rows={d.bs_stats ? [
                  { key: t.step3.bpa_records, val: d.bs_stats.bpa_records_loaded?.toLocaleString() },
                  { key: t.step3.bpp_records, val: d.bs_stats.bpp_records_loaded?.toLocaleString() },
                  { key: t.step3.records_after_filter, val: d.bs_stats.records_after_filter?.toLocaleString() },
                  { key: t.step3.annual_periods, val: d.bs_stats.annual_periods?.toLocaleString() },
                  { key: t.step3.quarterly_periods, val: d.bs_stats.quarterly_periods?.toLocaleString() },
                ] : []}
                coverage={d.bs_stats ? {
                  mapped: d.bs_stats.fields_mapped,
                  total: d.bs_stats.fields_total,
                } : null}
              />
              <StatementCard
                label={t.step3.cash_flow_label}
                sublabel={t.step3.dfc_label}
                t={t}
                unavailable={!d.cf_stats}
                rows={d.cf_stats ? [
                  { key: t.step3.records_loaded, val: d.cf_stats.dfc_records_loaded?.toLocaleString() },
                  { key: t.step3.records_after_filter, val: d.cf_stats.records_after_filter?.toLocaleString() },
                  { key: t.step3.annual_periods, val: d.cf_stats.annual_periods?.toLocaleString() },
                  { key: t.step3.quarterly_periods, val: d.cf_stats.quarterly_periods?.toLocaleString() },
                ] : []}
                subAccounts={d.cf_stats?.sub_accounts_found}
              />
            </div>
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
                      const borderTop = isSubtotal ? '2px solid rgba(11,31,58,0.07)' : undefined
                      return (
                        <tr key={row.description}>
                          <td style={{
                            whiteSpace: 'nowrap',
                            paddingLeft: `${12 + indent * 20}px`,
                            fontWeight: isSubtotal ? 700 : 400,
                            color: isSubtotal ? 'var(--navy)' : 'var(--gray)',
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
                              color: isSubtotal ? 'var(--navy)' : 'var(--gray)',
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

          {/* Balance Sheet Mapping Panel */}
          {d.bs_stats?.fields?.length > 0 && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step3.bs_mapping_title}</h3>
              <MappingPanel
                periods={d.bs_stats}
                t={t}
                coverageText={t.step3.coverage_bs
                  ?.replace('{mapped}', d.bs_stats.fields_mapped)
                  ?.replace('{total}', d.bs_stats.fields_total)}
              >
                <MappingTable fields={d.bs_stats.fields} t={t} showCvmCode />
              </MappingPanel>
              {d.bs_table && <BsValueTable table={d.bs_table} t={t} />}
            </div>
          )}

          {/* Cash Flow Mapping Panel */}
          {d.cf_stats && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step3.cf_mapping_title}</h3>
              <MappingPanel
                periods={d.cf_stats}
                t={t}
                coverageText={t.step3.coverage_cf
                  ?.replace('{matched}', d.cf_stats.sub_accounts_matched ?? 0)
                  ?.replace('{total}', d.cf_stats.sub_accounts_total ?? 0)}
              >
                {d.cf_stats.top_level?.length > 0 && (
                  <>
                    <SubSectionLabel>{t.step3.top_level_accounts_title}</SubSectionLabel>
                    <MappingTable fields={d.cf_stats.top_level} t={t} showCvmCode />
                  </>
                )}
                {d.cf_stats.sub_accounts?.length > 0 && (
                  <>
                    <SubSectionLabel>{t.step3.sub_accounts_keyword_title}</SubSectionLabel>
                    <SubAccountTable rows={d.cf_stats.sub_accounts} t={t} />
                  </>
                )}
              </MappingPanel>
              {d.cf_table && <CfValueTable table={d.cf_table} t={t} />}
            </div>
          )}

          {d.ytd_example && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step3.example_title}</h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--gray)' }}>{d.ytd_example.note}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── BS Value Table ──────────────────────────────────────────────────────────

// Display metadata: indent level, bold, separator line above
const BS_ROW_META = {
  current_assets:            { indent: 0, bold: false, sep: false },
  cash_and_equivalents:      { indent: 1, bold: false, sep: false },
  accounts_receivable:       { indent: 1, bold: false, sep: false },
  inventories:               { indent: 1, bold: false, sep: false },
  non_current_assets:        { indent: 0, bold: false, sep: false },
  property_plant_equipment:  { indent: 1, bold: false, sep: false },
  intangible_assets:         { indent: 1, bold: false, sep: false },
  total_assets:              { indent: 0, bold: true,  sep: true  },
  current_liabilities:       { indent: 0, bold: false, sep: true  },
  accounts_payable:          { indent: 1, bold: false, sep: false },
  short_term_debt:           { indent: 1, bold: false, sep: false },
  non_current_liabilities:   { indent: 0, bold: false, sep: false },
  long_term_debt:            { indent: 1, bold: false, sep: false },
  total_liabilities:         { indent: 0, bold: true,  sep: true  },
  total_equity:              { indent: 0, bold: true,  sep: true  },
  retained_earnings:         { indent: 1, bold: false, sep: false },
}

function BsValueTable({ table, t }) {
  const { years, rows } = table
  return (
    <div style={{ marginTop: '16px', overflowX: 'auto' }}>
      <div style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: '0.65rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: 'var(--blue)',
        marginBottom: '8px',
      }}>{t.step3.bs_values_title}</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>Account</th>
            {years.map((yr) => <th key={yr} style={{ textAlign: 'right' }}>{yr}</th>)}
          </tr>
        </thead>
        <tbody>
          {Object.keys(BS_ROW_META).map((field) => {
            const { indent, bold, sep } = BS_ROW_META[field]
            const label = t.step3[`bs_field_${field}`] ?? field
            const border = sep ? '2px solid rgba(11,31,58,0.07)' : undefined
            const vals = rows[field] ?? []
            return (
              <tr key={field}>
                <td style={{
                  whiteSpace: 'nowrap',
                  paddingLeft: `${12 + indent * 20}px`,
                  fontFamily: "'DM Sans', sans-serif",
                  fontWeight: bold ? 600 : 400,
                  color: bold ? 'var(--navy)' : 'var(--gray)',
                  borderTop: border,
                }}>{label}</td>
                {years.map((_, i) => {
                  const val = vals[i]
                  return (
                    <td key={i} style={{
                      textAlign: 'right',
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '0.82rem',
                      fontWeight: bold ? 700 : 400,
                      color: bold ? 'var(--navy)' : 'var(--gray)',
                      borderTop: border,
                      whiteSpace: 'nowrap',
                    }}>
                      {val == null ? '—' : val.toLocaleString()}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ─── CF Value Table ──────────────────────────────────────────────────────────

const CF_ROW_META = {
  operating_cash_flow:       { indent: 0, bold: true,  sep: false },
  depreciation_amortization: { indent: 1, bold: false, sep: false },
  investing_cash_flow:       { indent: 0, bold: true,  sep: false },
  capex:                     { indent: 1, bold: false, sep: false },
  acquisitions:              { indent: 1, bold: false, sep: false },
  financing_cash_flow:       { indent: 0, bold: true,  sep: false },
  debt_issuance:             { indent: 1, bold: false, sep: false },
  debt_repayment:            { indent: 1, bold: false, sep: false },
  dividends_paid:            { indent: 1, bold: false, sep: false },
  free_cash_flow:            { indent: 0, bold: true,  sep: true  },
}

function CfValueTable({ table, t }) {
  const { years, rows } = table
  return (
    <div style={{ marginTop: '16px', overflowX: 'auto' }}>
      <div style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: '0.65rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: 'var(--blue)',
        marginBottom: '8px',
      }}>{t.step3.cf_values_title}</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>Account</th>
            {years.map((yr) => <th key={yr} style={{ textAlign: 'right' }}>{yr}</th>)}
          </tr>
        </thead>
        <tbody>
          {Object.keys(CF_ROW_META).map((field) => {
            const { indent, bold, sep } = CF_ROW_META[field]
            const label = t.step3[`cf_field_${field}`] ?? field
            const border = sep ? '2px solid rgba(11,31,58,0.07)' : undefined
            const vals = rows[field] ?? []
            return (
              <tr key={field}>
                <td style={{
                  whiteSpace: 'nowrap',
                  paddingLeft: `${12 + indent * 20}px`,
                  fontFamily: "'DM Sans', sans-serif",
                  fontWeight: bold ? 600 : 400,
                  color: bold ? 'var(--navy)' : 'var(--gray)',
                  borderTop: border,
                }}>{label}</td>
                {years.map((_, i) => {
                  const val = vals[i]
                  return (
                    <td key={i} style={{
                      textAlign: 'right',
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '0.82rem',
                      fontWeight: bold ? 700 : 400,
                      color: bold ? 'var(--navy)' : 'var(--gray)',
                      borderTop: border,
                      whiteSpace: 'nowrap',
                    }}>
                      {val == null ? '—' : val.toLocaleString()}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function StatementCard({ label, sublabel, rows, coverage, subAccounts, unavailable, t }) {
  return (
    <div style={{
      background: 'var(--offwhite)',
      border: '1px solid rgba(11,31,58,0.07)',
      borderRadius: '8px',
      padding: '14px 16px',
    }}>
      {/* Header */}
      <div style={{ marginBottom: '12px' }}>
        <div style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '0.65rem',
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
          color: 'var(--blue)',
          marginBottom: '2px',
        }}>{sublabel}</div>
        <div style={{
          fontFamily: "'DM Sans', sans-serif",
          fontSize: '0.85rem',
          fontWeight: 600,
          color: 'var(--navy)',
        }}>{label}</div>
      </div>

      {unavailable ? (
        <p style={{ fontSize: '0.78rem', color: 'var(--gray)', fontStyle: 'italic', fontFamily: "'DM Sans', sans-serif" }}>
          {t.step3.not_available}
        </p>
      ) : (
        <>
          {/* Key-value rows */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', marginBottom: coverage || subAccounts ? '12px' : 0 }}>
            {rows.map(({ key, val }) => (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
                <span style={{ fontSize: '0.78rem', color: 'var(--gray)', fontFamily: "'DM Sans', sans-serif" }}>{key}</span>
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  color: 'var(--charcoal)',
                }}>{val ?? '—'}</span>
              </div>
            ))}
          </div>

          {/* Account mapping coverage (BS) */}
          {coverage && (
            <div style={{
              borderTop: '1px solid rgba(11,31,58,0.07)',
              paddingTop: '10px',
              marginTop: '4px',
            }}>
              <div style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '0.65rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                color: 'var(--blue)',
                marginBottom: '6px',
              }}>{t.step3.fields_mapped_label}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{
                  flex: 1,
                  height: '6px',
                  background: 'rgba(11,31,58,0.08)',
                  borderRadius: '3px',
                  overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%',
                    width: `${Math.round((coverage.mapped / coverage.total) * 100)}%`,
                    background: 'var(--blue)',
                    borderRadius: '3px',
                    transition: 'width 0.4s ease',
                  }} />
                </div>
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  color: 'var(--charcoal)',
                  whiteSpace: 'nowrap',
                }}>
                  {coverage.mapped} / {coverage.total}
                </span>
              </div>
            </div>
          )}

          {/* Sub-account checklist (CF) */}
          {subAccounts && (
            <div style={{
              borderTop: '1px solid rgba(11,31,58,0.07)',
              paddingTop: '10px',
              marginTop: '4px',
            }}>
              <div style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '0.65rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                color: 'var(--blue)',
                marginBottom: '6px',
              }}>{t.step3.sub_accounts_label}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {CF_SUB_ACCOUNT_KEYS.map((key) => {
                  const found = subAccounts[key]
                  const label = t.step3[`sub_account_${key}`] ?? key.replace(/_/g, ' ')
                  return (
                    <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                      <span style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: '0.78rem',
                        fontWeight: 700,
                        color: found ? 'var(--blue)' : 'var(--gray)',
                        width: '14px',
                        flexShrink: 0,
                      }}>{found ? '✓' : '—'}</span>
                      <span style={{
                        fontSize: '0.78rem',
                        color: found ? 'var(--charcoal)' : 'var(--gray)',
                        fontFamily: "'DM Sans', sans-serif",
                      }}>{label}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// Mapping panel wrapper — shows periods header + coverage footer
function MappingPanel({ periods, t, coverageText, children }) {
  const annual    = periods?.annual_periods ?? 0
  const quarterly = periods?.quarterly_periods ?? 0
  return (
    <div style={{
      background: 'var(--offwhite)',
      border: '1px solid rgba(11,31,58,0.07)',
      borderRadius: '8px',
      padding: '16px',
    }}>
      <div style={{
        fontSize: '0.78rem',
        color: 'var(--gray)',
        fontFamily: "'DM Sans', sans-serif",
        marginBottom: '14px',
      }}>
        {t.step3.periods_mapped}:{' '}
        <strong style={{ color: 'var(--charcoal)', fontFamily: "'JetBrains Mono', monospace" }}>
          {annual}
        </strong>{' '}
        {t.step3.annual_label}{' '}+{' '}
        <strong style={{ color: 'var(--charcoal)', fontFamily: "'JetBrains Mono', monospace" }}>
          {quarterly}
        </strong>{' '}
        {t.step3.quarterly_label}
      </div>
      {children}
      {coverageText && (
        <div style={{
          marginTop: '12px',
          paddingTop: '10px',
          borderTop: '1px solid rgba(11,31,58,0.07)',
          fontSize: '0.82rem',
          fontWeight: 600,
          color: 'var(--navy)',
          fontFamily: "'DM Sans', sans-serif",
        }}>
          {coverageText}
        </div>
      )}
    </div>
  )
}

function SubSectionLabel({ children }) {
  return (
    <div style={{
      fontFamily: "'JetBrains Mono', monospace",
      fontSize: '0.65rem',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      color: 'var(--blue)',
      marginBottom: '6px',
      marginTop: '12px',
    }}>{children}</div>
  )
}

// Table for BS fields and CF top-level accounts (field + CVM code + status)
function MappingTable({ fields, t, showCvmCode }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>{t.step3.col_common_field}</th>
            {showCvmCode && <th style={{ textAlign: 'left' }}>{t.step3.col_cvm_code}</th>}
            <th style={{ textAlign: 'left' }}>{t.step3.col_status}</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((row) => (
            <tr key={row.field}>
              <td style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '0.78rem',
                color: 'var(--charcoal)',
              }}>{row.field}</td>
              {showCvmCode && (
                <td style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: '0.78rem',
                  color: 'var(--gray)',
                }}>{row.cvm_code}</td>
              )}
              <td>
                <StatusBadge status={row.status} t={t} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Table for CF sub-accounts (field + status + matched DS_CONTA text)
function SubAccountTable({ rows, t }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>{t.step3.col_common_field}</th>
            <th style={{ textAlign: 'left' }}>{t.step3.col_status}</th>
            <th style={{ textAlign: 'left' }}>DS_CONTA match</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.field}>
              <td style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '0.78rem',
                color: 'var(--charcoal)',
                whiteSpace: 'nowrap',
              }}>{row.field}</td>
              <td>
                <StatusBadge status={row.status} t={t} />
              </td>
              <td style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '0.75rem',
                color: 'var(--gray)',
                fontStyle: row.matched_description ? 'normal' : 'italic',
              }}>
                {row.matched_description ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function StatusBadge({ status, t }) {
  const configs = {
    mapped:    { color: 'var(--blue)',    bg: 'rgba(30,144,255,0.08)', label: t.step3.status_mapped, icon: '✓' },
    computed:  { color: 'var(--blue)',    bg: 'rgba(30,144,255,0.08)', label: t.step3.status_computed, icon: '✓', italic: true },
    found:     { color: 'var(--blue)',    bg: 'rgba(30,144,255,0.08)', label: t.step3.status_found, icon: '✓' },
    not_found: { color: 'var(--gray)',    bg: 'rgba(11,31,58,0.05)',   label: t.step3.status_not_found, icon: '—' },
  }
  const cfg = configs[status] ?? configs.not_found
  return (
    <span style={{
      fontFamily: "'DM Sans', sans-serif",
      fontSize: '0.75rem',
      fontWeight: 600,
      fontStyle: cfg.italic ? 'italic' : 'normal',
      color: cfg.color,
      background: cfg.bg,
      borderRadius: '4px',
      padding: '2px 7px',
      whiteSpace: 'nowrap',
    }}>
      {cfg.icon} {cfg.label}
    </span>
  )
}
