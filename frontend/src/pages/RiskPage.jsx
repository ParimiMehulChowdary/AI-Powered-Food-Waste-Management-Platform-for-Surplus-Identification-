import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api.js'
import { Risk4Badge } from '../components/Badge.jsx'

const LEVELS = ['all', 'critical', 'high', 'moderate', 'low']

export default function RiskPage() {
  const [rows, setRows] = useState([])
  const [level, setLevel] = useState('all')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      setRows(await api.getRisk())
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const filtered = useMemo(
    () => (level === 'all' ? rows : rows.filter((r) => r.risk_level === level)),
    [rows, level],
  )

  if (loading) return <div className="card">Loading risk assessments…</div>
  if (error) return <div className="card"><div className="alert alert-error">{error}</div></div>

  const counts = LEVELS.filter((l) => l !== 'all').map((l) => ({ level: l, n: rows.filter((r) => r.risk_level === l).length }))

  return (
    <>
      <div className="toolbar">
        <h2 style={{ fontSize: 18 }}>Explainable Waste Risk</h2>
        <div className="spacer" />
        {LEVELS.map((l) => (
          <button key={l} className={`btn btn-sm ${level === l ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setLevel(l)} style={{ textTransform: 'capitalize' }}>
            {l}{l !== 'all' ? ` (${counts.find((c) => c.level === l).n})` : ''}
          </button>
        ))}
      </div>

      {rows.length === 0 ? (
        <div className="card"><div className="empty">No risk assessments yet — run the AI job on the dashboard.</div></div>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Product</th><th>Score</th><th>Level</th><th>Key Factors</th><th>Explanation</th><th>Updated</th></tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr key={r.id} style={{ verticalAlign: 'top' }}>
                    <td><Link to={`/products/${r.item_id}`} className="link">{r.item_name}</Link></td>
                    <td style={{ minWidth: 120 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{r.risk_score}</div>
                      <div className="risk-bar">
                        <div style={{ width: `${Math.min(r.risk_score, 100)}%`, background: r.risk_level === 'critical' ? '#7f1d1d' : r.risk_level === 'high' ? '#dc2626' : r.risk_level === 'moderate' ? '#d97706' : '#16a34a' }} />
                      </div>
                    </td>
                    <td><Risk4Badge level={r.risk_level} /></td>
                    <td style={{ fontSize: 12, maxWidth: 260 }}>
                      {(r.factors || []).slice(0, 4).map((f, i) => (
                        <div key={i} className="muted" style={{ marginBottom: 2 }}>{f.value}</div>
                      ))}
                    </td>
                    <td style={{ fontSize: 12, color: '#374151', maxWidth: 320 }}>{r.explanation}</td>
                    <td className="muted" style={{ fontSize: 12 }}>{new Date(r.created_at).toLocaleString()}</td>
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