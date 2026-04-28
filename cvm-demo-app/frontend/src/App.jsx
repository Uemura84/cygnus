import { useReducer, createContext, useContext, useEffect, lazy, Suspense } from 'react'
import StepWizard from './components/StepWizard'
const ExportCharts = lazy(() => import('./ExportCharts'))
import en from './i18n/en.json'
import ptBr from './i18n/pt-br.json'

// ---------------------------------------------------------------------------
// i18n context
// ---------------------------------------------------------------------------
export const I18nContext = createContext(null)

export function useI18n() {
  return useContext(I18nContext)
}

// ---------------------------------------------------------------------------
// Pipeline / app state
// ---------------------------------------------------------------------------
const TOTAL_STEPS = 9

const PENDING_STEPS = Object.fromEntries(
  Array.from({ length: TOTAL_STEPS }, (_, i) => [i + 1, 'pending'])
)

const initialState = {
  currentStep: 1,
  stepStates: { ...PENDING_STEPS },
  stepData: {},
  language: 'en',
  cacheMode: false,
  companyName: 'BRASKEM S.A.',
}

function appReducer(state, action) {
  switch (action.type) {
    case 'SET_STEP_RUNNING':
      return {
        ...state,
        stepStates: { ...state.stepStates, [action.step]: 'running' },
      }
    case 'SET_STEP_COMPLETE':
      return {
        ...state,
        stepStates: { ...state.stepStates, [action.step]: 'complete' },
        stepData: { ...state.stepData, [action.step]: action.data },
      }
    case 'SET_STEP_ERROR':
      return {
        ...state,
        stepStates: { ...state.stepStates, [action.step]: 'pending' },
      }
    case 'NAVIGATE_TO_STEP':
      return { ...state, currentStep: action.step }
    case 'TOGGLE_LANGUAGE':
      return { ...state, language: state.language === 'en' ? 'pt-br' : 'en' }
    case 'TOGGLE_CACHE':
      return { ...state, cacheMode: !state.cacheMode }
    case 'SET_COMPANY':
      return { ...state, companyName: action.companyName }
    case 'RESET_PIPELINE':
      return {
        ...state,
        currentStep: 1,
        stepStates: { ...PENDING_STEPS },
        stepData: {},
      }
    default:
      return state
  }
}

export const AppStateContext = createContext(null)
export const AppDispatchContext = createContext(null)

export function useAppState() {
  return useContext(AppStateContext)
}

export function useAppDispatch() {
  return useContext(AppDispatchContext)
}

// ---------------------------------------------------------------------------
// App root
// ---------------------------------------------------------------------------
export default function App() {
  if (window.location.search.includes('export=charts')) {
    return <Suspense fallback={<div>Loading…</div>}><ExportCharts /></Suspense>
  }

  const [state, dispatch] = useReducer(appReducer, initialState)

  // Sync config from backend on mount so UI labels and step data stay in the
  // same language (backend is the source of truth across reloads).
  useEffect(() => {
    fetch('/api/config')
      .then((r) => r.json())
      .then((cfg) => {
        if (cfg.company_name && cfg.company_name !== state.companyName) {
          dispatch({ type: 'SET_COMPANY', companyName: cfg.company_name })
        }
        if (cfg.language && cfg.language !== state.language) {
          dispatch({ type: 'TOGGLE_LANGUAGE' })
        }
        if (typeof cfg.cache_mode === 'boolean' && cfg.cache_mode !== state.cacheMode) {
          dispatch({ type: 'TOGGLE_CACHE' })
        }
      })
      .catch(() => {})
  }, [])

  const strings = state.language === 'en' ? en : ptBr

  return (
    <I18nContext.Provider value={strings}>
      <AppStateContext.Provider value={state}>
        <AppDispatchContext.Provider value={dispatch}>
          <StepWizard />
        </AppDispatchContext.Provider>
      </AppStateContext.Provider>
    </I18nContext.Provider>
  )
}
