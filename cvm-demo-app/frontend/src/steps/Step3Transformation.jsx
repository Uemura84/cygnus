import { useI18n } from '../App'
import RunStepButton from '../components/RunStepButton'
import styles from './Step.module.css'

const CF_SUB_ACCOUNT_KEYS = [
  'depreciation_amortization',
  'capex',
  'acquisitions',
  'debt_issuance',
  'debt_repayment',
  'dividends_paid',
]

// DVA account codes → internal field names
const DVA_ACCOUNT_CVM_CODES = {
  "7.01":    "revenues",
  "7.02":    "third_party_inputs",
  "7.03":    "gross_value_added",
  "7.04":    "retentions",
  "7.05":    "net_value_added",
  "7.06":    "value_received",
  "7.07":    "total_to_distribute",
  "7.08.01": "employees",
  "7.08.02": "government",
  "7.08.03": "lenders",
  "7.08.04": "shareholders",
}

// DVA row display metadata
const DVA_ROW_META = {
  revenues:             { indent: 0, isSubtotal: false },
  third_party_inputs:   { indent: 1, isSubtotal: false },
  gross_value_added:    { indent: 0, isSubtotal: true  },
  retentions:           { indent: 1, isSubtotal: false },
  net_value_added:      { indent: 0, isSubtotal: true  },
  value_received:       { indent: 1, isSubtotal: false },
  total_to_distribute:  { indent: 0, isSubtotal: true  },
  employees:            { indent: 1, isSubtotal: false },
  government:           { indent: 1, isSubtotal: false },
  lenders:              { indent: 1, isSubtotal: false },
  shareholders:         { indent: 1, isSubtotal: false },
}

