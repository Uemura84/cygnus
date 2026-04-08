import { useEffect, useRef, useState } from 'react'
import { useI18n, useAppState, useAppDispatch } from '../App'
import MarkdownView from '../components/MarkdownView'
import styles from './Step.module.css'

export default function Step8Summary({ stepState, data }) {
  const t = useI18n()
  const appState = useAppState()
  const dispatch = useAppDispatch()

  const [text, setText] = useState('')
  const [status, setStatus] = useState('idle') // idle | connecting | streaming | done | error
  const [payload, setPayload] = useState(null)
  const wsRef = useRef(null)
  const containerRef = useRef(null)

  const step6Data = appState.stepData[6]?.data ?? {}
  const step7Data = appState.stepData[7]?.data ?? {}

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
      setText((prev) => prev + e.data)
    }

    ws.onerror = () => setStatus('error')

    return () => ws.close()
  }, [payload])

  function handleGenerate() {
    setPayload({
      step: 8,
      step6_data: step6Data,
      step7_response: step7Data?.response_text ?? '',
      company_name: appState.companyName ?? 'BRASKEM S.A.',
      language: appState.language ?? 'en',
    })
  }

  const isStreaming = status === 'connecting' || status === 'streaming'
  const hasStep6Context = !!step6Data.findings?.length

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step8.title}</h2>
      <p className={styles.description}>{t.step8.description}</p>

      {/* Generate button */}
      {status === 'idle' || status === 'error' ? (
        <div style={{ marginBottom: '20px' }}>
          <button
            onClick={handleGenerate}
            disabled={!hasStep6Context || isStreaming}
            style={{
              padding: '10px 24px',
              borderRadius: '8px',
              background: hasStep6Context ? 'var(--blue)' : 'rgba(11,31,58,0.06)',
              color: hasStep6Context ? '#fff' : 'var(--gray)',
              border: 'none',
              cursor: hasStep6Context ? 'pointer' : 'not-allowed',
              fontWeight: 600,
              fontSize: '0.9rem',
              fontFamily: "'DM Sans', sans-serif",
            }}
          >
            {t.step8.run_button ?? 'Generate Summary'}
          </button>
          {!hasStep6Context && (
            <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '8px' }}>
              Run Step 6 first to enable summary generation.
            </p>
          )}
          {status === 'error' && (
            <p style={{ fontSize: '0.78rem', color: '#E24B4A', marginTop: '8px' }}>
              {t.error?.connection_error ?? 'Connection error'} — try again.
            </p>
          )}
        </div>
      ) : null}

      {/* Streaming status bar */}
      {status !== 'idle' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', fontSize: '0.8rem' }}>
          {status === 'connecting' && (
            <span style={{ color: '#EF9F27', fontFamily: "'JetBrains Mono', monospace" }}>⏳ {t.step8.running ?? 'Generating executive summary...'}</span>
          )}
          {status === 'streaming' && (
            <span style={{ color: 'var(--blue)', fontFamily: "'JetBrains Mono', monospace" }}>● {t.step8.running ?? 'Generating executive summary...'}</span>
          )}
          {status === 'done' && (
            <span style={{ color: 'var(--blue)', fontFamily: "'JetBrains Mono', monospace" }}>✓ Complete</span>
          )}
        </div>
      )}

      {/* Response area */}
      {(text || stepState === 'complete') && (
        <div
          ref={containerRef}
          style={{
            background: '#fff',
            border: '1px solid rgba(11,31,58,0.07)',
            borderRadius: '6px',
            padding: '28px 32px',
            maxHeight: '600px',
            overflowY: 'auto',
            marginBottom: '16px',
            fontSize: '1rem',
            lineHeight: 1.8,
            color: 'var(--charcoal)',
            fontFamily: "'DM Sans', sans-serif",
          }}
        >
          <MarkdownView text={text || data?.data?.response_text || ''} />
        </div>
      )}

      {/* AI disclaimer */}
      {status === 'done' && (
        <p style={{ fontSize: '0.75rem', color: '#94a3b8', fontStyle: 'italic', borderTop: '1px solid #f1f5f9', paddingTop: '12px' }}>
          {t.step8.ai_disclaimer ?? 'This summary was generated by AI. Domain expert review is recommended.'}
        </p>
      )}
    </div>
  )
}
