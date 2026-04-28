import { useState } from 'react'

const DX_LABELS = {
  'DX-1': 'Financial Distress Risk',
  'DX-2': 'Working Capital Trap',
  'DX-3': 'Low Quality Growth',
  'DX-4': 'Confirmed Recovery',
  'DX-5': 'Refinancing Cliff',
}

export default function Step7TransparencyPanel({ transparency, t }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [activeTab, setActiveTab]   = useState('reasoning')

  if (!transparency) return null

  const re = transparency.reasoning_engine ?? {}
  const calls = transparency.llm_calls ?? []

  return (
    <div style={{ marginTop: 24 }}>
      {/* ── Toggle ── */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 12,
          color: '#4a5568',
          padding: '6px 0',
        }}
      >
        {isExpanded ? '\u25BC' : '\u25B6'}{' '}
        {isExpanded ? t.transparency_hide : t.transparency_show}
      </button>

      {/* ── Expanded Panel ── */}
      <div
        style={{
          display: isExpanded ? 'block' : 'none',
        }}
      >
        <div
          style={{
            background: '#f5f7fa',
            border: '1px solid rgba(11,31,58,0.07)',
            borderRadius: 6,
            marginTop: 8,
            padding: 16,
          }}
        >
          {/* ── Tab Bar ── */}
          <div
            style={{
              display: 'flex',
              gap: 20,
              borderBottom: '1px solid rgba(11,31,58,0.07)',
              marginBottom: 16,
              paddingBottom: 8,
            }}
          >
            <TabButton
              active={activeTab === 'reasoning'}
              onClick={() => setActiveTab('reasoning')}
              label={t.tab_reasoning}
            />
            <TabButton
              active={activeTab === 'prompt'}
              onClick={() => setActiveTab('prompt')}
              label={t.tab_prompt}
            />
          </div>

          {/* ── Tab Content ── */}
          {activeTab === 'reasoning' ? (
            <ReasoningTab re={re} t={t} />
          ) : (
            <PromptTab calls={calls} t={t} />
          )}
        </div>
      </div>
    </div>
  )
}

function TabButton({ active, onClick, label }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: 'none',
        border: 'none',
        borderBottom: active ? '2px solid #0e8f9a' : '2px solid transparent',
        cursor: 'pointer',
        fontFamily: "'IBM Plex Sans', sans-serif",
        fontWeight: 400,
        fontSize: 13,
        color: active ? '#0e8f9a' : '#4a5568',
        padding: '4px 0',
      }}
    >
      {label}
    </button>
  )
}

// ── Reasoning Engine Tab ──────────────────────────────────────────────────

