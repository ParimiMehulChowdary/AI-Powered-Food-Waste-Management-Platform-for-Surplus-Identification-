import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api.js'
import { RiskBadge, Risk4Badge, StatusBadge } from '../components/Badge.jsx'
import { BarChart, LineChart, DonutChart } from '../components/Charts.jsx'

export default function DashboardPage() {
  const [summary, setSummary] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)

  async function load() {
    try {
      const [s, a] = await Promise.all([api.getDashboardSummary(), api.getAlerts()])
      setSummary(s)
      setAlerts(a)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function runJob() {
    setRunning(true)
    try {
      await api.runDailyJob()
      setLoading(true)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  async function handleResolveAlert(alertId) {
    try {
      await api.resolveAlert(alertId)
      setAlerts((prev) => prev.filter((a) => a.id !== alertId))
    } catch (e) {
      setError(e.message)
    }
  }

  if (loading) return <div className="card">Loading dashboard...</div>
  if (error && !summary) return <div className="card"><div className="alert alert-error">{error}</div></div>
  if (!summary) return null

  const { kpis, risk_counts, waste_by_category = [], top_waste_products = [], waste_causes = [], trend = [], forecast_vs_actual = [], action_center = {}, forecast_accuracy } = summary

  const riskLabels = { low: 'Low', moderate: 'Moderate', high: 'High', critical: 'Critical' }
  const riskColors = { low: '#16a34a', moderate: '#d97706', high: '#dc2626', critical: '#7f1d1d' }
  const riskSegments = Object.entries(risk_counts).map(([k, v]) => ({ label: k, value: v, color: riskColors[k] }))
  const causeSegments = waste_causes.map((c, i) => ({ label: c.cause, value: c.count, color: ['#2563eb', '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0891b2'][i % 6] }))

  const fmt$ = (v) => `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
  const fmt = (v) => Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })

  return (
    <>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="toolbar">
        <button className="btn btn-primary" onClick={runJob} disabled={running}>
          {running ? 'Running AI job…' : '⚡ Run AI analysis now'}
        </button>
        <span className="muted">
          {forecast_accuracy?.items_evaluated
            ? `Forecast accuracy: ${forecast_accuracy.overall_accuracy}% across ${forecast_accuracy.items_evaluated} product(s)`
            : 'Forecast accuracy starts appearing after a few forecast cycles'}
        </span>
      </div>

      <div className="stat-grid big-stats">
        <div className="stat"><div className="label">Total Items</div><div className="value">{kpis.total_items}</div></div>
        <div className="stat"><div className="label">Inventory Value</div><div className="value">{fmt$(kpis.total_value)}</div></div>
        <div className="stat"><div className="label">Waste Value (7d)</div><div className="value" style={{ color: '#dc2626' }}>{fmt$(kpis.waste_value)}</div></div>
        <div className="stat"><div className="label">Waste Rate</div><div className="value" style={{ color: kpis.waste_pct > 20 ? '#dc2626' : kpis.waste_pct > 8 ? '#d97706' : '#16a34a' }}>{kpis.waste_pct}%</div></div>
        <div className="stat"><div className="label">Predicted Waste (7d)</div><div className="value" style={{ color: kpis.predicted_waste > 0 ? '#d97706' : '#16a34a' }}>{fmt(kpis.predicted_waste)}</div></div>
        <div className="stat"><div className="label">Predicted Surplus</div><div className="value">{fmt(kpis.predicted_surplus)}</div></div>
        <div className="stat"><div className="label">High Risk Items</div><div className="value high">{kpis.high_risk_items}</div></div>
        <div className="stat"><div className="label">Est. Savings</div><div className="value" style={{ color: '#16a34a' }}>{fmt$(kpis.estimated_savings)}</div></div>
        <div className="stat"><div className="label">Notifications</div><div className="value"><Link to="/notifications" title="View notifications">{kpis.unread_notifications}</Link></div></div>
      </div>

      <div className="card">
        <h3>🧭 Action Center</h3>
        <div className="split-grid">
          <div className="split-col">
            <h4 style={{ fontSize: 13, color: '#374151', marginBottom: 8 }}>Critical Risk Items</h4>
            {action_center.critical_items?.length === 0 ? (
              <div className="empty">No critical risk items.</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Item</th><th>Qty</th><th>Risk</th><th>Days left</th></tr></thead>
                  <tbody>
                    {action_center.critical_items?.map((it) => (
                      <tr key={it.id}>
                        <td><Link to={`/products/${it.id}`} className="link">{it.name}</Link></td>
                        <td>{it.quantity}</td>
                        <td><Risk4Badge level={it.risk_level} /></td>
                        <td><span className={it.days_to_expiry < 0 ? 'high' : 'medium'}>{it.days_to_expiry ?? '—'}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <h4 style={{ fontSize: 13, color: '#374151', margin: '16px 0 8px' }}>Surplus Allocations</h4>
            {action_center.surplus_allocations?.length === 0 ? (
              <div className="empty">No pending surplus allocations.</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Item</th><th>Qty</th><th>Type</th><th>Partner</th></tr></thead>
                  <tbody>
                    {action_center.surplus_allocations?.map((s) => (
                      <tr key={s.id}>
                        <td>{s.item_name}</td>
                        <td>{s.surplus_quantity}</td>
                        <td><StatusBadge status={s.allocation_type} /></td>
                        <td>{s.suggested_partner || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="split-col">
            <h4 style={{ fontSize: 13, color: '#374151', marginBottom: 8 }}>Upcoming / Past Expiry</h4>
            {action_center.upcoming_expiries?.length === 0 ? (
              <div className="empty">Nothing expiring soon.</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Item</th><th>Qty</th><th>Days</th></tr></thead>
                  <tbody>
                    {action_center.upcoming_expiries?.map((it) => (
                      <tr key={`${it.id}-${it.status}`}>
                        <td><Link to={`/products/${it.id}`} className="link">{it.name}</Link></td>
                        <td>{it.quantity}</td>
                        <td><span className={it.status === 'expired' ? 'high' : 'medium'}>{it.days_to_expiry}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <h4 style={{ fontSize: 13, color: '#374151', margin: '16px 0 8px' }}>Detected Anomalies</h4>
            {action_center.anomalies?.length === 0 ? (
              <div className="empty">No anomalies detected.</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Item</th><th>Type</th><th>Severity</th></tr></thead>
                  <tbody>
                    {action_center.anomalies?.map((a) => (
                      <tr key={a.id}>
                        <td>{a.item_name || 'All items'}</td>
                        <td className="muted">{a.anomaly_type.replace(/_/g, ' ')}</td>
                        <td><Risk4Badge level={a.severity} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {alerts.length > 0 && (
        <div className="card" style={{ borderLeft: '4px solid #d97706' }}>
          <h3>🔔 Active Waste Alerts</h3>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Item</th><th>Days to Expiry</th><th>Risk</th><th>Message</th><th>Action</th></tr></thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id}>
                    <td>{a.item_name}</td>
                    <td><span className={a.days_to_expiry < 0 ? 'high' : 'medium'}>{a.days_to_expiry}</span></td>
                    <td><RiskBadge level={a.risk_score >= 70 ? 'high' : a.risk_score >= 40 ? 'medium' : 'low'} /></td>
                    <td style={{ fontSize: '12px', color: '#374151', maxWidth: '300px' }}>{a.message}</td>
                    <td><button className="btn btn-secondary btn-sm" onClick={() => handleResolveAlert(a.id)}>Dismiss</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="card">
        <h3>✅ Top Recommendations</h3>
        {action_center.recommendations?.length === 0 ? (
          <div className="empty">No open recommendations.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Item</th><th>Action</th><th>Qty</th><th>Priority</th><th>Expected Benefit</th></tr></thead>
              <tbody>
                {action_center.recommendations?.slice(0, 8).map((r) => (
                  <tr key={r.id}>
                    <td><Link to={`/products/${r.item_id}`} className="link">{r.item_name}</Link></td>
                    <td className="muted">{r.recommendation_type.replace(/_/g, ' ')}</td>
                    <td>{r.recommended_quantity}</td>
                    <td>{'★'.repeat(Math.min(r.priority, 5))}</td>
                    <td>{fmt$(r.expected_benefit)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>
          💡 Suggested discounts: {(action_center.recommended_discounts || []).map((d) => `${d.item_name} (${d.quantity})`).join(', ') || 'none'} ·
          🥫 Donate: {(action_center.recommended_donations || []).map((d) => `${d.item_name} (${d.quantity})`).join(', ') || 'none'}
        </p>
      </div>

      <div className="card">
        <h3>📈 30-Day Trend</h3>
        <BarChart data={trend} xKey="date" series={[{ key: 'sales', label: 'Sales' }, { key: 'waste', label: 'Waste' }]} colors={{ sales: '#16a34a', waste: '#dc2626' }} />
        <div className="legend">
          <span><i style={{ background: '#16a34a' }} /> Sales</span>
          <span><i style={{ background: '#dc2626' }} /> Waste</span>
        </div>
      </div>

      <div className="card">
        <h3>🎯 Forecast vs Actual</h3>
        <LineChart data={forecast_vs_actual} xKey="date" series={[{ key: 'predicted_demand', label: 'Predicted demand' }, { key: 'actual_demand', label: 'Actual demand' }]} colors={{ predicted_demand: '#2563eb', actual_demand: '#16a34a' }} />
        <div className="legend">
          <span><i style={{ background: '#2563eb' }} /> Predicted</span>
          <span><i style={{ background: '#16a34a' }} /> Actual</span>
        </div>
      </div>

      <div className="stat-grid two-up">
        <div className="card">
          <h3>🗂️ Waste by Category</h3>
          {waste_by_category.length === 0 ? (
            <div className="empty">No disposal data yet.</div>
          ) : (
            <BarChart data={waste_by_category} xKey="category" series={[{ key: 'quantity', label: 'Waste' }]} colors={{ quantity: '#94a3b8' }} />
          )}
        </div>
        <div className="card">
          <h3>🔴 Top Waste Products</h3>
          {top_waste_products.length === 0 ? (
            <div className="empty">No disposal data yet.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Product</th><th>Qty</th><th>Value</th></tr></thead>
                <tbody>
                  {top_waste_products.map((p, i) => (
                    <tr key={i}>
                      <td className="muted">{p.item_name}</td>
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
          <h3>🚦 Risk Distribution</h3>
          {riskSegments.every((s) => s.value === 0) ? (
            <div className="empty">No risk data yet — run the AI job.</div>
          ) : (
            <div style={{ textAlign: 'center' }}>
              <DonutChart segments={riskSegments} centerLabel="Items" centerValue={riskSegments.reduce((s, x) => s + x.value, 0)} />
              <div className="legend">
                {Object.entries(riskLabels).map(([k, label]) => (
                  <span key={k}><i style={{ background: riskColors[k] }} /> {label} ({risk_counts[k]})</span>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="card">
          <h3>🧬 Waste Causes</h3>
          {waste_causes.length === 0 ? (
            <div className="empty">Not enough history to classify causes.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Cause</th><th>Occurrences</th></tr></thead>
                <tbody>
                  {waste_causes.map((c, i) => (
                    <tr key={i}><td className="muted">{c.cause.replace(/_/g, ' ')}</td><td>{c.count}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  )
}