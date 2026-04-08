import { useEffect, useRef, useState } from 'react'
import { useI18n, useAppState, useAppDispatch } from '../App'
import MarkdownView from '../components/MarkdownView'
import styles from './Step.module.css'

// ── Confidence badge ──────────────────────────────────────────────────────────

function ConfidenceBadge({ confidence }) {
  const cls =
    confidence === 'HIGH'   ? styles.badgeHigh :
    confidence === 'MEDIUM' ? styles.badgeMedium :
                              styles.badgeLow
  return <span className={cls}>{confidence}</span>
}

// ── Collapsible toggle ────────────────────────────────────────────────────────

function CollapseToggle({ label, labelOpen, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--blue)',
          fontSize: '0.78rem',
          fontWeight: 600,
          fontFamily: "'JetBrains Mono', monospace",
          padding: '4px 0',
          marginTop: '8px',
        }}
      >
        <span style={{ fontSize: '0.65rem', transition: 'transform 0.15s', transform: open ? 'rotate(90deg)' : 'none' }}>▶</span>
        {open ? (labelOpen ?? label) : label}
      </button>
      {open && (
        <div style={{ marginTop: '8px', paddingLeft: '16px', borderLeft: '2px solid rgba(30,144,255,0.15)' }}>
          {children}
        </div>
      )}
    </div>
  )
}

// ── Hypothesis card ───────────────────────────────────────────────────────────

function HypothesisCard({ hyp, t, isTop = false }) {
  return (
    <div style={{
      background: isTop ? 'rgba(30,144,255,0.04)' : '#fff',
      border: `1px solid ${isTop ? 'rgba(30,144,255,0.18)' : 'rgba(11,31,58,0.06)'}`,
      borderRadius: '6px',
      padding: '12px 14px',
      marginBottom: isTop ? '0' : '8px',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px', marginBottom: '6px' }}>
        <span style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--charcoal)', lineHeight: 1.4 }}>
          {hyp.title}
        </span>
        <ConfidenceBadge confidence={hyp.confidence} />
      </div>
      <p style={{ fontSize: '0.83rem', color: 'var(--gray)', lineHeight: 1.65, margin: 0 }}>
        {hyp.explanation}
      </p>
      {hyp.confirmation_data?.length > 0 && (
        <CollapseToggle label={t.show_confirmation} labelOpen={t.hide_confirmation}>
          <ul style={{ margin: 0, padding: '0 0 0 16px', fontSize: '0.8rem', color: 'var(--gray)', lineHeight: 1.7 }}>
            {hyp.confirmation_data.map((src, i) => (
              <li key={i}>{src}</li>
            ))}
          </ul>
        </CollapseToggle>
      )}
    </div>
  )
}

// ── Finding group card ────────────────────────────────────────────────────────

function FindingGroupCard({ group, t }) {
  const hasAdditional = group.additional_hypotheses?.length > 0
  return (
    <div style={{
      background: '#fff',
      border: '1px solid rgba(11,31,58,0.07)',
      borderRadius: '6px',
      padding: '14px 16px',
      marginBottom: '12px',
    }}>
      {/* Group header */}
      <div style={{ marginBottom: '10px' }}>
        <span style={{
          fontSize: '0.68rem',
          fontWeight: 500,
          color: 'var(--blue)',
          fontFamily: "'JetBrains Mono', monospace",
          textTransform: 'uppercase',
          letterSpacing: '0.1em',
          marginRight: '10px',
        }}>
          {group.finding_ids?.join(' · ')}
        </span>
        <span style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--charcoal)' }}>
          {group.group_label}
        </span>
      </div>

      {/* Top hypothesis label */}
      <div style={{
        fontSize: '0.65rem',
        fontWeight: 600,
        color: 'var(--blue)',
        fontFamily: "'JetBrains Mono', monospace",
        textTransform: 'uppercase',
        letterSpacing: '0.12em',
        marginBottom: '6px',
      }}>
        {t.top_hypothesis}
      </div>

      {/* Top hypothesis — always visible */}
      {group.top_hypothesis && (
        <HypothesisCard hyp={group.top_hypothesis} t={t} isTop />
      )}

      {/* Additional hypotheses — collapsed */}
      {hasAdditional && (
        <CollapseToggle
          label={`${t.additional_hypotheses} (${group.additional_hypotheses.length})`}
          labelOpen={t.hide_additional}
        >
          {group.additional_hypotheses.map((hyp, i) => (
            <HypothesisCard key={i} hyp={hyp} t={t} />
          ))}
        </CollapseToggle>
      )}
    </div>
  )
}

