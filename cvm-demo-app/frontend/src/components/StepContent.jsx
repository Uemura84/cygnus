import { useAppState } from '../App'
import Step1Download from '../steps/Step1Download'
import Step2Preparation from '../steps/Step2Preparation'
import Step3Transformation from '../steps/Step3Transformation'
import Step4EBITDADrivers from '../steps/Step4EBITDADrivers'
import Step5QualityScan from '../steps/Step5QualityScan'
import Step6CoreAnalysis from '../steps/Step6CoreAnalysis'
import Step7Hypotheses from '../steps/Step7Hypotheses'
import Step8Summary from '../steps/Step8Summary'
import Step9LLMAnalysis from '../steps/Step9LLMAnalysis'

const STEP_COMPONENTS = {
  1: Step1Download,
  2: Step2Preparation,
  3: Step3Transformation,
  4: Step4EBITDADrivers,
  5: Step5QualityScan,
  6: Step6CoreAnalysis,
  7: Step7Hypotheses,
  8: Step8Summary,
  9: Step9LLMAnalysis,
}

export default function StepContent() {
  const state = useAppState()
  const StepComponent = STEP_COMPONENTS[state.currentStep]
  const stepState = state.stepStates[state.currentStep]
  const stepData = state.stepData[state.currentStep] ?? null

  if (!StepComponent) return null
  return <StepComponent stepState={stepState} data={stepData} />
}
