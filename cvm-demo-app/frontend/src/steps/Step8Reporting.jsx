import { useEffect, useRef, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts'
import { useI18n, useAppState, useAppDispatch } from '../App'
import MarkdownView from '../components/MarkdownView'
import styles from './Step.module.css'

// ── PDF Download button ───────────────────────────────────────────────────────

function PdfDownloadButton({ t, companyName, lang }) {
  const [loading, setLoading] = useState(false)

  async function handleClick() {
    if (loading) return
    setLoading(true)
    try {
      const res = await fetch('/api/report/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company: companyName, lang }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const cd = res.headers.get('Content-Disposition') || ''
      const match = cd.match(/filename="([^"]+)"/)
      const filename = match ? match[1] : 'cygnus-report.pdf'
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('[PDF export]', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        gap: '2px',
        padding: '12px 18px',
        borderRadius: '8px',
        border: '1px solid var(--teal-line)',
        background: loading ? 'var(--offwhite)' : 'transparent',
        cursor: loading ? 'not-allowed' : 'pointer',
        transition: 'background 0.15s, border-color 0.15s',
      }}
      onMouseEnter={(e) => { if (!loading) { e.currentTarget.style.background = 'var(--teal-dim)'; e.currentTarget.style.borderColor = 'var(--teal)' } }}
      onMouseLeave={(e) => { e.currentTarget.style.background = loading ? 'var(--offwhite)' : 'transparent'; e.currentTarget.style.borderColor = 'var(--teal-line)' }}
    >
      <span style={{ fontSize: '0.82rem', fontWeight: 600, color: loading ? 'var(--gray)' : 'var(--teal)', fontFamily: "'IBM Plex Sans', sans-serif" }}>
        {loading ? t.download_pdf_loading : `↓  ${t.download_pdf_label}`}
      </span>
      <span style={{ fontSize: '0.68rem', color: 'var(--gray)', fontFamily: "'IBM Plex Sans', sans-serif" }}>
        {t.download_pdf_sub}
      </span>
    </button>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtBRL(v) {
  if (v == null) return '—'
  const m = v / 1000 // BRL thousands → millions
  const abs = Math.abs(m)
  if (abs >= 1000) return (v < 0 ? '−' : '') + 'R$' + (Math.abs(m) / 1000).toFixed(1) + 'B'
  if (abs >= 1)    return (v < 0 ? '−' : '') + 'R$' + Math.abs(m).toFixed(0) + 'M'
  return (v < 0 ? '−' : '') + 'R$' + Math.abs(m).toFixed(1) + 'M'
}

function severityClass(sev) {
  const s = (sev ?? '').toUpperCase()
  if (s === 'CRITICAL' || s === 'HIGH' || s === 'CRÍTICO') return styles.badgeHigh
  if (s === 'MEDIUM' || s === 'MÉDIO') return styles.badgeMedium
  return styles.badgeLow
}

// ── JSON parse helpers (mirrors Step 7) ──────────────────────────────────────

function fixLiteralNewlines(str) {
  let out = ''
  let inString = false
  let i = 0
  while (i < str.length) {
    const ch = str[i]
    if (ch === '\\' && inString) { out += ch + (str[i + 1] ?? ''); i += 2; continue }
    if (ch === '"') { inString = !inString; out += ch; i++; continue }
    if (inString && ch === '\n') { out += '\\n'; i++; continue }
    if (inString && ch === '\r') { out += '\\r'; i++; continue }
    if (inString && ch === '\t') { out += '\\t'; i++; continue }
    out += ch; i++
  }
  return out
}

function tryParseJSON(text) {
  if (!text) return null
  const cleaned = text.replace(/^```json\s*$/im, '').replace(/^```\s*$/gim, '').trim()
  try { return JSON.parse(cleaned) } catch (_) {}
  try { return JSON.parse(fixLiteralNewlines(cleaned)) } catch (_) {}
  const fb = cleaned.indexOf('{'), lb = cleaned.lastIndexOf('}')
  if (fb !== -1 && lb > fb) {
    const ex = cleaned.slice(fb, lb + 1)
    try { return JSON.parse(ex) } catch (_) {}
    try { return JSON.parse(fixLiteralNewlines(ex)) } catch (e) {
      console.warn('[Step8] All parse attempts failed:', e.message)
    }
  }
  return null
}

// ── Metric callout cards ──────────────────────────────────────────────────────

function MetricCard({ label, value, sub, severity }) {
  const sev = severity ?? 'normal'
  const colorMap = { critical: '#E24B4A', high: '#b45309', normal: 'var(--teal)' }
  const bgMap    = { critical: 'rgba(226,75,74,0.05)', high: 'rgba(239,159,39,0.05)', normal: '#fff' }
  const borderMap = { critical: 'rgba(226,75,74,0.18)', high: 'rgba(239,159,39,0.18)', normal: 'rgba(11,31,58,0.07)' }
  const c = colorMap[sev] ?? colorMap.normal
  return (
    <div style={{
      background: bgMap[sev] ?? bgMap.normal,
      border: `1px solid ${borderMap[sev] ?? borderMap.normal}`,
      borderRadius: '6px',
      padding: '14px 16px',
      flex: 1,
      minWidth: '120px',
    }}>
      <div style={{ fontSize: '0.6rem', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: c, marginBottom: '6px' }}>
        {label}
      </div>
      <div style={{ fontSize: '1.25rem', fontWeight: 600, fontFamily: "'IBM Plex Sans', sans-serif", color: 'var(--charcoal)', lineHeight: 1.2 }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: '0.66rem', fontFamily: "'IBM Plex Mono', monospace", color: c, marginTop: '4px', fontWeight: 500 }}>
          {sub}
        </div>
      )}
    </div>
  )
}

