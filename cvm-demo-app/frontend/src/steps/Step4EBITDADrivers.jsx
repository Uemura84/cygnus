import {
  ResponsiveContainer,
  LineChart, Line,
  BarChart, Bar,
  ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from 'recharts'
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

function shortPeriod(p) {
  return p ? p.slice(0, 4) : p
}

function fmtK(v) {
  if (v == null) return '—'
  const abs = Math.abs(v)
  if (abs >= 1_000_000) return (v / 1_000_000).toFixed(1) + 'M'
  if (abs >= 1_000) return (v / 1_000).toFixed(0) + 'K'
  return v.toFixed(0)
}

// Convert BRL thousands → BRL millions/billions for compact metric tables
function fmtBrlM(v) {
  if (v == null) return '—'
  const m = v / 1000
  const abs = Math.abs(m)
  if (abs >= 1000) return (m / 1000).toFixed(1) + 'B'
  if (abs >= 1) return m.toFixed(0) + 'M'
  return m.toFixed(1) + 'M'
}

const BS_TABLE_ROWS = [
  { key: 'debt_to_ebitda',   labelKey: 'debt_to_ebitda_label',   descKey: 'debt_to_ebitda_desc',   fmt: v => v != null ? v.toFixed(2) + '×' : '—' },
  { key: 'current_ratio',    labelKey: 'current_ratio_label',    descKey: 'current_ratio_desc',    fmt: v => v != null ? v.toFixed(2) + '×' : '—' },
  { key: 'quick_ratio',      labelKey: 'quick_ratio_label',      descKey: 'quick_ratio_desc',      fmt: v => v != null ? v.toFixed(2) + '×' : '—' },
  { key: 'return_on_assets', labelKey: 'return_on_assets_label', descKey: 'return_on_assets_desc', fmt: v => v != null ? v.toFixed(1) + '%' : '—' },
  { key: 'return_on_equity', labelKey: 'return_on_equity_label', descKey: 'return_on_equity_desc', fmt: v => v != null ? v.toFixed(1) + '%' : '—' },
  { key: 'net_debt',         labelKey: 'net_debt_brlm_label',    descKey: 'net_debt_brlm_desc',    fmt: fmtBrlM },
]

const CF_TABLE_ROWS = [
  { key: 'operating_cash_flow', labelKey: 'ocf_label',              descKey: 'ocf_desc',              fmt: fmtBrlM },
  { key: 'free_cash_flow',      labelKey: 'fcf_brlm_label',         descKey: 'fcf_brlm_desc',         fmt: fmtBrlM },
  { key: 'ocf_to_net_income',   labelKey: 'ocf_to_ni_label',        descKey: 'ocf_to_ni_desc',        fmt: v => v != null ? v.toFixed(2) + '×' : '—' },
  { key: 'capex_to_revenue',    labelKey: 'capex_to_revenue_label', descKey: 'capex_to_revenue_desc', fmt: v => v != null ? v.toFixed(1) + '%' : '—' },
]

function MetricTable({ rows, data, t }) {
  if (!data || data.length === 0) return null
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className={styles.metricTable}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>Metric</th>
            {data.map(r => (
              <th key={r.period} style={{ textAlign: 'right' }}>{r.period}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ key, labelKey, descKey, fmt }) => (
            <tr key={key}>
              <td style={{ whiteSpace: 'nowrap' }}>
                {descKey
                  ? <span className={styles.tooltip} data-tooltip={t.step4[descKey]}>{t.step4[labelKey]}</span>
                  : t.step4[labelKey]
                }
              </td>
              {data.map(r => (
                <td key={r.period}>{fmt(r[key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Step4EBITDADrivers({ stepState, data }) {
  const t = useI18n()
  const d = data?.data

  const bsSeries = d?.balance_sheet_series ?? []
  const cfSeries = d?.cash_flow_series ?? []
  const interp   = d?.chart_interpretations ?? {}

  // Annual-only for charts — quarterly data stays in detection algorithms (Step 6)
  const bsData = bsSeries.filter(r => r.granularity === 'annual').map(r => ({ ...r, period: shortPeriod(r.period) }))
  const cfData = cfSeries.filter(r => r.granularity === 'annual').map(r => ({ ...r, period: shortPeriod(r.period) }))

  // ROE clipping: cap y-axis at [-100, 100], show note if values exceed range
  const ROE_MIN = -100
  const ROE_MAX = 100
  const roeValues = bsData.map(r => r.return_on_equity).filter(v => v != null)
  const roeActualMin = roeValues.length ? Math.min(...roeValues) : null
  const roeActualMax = roeValues.length ? Math.max(...roeValues) : null
  const roeClipped = roeActualMin != null && (roeActualMin < ROE_MIN || roeActualMax > ROE_MAX)

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
            <Stat label={t.step4.profitability_metrics_label} value={7} />
            <Stat label={t.step4.bs_metrics_label}            value={12} />
            <Stat label={t.step4.cf_metrics_label}            value={4} />
          </div>

          {/* ── Income Statement ─────────────────────────────────── */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step4.is_section_title}</h3>

            <div style={{ overflowX: 'auto' }}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left' }}>{t.step4.table_title}</th>
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
                        <td key={row.period} style={{ textAlign: 'right', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem' }}>
                          {fmt(row[key], isYoY)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className={styles.chartCard} style={{ marginTop: 18 }}>
              <h4 className={styles.chartTitle}>{t.step4.chart_margin_title}</h4>
              <MarginTrajectory
                data={d.time_series}
                labels={{
                  grossMargin: t.step4.gross_margin_label,
                  ebitMargin: t.step4.ebit_margin_label,
                  cogsRevenue: t.step4.cogs_revenue_label,
                  breakeven: t.charts?.breakeven,
                }}
              />
              {interp.margin_trajectory && (
                <p className={styles.chartCaption}>{interp.margin_trajectory}</p>
              )}
            </div>

            <div className={styles.chartCard} style={{ marginTop: 12 }}>
              <h4 className={styles.chartTitle}>{t.step4.chart_growth_title}</h4>
              <RevenueCOGSGrowth
                data={d.time_series}
                labels={{
                  revenue: t.step4.revenue_yoy_label,
                  cogs: t.step4.cogs_yoy_label,
                  divergenceGap: t.charts?.divergence_gap,
                  stickiness: t.charts?.cost_stickiness,
                }}
              />
              {interp.revenue_cogs_growth && (
                <p className={styles.chartCaption}>{interp.revenue_cogs_growth}</p>
              )}
            </div>
          </div>

          {/* ── Balance Sheet Health ─────────────────────────────── */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step4.bs_section_title}</h3>

            {bsData.length === 0 ? (
              <p style={{ color: 'var(--gray)', fontSize: '0.875rem' }}>{t.step4.bs_unavailable}</p>
            ) : (
              <>
                {/* Compact key-ratios summary table */}
                <p className={styles.sectionTitle} style={{ marginBottom: 8 }}>{t.step4.bs_table_title}</p>
                <MetricTable rows={BS_TABLE_ROWS} data={bsData} t={t} />

                {/* Chart 1: Liquidity Ratios */}
                <div className={styles.chartCard}>
                  <h4 className={styles.chartTitle}>{t.step4.chart_liquidity_title}</h4>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={bsData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
                      <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <YAxis tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <Tooltip formatter={(v) => v != null ? v.toFixed(2) : '—'} />
                      <Legend />
                      <ReferenceLine y={1} stroke="rgba(11,31,58,0.2)" strokeDasharray="4 4" />
                      <Line type="monotone" dataKey="current_ratio" name={t.step4.current_ratio_label} stroke="#1e90ff"              dot strokeWidth={2} connectNulls />
                      <Line type="monotone" dataKey="quick_ratio"   name={t.step4.quick_ratio_label}   stroke="rgba(30,144,255,0.55)" dot strokeWidth={2} connectNulls />
                    </LineChart>
                  </ResponsiveContainer>
                  {interp.liquidity && (
                    <p className={styles.chartCaption}>{interp.liquidity}</p>
                  )}
                </div>

                {/* Chart 2: Net Debt */}
                <div className={styles.chartCard}>
                  <h4 className={styles.chartTitle}>{t.step4.chart_net_debt_title}</h4>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={bsData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
                      <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <YAxis tickFormatter={fmtK} tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <Tooltip formatter={(v) => v != null ? fmtK(v) : '—'} />
                      <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" />
                      <Bar dataKey="net_debt" name={t.step4.net_debt_label} fill="rgba(30,144,255,0.55)" />
                    </BarChart>
                  </ResponsiveContainer>
                  {interp.net_debt && (
                    <p className={styles.chartCaption}>{interp.net_debt}</p>
                  )}
                </div>

                {/* Chart 3: Working Capital */}
                <div className={styles.chartCard}>
                  <h4 className={styles.chartTitle}>{t.step4.chart_working_capital_title}</h4>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={bsData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
                      <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <YAxis tickFormatter={fmtK} tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <Tooltip formatter={(v) => v != null ? fmtK(v) : '—'} />
                      <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" />
                      <Bar dataKey="working_capital" name={t.step4.working_capital_label} fill="#1e90ff" />
                    </BarChart>
                  </ResponsiveContainer>
                  {interp.working_capital && (
                    <p className={styles.chartCaption}>{interp.working_capital}</p>
                  )}
                </div>

                {/* Chart 4a: Return on Assets */}
                <div className={styles.chartCard}>
                  <h4 className={styles.chartTitle}>{t.step4.chart_roa_title}</h4>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={bsData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
                      <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <YAxis unit="%" tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <Tooltip formatter={(v) => v != null ? v.toFixed(1) + '%' : '—'} />
                      <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" strokeDasharray="4 4" />
                      <Line type="monotone" dataKey="return_on_assets" name={t.step4.return_on_assets_label} stroke="#1e90ff" dot strokeWidth={2} connectNulls />
                    </LineChart>
                  </ResponsiveContainer>
                  {interp.roa && (
                    <p className={styles.chartCaption}>{interp.roa}</p>
                  )}
                </div>

                {/* Chart 4b: Return on Equity — capped at [-100, +100] */}
                <div className={styles.chartCard}>
                  <h4 className={styles.chartTitle}>{t.step4.chart_roe_title}</h4>
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={bsData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
                      <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <YAxis unit="%" domain={[ROE_MIN, ROE_MAX]} tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <Tooltip formatter={(v) => v != null ? v.toFixed(1) + '%' : '—'} />
                      <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" strokeDasharray="4 4" />
                      <Line type="monotone" dataKey="return_on_equity" name={t.step4.return_on_equity_label} stroke="#1e90ff" dot strokeWidth={2} connectNulls />
                    </LineChart>
                  </ResponsiveContainer>
                  {roeClipped && (
                    <div style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '11px',
                      color: 'var(--gray)',
                      marginTop: '6px',
                    }}>
                      {t.step4.roe_clipped_note
                        ?.replace('{min}', roeActualMin.toFixed(1))
                        ?.replace('{max}', roeActualMax.toFixed(1))}
                    </div>
                  )}
                  {interp.roe && (
                    <p className={styles.chartCaption}>{interp.roe}</p>
                  )}
                </div>
              </>
            )}
          </div>

          {/* ── Cash Flow Analysis ───────────────────────────────── */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>{t.step4.cf_section_title}</h3>

            {cfData.length === 0 ? (
              <p style={{ color: 'var(--gray)', fontSize: '0.875rem' }}>{t.step4.cf_unavailable}</p>
            ) : (
              <>
                {/* Compact key-ratios summary table */}
                <p className={styles.sectionTitle} style={{ marginBottom: 8 }}>{t.step4.cf_table_title}</p>
                <MetricTable rows={CF_TABLE_ROWS} data={cfData} t={t} />

                {/* Chart 5: OCF / ICF / Financing */}
                <div className={styles.chartCard}>
                  <h4 className={styles.chartTitle}>{t.step4.chart_cf_statement_title}</h4>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={cfData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
                      <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <YAxis tickFormatter={fmtK} tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <Tooltip formatter={(v) => v != null ? fmtK(v) : '—'} />
                      <Legend />
                      <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" />
                      <Bar dataKey="operating_cash_flow"  name={t.step4.ocf_label}     fill="#1e90ff" />
                      <Bar dataKey="investing_cash_flow"  name={t.step4.icf_label}     fill="rgba(30,144,255,0.55)" />
                      <Bar dataKey="financing_cash_flow"  name={t.step4.fcf_fin_label} fill="rgba(30,144,255,0.3)" />
                    </BarChart>
                  </ResponsiveContainer>
                  {interp.cf_statement && (
                    <p className={styles.chartCaption}>{interp.cf_statement}</p>
                  )}
                </div>

                {/* Chart 6: Free Cash Flow */}
                <div className={styles.chartCard}>
                  <h4 className={styles.chartTitle}>{t.step4.chart_fcf_title}</h4>
                  <ResponsiveContainer width="100%" height={220}>
                    <ComposedChart data={cfData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
                      <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <YAxis tickFormatter={fmtK} tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <Tooltip formatter={(v) => v != null ? fmtK(v) : '—'} />
                      <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" />
                      <Bar dataKey="free_cash_flow" name={t.step4.fcf_label} fill="#1e90ff" />
                    </ComposedChart>
                  </ResponsiveContainer>
                  {interp.fcf && (
                    <p className={styles.chartCaption}>{interp.fcf}</p>
                  )}
                </div>

                {/* Chart 7: Cash Conversion Cycle — uses BS series */}
                {bsData.length > 0 && (
                  <div className={styles.chartCard}>
                    <h4 className={styles.chartTitle}>{t.step4.chart_ccc_title}</h4>
                    <ResponsiveContainer width="100%" height={220}>
                      <LineChart data={bsData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
                        <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                        <YAxis tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                        <Tooltip formatter={(v) => v != null ? v.toFixed(0) + 'd' : '—'} />
                        <Legend />
                        <ReferenceLine y={0} stroke="rgba(11,31,58,0.2)" strokeDasharray="4 4" />
                        <Line type="monotone" dataKey="receivable_days"      name={t.step4.receivable_days_label} stroke="#1e90ff"              dot strokeWidth={2} connectNulls />
                        <Line type="monotone" dataKey="inventory_days"       name={t.step4.inventory_days_label}  stroke="rgba(30,144,255,0.55)" dot strokeWidth={2} connectNulls />
                        <Line type="monotone" dataKey="payable_days"         name={t.step4.payable_days_label}    stroke="rgba(30,144,255,0.35)" dot strokeWidth={2} connectNulls />
                        <Line type="monotone" dataKey="cash_conversion_cycle" name={t.step4.ccc_label}           stroke="#1e90ff"               dot={false} strokeWidth={2} strokeDasharray="5 5" connectNulls />
                      </LineChart>
                    </ResponsiveContainer>
                    {interp.ccc && (
                      <p className={styles.chartCaption}>{interp.ccc}</p>
                    )}
                  </div>
                )}

                {/* Chart 8: Capex Metrics */}
                <div className={styles.chartCard}>
                  <h4 className={styles.chartTitle}>{t.step4.chart_capex_title}</h4>
                  <ResponsiveContainer width="100%" height={220}>
                    <ComposedChart data={cfData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
                      <XAxis dataKey="period" tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <YAxis yAxisId="left"  unit="%" tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                      <Tooltip />
                      <Legend />
                      <Bar yAxisId="left" dataKey="capex_to_revenue" name={t.step4.capex_to_revenue_label} fill="#1e90ff" />
                      <Line yAxisId="right" type="monotone" dataKey="capex_to_depreciation" name={t.step4.capex_to_da_label} stroke="rgba(30,144,255,0.55)" dot strokeWidth={2} connectNulls />
                    </ComposedChart>
                  </ResponsiveContainer>
                  {interp.capex && (
                    <p className={styles.chartCaption}>{interp.capex}</p>
                  )}
                </div>
              </>
            )}
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
