import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api.js'
import { BarChart, LineChart, DonutChart } from '../components/Charts.jsx'

const PERIODS = [
  { key: 'day', label: 'Last 24h' },
  { key: 'week', label: 'Last 7 days' },
  { key: 'month', label: 'Last 30 days' },
]

const fmt$ = (v) => `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`

export default function AnalyticsPage() {
  const [period, setPeriod] = useState('week')
  const [analytics, setAnalytics] = useState(null)
  const [trend, setTrend] = useState([])
  const [fva, setFva] = useState([])
  const [causes, setCauses] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      const [a, t] = await Promise.all([api.getAnalytics(period), api.getTrends(30)])
      setAnalytics(a)
      setTrend(t.daily || [])
      setFva(t.forecast_vs_actual?.series || [])
      try { setCauses(await api.getCauses()) } catch { setCauses([]) }
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [period])

  if (loading && !analytics) return <div className="card">Loading analytics…</div>
  if (error && !analytics) return <div className="card"><div className="alert alert-error">{error}</div></div>
  if (!analytics) return null

  const { kpis, waste_by_category = [], top_waste_products = [], waste_causes = [] } = analytics
  const causesList = causes.length ? causes : waste_causes
  const causeSegments = causesList.map((c, i) => ({ label: c.cause, value: c.count, color: ['#2563eb', '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0891b2'][i % 6] }))

  return (
    <>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="toolbar">
        <h2 style={{ fontSize: 18 }}>Waste Analytics</h2>
        <div className="spacer" />
        {PERIODS.map((p) => (
          <button key={p.key} className={`btn btn-sm ${period === p.key ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setPeriod(p.key)}>
            {p.label}
          </button>
        ))}
      </div>

      <div className="stat-grid big-stats">
        <div className="stat"><div className="label">Sales</div><div className="value">{kpis.sales}</div></div>
        <div className="stat"><div className="label">Waste Qty</div><div className="value" style={{ color: '#dc2626' }}>{kpis.waste_qty}</div></div>
        <div className="stat"><div className="label">Waste Value</div><div className="value" style={{ color: '#dc2626' }}>{fmt$(kpis.waste_value)}</div></div>
        <div className="stat"><div className="label">Waste %</div><div className="value" style={{ color: '#d97706' }}>{kpis.waste_pct}%</div></div>
        <div className="stat"><div className="label">Donations</div><div className="value" style={{ color: '#16a34a' }}>{kpis.donations}</div></div>
        <div className="stat"><div className="label">Predicted Waste (7d)</div><div className="value">{kpis.predicted_waste}</div></div>
        <div className="stat"><div className="label">Predicted Surplus</div><div className="value">{kpis.predicted_surplus}</div></div>
        <div className="stat"><div className="label">Expiring Items</div><div className="value medium">{kpis.expiring_items}</div></div>
      </div>

      <div className="card">
        <h3>📈 Daily Sales vs Waste (30 days)</h3>
        <BarChart data={trend} xKey="date" series={[{ key: 'sales' }, { key: 'waste' }]} colors={{ sales: '#16a34a', waste: '#dc2626' }} />
        <div className="legend">
          <span><i style={{ background: '#16a34a' }} /> Sales</span>
          <span><i style={{ background: '#dc2626' }} /> Waste</span>
        </div>
      </div>

      <div className="card">
        <h3>🎯 Forecast vs Actual Demand</h3>
        <LineChart data={fva} xKey="date" series={[{ key: 'predicted_demand' }, { key: 'actual_demand' }]} colors={{ predicted_demand: '#2563eb', actual_demand: '#16a34a' }} />
        <div className="legend">
          <span><i style={{ background: '#2563eb' }} /> Predicted demand</span>
          <span><i style={{ background: '#16a34a' }} /> Actual demand</span>
        </div>
      </div>

      <div className="stat-grid two-up">
        <div className="card">
          <h3>🗂️ Waste by Category</h3>
          {waste_by_category.length === 0 ? (
            <div className="empty">No disposal data for this period.</div>
          ) : (
            <BarChart data={waste_by_category} xKey="category" series={[{ key: 'quantity' }]} colors={{ quantity: '#94a3b8' }} />
          )}
        </div>
        <div className="card">
          <h3>🔴 Top Waste Products</h3>
          {top_waste_products.length === 0 ? (
            <div className="empty">No disposal data for this period.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Product</th><th>Qty</th><th>Value</th></tr></thead>
                <tbody>
                  {top_waste_products.map((p, i) => (
                    <tr key={i}>
                      <td><Link to={`/products/${p.item_id}`} className="link">{p.item_name}</Link></td>
                      <td>{p.quantity}</td>
                      <td>{fmt$(p.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="stat-grid two-up">
        <div className="card">
          <h3>🧬 Waste Causes</h3>
          {causesList.length === 0 ? (
            <div className="empty">Not enough history to classify causes.</div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
              <DonutChart segments={causeSegments} centerLabel="Causes" centerValue={causesList.reduce((s, c) => s + c.count, 0)} />
              <div>
                {causesList.map((c) => (
                  <div key={c.cause} className="muted" style={{ marginBottom: 4, textTransform: 'capitalize' }}>{c.cause.replace(/_/g, ' ')} — {c.count}</div>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="card">
          <h3>📊 Period Summary</h3>
          <div className="table-wrap">
            <table>
              <tbody>
                {[
                  ['Total inventory value', kpis.total_value],
                  ['Purchases', kpis.purchases],
                  ['Waste quantity', kpis.waste_qty],
                  ['Donation value', kpis.donation_value],
                  ['High risk items', kpis.high_risk_items],
                  ['Critical risk items', kpis.critical_items],
                ].map(([label, value]) => (
                  <tr key={label}><td className="muted">{label}</td><td style={{ fontWeight: 600 }}>{typeof value === 'number' && label.includes('$') ? fmt$(value) : value}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  )
}