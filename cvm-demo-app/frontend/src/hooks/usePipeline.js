/**
 * usePipeline — convenience hook for triggering a pipeline step via REST.
 *
 * Usage:
 *   const { runStep, loading, error } = usePipeline()
 *   await runStep(3)
 */
import { useState, useCallback } from 'react'
import { useAppDispatch } from '../App'

export function usePipeline() {
  const dispatch = useAppDispatch()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const runStep = useCallback(async (stepNumber) => {
    setLoading(true)
    setError(null)
    dispatch({ type: 'SET_STEP_RUNNING', step: stepNumber })
    try {
      const res = await fetch(`/api/step/${stepNumber}`, { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      dispatch({ type: 'SET_STEP_COMPLETE', step: stepNumber, data })
      return data
    } catch (err) {
      setError(err.message)
      dispatch({ type: 'SET_STEP_ERROR', step: stepNumber })
      throw err
    } finally {
      setLoading(false)
    }
  }, [dispatch])

  return { runStep, loading, error }
}