// ── Macro context section ─────────────────────────────────────────────────────

function MacroContextSection({ macro, t }) {
  if (!macro) return null
  return (
    <div style={{
      background: '#fff',
      border: '1px solid rgba(11,31,58,0.07)',
      borderRadius: '6px',
      padding: '16px 20px',
      marginBottom: '16px',
    }}>
      <div className={styles.sectionTitle}>{t.macro_context_title}</div>
      <p style={{ fontSize: '0.875rem', color: 'var(--charcoal)', lineHeight: 1.7, margin: 0 }}>
        {macro.summary}
      </p>
      {macro.full_narrative && (
        <CollapseToggle label={t.read_full_macro} labelOpen={t.hide_macro}>
          <div style={{ fontSize: '0.84rem', color: 'var(--gray)', lineHeight: 1.75, whiteSpace: 'pre-line' }}>
            {macro.full_narrative}
          </div>
        </CollapseToggle>
      )}
    </div>
  )
}

// ── Module section ────────────────────────────────────────────────────────────

function ModuleSection({ moduleData, title, t }) {
  if (!moduleData) return null
  const groups = moduleData.finding_groups ?? []
  return (
    <div style={{
      background: 'var(--offwhite)',
      border: '1px solid rgba(11,31,58,0.07)',
      borderRadius: '6px',
      padding: '14px 16px',
      marginBottom: '12px',
    }}>
      <div className={styles.sectionTitle}>{title}</div>
      {moduleData.summary && (
        <p style={{ fontSize: '0.84rem', color: 'var(--gray)', lineHeight: 1.65, marginTop: 0, marginBottom: '14px' }}>
          {moduleData.summary}
        </p>
      )}
      {groups.length === 0 ? (
        <p style={{ fontSize: '0.82rem', color: '#94a3b8', margin: 0, fontStyle: 'italic' }}>{t.no_findings}</p>
      ) : (
        groups.map((group, i) => (
          <FindingGroupCard key={i} group={group} t={t} />
        ))
      )}
    </div>
  )
}

// ── Cross-module section ──────────────────────────────────────────────────────

function CrossModuleSection({ crossData, t }) {
  if (!crossData) return null
  const diagnoses = crossData.diagnoses ?? []
  return (
    <div style={{
      background: '#fff',
      border: '1px solid rgba(226,75,74,0.15)',
      borderLeft: '3px solid #E24B4A',
      borderRadius: '6px',
      padding: '14px 16px',
      marginBottom: '12px',
    }}>
      <div className={styles.sectionTitle}>{t.module_cross}</div>
      {crossData.summary && (
        <p style={{ fontSize: '0.84rem', color: 'var(--charcoal)', lineHeight: 1.65, marginTop: 0, marginBottom: '12px' }}>
          {crossData.summary}
        </p>
      )}
      {diagnoses.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
          {diagnoses.map((dx, i) => (
            <div key={i} style={{
              background: 'rgba(226,75,74,0.04)',
              border: '1px solid rgba(226,75,74,0.12)',
              borderRadius: '5px',
              padding: '10px 12px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <span style={{
                  fontSize: '0.65rem',
                  fontFamily: "'JetBrains Mono', monospace",
                  color: '#E24B4A',
                  fontWeight: 600,
                }}>
                  {dx.id}
                </span>
                <span style={{ fontSize: '0.86rem', fontWeight: 600, color: 'var(--charcoal)' }}>
                  {dx.label}
                </span>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--gray)', lineHeight: 1.65, margin: 0 }}>
                {dx.interpretation}
              </p>
            </div>
          ))}
        </div>
      )}
      {crossData.what_would_change_this && (
        <CollapseToggle label={t.what_would_change}>
          <p style={{ fontSize: '0.82rem', color: 'var(--gray)', lineHeight: 1.65, margin: 0 }}>
            {crossData.what_would_change_this}
          </p>
        </CollapseToggle>
      )}
    </div>
  )
}

