/**
 * Step 2 — Data Funnel chart.
 * Shows row counts dropping at each filter stage as a horizontal bar chart.
 * Props: filters — array of { name, value } objects
 */
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const COLORS = ['#0e8f9a', 'rgba(14,143,154,0.7)', 'rgba(14,143,154,0.45)', 'rgba(14,143,154,0.25)']

export default function DataFunnel({ filters }) {
  if (!filters?.length) return null
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={filters} layout="vertical" margin={{ left: 20, right: 24, top: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11 }} />
        <YAxis dataKey="name" type="category" width={160} tick={{ fontSize: 11 }} />
        <Tooltip formatter={(v) => v.toLocaleString()} />
        <Bar dataKey="value" radius={[0, 4, 4, 0]}>
          {filters.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
