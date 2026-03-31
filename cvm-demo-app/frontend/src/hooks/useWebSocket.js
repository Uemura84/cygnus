/**
 * useWebSocket — low-level WebSocket hook.
 * Used by LLMStream (Step 9) for token-by-token streaming.
 *
 * Usage:
 *   const { connect, disconnect, messages, status } = useWebSocket('/ws/llm')
 */
import { useState, useRef, useCallback } from 'react'

export function useWebSocket(url) {
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState('idle') // idle | connecting | open | closed | error
  const wsRef = useRef(null)

  const connect = useCallback((onMessage, onDone) => {
    setMessages([])
    setStatus('connecting')

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const fullUrl = `${protocol}://${window.location.host}${url}`
    const ws = new WebSocket(fullUrl)
    wsRef.current = ws

    ws.onopen = () => setStatus('open')
    ws.onmessage = (e) => {
      if (e.data === '[DONE]') {
        setStatus('closed')
        ws.close()
        onDone?.()
        return
      }
      setMessages((prev) => [...prev, e.data])
      onMessage?.(e.data)
    }
    ws.onerror = () => setStatus('error')
    ws.onclose = () => setStatus((s) => s === 'open' ? 'closed' : s)
  }, [url])

  const disconnect = useCallback(() => {
    wsRef.current?.close()
    setStatus('closed')
  }, [])

  const send = useCallback((payload) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof payload === 'string' ? payload : JSON.stringify(payload))
    }
  }, [])

  return { connect, disconnect, send, messages, status }
}
