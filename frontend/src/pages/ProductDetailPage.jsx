import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../services/api.js'
import { Risk4Badge } from '../components/Badge.jsx'
import { LineChart, BarChart } from '../components/Charts.jsx'

const fmt$ = (v) => `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
const TYPE_LABEL = {
  reduce_next_purchase: 'Reduce next purchase',
  stop_reorder: 'Stop reorder',
  transfer_stock: 'Transfer stock',
  donate_surplus: 'Donate surplus',
  prioritize_sale: 'Prioritize sale',
  relocate_high_visibility: 'Move to high visibility',
  adjust_storage: 'Adjust storage',
  process_before_expiry: 'Process before expiry',
  mark_for_disposal: 'Mark for disposal',
}

export default function ProductDetailPage() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      setData(await api.getProductRisk(id))
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  async function applyRec(recId, status) {
    try {
      await api.updateRecommendation(recId, status)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  if (loading) return <div className="card">Loading product analysis…</div>
  if (error) return <div className="card"><div className="alert alert-error">{error}</div></div>
  if (!data) return null

  const { product, risk, forecast, recommendations = [], anomalies = [], reorder, forecast_accuracy, historical_sales = [], historical_waste = [] } = data
  const fc = forecast?.forecast || []

  const accuracy = forecast_accuracy?.demand
  const history = historical_sales.map((d) => ({ ...d, sales: d.quantity }))
  const wastSeries = historical_waste.map((d) => ({ ...d, waste: d.quantity }))
  const days = new Set([...historical_sales.map((d) => d.date), ...historical_waste.map((d) => d.date)])
  const combined = [...days].sort().map((date) => ({
    date,
    sales: historical_sales.find((d) => d.date === date)?.quantity || 0,
    waste: historical_waste.find((d) => d.date === date)?.quantity || 0,
  }))

  return (
    <>
      <Link to="/inventory" className="muted" style={{ fontSize: 13 }}>← Back to inventory</Link>

      <div className="stat-grid big-stats">
        <div className="stat" style={{ gridColumn: 'span 2' }}>
          <div className="label">Product</div>
          <div className="value" style={{ fontSize: 22 }}>{product.name}</div>
          <div className="muted" style={{ marginTop: 6 }}>
            {product.category_name || 'Uncategorized'} · {product.sku ? `SKU ${product.sku} · ` : ''}
            {product.supplier ? `supplier ${product.supplier} · ` : ''}
            {product.storage_requirement ? `${product.storage_requirement} storage` : ''}
          </div>
        </div>
        <div className="stat"><div className="label">Stock</div><div className="value">{product.quantity} {product.unit}</div></div>
        <div className="stat"><div className="label">Days to Expiry</div><div className="value" style={{ color: product.days_to_expiry !== null && product.days_to_expiry <= 0 ? '#dc2626' : product.days_to_expiry !== null && product.days_to_expiry <= 7 ? '#d97706' : '#16a34a' }}>{product.days_to_expiry ?? '—'}</div></div>
        <div className="stat"><div className="label">Unit Cost</div><div className="value">{fmt$(product.cost_per_unit)}</div></div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="stat-grid two-up">
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0 }}>⚠️ Risk Score</h3>
            <Risk4Badge level={risk.risk_level} />
          </div>
          <div style={{ fontSize: 40, fontWeight: 800, margin: '12px 0 6px' }}>
            {risk.risk_score}
            <span className="muted" style={{ fontSize: 14, fontWeight: 400 }}> / 100</span>
          </div>
          <div className="risk-bar" style={{ height: 10 }}>
            <div style={{ width: `${Math.min(risk.risk_score, 100)}%`, background: risk.risk_level === 'critical' ? '#7f1d1d' : risk.risk_level === 'high' ? '#dc2626' : risk.risk_level === 'moderate' ? '#d97706' : '#16a34a', height: '100%' }} />
          </div>
          <p style={{ fontSize: 13, color: '#374151', marginTop: 12 }}>{risk.explanation}</p>
          <div style={{ marginTop: 12 }}>
            {(risk.factors || []).map((f) => (
              <div key={f.factor} style={{ display: 'flex', gap: 8, padding: '6px 0', borderBottom: '1px solid #e5e7eb', fontSize: 13 }}>
                <span className="muted" style={{ width: 130, flexShrink: 0 }}>{f.factor.replace(/_/g, ' ')}</span>
                <strong>{f.value}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h3>📦 Reorder Recommendation</h3>
          <div style={{ fontSize: 26, fontWeight: 700, margin: '8px 0' }}>
            {reorder.recommended_quantity > 0 ? `${reorder.recommended_quantity} ${product.unit}` : 'No reorder needed'}
          </div>
          <div className="muted" style={{ fontSize: 13, marginBottom: 8 }}>{reorder.reason || '—'}</div>
          <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginTop: 8 }}>
            {['current_stock', 'reorder_point', 'max_stock', 'safety_stock'].map((k) => (
              <div key={k}>
                <div className="muted" style={{ fontSize: 11, textTransform: 'uppercase' }}>{k.replace(/_/g, ' ')}</div>
                <div style={{ fontWeight: 700 }}>{reorder[k] ?? '—'}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <h3>🔮 7-Day Forecast (demand · waste · surplus)</h3>
        {fc.length === 0 ? (
          <div className="empty">No forecast yet — run the AI job.</div>
        ) : (
          <>
            <LineChart
              data={fc.map((p) => ({ ...p, date: new Date(p.target_date).toLocaleDateString() }))}
              xKey="date"
              series={[{ key: 'predicted_waste' }, { key: 'predicted_surplus' }]}
              colors={{ predicted_waste: '#dc2626', predicted_surplus: '#2563eb' }}
            />
            <div className="legend">
              <span><i style={{ background: '#dc2626' }} /> Predicted waste</span>
              <span><i style={{ background: '#2563eb' }} /> Predicted surplus</span>
            </div>
            <div className="table-wrap" style={{ marginTop: 12 }}>
              <table>
                <thead><tr><th>Date</th><th>Demand</th><th>Waste</th><th>Surplus</th><th>Prob.</th><th>Risk</th><th>Value</th></tr></thead>
                <tbody>
                  {fc.map((p) => (
                    <tr key={p.target_date}>
                      <td className="muted">{new Date(p.target_date).toLocaleDateString()}</td>
                      <td>{p.predicted_demand}</td>
                      <td>{p.predicted_waste}</td>
                      <td>{p.predicted_surplus}</td>
                      <td>{Math.round(p.waste_probability * 100)}%</td>
                      <td><Risk4Badge level={p.waste_risk_level} /></td>
                      <td>{fmt$(p.expected_waste_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              Model: {fc[0].model_name}{fc[0].is_fallback ? ' (fallback — limited history)' : ''} · confidence {Math.round(fc[0].confidence * 100)}%
              {reorder.current_stock ? ` · 7-day demand ${forecast.total_demand} · surplus ${forecast.total_surplus}` : ''}
            </p>
          </>
        )}
      </div>

      <div className="card">
        <h3>🧾 Recommendations</h3>
        {recommendations.length === 0 ? (
          <div className="empty">No open recommendations for this product.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Action</th><th>Qty</th><th>Priority</th><th>Benefit</th><th>Reason</th><th>Decision</th></tr></thead>
              <tbody>
                {recommendations.map((r) => (
                  <tr key={r.id}>
                    <td>{TYPE_LABEL[r.recommendation_type] || r.recommendation_type.replace(/_/g, ' ')}</td>
                    <td>{r.recommended_quantity}</td>
                    <td>{'★'.repeat(Math.min(r.priority, 5))}</td>
                    <td>{fmt$(r.expected_benefit)}</td>
                    <td style={{ fontSize: 12, color: '#374151', maxWidth: 280 }}>{r.reason}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button className="btn btn-primary btn-sm" onClick={() => applyRec(r.id, 'applied')}>Apply</button>
                        <button className="btn btn-secondary btn-sm" onClick={() => applyRec(r.id, 'rejected')}>Reject</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="stat-grid two-up">
        <div className="card">
          <h3>🗓️ Sales History</h3>
          {combined.length === 0 ? (
            <div className="empty">No recorded sales.</div>
          ) : (
            <BarChart data={combined} xKey="date" series={[{ key: 'sales' }, { key: 'waste' }]} colors={{ sales: '#16a34a', waste: '#dc2626' }} />
          )}
        </div>
        <div className="card">
          <h3>🎯 Forecast Accuracy</h3>
          {!accuracy ? (
            <div className="empty">Accuracy builds after completed forecast cycles.</div>
          ) : (
            <>
              <div style={{ fontSize: 30, fontWeight: 700 }}>{accuracy.accuracy}<span className="muted" style={{ fontSize: 14, fontWeight: 400 }}>%</span></div>
              <div className="muted" style={{ marginTop: 8 }}>MAE {accuracy.mae} · RMSE {accuracy.rmse} · {accuracy.samples} samples</div>
            </>
          )}
        </div>
      </div>

      {anomalies.length > 0 && (
        <div className="card">
          <h3>🚨 Recent Anomalies</h3>
          {anomalies.map((a) => (
            <div key={a.id} style={{ padding: '8px 0', borderBottom: '1px solid #e5e7eb', fontSize: 13 }}>
              <Risk4Badge level={a.severity} /> <strong style={{ textTransform: 'capitalize' }}>{a.anomaly_type.replace(/_/g, ' ')}</strong>
              <span className="muted"> — {a.explanation}</span>
            </div>
          ))}
        </div>
      )}
    </>
  )
}