// CVM account codes for IS fields — used in the mapping table
const IS_ACCOUNT_CVM_CODES = {
  "Receita de Venda de Bens e/ou Serviços":                        "3.01",
  "Custo dos Bens e/ou Serviços Vendidos":                         "3.02",
  "Resultado Bruto":                                                "3.03",
  "Despesas com Vendas":                                           "3.04.01",
  "Despesas Gerais e Administrativas":                             "3.04.02",
  "Resultado Antes do Resultado Financeiro e dos Tributos (EBIT)": "3.05",
  "Resultado Financeiro":                                          "3.06",
  "Resultado Antes dos Tributos sobre o Lucro":                    "3.07",
  "Imposto de Renda e Contribuição Social sobre o Lucro":          "3.08",
  "Lucro/Prejuízo Consolidado do Período":                         "3.11",
}

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

      <RunStepButton step={3} />

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
              <StatementCard
                label={t.step3.dva_label ?? 'Value Added Statement'}
                sublabel={t.step3.dva_sublabel ?? 'DVA'}
                t={t}
                unavailable={!d.dva_stats}
                rows={d.dva_stats ? [
                  { key: t.step3.records_loaded, val: d.dva_stats.records_loaded?.toLocaleString() },
                  { key: t.step3.records_after_filter, val: d.dva_stats.records_after_filter?.toLocaleString() },
                  { key: t.step3.annual_periods, val: d.dva_stats.annual_periods?.toLocaleString() },
                  { key: t.step3.quarterly_periods, val: d.dva_stats.quarterly_periods?.toLocaleString() },
                ] : []}
              />
              <StatementCard
                label={t.step3.dmpl_label ?? 'Changes in Equity'}
                sublabel={t.step3.dmpl_sublabel ?? 'DMPL'}
                t={t}
                unavailable={!d.dmpl_stats}
                rows={d.dmpl_stats ? [
                  { key: t.step3.records_loaded, val: d.dmpl_stats.records_loaded?.toLocaleString() },
                  { key: t.step3.records_after_filter, val: d.dmpl_stats.records_after_filter?.toLocaleString() },
                  { key: t.step3.annual_periods, val: d.dmpl_stats.annual_periods?.toLocaleString() },
                  { key: t.step3.quarterly_periods, val: d.dmpl_stats.quarterly_periods?.toLocaleString() },
                ] : []}
              />
              <StatementCard
                label={t.step3.dra_label ?? 'Comprehensive Income'}
                sublabel={t.step3.dra_sublabel ?? 'DRA'}
                t={t}
                unavailable={!d.dra_stats}
                rows={d.dra_stats ? [
                  { key: t.step3.records_loaded, val: d.dra_stats.records_loaded?.toLocaleString() },
                  { key: t.step3.records_after_filter, val: d.dra_stats.records_after_filter?.toLocaleString() },
                  { key: t.step3.annual_periods, val: d.dra_stats.annual_periods?.toLocaleString() },
                  { key: t.step3.quarterly_periods, val: d.dra_stats.quarterly_periods?.toLocaleString() },
                ] : []}
              />
              <StatementCard
                label={t.step3.parecer_label ?? 'Auditor Report'}
                sublabel={t.step3.parecer_sublabel ?? 'PARECER'}
                t={t}
                unavailable={!d.parecer_stats}
                rows={d.parecer_stats ? [
                  { key: t.step3.parecer_reports_found ?? 'Reports Found', val: d.parecer_stats.reports_found },
                  { key: t.step3.parecer_filing_type ?? 'Filing Type', val: d.parecer_stats.filing_type },
                  { key: t.step3.annual_periods, val: d.parecer_stats.annual_periods },
                  { key: t.step3.quarterly_periods, val: '—' },
                ] : []}
                parecerPeriods={d.parecer_stats?.periods}
              />
              <StatementCard
                label={t.step3.fre_auditor_card_label ?? 'Auditor Profile'}
                sublabel={t.step3.fre_auditor_card_sublabel ?? 'FRE / AUDITOR'}
                t={t}
                unavailable={!d.fre_auditor_stats}
                rows={d.fre_auditor_stats ? [
                  { key: t.step3.records_loaded, val: d.fre_auditor_stats.records_loaded },
                  { key: t.step3.parecer_filing_type ?? 'Filing Type', val: d.fre_auditor_stats.filing_type },
                  { key: t.step3.annual_periods, val: d.fre_auditor_stats.annual_periods },
                  { key: t.step3.quarterly_periods, val: '—' },
                ] : []}
                parecerPeriods={d.fre_auditor_stats?.periods}
              />
              <StatementCard
                label={t.step3.fre_bonds_card_label ?? 'Foreign Bonds'}
                sublabel={t.step3.fre_bonds_card_sublabel ?? 'FRE / TÍTULO EXT.'}
                t={t}
                unavailable={!d.fre_bonds_stats}
                rows={d.fre_bonds_stats ? [
                  { key: t.step3.fre_bonds_count ?? 'Bonds', val: d.fre_bonds_stats.records_loaded },
                  { key: t.step3.parecer_filing_type ?? 'Filing Type', val: d.fre_bonds_stats.filing_type },
                  { key: t.step3.annual_periods, val: d.fre_bonds_stats.annual_periods },
                  { key: t.step3.quarterly_periods, val: '—' },
                ] : []}
                parecerPeriods={d.fre_bonds_stats?.periods}
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
              <MappingPanel
                periods={{ annual_periods: d.doc_types?.DFP ?? 0, quarterly_periods: d.doc_types?.ITR ?? 0 }}
                t={t}
                coverageText={null}
              >
                <IsAccountMappingTable t={t} />
              </MappingPanel>
              <IsValueTable statement={d.income_statement} t={t} />
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

          {/* DVA Mapping Panel */}
          {d.dva_stats && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step3.dva_mapping_title ?? 'Value Added Statement (DVA) — Account Mapping'}</h3>
              <MappingPanel
                periods={{ annual_periods: d.dva_stats.annual_periods, quarterly_periods: d.dva_stats.quarterly_periods }}
                t={t}
                coverageText={null}
              >
                <DvaMappingTable t={t} />
              </MappingPanel>
              {d.dva_table && <DvaValueTable table={d.dva_table} t={t} />}
            </div>
          )}

          {/* DMPL Mapping Panel */}
          {d.dmpl_stats && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step3.dmpl_mapping_title ?? 'Changes in Equity (DMPL) — Account Mapping'}</h3>
              <MappingPanel
                periods={{ annual_periods: d.dmpl_stats.annual_periods, quarterly_periods: d.dmpl_stats.quarterly_periods }}
                t={t}
                coverageText={null}
              >
                <DmplMappingTable t={t} />
              </MappingPanel>
              {d.dmpl_table && <DmplValueTable table={d.dmpl_table} t={t} />}
            </div>
          )}

          {/* DRA Mapping Panel */}
          {d.dra_stats && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step3.dra_mapping_title ?? 'Comprehensive Income (DRA) — Account Mapping'}</h3>
              <MappingPanel
                periods={{ annual_periods: d.dra_stats.annual_periods, quarterly_periods: d.dra_stats.quarterly_periods }}
                t={t}
                coverageText={null}
              >
                <DraMappingTable t={t} />
              </MappingPanel>
              {d.dra_table && <DraValueTable table={d.dra_table} t={t} />}
            </div>
          )}

          {/* Auditor Report (Parecer) Mapping Panel */}
          {d.parecer_stats && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step3.parecer_mapping_title ?? 'Auditor Report — Field Mapping'}</h3>
              <MappingPanel
                periods={{ annual_periods: d.parecer_stats.annual_periods, quarterly_periods: 0 }}
                t={t}
                coverageText={t.step3.parecer_coverage
                  ?.replace('{n}', d.parecer_stats.reports_found)
                  ?? `${d.parecer_stats.reports_found} reports available for LLM classification in Step 5`}
              >
                <MappingTable fields={d.parecer_stats.fields ?? []} t={t} showCvmCode={false} showDescription />
              </MappingPanel>
            </div>
          )}

          {/* FRE Auditor Profile Mapping Panel */}
          {d.fre_auditor_stats && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step3.fre_auditor_mapping_title ?? 'Auditor Profile (FRE) — Field Mapping'}</h3>
              <MappingPanel
                periods={{ annual_periods: d.fre_auditor_stats.annual_periods, quarterly_periods: 0 }}
                t={t}
                coverageText={t.step3.fre_coverage_auditor
                  ?.replace('{n}', d.fre_auditor_stats.records_loaded)
                  ?? `${d.fre_auditor_stats.records_loaded} annual profiles available`}
              >
                <MappingTable fields={d.fre_auditor_stats.fields ?? []} t={t} showCvmCode={false} showDescription />
              </MappingPanel>
              {d.fre_auditor_table && <FreAuditorValueTable table={d.fre_auditor_table} t={t} />}
            </div>
          )}

          {/* FRE Foreign Bonds Mapping Panel */}
          {d.fre_bonds_stats && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>{t.step3.fre_bonds_mapping_title ?? 'Foreign Bonds (FRE) — Field Mapping'}</h3>
              <MappingPanel
                periods={{ annual_periods: d.fre_bonds_stats.annual_periods, quarterly_periods: 0 }}
                t={t}
                coverageText={t.step3.fre_coverage_bonds
                  ?.replace('{n}', d.fre_bonds_stats.records_loaded)
                  ?? `${d.fre_bonds_stats.records_loaded} bond obligations from latest FRE`}
              >
                <MappingTable fields={d.fre_bonds_stats.fields ?? []} t={t} showCvmCode={false} showDescription />
              </MappingPanel>
              {d.fre_bonds_table && <FreBondsValueTable table={d.fre_bonds_table} t={t} />}
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
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: '0.65rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: 'var(--teal)',
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
                  fontFamily: "'IBM Plex Sans', sans-serif",
                  fontWeight: bold ? 600 : 400,
                  color: bold ? 'var(--navy)' : 'var(--gray)',
                  borderTop: border,
                }}>{label}</td>
                {years.map((_, i) => {
                  const val = vals[i]
                  return (
                    <td key={i} style={{
                      textAlign: 'right',
                      fontFamily: "'IBM Plex Mono', monospace",
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
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: '0.65rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: 'var(--teal)',
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
                  fontFamily: "'IBM Plex Sans', sans-serif",
                  fontWeight: bold ? 600 : 400,
                  color: bold ? 'var(--navy)' : 'var(--gray)',
                  borderTop: border,
                }}>{label}</td>
                {years.map((_, i) => {
                  const val = vals[i]
                  return (
                    <td key={i} style={{
                      textAlign: 'right',
                      fontFamily: "'IBM Plex Mono', monospace",
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

// ─── DVA Account Mapping Table ───────────────────────────────────────────────

function DvaMappingTable({ t }) {
  const fields = Object.entries(DVA_ACCOUNT_CVM_CODES).map(([code, field]) => ({
    field: t.step3[`dva_field_${field}`] ?? field,
    cvm_code: code,
    status: 'mapped',
  }))
  return <MappingTable fields={fields} t={t} showCvmCode />
}

// ─── DVA Value Table ─────────────────────────────────────────────────────────

function DvaValueTable({ table, t }) {
  const { years, rows } = table
  return (
    <div style={{ marginTop: '16px', overflowX: 'auto' }}>
      <div style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: '0.65rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: 'var(--teal)',
        marginBottom: '8px',
      }}>{t.step3.dva_values_title ?? 'DVA Annual Values (BRL Thousands)'}</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>{t.step3.col_common_field ?? 'Account'}</th>
            {years.map((yr) => <th key={yr} style={{ textAlign: 'right' }}>{yr}</th>)}
          </tr>
        </thead>
        <tbody>
          {Object.keys(DVA_ROW_META).map((field) => {
            const { indent, isSubtotal } = DVA_ROW_META[field]
            const label = t.step3[`dva_field_${field}`] ?? field
            const border = isSubtotal ? '2px solid rgba(11,31,58,0.07)' : undefined
            const vals = rows[field] ?? []
            return (
              <tr key={field}>
                <td style={{
                  whiteSpace: 'nowrap',
                  paddingLeft: `${12 + indent * 20}px`,
                  fontFamily: "'IBM Plex Sans', sans-serif",
                  fontWeight: isSubtotal ? 600 : 400,
                  color: isSubtotal ? 'var(--navy)' : 'var(--gray)',
                  borderTop: border,
                }}>{label}</td>
                {years.map((_, i) => {
                  const val = vals[i]
                  return (
                    <td key={i} style={{
                      textAlign: 'right',
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: '0.82rem',
                      fontWeight: isSubtotal ? 700 : 400,
                      color: isSubtotal ? 'var(--navy)' : 'var(--gray)',
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

// ─── DMPL Account Mapping Table ─────────────────────────────────────────────

// CD_CONTA → internal field names (Patrimônio Líquido Consolidado column only)
const DMPL_ACCOUNT_CVM_CODES = {
  "5.01":    "opening_equity",
  "5.05.01": "net_income",
  "5.04.06": "dividends_declared",
  "5.04.07": "jcp_declared",
  "5.04.12": "dividends_additional",
  "5.04.14": "dividends_proposed",
  "5.04.04": "treasury_acquired",
  "5.04.05": "treasury_sold",
  "5.04.01": "capital_increase",
  "5.05.02": "oci_total",
  "5.07":    "closing_equity",
}

// Derived fields not from a single CVM code
const DMPL_DERIVED_FIELDS = {
  total_dividends:    "5.04.06 + 5.04.07 + 5.04.12 + 5.04.14",
  treasury_shares_net: "5.04.04 + 5.04.05",
}

const DMPL_ROW_META = {
  opening_equity:      { indent: 0, bold: true,  sep: false },
  net_income:          { indent: 1, bold: false, sep: false },
  total_dividends:     { indent: 1, bold: false, sep: false },
  oci_total:           { indent: 1, bold: false, sep: false },
  capital_increase:    { indent: 1, bold: false, sep: false },
  treasury_shares_net: { indent: 1, bold: false, sep: false },
  closing_equity:      { indent: 0, bold: true,  sep: true  },
}

function DmplMappingTable({ t }) {
  const direct = Object.entries(DMPL_ACCOUNT_CVM_CODES).map(([code, field]) => ({
    field: t.step3[`dmpl_field_${field}`] ?? field,
    cvm_code: code,
    status: 'mapped',
  }))
  const derived = Object.entries(DMPL_DERIVED_FIELDS).map(([field, formula]) => ({
    field: t.step3[`dmpl_field_${field}`] ?? field,
    cvm_code: formula,
    status: 'computed',
  }))
  return (
    <>
      <MappingTable fields={direct} t={t} showCvmCode />
      <SubSectionLabel>{t.step3.derived_fields_label ?? 'Derived Fields'}</SubSectionLabel>
      <MappingTable fields={derived} t={t} showCvmCode />
    </>
  )
}

function DmplValueTable({ table, t }) {
  const { years, rows } = table
  return (
    <div style={{ marginTop: '16px', overflowX: 'auto' }}>
      <div style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: '0.65rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: 'var(--teal)',
        marginBottom: '8px',
      }}>{t.step3.dmpl_values_title ?? 'DMPL Annual Values (BRL Thousands)'}</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>{t.step3.col_common_field ?? 'Account'}</th>
            {years.map((yr) => <th key={yr} style={{ textAlign: 'right' }}>{yr}</th>)}
          </tr>
        </thead>
        <tbody>
          {Object.keys(DMPL_ROW_META).map((field) => {
            const { indent, bold, sep } = DMPL_ROW_META[field]
            const label = t.step3[`dmpl_field_${field}`] ?? field
            const border = sep ? '2px solid rgba(11,31,58,0.07)' : undefined
            const vals = rows[field] ?? []
            return (
              <tr key={field}>
                <td style={{
                  whiteSpace: 'nowrap',
                  paddingLeft: `${12 + indent * 20}px`,
                  fontFamily: "'IBM Plex Sans', sans-serif",
                  fontWeight: bold ? 600 : 400,
                  color: bold ? 'var(--navy)' : 'var(--gray)',
                  borderTop: border,
                }}>{label}</td>
                {years.map((_, i) => {
                  const val = vals[i]
                  return (
                    <td key={i} style={{
                      textAlign: 'right',
                      fontFamily: "'IBM Plex Mono', monospace",
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

// ─── DRA Account Mapping Table ───────────────────────────────────────────────

const DRA_ACCOUNT_CVM_CODES = {
  "4.01": "net_income",
  "4.02": "oci_total",
  "4.03": "total_comprehensive_income",
}

const DRA_OCI_KEYWORD_FIELDS = {
  "oci_fx":        "conversão de operações / variação cambial",
  "oci_hedge":     "hedge / proteção cambial",
  "oci_actuarial": "atuarial / benefícios pós-emprego",
}

const DRA_ROW_META = {
  net_income:                 { indent: 0, bold: true,  sep: false },
  oci_total:                  { indent: 0, bold: true,  sep: false },
  oci_fx:                     { indent: 1, bold: false, sep: false },
  oci_hedge:                  { indent: 1, bold: false, sep: false },
  oci_actuarial:              { indent: 1, bold: false, sep: false },
  total_comprehensive_income: { indent: 0, bold: true,  sep: true  },
}

function DraMappingTable({ t }) {
  const direct = Object.entries(DRA_ACCOUNT_CVM_CODES).map(([code, field]) => ({
    field: t.step3[`dra_field_${field}`] ?? field,
    cvm_code: code,
    status: 'mapped',
  }))
  const keyword = Object.entries(DRA_OCI_KEYWORD_FIELDS).map(([field, kw]) => ({
    field: t.step3[`dra_field_${field}`] ?? field,
    cvm_code: `4.02.x — keyword: ${kw}`,
    status: 'mapped',
  }))
  return (
    <>
      <MappingTable fields={direct} t={t} showCvmCode />
      <SubSectionLabel>{t.step3.oci_subcomponents_label ?? 'OCI Sub-components (keyword-matched from 4.02.x)'}</SubSectionLabel>
      <MappingTable fields={keyword} t={t} showCvmCode />
    </>
  )
}

function DraValueTable({ table, t }) {
  const { years, rows } = table
  return (
    <div style={{ marginTop: '16px', overflowX: 'auto' }}>
      <div style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: '0.65rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: 'var(--teal)',
        marginBottom: '8px',
      }}>{t.step3.dra_values_title ?? 'DRA Annual Values (BRL Thousands)'}</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>{t.step3.col_common_field ?? 'Account'}</th>
            {years.map((yr) => <th key={yr} style={{ textAlign: 'right' }}>{yr}</th>)}
          </tr>
        </thead>
        <tbody>
          {Object.keys(DRA_ROW_META).map((field) => {
            const { indent, bold, sep } = DRA_ROW_META[field]
            const label = t.step3[`dra_field_${field}`] ?? field
            const border = sep ? '2px solid rgba(11,31,58,0.07)' : undefined
            const vals = rows[field] ?? []
            return (
              <tr key={field}>
                <td style={{
                  whiteSpace: 'nowrap',
                  paddingLeft: `${12 + indent * 20}px`,
                  fontFamily: "'IBM Plex Sans', sans-serif",
                  fontWeight: bold ? 600 : 400,
                  color: bold ? 'var(--navy)' : 'var(--gray)',
                  borderTop: border,
                }}>{label}</td>
                {years.map((_, i) => {
                  const val = vals[i]
                  return (
                    <td key={i} style={{
                      textAlign: 'right',
                      fontFamily: "'IBM Plex Mono', monospace",
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

// ─── FRE Auditor Value Table ─────────────────────────────────────────────────

const FRE_AUDITOR_ROW_META = {
  firm_name:       { bold: false },
  tenure_years:    { bold: false },
  audit_fees:      { bold: true  },
  non_audit_fees:  { bold: false },
  non_audit_ratio: { bold: false },
}

function FreAuditorValueTable({ table, t }) {
  const { years, rows } = table
  return (
    <div style={{ marginTop: '16px', overflowX: 'auto' }}>
      <div style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: '0.65rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: 'var(--teal)',
        marginBottom: '8px',
      }}>{t.step3.fre_auditor_values_title ?? 'Auditor Fees (Annual, BRL Thousands)'}</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>{t.step3.col_common_field}</th>
            {years.map((yr) => <th key={yr} style={{ textAlign: 'right' }}>{yr}</th>)}
          </tr>
        </thead>
        <tbody>
          {Object.keys(FRE_AUDITOR_ROW_META).map((field) => {
            const { bold } = FRE_AUDITOR_ROW_META[field]
            const label = t.step3[`fre_field_${field}`] ?? field
            const vals = rows[field] ?? []
            return (
              <tr key={field}>
                <td style={{
                  whiteSpace: 'nowrap',
                  paddingLeft: '12px',
                  fontFamily: "'IBM Plex Sans', sans-serif",
                  fontWeight: bold ? 600 : 400,
                  color: bold ? 'var(--navy)' : 'var(--gray)',
                }}>{label}</td>
                {years.map((_, i) => {
                  const val = vals[i]
                  const display = val == null ? '—'
                    : typeof val === 'string' ? val
                    : val.toLocaleString()
                  return (
                    <td key={i} style={{
                      textAlign: 'right',
                      fontFamily: typeof val === 'string' ? "'IBM Plex Sans', sans-serif" : "'IBM Plex Mono', monospace",
                      fontSize: '0.82rem',
                      fontWeight: bold ? 700 : 400,
                      color: bold ? 'var(--navy)' : 'var(--gray)',
                      whiteSpace: 'nowrap',
                    }}>
                      {display}
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

// ─── FRE Bonds Value Table ────────────────────────────────────────────────────

function FreBondsValueTable({ table, t }) {
  if (!table?.length) return null
  return (
    <div style={{ marginTop: '16px', overflowX: 'auto' }}>
      <div style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: '0.65rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: 'var(--teal)',
        marginBottom: '8px',
      }}>{t.step3.fre_bonds_values_title ?? 'Foreign Bond Obligations (Latest FRE Year, BRL Thousands)'}</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>{t.step3.fre_col_instrument ?? 'Instrument'}</th>
            <th style={{ textAlign: 'left' }}>{t.step3.fre_col_identification ?? 'ISIN / Description'}</th>
            <th style={{ textAlign: 'left' }}>{t.step3.fre_col_maturity ?? 'Maturity'}</th>
            <th style={{ textAlign: 'right' }}>{t.step3.fre_col_outstanding ?? 'Outstanding (BRL k)'}</th>
            <th style={{ textAlign: 'left' }}>{t.step3.fre_col_currency ?? 'Currency'}</th>
          </tr>
        </thead>
        <tbody>
          {table.map((bond, i) => (
            <tr key={i}>
              <td style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontSize: '0.82rem', color: 'var(--gray)' }}>
                {bond.instrument_type ?? '—'}
              </td>
              <td style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.78rem', color: 'var(--charcoal)' }}>
                {bond.identification || '—'}
              </td>
              <td style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.82rem', color: 'var(--gray)', whiteSpace: 'nowrap' }}>
                {bond.maturity_date ?? '—'}
              </td>
              <td style={{ textAlign: 'right', fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.82rem', fontWeight: 700, color: 'var(--navy)', whiteSpace: 'nowrap' }}>
                {bond.outstanding_amount == null ? '—' : bond.outstanding_amount.toLocaleString()}
              </td>
              <td style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.78rem', color: 'var(--gray)' }}>
                {bond.currency ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── IS Account Mapping Table ────────────────────────────────────────────────

function IsAccountMappingTable({ t }) {
  const fields = Object.entries(IS_ACCOUNT_CVM_CODES).map(([desc, code]) => ({
    field: t.step3.is_account_labels?.[desc] ?? desc,
    cvm_code: code,
    status: 'mapped',
  }))
  return <MappingTable fields={fields} t={t} showCvmCode />
}

// ─── IS Value Table ──────────────────────────────────────────────────────────

function IsValueTable({ statement, t }) {
  if (!statement?.length) return null
  const years = Object.keys(statement[0].values)
  return (
    <div style={{ marginTop: '16px', overflowX: 'auto' }}>
      <div style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: '0.65rem',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: 'var(--teal)',
        marginBottom: '8px',
      }}>{t.step3.is_table_title}</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>{t.step3.col_common_field}</th>
            {years.map((yr) => <th key={yr} style={{ textAlign: 'right' }}>{yr}</th>)}
          </tr>
        </thead>
        <tbody>
          {statement.map((row) => {
            const { indent = 0, isSubtotal = false } = IS_STYLE[row.description] ?? {}
            const label = t.step3.is_account_labels?.[row.description] ?? row.description
            const border = isSubtotal ? '2px solid rgba(11,31,58,0.07)' : undefined
            return (
              <tr key={row.description}>
                <td style={{
                  whiteSpace: 'nowrap',
                  paddingLeft: `${12 + indent * 20}px`,
                  fontFamily: "'IBM Plex Sans', sans-serif",
                  fontWeight: isSubtotal ? 600 : 400,
                  color: isSubtotal ? 'var(--navy)' : 'var(--gray)',
                  borderTop: border,
                }}>{label}</td>
                {Object.values(row.values).map((val, i) => (
                  <td key={i} style={{
                    textAlign: 'right',
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: '0.82rem',
                    fontWeight: isSubtotal ? 700 : 400,
                    color: isSubtotal ? 'var(--navy)' : 'var(--gray)',
                    borderTop: border,
                    whiteSpace: 'nowrap',
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
  )
}

function StatementCard({ label, sublabel, rows, coverage, subAccounts, parecerPeriods, unavailable, t }) {
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
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: '0.65rem',
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
          color: 'var(--teal)',
          marginBottom: '2px',
        }}>{sublabel}</div>
        <div style={{
          fontFamily: "'IBM Plex Sans', sans-serif",
          fontSize: '0.85rem',
          fontWeight: 600,
          color: 'var(--navy)',
        }}>{label}</div>
      </div>

      {unavailable ? (
        <p style={{ fontSize: '0.78rem', color: 'var(--gray)', fontStyle: 'italic', fontFamily: "'IBM Plex Sans', sans-serif" }}>
          {t.step3.not_available}
        </p>
      ) : (
        <>
          {/* Key-value rows */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', marginBottom: coverage || subAccounts ? '12px' : 0 }}>
            {rows.map(({ key, val }) => (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px' }}>
                <span style={{ fontSize: '0.78rem', color: 'var(--gray)', fontFamily: "'IBM Plex Sans', sans-serif" }}>{key}</span>
                <span style={{
                  fontFamily: "'IBM Plex Mono', monospace",
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
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: '0.65rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                color: 'var(--teal)',
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
                    background: 'var(--teal)',
                    borderRadius: '3px',
                    transition: 'width 0.4s ease',
                  }} />
                </div>
                <span style={{
                  fontFamily: "'IBM Plex Mono', monospace",
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

          {/* Parecer period chips */}
          {parecerPeriods?.length > 0 && (
            <div style={{ borderTop: '1px solid rgba(11,31,58,0.07)', paddingTop: '10px', marginTop: '4px' }}>
              <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--teal)', marginBottom: '6px' }}>
                {t.step3.parecer_periods_found ?? 'Periods Found'}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                {parecerPeriods.map((yr) => (
                  <span key={yr} style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.72rem', fontWeight: 600, color: 'var(--teal)', background: 'var(--teal-dim)', border: '1px solid rgba(14,143,154,0.3)', borderRadius: '4px', padding: '1px 6px' }}>{yr}</span>
                ))}
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
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: '0.65rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                color: 'var(--teal)',
                marginBottom: '6px',
              }}>{t.step3.sub_accounts_label}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {CF_SUB_ACCOUNT_KEYS.map((key) => {
                  const found = subAccounts[key]
                  const label = t.step3[`sub_account_${key}`] ?? key.replace(/_/g, ' ')
                  return (
                    <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                      <span style={{
                        fontFamily: "'IBM Plex Mono', monospace",
                        fontSize: '0.78rem',
                        fontWeight: 700,
                        color: found ? 'var(--teal)' : 'var(--gray)',
                        width: '14px',
                        flexShrink: 0,
                      }}>{found ? '✓' : '—'}</span>
                      <span style={{
                        fontSize: '0.78rem',
                        color: found ? 'var(--charcoal)' : 'var(--gray)',
                        fontFamily: "'IBM Plex Sans', sans-serif",
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
        fontFamily: "'IBM Plex Sans', sans-serif",
        marginBottom: '14px',
      }}>
        {t.step3.periods_mapped}:{' '}
        <strong style={{ color: 'var(--charcoal)', fontFamily: "'IBM Plex Mono', monospace" }}>
          {annual}
        </strong>{' '}
        {t.step3.annual_label}{' '}+{' '}
        <strong style={{ color: 'var(--charcoal)', fontFamily: "'IBM Plex Mono', monospace" }}>
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
          fontFamily: "'IBM Plex Sans', sans-serif",
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
      fontFamily: "'IBM Plex Mono', monospace",
      fontSize: '0.65rem',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      color: 'var(--teal)',
      marginBottom: '6px',
      marginTop: '12px',
    }}>{children}</div>
  )
}

// Table for BS fields, CF top-level accounts, and Parecer fields
function MappingTable({ fields, t, showCvmCode, showDescription }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>{t.step3.col_common_field}</th>
            {showCvmCode && <th style={{ textAlign: 'left' }}>{t.step3.col_cvm_code}</th>}
            <th style={{ textAlign: 'left' }}>{t.step3.col_status}</th>
            {showDescription && <th style={{ textAlign: 'left' }}>{t.step3.col_description ?? 'Description'}</th>}
          </tr>
        </thead>
        <tbody>
          {fields.map((row) => (
            <tr key={row.field}>
              <td style={{
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: '0.78rem',
                color: 'var(--charcoal)',
              }}>{row.field}</td>
              {showCvmCode && (
                <td style={{
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: '0.78rem',
                  color: 'var(--gray)',
                }}>{row.cvm_code}</td>
              )}
              <td>
                <StatusBadge status={row.status} t={t} />
              </td>
              {showDescription && (
                <td style={{ fontSize: '0.78rem', color: 'var(--gray)', fontFamily: "'IBM Plex Sans', sans-serif" }}>
                  {row.description ?? ''}
                </td>
              )}
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
                fontFamily: "'IBM Plex Mono', monospace",
                fontSize: '0.78rem',
                color: 'var(--charcoal)',
                whiteSpace: 'nowrap',
              }}>{row.field}</td>
              <td>
                <StatusBadge status={row.status} t={t} />
              </td>
              <td style={{
                fontFamily: "'IBM Plex Mono', monospace",
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
    mapped:    { color: 'var(--teal)',    bg: 'rgba(14,143,154,0.08)', label: t.step3.status_mapped, icon: '✓' },
    computed:  { color: 'var(--teal)',    bg: 'rgba(14,143,154,0.08)', label: t.step3.status_computed, icon: '✓', italic: true },
    found:     { color: 'var(--teal)',    bg: 'rgba(14,143,154,0.08)', label: t.step3.status_found, icon: '✓' },
    not_found: { color: 'var(--gray)',    bg: 'rgba(11,31,58,0.05)',   label: t.step3.status_not_found, icon: '—' },
    not_used:  { color: 'var(--gray)',    bg: 'rgba(11,31,58,0.05)',   label: t.step3.status_not_used ?? 'Not used', icon: '—' },
  }
  const cfg = configs[status] ?? configs.not_found
  return (
    <span style={{
      fontFamily: "'IBM Plex Sans', sans-serif",
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