// ── Tiered briefing (full parsed render) ─────────────────────────────────────

function TieredBriefing({ parsed, t }) {
  const mods = parsed.modules ?? {}
  return (
    <div>
      <MacroContextSection macro={parsed.macro_context} t={t} />
      <ModuleSection moduleData={mods.profitability}  title={t.module_profitability} t={t} />
      <ModuleSection moduleData={mods.balance_sheet}  title={t.module_balance_sheet} t={t} />
      <ModuleSection moduleData={mods.cash_flow}      title={t.module_cash_flow}     t={t} />
      <CrossModuleSection crossData={mods.cross_module} t={t} />
    </div>
  )
}

// ── JSON parsing (robust) ─────────────────────────────────────────────────────

// Fix literal (unescaped) newlines inside JSON string values.
// Claude sometimes streams actual \n characters inside multi-line fields
// (full_narrative, explanation) rather than the \\n escape sequence,
// making the JSON technically invalid.
function fixLiteralNewlines(str) {
  let out = ''
  let inString = false
  let i = 0
  while (i < str.length) {
    const ch = str[i]
    // Inside a string, a backslash introduces a 2-char escape — pass both through unchanged
    if (ch === '\\' && inString) {
      out += ch + (str[i + 1] ?? '')
      i += 2
      continue
    }
    if (ch === '"') {
      inString = !inString
      out += ch
      i++
      continue
    }
    // Replace literal control characters that are invalid inside JSON strings
    if (inString && ch === '\n') { out += '\\n'; i++; continue }
    if (inString && ch === '\r') { out += '\\r'; i++; continue }
    if (inString && ch === '\t') { out += '\\t'; i++; continue }
    out += ch
    i++
  }
  return out
}

function tryParseJSON(text) {
  if (!text) return null

  // Step 1: strip markdown code fences (multiline flag so ^/$ match line boundaries)
  const cleaned = text
    .replace(/^```json\s*$/im, '')
    .replace(/^```\s*$/gim, '')
    .trim()

  // Step 2: direct parse (works when LLM outputs clean JSON)
  try { return JSON.parse(cleaned) } catch (e1) {
    console.warn('[Step7] Direct parse failed:', e1.message)
    console.log('[Step7] First 200 chars:', cleaned.slice(0, 200))
    console.log('[Step7] Last 200 chars:', cleaned.slice(-200))
  }

  // Step 3: fix literal newlines in strings, then retry
  try { return JSON.parse(fixLiteralNewlines(cleaned)) } catch (e2) {
    console.warn('[Step7] Literal-newline-fixed parse failed:', e2.message)
  }

  // Step 4: extract content between outermost braces, retry both ways
  const firstBrace = cleaned.indexOf('{')
  const lastBrace  = cleaned.lastIndexOf('}')
  if (firstBrace !== -1 && lastBrace > firstBrace) {
    const extracted = cleaned.slice(firstBrace, lastBrace + 1)
    try { return JSON.parse(extracted) } catch (_) {}
    try { return JSON.parse(fixLiteralNewlines(extracted)) } catch (e3) {
      console.warn('[Step7] All parse attempts failed:', e3.message)
      console.log('[Step7] Extracted first 200:', extracted.slice(0, 200))
      console.log('[Step7] Extracted last 200:', extracted.slice(-200))
    }
  }

  return null
}

// ── Staged progress messages ──────────────────────────────────────────────────

const PROGRESS_KEYS = [
  'progress_macro',
  'progress_profitability',
  'progress_balance_sheet',
  'progress_cash_flow',
  'progress_synthesis',
]

