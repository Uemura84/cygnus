import { useEffect, useRef, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts'
import { useI18n, useAppState, useAppDispatch } from '../App'
import MarkdownView from '../components/MarkdownView'
import styles from './Step.module.css'

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
  const colorMap = { critical: '#E24B4A', high: '#b45309', normal: 'var(--blue)' }
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
      <div style={{ fontSize: '0.6rem', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: c, marginBottom: '6px' }}>
        {label}
      </div>
      <div style={{ fontSize: '1.25rem', fontWeight: 600, fontFamily: "'DM Sans', sans-serif", color: 'var(--charcoal)', lineHeight: 1.2 }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: '0.66rem', fontFamily: "'JetBrains Mono', monospace", color: c, marginTop: '4px', fontWeight: 500 }}>
          {sub}
        </div>
      )}
    </div>
  )
}

function MetricCalloutRow({ step4Data, step6Data, t }) {
  const riskScore = step6Data.risk_score ?? null
  const riskLevel = (step6Data.risk_level ?? '').toUpperCase()

  const bsSeries  = step4Data.balance_sheet_series ?? []
  const latestBS  = bsSeries.at(-1) ?? {}
  const equity    = latestBS.total_equity ?? null
  const debtEbitda = latestBS.debt_to_ebitda ?? null
  const equityNeg  = equity != null && equity < 0
  const debtHigh   = debtEbitda != null && debtEbitda > 4

  const cfSeries = step4Data.cash_flow_series ?? []
  let fcfStreak = 0
  for (let i = cfSeries.length - 1; i >= 0; i--) {
    if ((cfSeries[i].free_cash_flow ?? 0) < 0) fcfStreak++
    else break
  }

  const riskSev = riskLevel === 'CRITICAL' ? 'critical' : riskLevel === 'HIGH' ? 'high' : 'normal'

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
    </div>
  )
}

// ── Mini Margin Trajectory chart ──────────────────────────────────────────────

