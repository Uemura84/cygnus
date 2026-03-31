import { useEffect, useRef, useState } from 'react'
import styles from './LLMStream.module.css'

/**
 * Connects to /ws/llm, sends payload, and streams tokens into a text display.
 * Props:
 *   payload   — object to send over WebSocket
 *   onDone    — callback fired when stream completes
 */
export default function LLMStream({ payload, onDone }) {
  const [text, setText] = useState('')
  const [status, setStatus] = useState('idle') // idle | connecting | streaming | done | error
  const wsRef = useRef(null)
  const containerRef = useRef(null)

  useEffect(() => {
    if (!payload) return

    setText('')
    setStatus('connecting')

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/llm`)
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('streaming')
      ws.send(JSON.stringify(payload))
    }

    ws.onmessage = (e) => {
      if (e.data === '[DONE]') {
        setStatus('done')
        ws.close()
        onDone?.()
        return
      }
      if (e.data.startsWith('[ERROR]')) {
        setStatus('error')
        ws.close()
        return
      }
      setText((prev) => prev + e.data)
    }

    ws.onerror = () => setStatus('error')
    ws.onclose = () => {
      if (status === 'streaming') setStatus('done')
    }

    return () => ws.close()
  }, [payload])

  // Auto-scroll to bottom as text grows
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [text])

  return (
    <div className={styles.wrapper}>
      <div className={styles.statusBar}>
        {status === 'connecting' && <span className={styles.connecting}>Connecting…</span>}
        {status === 'streaming' && <span className={styles.streaming}>● Streaming</span>}
        {status === 'done' && <span className={styles.done}>✓ Complete</span>}
        {status === 'error' && <span className={styles.error}>Connection error</span>}
      </div>
      <div ref={containerRef} className={styles.content}>
        {text ? (
          <pre className={styles.text}>{text}</pre>
        ) : (
          <span className={styles.placeholder}>Claude's response will appear here…</span>
        )}
      </div>
    </div>
  )
}
