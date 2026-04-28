import { useEffect } from 'react'
import RevenueCOGSGrowth from './components/charts/RevenueCOGSGrowth'
import WaterfallChart from './components/charts/WaterfallChart'
import RiskGauge from './components/charts/RiskGauge'
import data from './exportData.json'

function buildWaterfallData(bridge) {
  if (!bridge || bridge.start_value == null) return null
  const fmt = s => s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
  return [
    { name: fmt(bridge.start_label), value: bridge.start_value, type: 'total' },
    ...bridge.factors.map(f => ({ name: fmt(f.name), value: f.value, type: 'change' })),
    { name: fmt(bridge.end_label), value: bridge.end_value, type: 'total' },
  ]
}

function CompanyCharts({ name, step4, step6 }) {
  const ts = step4?.time_series ?? []
  const waterfallData = buildWaterfallData(step4?.margin_bridge)
  const distress = step6?.distress ?? {}
  const score = distress.distress_score ?? step6?.risk_score ?? 0
  const level = distress.band ?? step6?.risk_level ?? ''

  return (
    <>
      <div id={`${name.toLowerCase()}_revenue_cogs`}
           style={{ width: 900, padding: '28px 32px 20px', background: '#fff' }}>
        <h4 style={{ fontSize: 16, fontWeight: 700, color: '#0b1f3a', marginBottom: 12 }}>
          {name} — Revenue vs COGS
        </h4>
        <RevenueCOGSGrowth data={ts} />
      </div>

      <div id={`${name.toLowerCase()}_margin_bridge`}
           style={{ width: 900, padding: '28px 32px 20px', background: '#fff' }}>
        <h4 style={{ fontSize: 16, fontWeight: 700, color: '#0b1f3a', marginBottom: 12 }}>
          {name} — Margin Bridge: Peak → Current
        </h4>
        {waterfallData && <WaterfallChart data={waterfallData} unit="%" height={340} />}
      </div>

      <div id={`${name.toLowerCase()}_distress_gauge`}
           style={{ width: 500, padding: '28px 32px 20px', background: '#fff', textAlign: 'center' }}>
        <h4 style={{ fontSize: 16, fontWeight: 700, color: '#0b1f3a', marginBottom: 12 }}>
          {name} — Distress Score
        </h4>
        <RiskGauge score={score} level={level} />
      </div>
    </>
  )
}

export default function ExportCharts() {
  useEffect(() => {
    setTimeout(() => { document.title = 'CHARTS_READY' }, 1500)
  }, [])

  return (
    <div style={{ background: '#fff', padding: 20 }}>
      <CompanyCharts name="Braskem" step4={data.braskem.step4} step6={data.braskem.step6} />
      <CompanyCharts name="Vale" step4={data.vale.step4} step6={data.vale.step6} />
    </div>
  )
}
