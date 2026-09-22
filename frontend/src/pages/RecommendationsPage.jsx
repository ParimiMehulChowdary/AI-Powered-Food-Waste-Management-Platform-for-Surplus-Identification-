import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api.js'
import { StatusBadge } from '../components/Badge.jsx'

const FILTERS = [
  { key: 'pending', label: 'Open' },
  { key: 'applied', label: 'Applied' },
  { key: 'rejected', label: 'Rejected' },
]

const TYPE_LABEL = {
  discount: 'Discount',
  promotion: 'Promotion',
  reduce_next_purchase: 'Reduce next purchase',
  stop_reorder: 'Stop reorder',
  transfer_stock: 'Transfer stock',
  donate_surplus: 'Donate surplus',
  prioritize_sale: 'Prioritize sale',
  relocate_high_visibility: 'Move to high visibility',
  adjust_storage: 'Adjust storage',
  process_before_expiry: 'Process before expiry',
  mark_for_disposal: 'Mark for disposal',
  reorder: 'Reorder',
}

const fmt$ = (v) => `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`

export default function RecommendationsPage() {
  const [rows, setRows] = useState([])
  const [filter, setFilter] = useState('pending')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      setRows(await api.getRecommendations(filter === 'all' ? undefined : filter))
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [filter])

  async function apply(id, status) {
    try {
      await api.updateRecommendation(id, status)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  if (loading) return <div className="card">Loading recommendations…</div>
  if (error && rows.length === 0) return <div className="card"><div className="alert alert-error">{error}</div></div>

  return (
    <>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="toolbar">
        <h2 style={{ fontSize: 18 }}>AI Recommendations</h2>
        <div className="spacer" />
        <button className={`btn btn-sm ${filter === 'all' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setFilter('all')}>All</button>
        {FILTERS.map((f) => (
          <button key={f.key} className={`btn btn-sm ${filter === f.key ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setFilter(f.key)}>
            {f.label}
          </button>
        ))}
      </div>

      {rows.length === 0 ? (
        <div className="card"><div className="empty">No recommendations here — run the AI job on the dashboard.</div></div>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Item</th><th>Action</th><th>Qty</th><th>Priority</th><th>Benefit</th><th>Deadline</th><th>Status</th><th>Decision</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td><Link to={`/products/${r.item_id}`} className="link">{r.item_name}</Link></td>
                    <td>{TYPE_LABEL[r.recommendation_type] || r.recommendation_type.replace(/_/g, ' ')}</td>
                    <td>{r.recommended_quantity}</td>
                    <td>{'★'.repeat(Math.min(r.priority, 5)).padEnd(5, '☆')}</td>
                    <td>{fmt$(r.expected_benefit)}</td>
                    <td className="muted" style={{ fontSize: 12 }}>{r.deadline ? new Date(r.deadline).toLocaleDateString() : '—'}</td>
                    <td><StatusBadge status={r.status} /></td>
                    <td>
                      {r.status === 'pending' ? (
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="btn btn-primary btn-sm" onClick={() => apply(r.id, 'applied')}>Apply</button>
                          <button className="btn btn-secondary btn-sm" onClick={() => apply(r.id, 'rejected')}>Reject</button>
                        </div>
                      ) : (
                        <span className="muted" style={{ fontSize: 12 }}>{r.reason?.slice(0, 60) || '—'}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ marginTop: 10, fontSize: 13 }}>
            Each recommendation is generated from live forecast & risk data with an expected benefit estimate.
          </p>
        </div>
      )}
    </>
  )
}