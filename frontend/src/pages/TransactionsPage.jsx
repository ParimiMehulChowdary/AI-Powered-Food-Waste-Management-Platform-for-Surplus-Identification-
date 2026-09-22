import { useEffect, useState } from 'react'
import { api } from '../services/api.js'
import { TypeBadge } from '../components/Badge.jsx'

export default function TransactionsPage() {
  const [txs, setTxs] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      setTxs(await api.getTransactions())
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="card">Loading transactions...</div>

  return (
    <>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="card">
        <h3>Transaction History</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Date</th><th>Item</th><th>Type</th><th>Quantity</th><th>Unit Price</th><th>Reference</th></tr></thead>
            <tbody>
              {txs.length === 0 ? (
                <tr><td colSpan={6} className="empty">No transactions recorded yet.</td></tr>
              ) : txs.map((t) => (
                <tr key={t.id}>
                  <td>{new Date(t.transaction_date).toLocaleString()}</td>
                  <td>{t.item_name || '—'}</td>
                  <td><TypeBadge type={t.transaction_type} /></td>
                  <td>{t.quantity} {t.unit}</td>
                  <td>${t.unit_price}</td>
                  <td>{t.reference}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
