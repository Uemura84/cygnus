import { useMemo, useState } from 'react'
import { useI18n, useAppState } from '../App'
import LLMStream from '../components/LLMStream'
import styles from './Step.module.css'

const SEVERITY_BADGE = { HIGH: styles.badgeHigh, MEDIUM: styles.badgeMedium, LOW: styles.badgeLow }

const CATEGORY_BADGE = {
  core:       { bg: '#dbeafe', color: '#1d4ed8', label: 'Core' },
  supporting: { bg: '#dcfce7', color: '#166534', label: 'Supporting' },
  contextual: { bg: '#f1f5f9', color: '#64748b', label: 'Context' },
  anomalies:  { bg: '#fef9c3', color: '#854d0e', label: 'Anomaly' },
}

export default function Step9LLMAnalysis({ stepState, data }) {
  const t = useI18n()
  const appState = useAppState()
  const [selectedFinding, setSelectedFinding] = useState(null)
  const [wsPayload, setWsPayload] = useState(null)

  const findings = appState.stepData[6]?.data?.findings ?? []
  const hypotheses = appState.stepData[7]?.data?.hypotheses ?? []

  // Build finding → category map from step6 finding_categories
  const findingCategory = useMemo(() => {
    const cats = appState.stepData[6]?.data?.finding_categories ?? {}
    const map = {}
    for (const [cat, ids] of Object.entries(cats)) {
      for (const id of ids) map[id] = cat
    }
    return map
  }, [appState.stepData[6]])

  function handleAnalyze() {
    if (!selectedFinding) return
    const base = findings.find((f) => f.id === selectedFinding)
    const macro = appState.stepData[6]?.data?.macro_timeline?.map((m) => m.event) ?? []
    const top3Hypotheses = hypotheses.slice(0, 3)

    setWsPayload({
      finding_id: selectedFinding,
      finding: base,
      company_context: {
        name: 'BRASKEM S.A.',
        sector: 'Petrochemical',
        period: '2020-2025',
      },
      macro_context: macro,
      hypotheses: top3Hypotheses,
      language: appState.language ?? 'en',
    })
  }

  const hypothesisCount = hypotheses.length

  return (
    <div className={styles.wrapper}>
      <h2 className={styles.title}>{t.step9.title}</h2>
      <p className={styles.description}>{t.step9.description}</p>

      {/* Finding selector */}
      {findings.length > 0 && (
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap' }}>
          <select
            value={selectedFinding ?? ''}
            onChange={(e) => { setSelectedFinding(e.target.value); setWsPayload(null) }}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.88rem', minWidth: '280px' }}
          >
            <option value="">{t.step9.select_finding}</option>
            {findings.map((f) => {
              const cat = findingCategory[f.id]
              const catLabel = cat ? ` [${CATEGORY_BADGE[cat]?.label ?? cat}]` : ''
              return (
                <option key={f.id} value={f.id}>{f.id} — {f.pattern}{catLabel}</option>
              )
            })}
          </select>
          <button
            onClick={handleAnalyze}
            disabled={!selectedFinding}
            style={{
              padding: '8px 20px',
              borderRadius: '7px',
              background: selectedFinding ? '#2563eb' : '#e2e8f0',
              color: selectedFinding ? '#fff' : '#94a3b8',
              border: 'none',
              cursor: selectedFinding ? 'pointer' : 'not-allowed',
              fontWeight: 600,
              fontSize: '0.88rem',
            }}
          >
            {t.step9.analyzing}
          </button>
        </div>
      )}

      {/* Hypothesis context indicator */}
      <div style={{ fontSize: '0.78rem', color: hypothesisCount > 0 ? '#166534' : '#94a3b8', marginBottom: '16px' }}>
        {hypothesisCount > 0
          ? t.step9.hypothesis_context.replace('{count}', hypothesisCount)
          : t.step9.no_hypothesis_context}
      </div>

      {/* Split view */}
      {selectedFinding && (
        <div className={styles.splitView}>
          {/* Left: finding card */}
          <div className={styles.section} style={{ overflow: 'auto' }}>
            <h3 className={styles.sectionTitle}>{t.step9.finding_card_title}</h3>
            {(() => {
              const f = findings.find((x) => x.id === selectedFinding)
              if (!f) return null
              const cat = findingCategory[f.id]
              const catStyle = CATEGORY_BADGE[cat]
              return (
                <>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '8px' }}>
                    <strong style={{ fontSize: '0.88rem' }}>{f.pattern}</strong>
                    <span className={SEVERITY_BADGE[f.severity]}>{f.severity}</span>
                    {catStyle && (
                      <span style={{ background: catStyle.bg, color: catStyle.color, borderRadius: '4px', padding: '2px 8px', fontSize: '0.72rem', fontWeight: 700 }}>
                        {catStyle.label}
                      </span>
                    )}
                  </div>
                  <p style={{ fontSize: '0.82rem', color: '#475569', lineHeight: 1.6 }}>{f.description}</p>
                  {f.data_points && (
                    <pre style={{ marginTop: '12px', fontSize: '0.78rem', background: '#f8fafc', padding: '10px', borderRadius: '6px', overflow: 'auto' }}>
                      {JSON.stringify(f.data_points, null, 2)}
                    </pre>
                  )}
                </>
              )
            })()}
          </div>

          {/* Right: LLM stream + expert cue */}
          <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
            <LLMStream payload={wsPayload} />
            {wsPayload && (
              <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid #e2e8f0', fontSize: '0.78rem', color: '#94a3b8', fontStyle: 'italic', textAlign: 'center' }}>
                {t.step9.expert_cue}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
