export function RiskBadge({ level }) {
  const map = { low: ['badge-green', 'Low'], medium: ['badge-amber', 'Medium'], high: ['badge-red', 'High'] }
  const [cls, label] = map[level] || ['badge-gray', level]
  return <span className={`badge ${cls}`}>{label}</span>
}

export function TypeBadge({ type }) {
  const map = {
    purchase: ['badge-green', 'Purchase'],
    sale: ['badge-gray', 'Sale'],
    donation: ['badge-green', 'Donation'],
    disposal: ['badge-red', 'Disposal'],
    adjustment: ['badge-amber', 'Adjustment'],
  }
  const [cls, label] = map[type] || ['badge-gray', type]
  return <span className={`badge ${cls}`}>{label}</span>
}

export function ExpiryBadge({ status }) {
  const map = {
    expired: ['badge-red', 'Expired'],
    expiring_soon: ['badge-amber', 'Expiring soon'],
    expiring: ['badge-amber', 'Expiring'],
    fresh: ['badge-green', 'Fresh'],
    no_expiry: ['badge-gray', 'No expiry'],
  }
  const [cls, label] = map[status] || ['badge-gray', status]
  return <span className={`badge ${cls}`}>{label}</span>
}

export function Risk4Badge({ level }) {
  const map = {
    low: ['badge-green', 'Low'],
    moderate: ['badge-amber', 'Moderate'],
    high: ['badge-red', 'High'],
    critical: ['badge-critical', 'Critical'],
  }
  const [cls, label] = map[level] || ['badge-gray', level]
  return <span className={`badge ${cls}`}>{label}</span>
}

export function SeverityBadge({ level }) {
  const map = {
    low: ['badge-green', 'Low'],
    medium: ['badge-amber', 'Medium'],
    high: ['badge-red', 'High'],
    critical: ['badge-critical', 'Critical'],
  }
  const [cls, label] = map[level] || ['badge-gray', level]
  return <span className={`badge ${cls}`}>{label}</span>
}

export function StatusBadge({ status }) {
  const map = {
    pending: ['badge-amber', 'Pending'],
    applied: ['badge-green', 'Applied'],
    rejected: ['badge-gray', 'Rejected'],
    expired: ['badge-gray', 'Expired'],
    open: ['badge-amber', 'Open'],
    resolved: ['badge-green', 'Resolved'],
    active: ['badge-green', 'Active'],
    inactive: ['badge-gray', 'Inactive'],
  }
  const [cls, label] = map[status] || ['badge-gray', status]
  return <span className={`badge ${cls}`}>{label}</span>
}

export function riskLevelColor(level) {
  return { low: '#16a34a', moderate: '#d97706', high: '#dc2626', critical: '#7f1d1d' }[level] || '#6b7280'
}