function MiniMarginChart({ step4Data, t }) {
  const data = (step4Data.time_series ?? [])
    .filter(r => r.Gross_Margin_pct != null)
  if (!data.length) return null

  return (
    <div style={{
      background: 'var(--offwhite)',
      border: '1px solid rgba(11,31,58,0.07)',
      borderRadius: '6px',
      padding: '12px 14px',
      marginTop: '12px',
    }}>
      <div style={{ fontSize: '0.6rem', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: 'var(--blue)', marginBottom: '8px' }}>
        {t.chart_margin_mini ?? 'Margin Trajectory'}
      </div>
      <ResponsiveContainer width="100%" height={150}>
        <LineChart data={data} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,58,0.06)" />
          <XAxis dataKey="period" tick={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} />
          <YAxis unit="%" tick={{ fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }} width={32} domain={[-15, 40]} />
          <Tooltip formatter={(v) => `${v?.toFixed(1)}%`} />
          <ReferenceLine y={0} stroke="rgba(11,31,58,0.18)" strokeDasharray="4 2" strokeWidth={1} />
          <Line
            type="monotone" dataKey="Gross_Margin_pct"
            name={t.gross_margin_label ?? 'Gross Margin %'}
            stroke="#1e90ff" strokeWidth={2} dot={{ r: 3 }}
          />
          <Line
            type="monotone" dataKey="EBIT_Margin_pct"
            name={t.ebit_margin_label ?? 'EBIT Margin %'}
            stroke="rgba(30,144,255,0.45)" strokeWidth={1.5} dot={{ r: 2 }}
          />
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
      <div style={{ fontSize: '0.6rem', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: '#E24B4A', marginBottom: '10px' }}>
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
      <div style={{ fontSize: '0.6rem', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: 'var(--blue)', marginBottom: '10px' }}>
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
        fontFamily: "'DM Sans', sans-serif",
        color: 'var(--navy)',
        margin: '0 0 10px 0',
        letterSpacing: '-0.01em',
      }}>
        {header}
      </h3>
      {narrative && (
        <p style={{
          fontFamily: "'DM Sans', sans-serif",
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
            <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
              {f.module}
            </td>
            <td style={{ fontFamily: "'DM Sans', sans-serif", fontWeight: 400 }}>{f.finding}</td>
            <td><span className={severityClass(f.severity)}>{f.severity}</span></td>
            <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.78rem' }}>{f.evidence}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// ── Structured briefing ───────────────────────────────────────────────────────

function StructuredBriefing({ parsed, step4Data, step6Data, t }) {
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
        <div style={{ fontSize: '0.6rem', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: 'var(--blue)', marginBottom: '14px' }}>
          {t.h_executive_summary}
        </div>
        <MetricCalloutRow step4Data={step4Data} step6Data={step6Data} t={t} />
        {parsed.executive_summary && (
          <p style={{
            fontFamily: "'DM Sans', sans-serif",
            fontWeight: 400,
            fontSize: '0.9rem',
            lineHeight: 1.8,
            color: 'var(--charcoal)',
            margin: 0,
          }}>
            {parsed.executive_summary}
          </p>
        )}
      </div>

      {/* What Happened + mini chart */}
      <Section header={t.h_what_happened} narrative={parsed.what_happened}>
        <MiniMarginChart step4Data={step4Data} t={t} />
      </Section>

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
  const [parseError, setParseError] = useState(false)
  const [status,     setStatus]     = useState('idle') // idle | connecting | streaming | parsing | done | error
  const [payload,    setPayload]    = useState(null)
  const wsRef = useRef(null)

  const step4Data = appState.stepData[4]?.data ?? {}
  const step6Data = appState.stepData[6]?.data ?? {}
  const step7Data = appState.stepData[7]?.data ?? {}

  const isStreaming     = status === 'connecting' || status === 'streaming'
  const hasFindingsCtx  = !!step6Data.findings?.length

  // Start WebSocket when payload is set
  useEffect(() => {
    if (!payload) return

    setParsedData(null)
    setRawText('')
    setParseError(false)
    setStatus('connecting')

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/llm`)
    wsRef.current = ws
    let accumulated = ''

    ws.onopen = () => {
      setStatus('streaming')
      ws.send(JSON.stringify(payload))
    }

    ws.onmessage = (e) => {
      if (e.data === '[DONE]') {
        setStatus('parsing')
        ws.close()
        const parsed = tryParseJSON(accumulated)
        if (parsed) {
          setParsedData(parsed)
          setParseError(false)
        } else {
          setRawText(accumulated)
          setParseError(true)
        }
        setStatus('done')
        dispatch({
          type: 'SET_STEP_COMPLETE',
          step: 8,
          data: {
            status: 'complete',
            data: { response_text: accumulated, status: 'complete' },
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
      accumulated += e.data
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
      step6_data:     step6Data,
      step7_response: step7Data.response_text ?? '',
      company_name:   appState.companyName ?? 'BRASKEM S.A.',
      language:       appState.language ?? 'en',
    })
  }

  const showRunButton = status === 'idle' || status === 'error'
  const showResults   = status === 'done'

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
              background: hasFindingsCtx ? 'var(--blue)' : 'rgba(11,31,58,0.06)',
              color: hasFindingsCtx ? '#fff' : 'var(--gray)',
              border: 'none',
              cursor: hasFindingsCtx ? 'pointer' : 'not-allowed',
              fontWeight: 600,
              fontSize: '0.9rem',
              fontFamily: "'DM Sans', sans-serif",
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
          background: 'rgba(30,144,255,0.04)',
          border: '1px solid rgba(30,144,255,0.12)',
          borderRadius: '6px',
        }}>
          <div className={styles.running} style={{ fontSize: '0.82rem' }}>
            {status === 'parsing' ? t.parsing_analysis : t.running_message}
          </div>
        </div>
      )}

      {/* Done row */}
      {status === 'done' && !showRunButton && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', fontSize: '0.78rem' }}>
          <span style={{ color: 'var(--blue)', fontFamily: "'JetBrains Mono', monospace" }}>✓ Complete</span>
          {parseError && (
            <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>— {t.fallback_note}</span>
          )}
        </div>
      )}

      {/* Results */}
      {showResults && (
        parsedData
          ? <StructuredBriefing parsed={parsedData} step4Data={step4Data} step6Data={step6Data} t={tMerged} />
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