function MetricCalloutRow({ step4Data, step6Data, t }) {
  const riskScore = step6Data.risk_score ?? null
  const riskLevel = (step6Data.risk_level ?? '').toUpperCase()

  // Use annual entries only to avoid quarterly/annual double-counting
  const bsAnnual  = (step4Data.balance_sheet_series ?? []).filter(r => r.granularity === 'annual')
  const latestBS  = bsAnnual.at(-1) ?? {}
  const equity    = latestBS.total_equity ?? null
  const debtEbitda = latestBS.debt_to_ebitda ?? null
  const equityNeg  = equity != null && equity < 0
  const debtHigh   = debtEbitda != null && debtEbitda > 4

  const cfAnnual = (step4Data.cash_flow_series ?? []).filter(r => r.granularity === 'annual')
  let fcfStreak = 0
  for (let i = cfAnnual.length - 1; i >= 0; i--) {
    if ((cfAnnual[i].free_cash_flow ?? 0) < 0) fcfStreak++
    else break
  }

  const riskSev = riskLevel === 'CRITICAL' ? 'critical' : riskLevel === 'HIGH' ? 'high' : 'normal'

  const freMaturity  = step4Data.fre_debt_maturity ?? null
  const nearTermPct  = freMaturity?.near_term_pct ?? null

  return (
    <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '20px' }}>
      <MetricCard
        label={t.metric_risk_score}
        value={riskScore != null ? `${riskScore}/100` : '—'}
        sub={riskLevel || null}
        severity={riskSev}
      />
      <MetricCard
        label={t.metric_net_equity}
        value={equity != null ? fmtBRL(equity) : '—'}
        sub={equityNeg ? t.metric_critical : null}
        severity={equityNeg ? 'critical' : 'normal'}
      />
      <MetricCard
        label={t.metric_debt_ebitda}
        value={debtEbitda != null ? debtEbitda.toFixed(1) + '×' : '—'}
        sub={debtHigh ? t.metric_critical : null}
        severity={debtHigh ? (debtEbitda > 8 ? 'critical' : 'high') : 'normal'}
      />
      <MetricCard
        label={t.metric_fcf_streak}
        value={fcfStreak > 0 ? String(fcfStreak) : '—'}
        sub={fcfStreak > 0 ? t.metric_consecutive_negative : null}
        severity={fcfStreak >= 4 ? 'critical' : fcfStreak >= 2 ? 'high' : 'normal'}
      />
      {nearTermPct != null && (
        <MetricCard
          label={t.metric_debt_maturity}
          value={nearTermPct.toFixed(0) + '%'}
          sub={t.metric_near_term_sub}
          severity={nearTermPct >= 50 ? 'critical' : nearTermPct >= 30 ? 'high' : 'normal'}
        />
      )}
    </div>
  )
}

