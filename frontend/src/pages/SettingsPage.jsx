import { useEffect, useState, useCallback } from 'react'
import { api } from '../services/api.js'

export default function SettingsPage() {
  const [settings, setSettings] = useState(null)
  const [form, setForm] = useState({ low_stock_threshold: '', expiry_alert_days: '', shelf_life_breach_enabled: true, low_stock_alert_enabled: true })
  const [keys, setKeys] = useState([])
  const [newKeyLabel, setNewKeyLabel] = useState('')
  const [newKey, setNewKey] = useState('')
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const [s, k] = await Promise.all([api.getSettings(), api.getApiKeys()])
      setSettings(s)
      setForm({
        low_stock_threshold: s.low_stock_threshold,
        expiry_alert_days: s.expiry_alert_days,
        shelf_life_breach_enabled: !!s.shelf_life_breach_enabled,
        low_stock_alert_enabled: !!s.low_stock_alert_enabled,
      })
      setKeys(k)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  function onChange(e) { setForm({ ...form, [e.target.name]: e.target.value }) }
  function onToggle(e) { setForm({ ...form, [e.target.name]: e.target.checked }) }

  async function handleSave(e) {
    e.preventDefault()
    setError(''); setMsg('')
    const payload = {
      low_stock_threshold: Number(form.low_stock_threshold || 0),
      expiry_alert_days: Number(form.expiry_alert_days || 0),
      shelf_life_breach_enabled: form.shelf_life_breach_enabled ? 1 : 0,
      low_stock_alert_enabled: form.low_stock_alert_enabled ? 1 : 0,
    }
    try {
      const updated = await api.updateSettings(payload)
      setSettings(updated)
      setMsg('Settings saved.')
    } catch (err) { setError(err.message) }
  }

  async function handleCreateKey(e) {
    e.preventDefault()
    setError(''); setMsg(''); setNewKey('')
    try {
      const created = await api.createApiKey(newKeyLabel.trim() || 'POS integration')
      setNewKey(created.key)
      setNewKeyLabel('')
      await load()
    } catch (err) { setError(err.message) }
  }

  async function handleDeleteKey(id) {
    if (!confirm('Delete this API key? Any system using it will lose access.')) return
    setError('')
    try {
      await api.deleteApiKey(id)
      setNewKey('')
      await load()
    } catch (err) { setError(err.message) }
  }

  function copyKey() {
    navigator.clipboard?.writeText(newKey)
    setMsg('API key copied to clipboard.')
  }

  if (loading) return <div className="card">Loading settings…</div>

  return (
    <>
      {error && <div className="alert alert-error">{error}</div>}
      {msg && <div className="alert" style={{ background: '#dcfce7', color: '#15803d' }}>{msg}</div>}

      <div className="card">
        <h3>Alert & Risk Thresholds</h3>
        <form onSubmit={handleSave}>
          <div className="form-grid">
            <div><label>Low Stock Threshold (units)</label>
              <input type="number" step="any" min="0" name="low_stock_threshold" value={form.low_stock_threshold} onChange={onChange} /></div>
            <div><label>Expiry Alert Days</label>
              <input type="number" min="1" name="expiry_alert_days" value={form.expiry_alert_days} onChange={onChange} /></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '24px' }}>
              <input type="checkbox" name="low_stock_alert_enabled" checked={form.low_stock_alert_enabled} onChange={onToggle} style={{ width: 'auto' }} />
              <label style={{ margin: 0 }}>Low-stock alerts</label>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '24px' }}>
              <input type="checkbox" name="shelf_life_breach_enabled" checked={form.shelf_life_breach_enabled} onChange={onToggle} style={{ width: 'auto' }} />
              <label style={{ margin: 0 }}>Shelf-life breach alerts</label>
            </div>
          </div>
          <div className="toolbar" style={{ marginTop: '16px', marginBottom: '0' }}>
            <button type="submit" className="btn btn-primary">Save Settings</button>
          </div>
        </form>
      </div>

      <div className="card">
        <h3>API Keys (POS integration)</h3>
        <p style={{ fontSize: '13px', color: '#6b7280', marginBottom: '14px' }}>
          Use a key as the <code>X-API-Key</code> header to push inventory or record sales from a POS terminal.
        </p>

        {newKey && (
          <div className="alert" style={{ background: '#fef3c7', color: '#92400e' }}>
            <strong>Copy this key now</strong> — it is only shown once.
            <div style={{ display: 'flex', gap: '8px', marginTop: '8px', alignItems: 'center' }}>
              <code style={{ flex: 1, background: '#fff', padding: '8px 10px', borderRadius: '6px', border: '1px solid #e5e7eb', wordBreak: 'break-all' }}>{newKey}</code>
              <button type="button" className="btn btn-secondary btn-sm" onClick={copyKey}>Copy</button>
            </div>
          </div>
        )}

        {keys.length === 0 ? (
          <p style={{ fontSize: '14px', color: '#6b7280' }}>No API keys yet.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Label</th><th>Key</th><th>Created</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {keys.map((k) => (
                  <tr key={k.id}>
                    <td>{k.label || '—'}</td>
                    <td><code>{k.key}</code></td>
                    <td>{k.created_at ? k.created_at.slice(0, 10) : '—'}</td>
                    <td>{k.is_active ? 'Active' : 'Inactive'}</td>
                    <td><button className="btn btn-danger btn-sm" onClick={() => handleDeleteKey(k.id)}>Delete</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <form onSubmit={handleCreateKey} style={{ display: 'flex', gap: '10px', marginTop: '16px', alignItems: 'center' }}>
          <input placeholder="Label (e.g. POS Terminal 2)" value={newKeyLabel} onChange={(e) => setNewKeyLabel(e.target.value)} style={{ width: '280px' }} />
          <button type="submit" className="btn btn-primary">Generate Key</button>
        </form>
      </div>
    </>
  )
}