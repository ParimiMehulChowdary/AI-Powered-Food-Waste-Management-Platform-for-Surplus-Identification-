const API_BASE = '/api'

export function getToken() {
  return localStorage.getItem('token')
}

export function setToken(token) {
  localStorage.setItem('token', token)
}

export function clearToken() {
  localStorage.removeItem('token')
}

async function request(method, path, body, isForm = false) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body && !isForm) headers['Content-Type'] = 'application/json'

  const opts = { method, headers }
  if (body) opts.body = isForm ? body : JSON.stringify(body)

  const res = await fetch(API_BASE + path, opts)
  if (res.status === 204) return null
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : 'Request failed'
    throw new Error(detail)
  }
  return data
}

function buildQuery(params) {
  const entries = Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== '')
  return entries.length ? '?' + new URLSearchParams(entries).toString() : ''
}

export const api = {
  register: (data) => request('POST', '/auth/register', data),
  login: (username, password) => {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    return request('POST', '/auth/login', form, true)
  },
  getDashboard: () => request('GET', '/dashboard'),
  getAlerts: () => request('GET', '/dashboard/alerts'),
  resolveAlert: (id) => request('POST', `/dashboard/alerts/${id}/resolve`),
  getInventory: (filters = {}) => request('GET', '/inventory' + buildQuery(filters)),
  getItemByBarcode: async (barcode) => {
    try {
      return await request('GET', `/inventory/barcode/${encodeURIComponent(barcode)}`)
    } catch (e) {
      return null
    }
  },
  createItem: (data) => request('POST', '/inventory', data),
  updateItem: (id, data) => request('PUT', `/inventory/${id}`, data),
  deleteItem: (id) => request('DELETE', `/inventory/${id}`),
  exportInventoryCsv: () => {
    const token = getToken()
    const headers = token ? { Authorization: `Bearer ${token}` } : {}
    return fetch(API_BASE + '/inventory/export/csv', { headers })
      .then((res) => {
        if (!res.ok) throw new Error('Export failed')
        return res.blob()
      })
  },
  bulkUpload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('POST', '/inventory/bulk', form, true)
  },
  sale: (id, quantity) => {
    const form = new FormData()
    form.append('quantity', quantity)
    return request('POST', `/inventory/sale/${id}`, form, true)
  },
  donate: (id, quantity) => {
    const form = new FormData()
    form.append('quantity', quantity)
    return request('POST', `/inventory/donate/${id}`, form, true)
  },
  dispose: (id, quantity) => {
    const form = new FormData()
    form.append('quantity', quantity)
    return request('POST', `/inventory/dispose/${id}`, form, true)
  },
getCategories: () => request('GET', '/categories'),
createCategory: (data) => request('POST', '/categories', data),
updateCategory: (id, data) => request('PUT', `/categories/${id}`, data),
deleteCategory: (id) => request('DELETE', `/categories/${id}`),
seedCategories: () => request('POST', '/categories/seed'),
  getTransactions: () => request('GET', '/transactions'),
  getSettings: () => request('GET', '/settings'),
  updateSettings: (data) => request('PUT', '/settings', data),
  getApiKeys: () => request('GET', '/settings/api-keys'),
  createApiKey: (label) => request('POST', '/settings/api-keys', { label }),
  deleteApiKey: (id) => request('DELETE', `/settings/api-keys/${id}`),

  // Milestone 2 — AI prediction, risk, optimization & decision support
  getDashboardSummary: () => request('GET', '/dashboard/summary'),
  runDailyJob: () => request('POST', '/waste/jobs/daily'),
  predictOnDemand: (itemId) => request('POST', '/waste/predict' + (itemId ? buildQuery({ item_id: itemId }) : '')),
  getPredictions: (params = {}) => request('GET', '/waste/predictions' + buildQuery(params)),
  getPredictionsSummary: () => request('GET', '/waste/predictions/summary'),
  getRisk: (params = {}) => request('GET', '/waste/risk' + buildQuery(params)),
  getAnalytics: (period = 'week') => request('GET', '/waste/analytics' + buildQuery({ period })),
  getTrends: (days = 30) => request('GET', '/waste/trends' + buildQuery({ days })),
  getCauses: () => request('GET', '/waste/causes'),
  getAnomalies: (includeResolved = false) =>
    request('GET', '/waste/anomalies' + buildQuery({ include_resolved: includeResolved })),
  resolveAnomaly: (id) => request('POST', `/waste/anomalies/${id}/resolve`),
  getForecastAccuracy: () => request('GET', '/waste/forecast-accuracy'),
  getReorder: () => request('GET', '/waste/reorder'),
  getProductForecast: (itemId) => request('GET', `/products/${itemId}/forecast`),
  getProductRisk: (itemId) => request('GET', `/products/${itemId}/risk`),
  getRecommendations: (status) => request('GET', '/recommendations' + buildQuery({ status })),
  updateRecommendation: (id, status) => request('PATCH', `/recommendations/${id}`, { status }),
  runSimulation: (data) => request('POST', '/simulations', data),
  getSimulations: () => request('GET', '/simulations'),
  getNotifications: (unreadOnly = false) =>
    request('GET', '/notifications' + buildQuery({ unread_only: unreadOnly })),
  getUnreadCount: () => request('GET', '/notifications/unread-count'),
  markNotificationRead: (id) => request('POST', `/notifications/${id}/read`),
  readAllNotifications: () => request('POST', '/notifications/read-all'),
  getSurplusAllocations: () => request('GET', '/surplus/allocations'),
  updateAllocation: (id, data) => request('PATCH', `/surplus/allocations/${id}`, data),
  getDonationPartners: () => request('GET', '/surplus/partners'),
  createDonationPartner: (data) => request('POST', '/surplus/partners', data),
}
