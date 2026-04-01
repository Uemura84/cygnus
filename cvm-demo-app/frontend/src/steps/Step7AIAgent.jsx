import { useEffect, useRef, useState } from 'react'
import { useI18n, useAppState, useAppDispatch } from '../App'
import MarkdownView from '../components/MarkdownView'
import styles from './Step.module.css'

export default function Step7AIAgent({ stepState, data }) {
  const t = useI18n()
  const appState = useAppState()
  const dispatch = useAppDispatch()

  const [text, setText] = useState('')
  const [status, setStatus] = useState('idle') // idle | connecting | streaming | done | error
  const [payload, setPayload] = useState(null)
  const wsRef = useRef(null)
  const containerRef = useRef(null)

  // Build payload from step 6 state
  const step6Data = appState.stepData[6]?.data ?? {}

  // Auto-scroll as text grows
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [text])

  // Start streaming when payload is set
  useEffect(() => {
    if (!payload) return

    setText('')
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
        setStatus('done')
        ws.close()
        // Mark step 7 complete in frontend state
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
      setText((prev) => prev + e.data)
    }

    ws.onerror = () => setStatus('error')

    return () => ws.close()
  }, [payload])

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

  const isStreaming = status === 'connecting' || status === 'streaming'
  const hasFindingsContext = !!step6Data.findings?.length

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step7.title}</h2>
      <p className={styles.description}>{t.step7.description}</p>

      {/* Consult button */}
      {status === 'idle' || status === 'error' ? (
        <div style={{ marginBottom: '20px' }}>
          <button
            onClick={handleConsult}
            disabled={!hasFindingsContext || isStreaming}
            style={{
              padding: '10px 24px',
              borderRadius: '8px',
              background: hasFindingsContext ? '#2563eb' : '#e2e8f0',
              color: hasFindingsContext ? '#fff' : '#94a3b8',
              border: 'none',
              cursor: hasFindingsContext ? 'pointer' : 'not-allowed',
              fontWeight: 700,
              fontSize: '0.9rem',
            }}
          >
            {t.step7.run_button ?? 'Consult AI Agent'}
          </button>
          {!hasFindingsContext && (
            <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '8px' }}>
              Run Step 6 first to enable AI analysis.
            </p>
          )}
          {status === 'error' && (
            <p style={{ fontSize: '0.78rem', color: '#dc2626', marginTop: '8px' }}>
              {t.error?.connection_error ?? 'Connection error'} — try again.
            </p>
          )}
        </div>
      ) : null}

      {/* Streaming status bar */}
      {status !== 'idle' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', fontSize: '0.8rem' }}>
          {status === 'connecting' && (
            <span style={{ color: '#f59e0b' }}>⏳ {t.step7.running ?? 'Consulting AI Industry Specialist...'}</span>
          )}
          {status === 'streaming' && (
            <span style={{ color: '#2563eb' }}>● {t.step7.running ?? 'Consulting AI Industry Specialist...'}</span>
          )}
          {status === 'done' && (
            <span style={{ color: '#16a34a' }}>✓ Complete</span>
          )}
        </div>
      )}

      {/* Response area */}
      {(text || stepState === 'complete') && (
        <div
          ref={containerRef}
          style={{
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            padding: '16px 20px',
            maxHeight: '520px',
            overflowY: 'auto',
            marginBottom: '16px',
            fontSize: '0.875rem',
            lineHeight: 1.7,
            color: '#1e293b',
          }}
        >
          <MarkdownView text={text || data?.data?.response_text || ''} />
        </div>
      )}

      {/* AI disclaimer */}
      {status === 'done' && (
        <p style={{ fontSize: '0.75rem', color: '#94a3b8', fontStyle: 'italic', borderTop: '1px solid #f1f5f9', paddingTop: '12px' }}>
          {t.step7.ai_disclaimer ?? 'This analysis was generated by AI. Domain expert review is recommended.'}
        </p>
      )}
    </div>
  )
}