// ── Mini chart driven by LLM-chosen metric ────────────────────────────────────

const METRIC_LABELS = {
  revenue_abs:      'Revenue',
  cogs_abs:         'COGS',
  gross_profit_abs: 'Gross Profit',
  ebit_abs:         'EBIT',
  ebitda_abs:       'EBITDA',
}

// Format BRL thousands → human-readable (B/M)
function fmtBRLAxis(v) {
  if (v == null) return ''
  const b = v / 1_000_000  // thousands → billions
  if (Math.abs(b) >= 1) return `R$${b.toFixed(1)}B`
  const m = v / 1_000      // thousands → millions
  return `R$${m.toFixed(0)}M`
}

function MiniMarginChart({ step4Data, featuredChart, t }) {
  const primary   = featuredChart?.primary_metric   ?? 'revenue_abs'
  const secondary = featuredChart?.secondary_metric ?? null
  const title     = featuredChart?.chart_title      ?? t.chart_margin_mini ?? 'Financial Trajectory'
  const reason    = featuredChart?.reason           ?? null

  const data = (step4Data.time_series ?? []).filter(r => r[primary] != null)
  if (!data.length) return null

  // Y-axis domain from actual data with 10% padding
  const allVals = data.flatMap(r => [r[primary], secondary ? r[secondary] : null].filter(v => v != null))
  const rawMin = Math.min(...allVals)
  const rawMax = Math.max(...allVals)
  const pad = (rawMax - rawMin) * 0.1
  const domain = [rawMin - pad, rawMax + pad]

  return (
    <div style={{
      background: 'var(--offwhite)',
      border: '1px solid rgba(11,31,58,0.07)',
      borderRadius: '6px',
      padding: '12px 14px',
      marginTop: '12px',
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: '8px' }}>
        <div style={{ fontSize: '0.6rem', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: 'var(--teal)' }}>
          {title}
        </div>
        {reason && (
          <div style={{ fontSize: '0.62rem', fontFamily: "'IBM Plex Sans', sans-serif", color: 'var(--gray)', fontStyle: 'italic', maxWidth: '55%', textAlign: 'right' }}>
            {reason}
          </div>
        )}
      </div>
      <ResponsiveContainer width="100%" height={150}>
        <LineChart data={data} margin={{ top: 4, right: 12, bottom: 4, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
          <XAxis dataKey="period" tick={{ fontSize: 9, fontFamily: "'IBM Plex Mono', monospace" }} />
          <YAxis
            tickFormatter={fmtBRLAxis}
            tick={{ fontSize: 9, fontFamily: "'IBM Plex Mono', monospace" }}
            width={52}
            domain={domain}
          />
          <Tooltip formatter={(v, name) => [fmtBRLAxis(v), METRIC_LABELS[name] ?? name]} />
          <ReferenceLine y={0} stroke="rgba(11,31,58,0.18)" strokeDasharray="4 2" strokeWidth={1} />
          <Line
            type="monotone" dataKey={primary}
            name={primary}
            stroke="#2E86C1" strokeWidth={2} dot={{ r: 3 }}
          />
          {secondary && secondary !== primary && (
            <Line
              type="monotone" dataKey={secondary}
              name={secondary}
              stroke="rgba(46,134,193,0.45)" strokeWidth={1.5} dot={{ r: 2 }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Cross-module diagnosis summary ────────────────────────────────────────────

function DiagnosisSummary({ step6Data, t }) {
  const diagnoses = (step6Data.findings ?? []).filter(f => f.module === 'stacked')
  if (!diagnoses.length) return null
  return (
    <div style={{
      background: 'rgba(226,75,74,0.03)',
      border: '1px solid rgba(226,75,74,0.12)',
      borderLeft: '3px solid #E24B4A',
      borderRadius: '6px',
      padding: '12px 16px',
      marginTop: '12px',
    }}>
      <div style={{ fontSize: '0.6rem', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: '#E24B4A', marginBottom: '10px' }}>
        {t.cross_module_diagnosis_summary}
      </div>
      {diagnoses.map((dx, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '5px 0',
          borderBottom: i < diagnoses.length - 1 ? '1px solid rgba(226,75,74,0.07)' : 'none',
        }}>
          <span style={{ fontSize: '0.84rem', color: 'var(--charcoal)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#E24B4A', fontWeight: 600, fontSize: '0.7rem' }}>●</span>
            {dx.pattern || dx.code || dx.description?.slice(0, 60)}
          </span>
          <span className={severityClass(dx.severity)}>{dx.severity}</span>
        </div>
      ))}
    </div>
  )
}

// ── Data gaps list ────────────────────────────────────────────────────────────

function DataGapsList({ gaps, t }) {
  if (!gaps?.length) return null
  return (
    <div style={{
      background: '#fff',
      border: '1px solid rgba(11,31,58,0.07)',
      borderRadius: '6px',
      padding: '12px 16px',
      marginTop: '12px',
    }}>
      <div style={{ fontSize: '0.6rem', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: 'var(--teal)', marginBottom: '10px' }}>
        {t.internal_data_needed}
      </div>
      <ol style={{ margin: 0, paddingLeft: '18px' }}>
        {gaps.map((gap, i) => (
          <li key={i} style={{ fontSize: '0.84rem', color: 'var(--gray)', lineHeight: 1.65, marginBottom: '5px' }}>
            {gap}
          </li>
        ))}
      </ol>
    </div>
  )
}

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ header, narrative, italic = false, children }) {
  return (
    <div style={{ marginBottom: '28px' }}>
      <h3 style={{
        fontSize: '1.15rem',
        fontWeight: 700,
        fontFamily: "'IBM Plex Sans', sans-serif",
        color: 'var(--navy)',
        margin: '0 0 10px 0',
        letterSpacing: '-0.01em',
      }}>
        {header}
      </h3>
      {narrative && (
        <p style={{
          fontFamily: "'IBM Plex Sans', sans-serif",
          fontWeight: 400,
          fontStyle: italic ? 'italic' : 'normal',
          fontSize: '0.9rem',
          lineHeight: 1.8,
          color: 'var(--charcoal)',
          margin: children ? '0 0 0 0' : 0,
        }}>
          {narrative}
        </p>
      )}
      {children}
    </div>
  )
}

// ── Key findings table ────────────────────────────────────────────────────────

function KeyFindingsTable({ findings, t }) {
  if (!findings?.length) return null
  return (
    <table className={styles.table} style={{ marginTop: '4px' }}>
      <thead>
        <tr>
          <th>{t.finding_module}</th>
          <th>{t.finding_label}</th>
          <th>{t.finding_severity}</th>
          <th>{t.finding_evidence}</th>
        </tr>
      </thead>
      <tbody>
        {findings.map((f, i) => (
          <tr key={i}>
            <td style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
              {f.module}
            </td>
            <td style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontWeight: 400 }}>{f.finding}</td>
            <td><span className={severityClass(f.severity)}>{f.severity}</span></td>
            <td style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.78rem' }}>{f.evidence}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// ── Structured briefing ───────────────────────────────────────────────────────

function StructuredBriefing({ parsed, step4Data, step6Data, t }) {
  const featuredChart = parsed.featured_chart ?? null
  return (
    <div>
      {/* Opening: metric callout cards + executive summary sentence */}
      <div style={{
        background: 'var(--offwhite)',
        border: '1px solid rgba(11,31,58,0.07)',
        borderRadius: '8px',
        padding: '18px 20px',
        marginBottom: '28px',
      }}>
        <div style={{ fontSize: '0.6rem', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: 'var(--teal)', marginBottom: '14px' }}>
          {t.h_executive_summary}
        </div>
        <MetricCalloutRow step4Data={step4Data} step6Data={step6Data} t={t} />
        {parsed.executive_summary && (
          <p style={{
            fontFamily: "'IBM Plex Sans', sans-serif",
            fontWeight: 400,
            fontSize: '0.9rem',
            lineHeight: 1.8,
            color: 'var(--charcoal)',
            margin: 0,
          }}>
            {parsed.executive_summary}
          </p>
        )}
        <MiniMarginChart step4Data={step4Data} featuredChart={featuredChart} t={t} />
      </div>

      {/* What Happened */}
      <Section header={t.h_what_happened} narrative={parsed.what_happened} />

      {/* How Serious + diagnosis summary */}
      <Section header={t.h_how_serious} narrative={parsed.how_serious}>
        <DiagnosisSummary step6Data={step6Data} t={t} />
      </Section>

      {/* When Things Turned — text only */}
      <Section header={t.h_when_things_turned} narrative={parsed.when_things_turned} />

      {/* What Comes Next — text only */}
      <Section header={t.h_what_comes_next} narrative={parsed.what_comes_next} />

      {/* What We Can't Answer + data gaps list */}
      <Section header={t.h_what_we_cant_answer} narrative={parsed.what_we_cant_answer}>
        <DataGapsList gaps={parsed.data_gaps} t={t} />
      </Section>

      {/* Key Findings table */}
      <Section header={t.h_key_findings}>
        <KeyFindingsTable findings={parsed.key_findings} t={t} />
      </Section>

      {/* Next Step — italic */}
      <Section header={t.h_next_step} narrative={parsed.next_step} italic />

      {/* AI disclaimer */}
      <p style={{ fontSize: '0.75rem', color: '#94a3b8', fontStyle: 'italic', borderTop: '1px solid #f1f5f9', paddingTop: '12px', marginTop: '8px' }}>
        {t.ai_disclaimer}
      </p>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Step8Reporting({ stepState, data }) {
  const t        = useI18n().step8
  const t4       = useI18n().step4
  const appState = useAppState()
  const dispatch = useAppDispatch()

  const [parsedData, setParsedData] = useState(null)
  const [rawText,    setRawText]    = useState('')
  const [sections,   setSections]   = useState({})
  const [parseError, setParseError] = useState(false)
  const [status,     setStatus]     = useState('idle') // idle | connecting | streaming | parsing | done | error
  const [payload,    setPayload]    = useState(null)
  const wsRef = useRef(null)

  const step4Data = appState.stepData[4]?.data ?? {}
  const step6Data = appState.stepData[6]?.data ?? {}
  const step7Data = appState.stepData[7]?.data ?? {}

  const isStreaming    = status === 'connecting' || status === 'streaming'
  const hasFindingsCtx = !!step6Data.findings?.length

  // Partial parsed object assembled from sections during streaming
  const partialParsed = isStreaming && Object.keys(sections).length > 0 ? {
    ...sections.diagnosis,
    ...sections.timeline,
    ...sections.severity,
    ...sections.gaps,
  } : null

  // Start WebSocket when payload is set
  useEffect(() => {
    if (!payload) return

    setParsedData(null)
    setRawText('')
    setSections({})
    setParseError(false)
    setStatus('connecting')

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/llm`)
    wsRef.current = ws

    const sectionsAccum = {}

    ws.onopen = () => {
      setStatus('streaming')
      ws.send(JSON.stringify(payload))
    }

    ws.onmessage = (e) => {
      if (e.data === '[DONE]') {
        ws.close()
        const assembled = {
          ...sectionsAccum.diagnosis,
          ...sectionsAccum.timeline,
          ...sectionsAccum.severity,
          ...sectionsAccum.gaps,
        }
        setParsedData(assembled)
        setParseError(false)
        setStatus('done')
        dispatch({
          type: 'SET_STEP_COMPLETE',
          step: 8,
          data: {
            status: 'complete',
            data: { response_text: JSON.stringify(assembled), status: 'complete' },
            metadata: { source: 'websocket' },
          },
        })
        return
      }
      if (e.data.startsWith('[ERROR]')) {
        setStatus('error')
        ws.close()
        return
      }
      try {
        const msg = JSON.parse(e.data)
        if (msg.__section && msg.data) {
          sectionsAccum[msg.__section] = msg.data
          setSections({ ...sectionsAccum })
        }
      } catch (_) {}
    }

    ws.onerror = () => setStatus('error')

    return () => ws.close()
  }, [payload])

  // On mount: if already complete from cache, parse cached response
  useEffect(() => {
    if (stepState === 'complete' && data?.data?.response_text && status === 'idle') {
      const parsed = tryParseJSON(data.data.response_text)
      if (parsed) {
        setParsedData(parsed)
      } else {
        setRawText(data.data.response_text)
        setParseError(true)
      }
      setStatus('done')
    }
  }, [stepState, data])

  function handleGenerate() {
    if (!hasFindingsCtx) return
    setPayload({
      step: 8,
      step6_data:          step6Data,
      step7_response:      step7Data.response_text ?? '',
      company_name:        appState.companyName ?? 'BRASKEM S.A.',
      language:            appState.language ?? 'en',
      fre_available:       step4Data?.fre_debt_maturity != null,
      fre_debt_maturity:   step4Data?.fre_debt_maturity ?? null,
      fre_debt_currency:   step4Data?.fre_debt_currency ?? null,
    })
  }

  const showRunButton = status === 'idle' || status === 'error'
  const showResults   = status === 'done' || (isStreaming && partialParsed !== null)
  const displayData   = parsedData ?? partialParsed

  // Merge i18n t4 keys needed for chart labels into t
  const tMerged = {
    ...t,
    gross_margin_label:  t4.gross_margin_label,
    ebit_margin_label:   t4.ebit_margin_label,
    chart_margin_mini:   t4.chart_margin_title,
  }

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.title}</h2>
      <p className={styles.description}>{t.description}</p>

      {/* Run button */}
      {showRunButton && (
        <div style={{ marginBottom: '20px' }}>
          <button
            onClick={handleGenerate}
            disabled={!hasFindingsCtx}
            style={{
              padding: '10px 24px',
              borderRadius: '8px',
              background: hasFindingsCtx ? 'var(--teal)' : 'rgba(11,31,58,0.06)',
              color: hasFindingsCtx ? '#fff' : 'var(--gray)',
              border: 'none',
              cursor: hasFindingsCtx ? 'pointer' : 'not-allowed',
              fontWeight: 600,
              fontSize: '0.9rem',
              fontFamily: "'IBM Plex Sans', sans-serif",
            }}
          >
            {t.run_button}
          </button>
          {!hasFindingsCtx && (
            <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '8px' }}>
              {t.no_step6_data}
            </p>
          )}
          {status === 'error' && (
            <p style={{ fontSize: '0.78rem', color: '#E24B4A', marginTop: '8px' }}>
              Connection error — try again.
            </p>
          )}
        </div>
      )}

      {/* Streaming / parsing status */}
      {(isStreaming || status === 'parsing') && (
        <div style={{
          marginBottom: '20px',
          padding: '12px 16px',
          background: 'rgba(14,143,154,0.04)',
          border: '1px solid rgba(14,143,154,0.12)',
          borderRadius: '6px',
        }}>
          <div className={styles.running} style={{ fontSize: '0.82rem' }}>
            {status === 'parsing' ? t.parsing_analysis : t.running_message}
          </div>
        </div>
      )}

      {/* Done row + PDF download button */}
      {status === 'done' && !showRunButton && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.78rem' }}>
            <span style={{ color: 'var(--teal)', fontFamily: "'IBM Plex Mono', monospace" }}>✓ Complete</span>
            {parseError && (
              <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>— {t.fallback_note}</span>
            )}
          </div>
          <PdfDownloadButton
            t={t}
            companyName={appState.companyName ?? 'BRASKEM S.A.'}
            lang={appState.language ?? 'en'}
          />
        </div>
      )}

      {/* Results */}
      {showResults && (
        displayData
          ? <StructuredBriefing parsed={displayData} step4Data={step4Data} step6Data={step6Data} t={tMerged} />
          : (
            <div style={{
              background: 'var(--offwhite)',
              border: '1px solid rgba(11,31,58,0.07)',
              borderRadius: '6px',
              padding: '16px 20px',
              fontSize: '0.875rem',
              lineHeight: 1.7,
              color: 'var(--charcoal)',
            }}>
              <MarkdownView text={rawText || data?.data?.response_text || ''} />
            </div>
          )
      )}
    </div>
  )
}
