import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api.js'
import { Risk4Badge } from '../components/Badge.jsx'

export default function AnomaliesPage() {
  const [rows, setRows] = useState([])
  const [includeResolved, setIncludeResolved] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      setRows(await api.getAnomalies(includeResolved))
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [includeResolved])

  async function resolve(id) {
    try {
      await api.resolveAnomaly(id)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  if (loading) return <div className="card">Loading anomalies…</div>
  if (error) return <div className="card"><div className="alert alert-error">{error}</div></div>

  return (
    <>
      <div className="toolbar">
        <h2 style={{ fontSize: 18 }}>Anomaly Detection</h2>
        <div className="spacer" />
        <label className="check" style={{ display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
          <input type="checkbox" checked={includeResolved} onChange={(e) => setIncludeResolved(e.target.checked)} style={{ width: 'auto' }} />
          Include resolved
        </label>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {rows.length === 0 ? (
        <div className="card"><div className="empty">No anomalies detected. Unusual sales, stock or waste patterns will appear here automatically.</div></div>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Detected</th><th>Scope</th><th>Type</th><th>Severity</th><th>Detected value</th><th>Expected</th><th>Explanation</th><th>Method</th><th>Action</th></tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id} style={{ verticalAlign: 'top' }}>
                    <td className="muted" style={{ fontSize: 12 }}>{new Date(a.detected_at).toLocaleString()}</td>
                    <td>{a.item_name ? <Link to={`/products/${a.item_id}`} className="link">{a.item_name}</Link> : 'All items'}</td>
                    <td className="muted" style={{ textTransform: 'capitalize' }}>{a.anomaly_type.replace(/_/g, ' ')}</td>
                    <td><Risk4Badge level={a.severity} /></td>
                    <td style={{ fontWeight: 600 }}>{a.detected_value}</td>
                    <td className="muted">{a.expected_value}</td>
                    <td style={{ fontSize: 12, color: '#374151', maxWidth: 320 }}>{a.explanation}</td>
                    <td className="muted" style={{ fontSize: 12 }}>{a.method}</td>
                    <td>
                      {!a.is_resolved ? (
                        <button className="btn btn-secondary btn-sm" onClick={() => resolve(a.id)}>Resolve</button>
                      ) : (
                        <span className="badge badge-green">Resolved</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}