function useProgressMessages(t, active) {
  const [idx, setIdx] = useState(0)
  useEffect(() => {
    if (!active) { setIdx(0); return }
    const timer = setInterval(() => setIdx(i => (i + 1) % PROGRESS_KEYS.length), 4000)
    return () => clearInterval(timer)
  }, [active])
  return t[PROGRESS_KEYS[idx]] ?? t.running
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Step7AIAgent({ stepState, data }) {
  const t        = useI18n().step7
  const appState = useAppState()
  const dispatch = useAppDispatch()

  const [rawText,    setRawText]    = useState('')
  const [parsedData, setParsedData] = useState(null)
  const [parseError, setParseError] = useState(false)
  const [status,     setStatus]     = useState('idle') // idle | connecting | streaming | parsing | done | error
  const [payload,    setPayload]    = useState(null)
  const wsRef = useRef(null)

  const isStreaming = status === 'connecting' || status === 'streaming'
  const progressMsg = useProgressMessages(t, isStreaming)

  const step6Data = appState.stepData[6]?.data ?? {}

  // Start streaming when payload is set
  useEffect(() => {
    if (!payload) return

    setRawText('')
    setParsedData(null)
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
          step: 7,
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

  // On mount: if already complete from cache/pipeline_state, try to parse cached response
  useEffect(() => {
    if (stepState === 'complete' && data?.data?.response_text && status === 'idle') {
      const cached = data.data.response_text
      const parsed = tryParseJSON(cached)
      if (parsed) {
        setParsedData(parsed)
      } else {
        setRawText(cached)
        setParseError(true)
      }
      setStatus('done')
    }
  }, [stepState, data])

  function handleConsult() {
    if (!step6Data.findings) return
    setPayload({
      step: 7,
      findings: step6Data.findings ?? [],
      composite_signals: step6Data.composite_signals ?? [],
      risk_score: step6Data.risk_score ?? 0,
      risk_level: step6Data.risk_level ?? 'UNKNOWN',
      finding_categories: step6Data.finding_categories ?? {},
      company_name: appState.companyName ?? 'BRASKEM S.A.',
      date_range: '2020–2025',
      language: appState.language ?? 'en',
    })
  }

  const hasFindingsContext = !!step6Data.findings?.length
  const showConsultButton = status === 'idle' || status === 'error'
  const showResults = status === 'done'

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.title}</h2>
      <p className={styles.description}>{t.description}</p>

      {/* Consult button */}
      {showConsultButton && (
        <div style={{ marginBottom: '20px' }}>
          <button
            onClick={handleConsult}
            disabled={!hasFindingsContext}
            style={{
              padding: '10px 24px',
              borderRadius: '8px',
              background: hasFindingsContext ? 'var(--blue)' : 'rgba(11,31,58,0.06)',
              color: hasFindingsContext ? '#fff' : 'var(--gray)',
              border: 'none',
              cursor: hasFindingsContext ? 'pointer' : 'not-allowed',
              fontWeight: 600,
              fontSize: '0.9rem',
              fontFamily: "'DM Sans', sans-serif",
            }}
          >
            {t.run_button}
          </button>
          {!hasFindingsContext && (
            <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '8px' }}>
              Run Step 6 first to enable AI analysis.
            </p>
          )}
          {status === 'error' && (
            <p style={{ fontSize: '0.78rem', color: '#E24B4A', marginTop: '8px' }}>
              Connection error — try again.
            </p>
          )}
        </div>
      )}

      {/* Streaming / parsing status bar */}
      {(isStreaming || status === 'parsing') && (
        <div style={{
          marginBottom: '20px',
          padding: '12px 16px',
          background: 'rgba(30,144,255,0.04)',
          border: '1px solid rgba(30,144,255,0.12)',
          borderRadius: '6px',
        }}>
          <div className={styles.running} style={{ fontSize: '0.82rem' }}>
            {status === 'parsing' ? t.parsing_analysis : progressMsg}
          </div>
        </div>
      )}

      {/* Done status row */}
      {status === 'done' && !showConsultButton && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', fontSize: '0.78rem' }}>
          <span style={{ color: 'var(--blue)', fontFamily: "'JetBrains Mono', monospace" }}>✓ Complete</span>
          {parseError && (
            <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>— {t.fallback_note}</span>
          )}
        </div>
      )}


      {/* Results */}
      {showResults && (
        <>
          {parsedData ? (
            <TieredBriefing parsed={parsedData} t={t} />
          ) : (
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
          )}

          {/* AI disclaimer */}
          <p style={{
            fontSize: '0.75rem',
            color: '#94a3b8',
            fontStyle: 'italic',
            borderTop: '1px solid #f1f5f9',
            paddingTop: '12px',
            marginTop: '16px',
          }}>
            {t.ai_disclaimer}
          </p>
        </>
      )}
    </div>
  )
}
