import { useEffect, useRef, useState } from 'react'
import { useI18n, useAppState, useAppDispatch } from '../App'
import styles from './Step.module.css'

// ── Context download button ───────────────────────────────────────────────────

function ContextDownloadButton({ t, companyName, lang }) {
  const [loading, setLoading] = useState(false)

  async function handleClick() {
    if (loading) return
    setLoading(true)
    try {
      const params = new URLSearchParams({ company: companyName, lang })
      const res = await fetch(`/api/export/context?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const text = await res.text()
      const cd = res.headers.get('Content-Disposition') || ''
      const match = cd.match(/filename="([^"]+)"/)
      const filename = match ? match[1] : 'cygnus-context.md'
      const blob = new Blob([text], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('[Context export]', err)
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
        marginBottom: '20px',
      }}
      onMouseEnter={(e) => { if (!loading) { e.currentTarget.style.background = 'var(--teal-dim)'; e.currentTarget.style.borderColor = 'var(--teal)' } }}
      onMouseLeave={(e) => { e.currentTarget.style.background = loading ? 'var(--offwhite)' : 'transparent'; e.currentTarget.style.borderColor = 'var(--teal-line)' }}
    >
      <span style={{ fontSize: '0.875rem', fontWeight: 600, color: loading ? 'var(--gray)' : 'var(--teal)', fontFamily: "'IBM Plex Sans', sans-serif" }}>
        {loading ? t.download_context_loading : `↓  ${t.download_context_label}`}
      </span>
      <span style={{ fontSize: '0.72rem', color: 'var(--gray)', fontFamily: "'IBM Plex Sans', sans-serif" }}>
        {t.download_context_sub}
      </span>
    </button>
  )
}

// ── JSON parse helper ─────────────────────────────────────────────────────────

function tryParseJSON(text) {
  if (!text) return null
  const cleaned = text.replace(/^```json\s*$/im, '').replace(/^```\s*$/gim, '').trim()
  try { return JSON.parse(cleaned) } catch (_) {}
  let fixed = ''
  let inStr = false
  for (let i = 0; i < cleaned.length; i++) {
    const ch = cleaned[i]
    if (ch === '\\' && inStr) { fixed += ch + (cleaned[i + 1] ?? ''); i++; continue }
    if (ch === '"') { inStr = !inStr; fixed += ch; continue }
    if (inStr && ch === '\n') { fixed += '\\n'; continue }
    if (inStr && ch === '\r') { fixed += '\\r'; continue }
    fixed += ch
  }
  try { return JSON.parse(fixed) } catch (_) {}
  const fb = cleaned.indexOf('{'), lb = cleaned.lastIndexOf('}')
  if (fb !== -1 && lb > fb) {
    try { return JSON.parse(cleaned.slice(fb, lb + 1)) } catch (_) {}
  }
  return null
}

// ── User question bubble ──────────────────────────────────────────────────────

function UserBubble({ content }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '4px' }}>
      <div style={{
        maxWidth: '78%',
        padding: '10px 14px',
        borderRadius: '16px 16px 4px 16px',
        background: 'var(--teal)',
        color: '#fff',
        fontSize: '0.875rem',
        lineHeight: 1.6,
        wordBreak: 'break-word',
        fontFamily: "'IBM Plex Sans', sans-serif",
      }}>
        <span style={{ whiteSpace: 'pre-wrap' }}>{content}</span>
      </div>
    </div>
  )
}

// ── Loading indicator ─────────────────────────────────────────────────────────

function LoadingIndicator({ t }) {
  return (
    <div style={{
      background: 'var(--offwhite)',
      border: '1px solid rgba(11,31,58,0.07)',
      borderRadius: '8px',
      padding: '16px 18px',
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      color: 'var(--gray)',
      fontSize: '0.84rem',
      fontFamily: "'IBM Plex Sans', sans-serif",
    }}>
      <span style={{ display: 'flex', gap: '4px' }}>
        {[0, 1, 2].map(i => (
          <span key={i} style={{
            width: '6px', height: '6px', borderRadius: '50%',
            background: 'var(--teal)',
            opacity: 0.5,
            animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
          }} />
        ))}
      </span>
      {t?.thinking ?? 'Analysing…'}
    </div>
  )
}

// ── Structured answer card (mirrors Step 8 style) ─────────────────────────────

function AnswerCard({ parsed, rawText, onFollowUp, t }) {
  // If parse failed, show raw text as fallback
  if (!parsed) {
    return (
      <div style={{
        background: 'var(--offwhite)',
        border: '1px solid rgba(11,31,58,0.07)',
        borderRadius: '8px',
        padding: '14px 18px',
        fontSize: '0.875rem',
        lineHeight: 1.7,
        color: 'var(--charcoal)',
        fontFamily: "'IBM Plex Sans', sans-serif",
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
        {rawText}
      </div>
    )
  }

  return (
    <div>
      {/* Answer */}
      <div style={{
        background: 'var(--offwhite)',
        border: '1px solid rgba(11,31,58,0.07)',
        borderRadius: '8px',
        padding: '16px 18px',
        marginBottom: '10px',
      }}>
        <div style={{ fontSize: '0.6rem', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: 'var(--teal)', marginBottom: '8px' }}>
          {t?.answer_label ?? 'Answer'}
        </div>
        <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.8, color: 'var(--charcoal)', fontFamily: "'IBM Plex Sans', sans-serif" }}>
          {parsed.answer}
        </p>
      </div>

      {/* Evidence table */}
      {parsed.evidence?.length > 0 && (
        <div style={{ marginBottom: '10px' }}>
          <div style={{ fontSize: '0.6rem', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: 'var(--teal)', marginBottom: '8px' }}>
            {t?.evidence_label ?? 'Evidence'}
          </div>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t?.col_metric ?? 'Metric'}</th>
                <th>{t?.col_value ?? 'Value'}</th>
                <th>{t?.col_note ?? 'Note'}</th>
              </tr>
            </thead>
            <tbody>
              {parsed.evidence.map((row, i) => (
                <tr key={i}>
                  <td style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.75rem', whiteSpace: 'nowrap' }}>{row.label}</td>
                  <td style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.78rem', whiteSpace: 'nowrap' }}>{row.value}</td>
                  <td style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontWeight: 400 }}>{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Implications */}
      {parsed.implications && (
        <div style={{ marginBottom: '10px' }}>
          <div style={{ fontSize: '0.6rem', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: 'var(--teal)', marginBottom: '6px' }}>
            {t?.implications_label ?? 'Implications'}
          </div>
          <p style={{ margin: 0, fontSize: '0.875rem', lineHeight: 1.7, color: 'var(--charcoal)', fontFamily: "'IBM Plex Sans', sans-serif" }}>
            {parsed.implications}
          </p>
        </div>
      )}

      {/* Internal data needed */}
      {parsed.data_needed && (
        <div style={{
          background: 'rgba(11,31,58,0.03)',
          border: '1px solid rgba(11,31,58,0.07)',
          borderLeft: '3px solid var(--teal-line)',
          borderRadius: '6px',
          padding: '10px 14px',
          marginBottom: '10px',
        }}>
          <div style={{ fontSize: '0.6rem', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: 'var(--gray)', marginBottom: '4px' }}>
            {t?.data_needed_label ?? 'Internal data needed'}
          </div>
          <p style={{ margin: 0, fontSize: '0.84rem', lineHeight: 1.65, color: 'var(--gray)', fontFamily: "'IBM Plex Sans', sans-serif" }}>
            {parsed.data_needed}
          </p>
        </div>
      )}

      {/* Follow-up suggestion */}
      {parsed.follow_up && onFollowUp && (
        <div>
          <div style={{ fontSize: '0.6rem', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.11em', color: 'var(--teal)', marginBottom: '6px' }}>
            {t?.follow_up_label ?? 'Suggested follow-up'}
          </div>
          <button
            onClick={() => onFollowUp(parsed.follow_up)}
            style={{
              padding: '8px 14px',
              borderRadius: '20px',
              border: '1px solid var(--teal-line)',
              background: 'var(--teal-dim)',
              color: 'var(--teal)',
              fontSize: '0.82rem',
              cursor: 'pointer',
              textAlign: 'left',
              lineHeight: 1.4,
              fontFamily: "'IBM Plex Sans', sans-serif",
              transition: 'background 0.15s, border-color 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(14,143,154,0.14)'; e.currentTarget.style.borderColor = 'var(--teal)' }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--teal-dim)'; e.currentTarget.style.borderColor = 'var(--teal-line)' }}
          >
            {parsed.follow_up}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Step9QA({ stepState, data }) {
  const t = useI18n()
  const appState = useAppState()
  const dispatch = useAppDispatch()
  const t9 = t.step9 ?? {}

  // Each entry: { role: 'user'|'assistant', content: string, parsed: object|null }
  const [conversation, setConversation] = useState(() => {
    const saved = data?.data?.conversation ?? []
    return saved.map(m => ({ ...m, parsed: m.role === 'assistant' ? tryParseJSON(m.content) : null }))
  })
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const wsRef = useRef(null)
  const chatRef = useRef(null)

  const hasContext = !!(appState.stepData[6]?.data || appState.stepData[7]?.data)

  // Auto-scroll
  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight
  }, [conversation, isLoading])

  // Prefer company-specific questions from Step 8; fall back to i18n defaults
  const step8Questions = (() => {
    const responseText = appState.stepData[8]?.data?.response_text
    if (!responseText) return null
    try {
      const parsed = typeof responseText === 'string' ? JSON.parse(responseText) : responseText
      const qs = parsed?.suggested_questions
      if (Array.isArray(qs) && qs.length > 0) return qs
    } catch (_) {}
    return null
  })()

  const suggestedQuestions = step8Questions ?? [
    t9.suggested_q1, t9.suggested_q2, t9.suggested_q3, t9.suggested_q4, t9.suggested_q5,
    t9.suggested_q6, t9.suggested_q7,
  ].filter(Boolean)

  // Conversation history sent to the backend: only role + content (raw JSON text)
  function _historyForBackend(conv) {
    return conv.map(m => ({ role: m.role, content: m.content }))
  }

  function sendMessage(message) {
    if (!message.trim() || isLoading) return

    const userEntry = { role: 'user', content: message.trim(), parsed: null }
    setConversation(prev => [...prev, userEntry])
    setInputValue('')
    setIsLoading(true)

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/llm`)
    wsRef.current = ws

    let responseText = ''
    const historySnapshot = _historyForBackend(conversation)

    ws.onopen = () => {
      ws.send(JSON.stringify({
        step: 9,
        message: message.trim(),
        conversation_history: historySnapshot,
        language: appState.language ?? 'en',
        company_name: appState.companyName ?? 'BRASKEM S.A.',
      }))
    }

    ws.onmessage = (e) => {
      if (e.data === '[DONE]') {
        setIsLoading(false)
        const parsed = tryParseJSON(responseText)
        const assistantEntry = { role: 'assistant', content: responseText, parsed }
        setConversation(prev => {
          const updated = [...prev, assistantEntry]
          dispatch({
            type: 'SET_STEP_COMPLETE',
            step: 9,
            data: {
              status: 'complete',
              data: { conversation: updated.map(m => ({ role: m.role, content: m.content })) },
              metadata: { source: 'websocket' },
            },
          })
          return updated
        })
        ws.close()
        return
      }
      if (e.data.startsWith('[ERROR]')) {
        setIsLoading(false)
        setConversation(prev => [...prev, { role: 'assistant', content: '⚠ Connection error — please try again.', parsed: null }])
        ws.close()
        return
      }
      responseText += e.data
    }

    ws.onerror = () => { setIsLoading(false) }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(inputValue) }
  }

  function handleNewConversation() {
    setConversation([])
    setIsLoading(false)
    if (wsRef.current) wsRef.current.close()
    dispatch({ type: 'SET_STEP_ERROR', step: 9 })
  }

  const isEmpty = conversation.length === 0 && !isLoading

  return (
    <div className={styles.wrapper} style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', marginBottom: '4px' }}>
        <h2 className={styles.title} style={{ margin: 0 }}>{t9.title}</h2>
        {conversation.length > 0 && (
          <button
            onClick={handleNewConversation}
            style={{ fontSize: '0.78rem', color: 'var(--gray)', background: 'none', border: '1px solid rgba(11,31,58,0.1)', borderRadius: '6px', padding: '4px 10px', cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
          >
            {t9.new_conversation ?? 'New conversation'}
          </button>
        )}
      </div>
      <p className={styles.description}>{t9.description}</p>

      {/* Context indicator */}
      <div style={{ fontSize: '0.75rem', color: hasContext ? 'var(--teal)' : 'var(--gray)', marginBottom: '12px', fontFamily: "'IBM Plex Mono', monospace" }}>
        {hasContext
          ? `✓ ${t9.ai_context_note ?? 'AI has context from Steps 6 and 7'}`
          : 'Run Steps 6 and 7 first for best results'}
      </div>

      {/* Context download button */}
      {hasContext && (
        <ContextDownloadButton
          t={t9}
          companyName={appState.companyName ?? 'BRASKEM S.A.'}
          lang={appState.language ?? 'en'}
        />
      )}

      {/* Suggested questions — shown when chat is empty */}
      {isEmpty && suggestedQuestions.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <p style={{ fontSize: '0.68rem', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.13em', color: 'var(--teal)', fontFamily: "'IBM Plex Mono', monospace", marginBottom: '10px' }}>
            {t9.suggested_label ?? 'Suggested questions'}
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {suggestedQuestions.map((q, i) => (
              <button
                key={i}
                onClick={() => sendMessage(q)}
                disabled={isLoading}
                style={{
                  padding: '8px 14px',
                  borderRadius: '20px',
                  border: '1px solid var(--teal-line)',
                  background: 'var(--teal-dim)',
                  color: 'var(--teal)',
                  fontSize: '0.82rem',
                  cursor: isLoading ? 'not-allowed' : 'pointer',
                  textAlign: 'left',
                  lineHeight: 1.4,
                  fontFamily: "'IBM Plex Sans', sans-serif",
                  transition: 'background 0.15s, border-color 0.15s',
                }}
                onMouseEnter={(e) => { if (!isLoading) { e.currentTarget.style.background = 'rgba(14,143,154,0.14)'; e.currentTarget.style.borderColor = 'var(--teal)' } }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--teal-dim)'; e.currentTarget.style.borderColor = 'var(--teal-line)' }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Q&A area */}
      {!isEmpty && (
        <div
          ref={chatRef}
          style={{
            marginBottom: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          {conversation.map((msg, i) =>
            msg.role === 'user'
              ? <UserBubble key={i} content={msg.content} />
              : <AnswerCard key={i} parsed={msg.parsed} rawText={msg.content} onFollowUp={sendMessage} t={t9} />
          )}
          {isLoading && <LoadingIndicator t={t9} />}
        </div>
      )}

      {/* Input area */}
      <div style={{
        display: 'flex',
        gap: '8px',
        alignItems: 'flex-end',
        borderTop: isEmpty ? 'none' : '1px solid #f1f5f9',
        paddingTop: isEmpty ? 0 : '16px',
        marginTop: 'auto',
      }}>
        <textarea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder={t9.input_placeholder ?? 'Ask anything about the analysis...'}
          rows={2}
          style={{
            flex: 1,
            padding: '10px 14px',
            borderRadius: '8px',
            border: '1px solid rgba(11,31,58,0.12)',
            fontSize: '0.875rem',
            resize: 'none',
            fontFamily: "'IBM Plex Sans', sans-serif",
            lineHeight: 1.5,
            outline: 'none',
            color: 'var(--charcoal)',
          }}
        />
        <button
          onClick={() => sendMessage(inputValue)}
          disabled={!inputValue.trim() || isLoading}
          style={{
            padding: '10px 18px',
            borderRadius: '8px',
            background: inputValue.trim() && !isLoading ? 'var(--teal)' : 'rgba(11,31,58,0.06)',
            color: inputValue.trim() && !isLoading ? '#fff' : 'var(--gray)',
            border: 'none',
            cursor: inputValue.trim() && !isLoading ? 'pointer' : 'not-allowed',
            fontWeight: 600,
            fontSize: '0.875rem',
            fontFamily: "'IBM Plex Sans', sans-serif",
            alignSelf: 'flex-end',
            height: '42px',
          }}
        >
          →
        </button>
      </div>
    </div>
  )
}
