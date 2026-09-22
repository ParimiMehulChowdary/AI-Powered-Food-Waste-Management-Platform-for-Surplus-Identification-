import { useEffect, useState } from 'react'
import { api } from '../services/api.js'

const fmt$ = (v) => `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`

export default function SimulationPage() {
  const [items, setItems] = useState([])
  const [itemId, setItemId] = useState('')
  const [form, setForm] = useState({
    current_stock: 100,
    expected_demand: 60,
    purchase_quantity: 0,
    discount_pct: 0,
    donation_quantity: 0,
    horizon_days: 7,
    elasticity: 0.5,
  })
  const [result, setResult] = useState(null)
  const [history, setHistory] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)

  async function load() {
    try {
      const [inv, sims] = await Promise.all([api.getInventory(), api.getSimulations()])
      setItems(inv)
      setHistory(sims)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function onSelectItem(id) {
    const item = items.find((i) => i.id === Number(id))
    setItemId(id)
    if (item && Number(item.quantity) >= 0) {
      setForm((f) => ({ ...f, current_stock: item.quantity }))
    }
  }

  function setField(key, value) {
    setForm((f) => ({ ...f, [key]: Number(value) }))
  }

  async function run(e) {
    e.preventDefault()
    setRunning(true)
    setError('')
    try {
      const data = await api.runSimulation({
        item_id: itemId ? Number(itemId) : null,
        current_stock: form.current_stock,
        expected_demand: form.expected_demand,
        purchase_quantity: form.purchase_quantity,
        discount_pct: form.discount_pct,
        donation_quantity: form.donation_quantity,
        horizon_days: form.horizon_days,
        elasticity: form.elasticity,
        save: true,
      })
      setResult(data)
      setLoading(true)
      const sims = await api.getSimulations()
      setHistory(sims)
    } catch (err) {
      setError(err.message)
    } finally {
      setRunning(false)
      setLoading(false)
    }
  }

  if (loading && items.length === 0) return <div className="card">Loading inventory…</div>

  return (
    <>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="card">
        <h3>🔮 What-If Simulation</h3>
        <p className="muted" style={{ marginBottom: 14, fontSize: 13 }}>
          Estimate how pricing, donations and purchasing decisions change forecast waste. Results are labelled simulations, not actuals.
        </p>
        <form onSubmit={run}>
          <div className="form-grid">
            <div>
              <label>Product</label>
              <select value={itemId} onChange={(e) => onSelectItem(e.target.value)}>
                <option value="">Region / all products (free-form)</option>
                {items.map((i) => (
                  <option key={i.id} value={i.id}>{i.name} (stock {i.quantity})</option>
                ))}
              </select>
            </div>
            <div>
              <label>Current stock</label>
              <input type="number" min="0" step="any" value={form.current_stock} onChange={(e) => setField('current_stock', e.target.value)} />
            </div>
            <div>
              <label>Expected demand (units)</label>
              <input type="number" min="0" step="any" value={form.expected_demand} onChange={(e) => setField('expected_demand', e.target.value)} />
            </div>
            <div>
              <label>Extra purchase (units)</label>
              <input type="number" min="0" step="any" value={form.purchase_quantity} onChange={(e) => setField('purchase_quantity', e.target.value)} />
            </div>
            <div>
              <label>Discount %</label>
              <input type="number" min="0" max="100" step="any" value={form.discount_pct} onChange={(e) => setField('discount_pct', e.target.value)} />
            </div>
            <div>
              <label>Donate (units)</label>
              <input type="number" min="0" step="any" value={form.donation_quantity} onChange={(e) => setField('donation_quantity', e.target.value)} />
            </div>
            <div>
              <label>Horizon (days)</label>
              <input type="number" min="1" step="1" value={form.horizon_days} onChange={(e) => setField('horizon_days', e.target.value)} />
            </div>
            <div>
              <label>Price elasticity</label>
              <input type="number" min="0" max="2" step="0.1" value={form.elasticity} onChange={(e) => setField('elasticity', e.target.value)} />
            </div>
          </div>
          <button type="submit" className="btn btn-primary" style={{ marginTop: 16 }} disabled={running}>
            {running ? 'Simulating…' : 'Run simulation'}
          </button>
        </form>
      </div>

      {result && (
        <div className="card">
          <h3>📊 Simulation Result</h3>
          <div className="stat-grid two-up" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
            {[
              ['Baseline waste', result.baseline.waste, '#dc2626'],
              ['Simulated waste', result.simulated.waste, '#16a34a'],
              ['Baseline value', fmt$(result.baseline.waste_value), '#dc2626'],
              ['Simulated value', fmt$(result.simulated.waste_value), '#16a34a'],
              ['Donated', result.simulated.donated_quantity || 0, '#2563eb'],
              ['Potential savings', fmt$(result.potential_savings), '#16a34a'],
            ].map(([label, value, color]) => (
              <div className="stat" key={label}>
                <div className="label">{label}</div>
                <div className="value" style={{ color }}>{value}</div>
              </div>
            ))}
          </div>
          <p className="muted" style={{ fontSize: 13 }}>
            {result.label} · {result.explanation || `Waste drops from ${result.baseline.waste} to ${result.simulated.waste} units.`}
          </p>
        </div>
      )}

      {history.length > 0 && (
        <div className="card">
          <h3>🕘 Saved Simulations</h3>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Product</th><th>Run at</th><th>Baseline waste</th><th>Simulated waste</th><th>Savings</th></tr></thead>
              <tbody>
                {history.map((s) => {
                  const res = s.results || {}
                  return (
                    <tr key={s.id}>
                      <td>{s.item_name || 'Region'}</td>
                      <td className="muted" style={{ fontSize: 12 }}>{new Date(s.created_at).toLocaleString()}</td>
                      <td>{res.baseline?.waste ?? '—'}</td>
                      <td>{res.simulated?.waste ?? '—'}</td>
                      <td>{fmt$(res.potential_savings)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}