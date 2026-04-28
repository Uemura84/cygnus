import { useI18n, useAppState, useAppDispatch } from '../App'

export default function RunStepButton({ step }) {
  const t        = useI18n()
  const state    = useAppState()
  const dispatch = useAppDispatch()

  const stepState = state.stepStates[step]
  const isRunning = stepState === 'running'
  const isComplete = stepState === 'complete'

  if (isComplete) return null

  async function handleRun() {
    dispatch({ type: 'SET_STEP_RUNNING', step })
    try {
      const res = await fetch(`/api/step/${step}`, { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      dispatch({ type: 'SET_STEP_COMPLETE', step, data: json })
    } catch (err) {
      console.error('Step failed:', err)
      dispatch({ type: 'SET_STEP_ERROR', step })
    }
  }

  const label = t.run_actions?.[String(step)] ?? t.nav?.run_step ?? 'Run Step'

  return (
    <div style={{ marginBottom: '20px' }}>
      <button
        onClick={handleRun}
        disabled={isRunning}
        style={{
          padding: '10px 24px',
          borderRadius: '8px',
          background: isRunning ? 'rgba(14,143,154,0.5)' : 'var(--teal)',
          color: '#fff',
          border: 'none',
          cursor: isRunning ? 'not-allowed' : 'pointer',
          fontWeight: 600,
          fontSize: '0.9rem',
          fontFamily: "'IBM Plex Sans', sans-serif",
          transition: 'background 0.15s',
        }}
      >
        {isRunning ? (t.nav?.running ?? 'Running…') : label}
      </button>
    </div>
  )
}