function ReasoningTab({ re, t }) {
  const chains = re.evidence_chains ?? []
  const explanations = re.ranked_explanations ?? []
  const unmatched = re.unmatched_findings ?? []

  return (
    <div style={{ fontSize: 13, color: '#4a5568' }}>
      {/* Evidence Chains */}
      <SectionLabel text={t.evidence_chains} />
      {chains.length === 0 ? (
        <p style={S.muted}>No evidence chains built.</p>
      ) : (
        chains.map((ch, i) => <ChainCard key={i} chain={ch} t={t} />)
      )}

      {/* Ranked Explanations */}
      <SectionLabel text={t.ranked_explanations} style={{ marginTop: 20 }} />
      {explanations.length === 0 ? (
        <p style={S.muted}>No ranked explanations.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>Rank</th>
                <th style={S.th}>Diagnosis</th>
                <th style={S.th}>Relationship</th>
                <th style={S.th}>Score</th>
                <th style={S.th}>{t.driver} &rarr; {t.outcome}</th>
              </tr>
            </thead>
            <tbody>
              {explanations.map((exp, i) => (
                <tr key={i}>
                  <td style={S.td}>
                    <span style={{
                      ...S.mono,
                      color: exp.rank === 'primary' || exp.rank === 'co-primary'
                        ? '#0e8f9a' : '#4a5568',
                      fontWeight: exp.rank === 'primary' ? 600 : 400,
                    }}>
                      {exp.rank}
                    </span>
                  </td>
                  <td style={S.td}>{exp.diagnosis}</td>
                  <td style={{ ...S.td, ...S.mono }}>{exp.relationship || '—'}</td>
                  <td style={{ ...S.td, ...S.mono }}>{exp.score}</td>
                  <td style={{ ...S.td, ...S.mono, fontSize: 11 }}>
                    {(exp.primary_driver_concepts ?? []).join(', ') || '—'}
                    {' \u2192 '}
                    {(exp.affected_concepts ?? []).join(', ') || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Unmatched Findings */}
      <SectionLabel text={t.unmatched} style={{ marginTop: 20 }} />
      {unmatched.length === 0 ? (
        <p style={S.muted}>{t.all_matched}</p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 18, listStyle: 'none' }}>
          {unmatched.map((fid, i) => (
            <li key={i} style={{ ...S.mono, fontSize: 12, lineHeight: 1.8 }}>{fid}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ChainCard({ chain, t }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontFamily: "'IBM Plex Sans', sans-serif", fontWeight: 600, fontSize: 13, marginBottom: 4 }}>
        {chain.diagnosis} — {DX_LABELS[chain.diagnosis] ?? ''}
      </div>
      <div style={{ ...S.mono, fontSize: 12, marginBottom: 8, color: '#4a5568' }}>
        {t.concept_path}: {(chain.concept_path ?? []).join(' \u2192 ')}
      </div>

      {(chain.steps ?? []).map((step, i) => (
        <div
          key={i}
          style={{
            borderLeft: '2px solid rgba(14,143,154,0.20)',
            paddingLeft: 12,
            marginLeft: 8,
            marginBottom: 8,
          }}
        >
          <div style={{ ...S.mono, fontSize: 12, fontWeight: 500, color: '#2b2b2b' }}>
            Step {i + 1}: {step.relationship}
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.5, marginTop: 2 }}>
            <span style={{ color: '#4a5568' }}>{t.mechanism}: </span>
            {step.mechanism}
          </div>
          {step.specificity && (
            <div style={{ fontSize: 13, lineHeight: 1.5 }}>
              <span style={{ color: '#4a5568' }}>{t.specificity}: </span>
              {step.specificity}
            </div>
          )}
          <div style={{ ...S.mono, fontSize: 11, marginTop: 2, color: '#4a5568' }}>
            {t.findings_label}: {(step.supporting_findings ?? []).join(', ')}
            {'  |  '}
            {t.driver}: {(step.driver_concepts ?? []).join(', ')}
            {' \u2192 '}
            {t.outcome}: {(step.outcome_concepts ?? []).join(', ')}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── LLM Prompt Tab ────────────────────────────────────────────────────────

function PromptTab({ calls, t }) {
  if (calls.length === 0) {
    return <p style={S.muted}>No LLM call data available.</p>
  }

  return (
    <div>
      {calls.map((call, i) => (
        <div key={i} style={{ marginBottom: 24 }}>
          <SectionLabel text={`Call ${i + 1}: ${call.name}`} />

          <div style={{ marginBottom: 8 }}>
            <div style={{ ...S.mono, fontSize: 11, color: '#4a5568', marginBottom: 4 }}>
              {t.system_prompt}:
            </div>
            <pre style={S.codeBlock}>{call.system_prompt}</pre>
          </div>

          <div>
            <div style={{ ...S.mono, fontSize: 11, color: '#4a5568', marginBottom: 4 }}>
              {t.user_message}:
            </div>
            <pre style={S.codeBlock}>{call.user_message}</pre>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Shared ────────────────────────────────────────────────────────────────

function SectionLabel({ text, style = {} }) {
  return (
    <div
      style={{
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 11,
        fontWeight: 500,
        textTransform: 'uppercase',
        letterSpacing: '0.12em',
        color: '#0e8f9a',
        marginBottom: 8,
        ...style,
      }}
    >
      {text}
    </div>
  )
}

const S = {
  mono: {
    fontFamily: "'IBM Plex Mono', monospace",
  },
  muted: {
    fontSize: 13,
    color: '#94a3b8',
    fontStyle: 'italic',
    margin: '4px 0',
  },
  codeBlock: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 12,
    lineHeight: 1.5,
    background: 'rgba(11,31,58,0.03)',
    border: '1px solid rgba(11,31,58,0.07)',
    borderRadius: 4,
    padding: 12,
    maxHeight: 400,
    overflowY: 'auto',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    margin: 0,
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 12,
  },
  th: {
    textAlign: 'left',
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 11,
    fontWeight: 500,
    color: '#4a5568',
    borderBottom: '1px solid rgba(11,31,58,0.10)',
    padding: '4px 8px',
  },
  td: {
    padding: '4px 8px',
    borderBottom: '1px solid rgba(11,31,58,0.05)',
    verticalAlign: 'top',
  },
}
