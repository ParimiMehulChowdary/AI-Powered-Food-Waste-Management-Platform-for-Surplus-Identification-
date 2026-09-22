import { useEffect, useState } from 'react'
import { api } from '../services/api.js'
import { Risk4Badge } from '../components/Badge.jsx'

const TYPE_LABEL = {
  high_waste_risk: 'High waste risk',
  critical_expiry: 'Critical expiry',
  predicted_surplus: 'Predicted surplus',
  donation_opportunity: 'Donation opportunity',
  unusual_waste: 'Unusual waste',
  demand_anomaly: 'Demand anomaly',
  overstock: 'Overstock',
  forecast_accuracy: 'Forecast accuracy',
}

export default function NotificationsPage() {
  const [rows, setRows] = useState([])
  const [unreadOnly, setUnreadOnly] = useState(true)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      setRows(await api.getNotifications(unreadOnly))
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [unreadOnly])

  async function markRead(id) {
    try {
      await api.markNotificationRead(id)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  async function readAll() {
    try {
      await api.readAllNotifications()
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  if (loading) return <div className="card">Loading notifications…</div>

  return (
    <>
      <div className="toolbar">
        <h2 style={{ fontSize: 18 }}>Notifications</h2>
        <div className="spacer" />
        <label className="check" style={{ display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
          <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} style={{ width: 'auto' }} />
          Unread only
        </label>
        <button className="btn btn-secondary btn-sm" onClick={readAll}>Mark all read</button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {rows.length === 0 ? (
        <div className="card"><div className="empty">No notifications. AI alerts about risk, surplus and anomalies will appear here.</div></div>
      ) : (
        <div className="card">
          {rows.map((n) => (
            <div key={n.id} className={`notif ${n.is_read ? 'read' : ''}`}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                {!n.is_read && <span className="dot" />}
                <Risk4Badge level={n.severity} />
                <strong style={{ fontSize: 14 }}>{TYPE_LABEL[n.notification_type] || n.notification_type.replace(/_/g, ' ')}</strong>
                {n.item_name && <span className="muted" style={{ fontSize: 13 }}>— {n.item_name}</span>}
                <span className="muted" style={{ fontSize: 12, marginLeft: 'auto' }}>{new Date(n.created_at).toLocaleString()}</span>
              </div>
              <p style={{ fontSize: 13, color: '#374151', margin: '6px 0', whiteSpace: 'pre-wrap' }}>{n.message}</p>
              {!n.is_read && <button className="btn btn-secondary btn-sm" onClick={() => markRead(n.id)}>Mark read</button>}
            </div>
          ))}
        </div>
      )}
    </>
  )
}