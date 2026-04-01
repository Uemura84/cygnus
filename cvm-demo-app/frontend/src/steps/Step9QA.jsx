import { useEffect, useRef, useState } from 'react'
import { useI18n, useAppState, useAppDispatch } from '../App'
import MarkdownView from '../components/MarkdownView'
import styles from './Step.module.css'

export default function Step9QA({ stepState, data }) {
  const t = useI18n()
  const appState = useAppState()
  const dispatch = useAppDispatch()

  // Seed conversation from persisted app state so navigation doesn't lose it
  const [conversation, setConversation] = useState(() => data?.data?.conversation ?? [])
  const [inputValue, setInputValue] = useState('')
  const [streamingText, setStreamingText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const wsRef = useRef(null)
  const chatRef = useRef(null)
  const inputRef = useRef(null)

  const hasContext = !!(appState.stepData[6]?.data || appState.stepData[7]?.data)

  // Auto-scroll chat
  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight
    }
  }, [conversation, streamingText])

  const suggestedQuestions = [
    t.step9?.suggested_q1,
    t.step9?.suggested_q2,
    t.step9?.suggested_q3,
    t.step9?.suggested_q4,
    t.step9?.suggested_q5,
  ].filter(Boolean)

  function sendMessage(message) {
    if (!message.trim() || isStreaming) return

    const userMsg = { role: 'user', content: message.trim() }
    const newConversation = [...conversation, userMsg]
    setConversation(newConversation)
    setInputValue('')
    setStreamingText('')
    setIsStreaming(true)

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/llm`)
    wsRef.current = ws

    let accumulated = ''

    ws.onopen = () => {
      ws.send(JSON.stringify({
        step: 9,
        message: message.trim(),
        conversation_history: conversation,  // history before this message
        language: appState.language ?? 'en',
        company_name: 'BRASKEM S.A.',
      }))
    }

    ws.onmessage = (e) => {
      if (e.data === '[DONE]') {
        setIsStreaming(false)
        setConversation((prev) => {
          const updated = [...prev, { role: 'assistant', content: accumulated }]
          // Persist conversation in app state so navigation doesn't lose it
          dispatch({
            type: 'SET_STEP_COMPLETE',
            step: 9,
            data: {
              status: 'complete',
              data: { conversation: updated },
              metadata: { source: 'websocket' },
            },
          })
          return updated
        })
        setStreamingText('')
        ws.close()
        return
      }
      if (e.data.startsWith('[ERROR]')) {
        setIsStreaming(false)
        setConversation((prev) => [...prev, { role: 'assistant', content: '⚠ Connection error — please try again.' }])
        setStreamingText('')
        ws.close()
        return
      }
      accumulated += e.data
      setStreamingText(accumulated)
    }

    ws.onerror = () => {
      setIsStreaming(false)
      setStreamingText('')
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(inputValue)
    }
  }

  function handleNewConversation() {
    setConversation([])
    setStreamingText('')
    setIsStreaming(false)
    if (wsRef.current) wsRef.current.close()
    dispatch({ type: 'SET_STEP_ERROR', step: 9 })  // reset to pending so sidebar clears
  }

  const isEmpty = conversation.length === 0 && !streamingText

  return (
    <div className={styles.wrapper} style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', marginBottom: '4px' }}>
        <h2 className={styles.title} style={{ margin: 0 }}>{t.step9.title}</h2>
        {conversation.length > 0 && (
          <button
            onClick={handleNewConversation}
            style={{ fontSize: '0.78rem', color: '#64748b', background: 'none', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '4px 10px', cursor: 'pointer' }}
          >
            {t.step9?.new_conversation ?? 'New conversation'}
          </button>
        )}
      </div>
      <p className={styles.description}>{t.step9.description}</p>

      {/* Context indicator */}
      <div style={{ fontSize: '0.75rem', color: hasContext ? '#16a34a' : '#94a3b8', marginBottom: '16px' }}>
        {hasContext
          ? `✓ ${t.step9?.ai_context_note ?? 'AI has context from Steps 6 and 7'}`
          : 'Run Steps 6 and 7 first for best results'}
      </div>

      {/* Suggested questions */}
      {isEmpty && suggestedQuestions.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8', marginBottom: '10px' }}>
            Suggested questions
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {suggestedQuestions.map((q, i) => (
              <button
                key={i}
                onClick={() => sendMessage(q)}
                disabled={isStreaming}
                style={{
                  padding: '8px 14px',
                  borderRadius: '20px',
                  border: '1px solid #cbd5e1',
                  background: '#fff',
                  color: '#334155',
                  fontSize: '0.82rem',
                  cursor: isStreaming ? 'not-allowed' : 'pointer',
                  textAlign: 'left',
                  lineHeight: 1.4,
                  transition: 'border-color 0.15s',
                }}
                onMouseEnter={(e) => { if (!isStreaming) e.currentTarget.style.borderColor = '#2563eb' }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#cbd5e1' }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Chat area */}
      {!isEmpty && (
        <div
          ref={chatRef}
          style={{
            flex: 1,
            overflowY: 'auto',
            minHeight: '260px',
            maxHeight: '420px',
            marginBottom: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          {conversation.map((msg, i) => (
            <ChatBubble key={i} role={msg.role} content={msg.content} />
          ))}
          {streamingText && (
            <ChatBubble role="assistant" content={streamingText} streaming />
          )}
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
          ref={inputRef}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          placeholder={t.step9?.input_placeholder ?? 'Ask anything about the analysis...'}
          rows={2}
          style={{
            flex: 1,
            padding: '10px 14px',
            borderRadius: '8px',
            border: '1px solid #cbd5e1',
            fontSize: '0.875rem',
            resize: 'none',
            fontFamily: 'inherit',
            lineHeight: 1.5,
            outline: 'none',
            color: '#1e293b',
          }}
        />
        <button
          onClick={() => sendMessage(inputValue)}
          disabled={!inputValue.trim() || isStreaming}
          style={{
            padding: '10px 18px',
            borderRadius: '8px',
            background: inputValue.trim() && !isStreaming ? '#2563eb' : '#e2e8f0',
            color: inputValue.trim() && !isStreaming ? '#fff' : '#94a3b8',
            border: 'none',
            cursor: inputValue.trim() && !isStreaming ? 'pointer' : 'not-allowed',
            fontWeight: 700,
            fontSize: '0.875rem',
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

function ChatBubble({ role, content, streaming }) {
  const isUser = role === 'user'
  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
    }}>
      <div style={{
        maxWidth: '82%',
        padding: '10px 14px',
        borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        background: isUser ? '#2563eb' : '#f1f5f9',
        color: isUser ? '#fff' : '#1e293b',
        fontSize: '0.875rem',
        lineHeight: 1.6,
        wordBreak: 'break-word',
      }}>
        {isUser ? (
          <span style={{ whiteSpace: 'pre-wrap' }}>{content}</span>
        ) : (
          <MarkdownView text={content} />
        )}
        {streaming && (
          <span style={{ display: 'inline-block', width: '2px', height: '1em', background: '#475569', marginLeft: '2px', animation: 'blink 1s step-end infinite', verticalAlign: 'text-bottom' }} />
        )}
      </div>
    </div>
  )
}
