import { useEffect, useState, useCallback, lazy, Suspense } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api.js'
import { RiskBadge, ExpiryBadge } from '../components/Badge.jsx'

const ScannerModal = lazy(() => import('../components/ScannerModal.jsx'))

function computeStatus(days) {
  if (days === null || days === undefined) return 'no_expiry'
  if (days < 0) return 'expired'
  if (days <= 3) return 'expiring_soon'
  if (days <= 7) return 'expiring'
  return 'fresh'
}

const expiryOptions = [
  { value: '', label: 'All' },
  { value: 'expired', label: 'Expired' },
  { value: 'expiring_soon', label: 'Expiring Soon (≤3d)' },
  { value: 'expiring', label: 'Expiring (4–7d)' },
  { value: 'fresh', label: 'Fresh' },
  { value: 'no_expiry', label: 'No Expiry' },
]

const riskOptions = [
  { value: '', label: 'All' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

export default function InventoryPage() {
  const [items, setItems] = useState([])
  const [categories, setCategories] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(emptyForm())
  const [actionItem, setActionItem] = useState(null)
  const [actionQty, setActionQty] = useState('')
  const [actionType, setActionType] = useState('')
  const [file, setFile] = useState(null)
  const [bulkMsg, setBulkMsg] = useState('')

  const [filterCategory, setFilterCategory] = useState('')
  const [filterRisk, setFilterRisk] = useState('')
  const [filterExpiry, setFilterExpiry] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  const [scannerOpen, setScannerOpen] = useState(false)
  const [scanMode, setScanMode] = useState('lookup')
  const [scanMsg, setScanMsg] = useState('')
  const [catMsg, setCatMsg] = useState('')
  const [quickCatName, setQuickCatName] = useState('')

  function emptyForm() {
    return { name: '', category_id: '', sku: '', barcode: '', quantity: '', unit: 'units', cost_per_unit: '', expiry_date: '', storage_location: '', supplier: '', notes: '' }
  }

  const load = useCallback(async () => {
    try {
      const filters = {}
      if (filterCategory) filters.category_id = filterCategory
      if (filterRisk) filters.risk_level = filterRisk
      if (filterExpiry) filters.expiry_status = filterExpiry
      if (searchQuery) filters.search = searchQuery
      const [i, c] = await Promise.all([api.getInventory(filters), api.getCategories()])
      setItems(i)
      setCategories(c)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [filterCategory, filterRisk, filterExpiry, searchQuery])

  useEffect(() => { load() }, [load])

  function onChange(e) { setForm({ ...form, [e.target.name]: e.target.value }) }

  function openNew() {
    setEditing(null)
    setForm(emptyForm())
    setShowForm(true)
  }

  function openEdit(it) {
    setEditing(it)
    setForm({
      name: it.name, category_id: it.category_id || '', sku: it.sku || '', barcode: it.barcode || '',
      quantity: it.quantity, unit: it.unit, cost_per_unit: it.cost_per_unit, expiry_date: it.expiry_date ? it.expiry_date.slice(0, 10) : '',
      storage_location: it.storage_location || '', supplier: it.supplier || '', notes: it.notes || '',
    })
    setShowForm(true)
  }

  async function handleSave(e) {
    e.preventDefault()
    setError('')
    const payload = { ...form, category_id: form.category_id ? Number(form.category_id) : null, quantity: Number(form.quantity || 0), cost_per_unit: Number(form.cost_per_unit || 0), expiry_date: form.expiry_date || null }
    try {
      if (editing) {
        await api.updateItem(editing.id, payload)
      } else {
        await api.createItem(payload)
      }
      setShowForm(false)
      setLoading(true)
      await load()
      setLoading(false)
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleDelete(it) {
    if (!confirm(`Delete item "${it.name}"?`)) return
    try {
      await api.deleteItem(it.id)
      await load()
    } catch (err) { setError(err.message) }
  }

  async function handleAction(e) {
    e.preventDefault()
    if (!actionItem || !actionQty) return
    const q = Number(actionQty)
    try {
      if (actionType === 'sale') await api.sale(actionItem.id, q)
      else if (actionType === 'donate') await api.donate(actionItem.id, q)
      else await api.dispose(actionItem.id, q)
      setActionItem(null)
      await load()
    } catch (err) { setError(err.message) }
  }

  async function handleBulk(e) {
    e.preventDefault()
    if (!file) return
    setBulkMsg('')
    try {
      const res = await api.bulkUpload(file)
      setBulkMsg(`Uploaded ${res.created} items. ${res.errors?.length ? `Skipped ${res.errors.length} rows.` : ''}`)
      setFile(null)
      await load()
    } catch (err) { setBulkMsg('') ; setError(err.message) }
  }

  async function handleSeedCategories() {
    setCatMsg('')
    setError('')
    try {
      const res = await api.seedCategories()
      setCategories(res)
      setCatMsg(`Added ${res.length} default categories.`)
    } catch (err) { setError(err.message) }
  }

  async function handleQuickAddCategory() {
    const name = quickCatName.trim()
    if (!name) return
    setCatMsg('')
    try {
      const created = await api.createCategory({ name })
      setCategories((prev) => [...prev, created])
      setQuickCatName('')
      setCatMsg(`Category "${name}" added and selected.`)
      setForm((f) => ({ ...f, category_id: created.id }))
    } catch (err) { setError(err.message) }
  }

  async function handleExport() {
    try {
      const blob = await api.exportInventoryCsv()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'inventory_export.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) { setError(err.message) }
  }

  function openAction(item, type) {
    setActionItem(item)
    setActionType(type)
    setActionQty('')
  }

  function clearFilters() {
    setFilterCategory('')
    setFilterRisk('')
    setFilterExpiry('')
    setSearchQuery('')
  }

  function openScanner(mode) {
    setScanMsg('')
    setError('')
    setScanMode(mode)
    setScannerOpen(true)
  }

  function applyFoundItem(it) {
    setError('')
    if (scanMode === 'lookup') {
      setSearchQuery(it.barcode || it.sku || it.name)
      setScanMsg(`Found "${it.name}" — filtered to show it.`)
      return
    }
    setEditing(it)
    setForm({
      name: it.name, category_id: it.category_id || '', sku: it.sku || '', barcode: it.barcode || '',
      quantity: it.quantity, unit: it.unit, cost_per_unit: it.cost_per_unit, expiry_date: it.expiry_date ? it.expiry_date.slice(0, 10) : '',
      storage_location: it.storage_location || '', supplier: it.supplier || '', notes: it.notes || '',
    })
    setShowForm(true)
    setScanMsg(`"${it.name}" loaded into the edit form — adjust and save.`)
  }

  const handleScan = useCallback(async (code) => {
    setScannerOpen(false)
    const trimmed = (code || '').trim()
    if (!trimmed) return
    setScanMsg('')

    if (scanMode === 'field') {
      setForm((f) => ({ ...f, barcode: trimmed }))
      const existing = await api.getItemByBarcode(trimmed)
      setScanMsg(existing ? `Barcode "${trimmed}" already belongs to "${existing.name}".` : `Barcode "${trimmed}" entered into the form.`)
      return
    }

    const item = await api.getItemByBarcode(trimmed)
    if (item) {
      applyFoundItem(item)
    } else {
      setEditing(null)
      setForm((f) => ({ ...f, barcode: trimmed }))
      setShowForm(true)
      setScanMsg(scanMode === 'lookup' ? `No inventory item has barcode "${trimmed}" — opened the form so you can add it.` : `Barcode "${trimmed}" not in inventory — opened the form to add a new item.`)
    }
  }, [scanMode])

  if (loading) return <div className="card">Loading inventory...</div>

  return (
    <>
      {error && <div className="alert alert-error">{error}</div>}
      {bulkMsg && <div className="alert" style={{ background: '#dcfce7', color: '#15803d' }}>{bulkMsg}</div>}
      {scanMsg && <div className="alert" style={{ background: '#dbeafe', color: '#1d4ed8' }}>{scanMsg}</div>}

      <div className="toolbar">
        <button className="btn btn-primary" onClick={openNew}>+ Add Item</button>
        <button className="btn btn-secondary" onClick={() => openScanner('lookup')}>Scan to Find</button>
        <button className="btn btn-secondary" onClick={() => openScanner('update')}>Scan to Update</button>
        <form onSubmit={handleBulk} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files[0] || null)} style={{ width: '220px' }} />
          <button type="submit" className="btn btn-secondary btn-sm">CSV Upload</button>
        </form>
        <button className="btn btn-secondary btn-sm" onClick={handleExport}>Export CSV</button>
        <div className="spacer" />
        <input
          placeholder="Search name, SKU, barcode..."
          style={{ width: '220px' }}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <div className="card" style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ marginBottom: 0, whiteSpace: 'nowrap' }}>Filters:</label>
          <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)} style={{ width: '160px' }}>
            <option value="">All Categories</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select value={filterRisk} onChange={(e) => setFilterRisk(e.target.value)} style={{ width: '140px' }}>
            {riskOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <select value={filterExpiry} onChange={(e) => setFilterExpiry(e.target.value)} style={{ width: '160px' }}>
            {expiryOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          {(filterCategory || filterRisk || filterExpiry || searchQuery) && (
            <button className="btn btn-secondary btn-sm" onClick={clearFilters}>Clear Filters</button>
          )}
        </div>
      </div>

      {showForm && (
        <div className="card">
          <h3>{editing ? 'Edit Item' : 'Add New Inventory Item'}</h3>
          <form onSubmit={handleSave}>
            <div className="form-grid">
              <div><label>Name *</label><input name="name" value={form.name} onChange={onChange} required /></div>
              <div><label>Category</label>
                <select name="category_id" value={form.category_id} onChange={onChange}>
                  <option value="">— Uncategorized —</option>
                  {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <div style={{ display: 'flex', gap: '8px', marginTop: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={handleSeedCategories} title="Load the 12 built-in food categories">＋ Load default categories</button>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                    <input
                      placeholder="Quick-add category name…"
                      value={quickCatName}
                      onChange={(e) => setQuickCatName(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleQuickAddCategory() } }}
                      style={{ width: '180px' }}
                    />
                    <button type="button" className="btn btn-secondary btn-sm" disabled={!quickCatName.trim()} onClick={handleQuickAddCategory}>Add</button>
                  </div>
                </div>
                {catMsg && <div style={{ fontSize: '12px', color: '#15803d', marginTop: '4px' }}>{catMsg}</div>}
              </div>
              <div><label>SKU</label><input name="sku" value={form.sku} onChange={onChange} /></div>
              <div>
                <label>Barcode / QR</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input name="barcode" value={form.barcode} onChange={onChange} placeholder="Scan or enter barcode" />
                  <button type="button" className="btn btn-secondary btn-sm" style={{ whiteSpace: 'nowrap' }} onClick={() => openScanner('field')}>Scan</button>
                </div>
              </div>
              <div><label>Quantity</label><input type="number" step="any" name="quantity" value={form.quantity} onChange={onChange} /></div>
              <div><label>Unit</label><input name="unit" value={form.unit} onChange={onChange} /></div>
              <div><label>Cost / Unit</label><input type="number" step="any" name="cost_per_unit" value={form.cost_per_unit} onChange={onChange} /></div>
              <div><label>Expiry Date</label><input type="date" name="expiry_date" value={form.expiry_date} onChange={onChange} /></div>
              <div><label>Storage Location</label><input name="storage_location" value={form.storage_location} onChange={onChange} /></div>
              <div><label>Supplier</label><input name="supplier" value={form.supplier} onChange={onChange} /></div>
              <div className="full"><label>Notes</label><input name="notes" value={form.notes} onChange={onChange} /></div>
            </div>
            <div className="toolbar" style={{ marginTop: '16px', marginBottom: '0' }}>
              <button type="submit" className="btn btn-primary">{editing ? 'Save Changes' : 'Add Item'}</button>
              <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <h3 style={{ margin: 0 }}>Inventory ({items.length} items)</h3>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Item</th><th>Category</th><th>Qty</th><th>Expiry</th><th>Risk Score</th><th>Risk</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr><td colSpan={7} className="empty">No inventory items found. Add your first item or adjust filters.</td></tr>
              ) : items.map((it) => {
                const status = computeStatus(it.days_to_expiry)
                return (
                  <tr key={it.id}>
                    <td><Link to={`/products/${it.id}`} className="link"><strong>{it.name}</strong></Link>{it.sku ? <div style={{ fontSize: '12px', color: '#6b7280' }}>{it.sku}</div> : null}</td>
                    <td>{it.category_name || '—'}</td>
                    <td>{it.quantity} {it.unit}</td>
                    <td><ExpiryBadge status={status} />{it.days_to_expiry !== null && it.days_to_expiry !== undefined ? <div style={{ fontSize: '12px', color: '#6b7280' }}>{it.days_to_expiry} days</div> : null}</td>
                    <td style={{ fontSize: '13px' }}>{it.risk_score.toFixed(0)} / 100</td>
                    <td><RiskBadge level={it.risk_level} /></td>
                    <td>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        <button className="btn btn-secondary btn-sm" onClick={() => openAction(it, 'sale')}>Sell</button>
                        <button className="btn btn-secondary btn-sm" onClick={() => openAction(it, 'donate')}>Donate</button>
                        <button className="btn btn-secondary btn-sm" onClick={() => openAction(it, 'dispose')}>Dispose</button>
                        <button className="btn btn-secondary btn-sm" onClick={() => openEdit(it)}>Edit</button>
                        <button className="btn btn-danger btn-sm" onClick={() => handleDelete(it)}>Del</button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {actionItem && (
        <div className="card">
          <h3>{actionType === 'sale' ? 'Record Sale' : actionType === 'donate' ? 'Record Donation' : 'Record Disposal'} — {actionItem.name}</h3>
          <form onSubmit={handleAction} style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
            <div style={{ width: '200px' }}>
              <label>Quantity (max {actionItem.quantity})</label>
              <input type="number" step="any" min="0" max={actionItem.quantity} value={actionQty} onChange={(e) => setActionQty(e.target.value)} required />
            </div>
            <button type="submit" className="btn btn-primary">Confirm {actionType}</button>
            <button type="button" className="btn btn-secondary" onClick={() => setActionItem(null)}>Cancel</button>
          </form>
        </div>
      )}

      {scannerOpen && (
        <Suspense fallback={<div className="alert">Loading camera scanner…</div>}>
          <ScannerModal onScan={handleScan} onClose={() => setScannerOpen(false)} />
        </Suspense>
      )}
    </>
  )
}
