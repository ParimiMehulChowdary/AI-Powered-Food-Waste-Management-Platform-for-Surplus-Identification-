import { useEffect, useState } from 'react'
import { api } from '../services/api.js'

const riskOpts = ['low', 'medium', 'high']
const storageOpts = ['ambient', 'chilled', 'frozen']

export default function CategoriesPage() {
  const [cats, setCats] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(emptyForm())

  function emptyForm() {
    return { name: '', description: '', perishability_risk: 'medium', storage_requirement: 'ambient', default_shelf_life_days: 7, waste_risk_weight: 1 }
  }

  async function load() {
    try {
      setCats(await api.getCategories())
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  function onChange(e) { setForm({ ...form, [e.target.name]: e.target.value }) }

  function openNew() { setEditing(null); setForm(emptyForm()); setShowForm(true) }
  function openEdit(c) { setEditing(c); setForm({ name: c.name, description: c.description || '', perishability_risk: c.perishability_risk, storage_requirement: c.storage_requirement, default_shelf_life_days: c.default_shelf_life_days, waste_risk_weight: c.waste_risk_weight }); setShowForm(true) }

  async function handleSave(e) {
    e.preventDefault()
    const payload = { ...form, default_shelf_life_days: Number(form.default_shelf_life_days), waste_risk_weight: Number(form.waste_risk_weight) }
    try {
      if (editing) await api.updateCategory(editing.id, payload)
      else await api.createCategory(payload)
      setShowForm(false)
      setLoading(true); await load(); setLoading(false)
    } catch (err) { setError(err.message) }
  }

  async function handleDelete(c) {
    if (!confirm(`Delete category "${c.name}"? Items will become uncategorized.`)) return
    try { await api.deleteCategory(c.id); await load() } catch (err) { setError(err.message) }
  }

  const riskLabel = { low: 'Low', medium: 'Medium', high: 'High' }
  const storageLabel = { ambient: 'Ambient', chilled: 'Chilled', frozen: 'Frozen' }

  if (loading) return <div className="card">Loading categories...</div>

  return (
    <>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="toolbar">
        <button className="btn btn-primary" onClick={openNew}>+ Add Category</button>
        <div className="spacer" />
      </div>

      {showForm && (
        <div className="card">
          <h3>{editing ? 'Edit Category' : 'New Category'}</h3>
          <form onSubmit={handleSave}>
            <div className="form-grid">
              <div><label>Name *</label><input name="name" value={form.name} onChange={onChange} required /></div>
              <div><label>Perishability Risk</label>
                <select name="perishability_risk" value={form.perishability_risk} onChange={onChange}>{riskOpts.map((r) => <option key={r} value={r}>{riskLabel[r]}</option>)}</select>
              </div>
              <div><label>Storage Requirement</label>
                <select name="storage_requirement" value={form.storage_requirement} onChange={onChange}>{storageOpts.map((s) => <option key={s} value={s}>{storageLabel[s]}</option>)}</select>
              </div>
              <div><label>Default Shelf Life (days)</label><input type="number" name="default_shelf_life_days" value={form.default_shelf_life_days} onChange={onChange} /></div>
              <div><label>Waste Risk Weight</label><input type="number" step="0.1" name="waste_risk_weight" value={form.waste_risk_weight} onChange={onChange} /></div>
              <div className="full"><label>Description</label><input name="description" value={form.description} onChange={onChange} /></div>
            </div>
            <div className="toolbar" style={{ marginTop: '16px', marginBottom: '0' }}>
              <button type="submit" className="btn btn-primary">{editing ? 'Save Changes' : 'Add Category'}</button>
              <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Perishability</th><th>Storage</th><th>Shelf Life</th><th>Risk Weight</th><th>Items</th><th>Actions</th></tr></thead>
            <tbody>
              {cats.length === 0 ? (
                <tr><td colSpan={7} className="empty">No categories yet. Add one to classify inventory.</td></tr>
              ) : cats.map((c) => (
                <tr key={c.id}>
                  <td><strong>{c.name}</strong>{c.description ? <div style={{ fontSize: '12px', color: '#6b7280' }}>{c.description}</div> : null}</td>
                  <td><span className={`badge ${c.perishability_risk === 'high' ? 'badge-red' : c.perishability_risk === 'medium' ? 'badge-amber' : 'badge-green'}`}>{riskLabel[c.perishability_risk]}</span></td>
                  <td><span className="badge badge-gray">{storageLabel[c.storage_requirement]}</span></td>
                  <td>{c.default_shelf_life_days} days</td>
                  <td>{c.waste_risk_weight}x</td>
                  <td>{c.item_count}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button className="btn btn-secondary btn-sm" onClick={() => openEdit(c)}>Edit</button>
                      <button className="btn btn-danger btn-sm" onClick={() => handleDelete(c)}>Del</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
