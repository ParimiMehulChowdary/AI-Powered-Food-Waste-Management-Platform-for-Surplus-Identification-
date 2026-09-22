import { useEffect, useState } from 'react'
import { NavLink, Outlet, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { api } from '../services/api.js'

const navItems = [
  { to: '/', label: 'AI Dashboard', end: true },
  { to: '/inventory', label: 'Inventory' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/risk', label: 'Risk' },
  { to: '/recommendations', label: 'Recommendations' },
  { to: '/anomalies', label: 'Anomalies' },
  { to: '/simulation', label: 'Simulation' },
  { to: '/transactions', label: 'Transactions' },
  { to: '/categories', label: 'Categories' },
  { to: '/settings', label: 'Settings' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const [unread, setUnread] = useState(0)

  useEffect(() => {
    let cancelled = false
    async function poll() {
      try {
        const data = await api.getUnreadCount()
        if (!cancelled) setUnread(data.count || 0)
      } catch {
        /* ignore transient errors */
      }
    }
    poll()
    const t = setInterval(poll, 30000)
    return () => {
      cancelled = true
      clearInterval(t)
    }
  }, [])

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">🥗 <span>FoodWaste</span> Platform</div>
        <nav>
          {navItems.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? 'active' : '')}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="logout">
          <button onClick={logout}>Logout</button>
        </div>
      </aside>
      <div className="main">
        <div className="topbar">
          <h1>Inventory & Expiry Tracking</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <Link to="/notifications" className="bell" title="Notifications">
              🔔
              {unread > 0 && <span className="bell-dot">{unread > 99 ? '99+' : unread}</span>}
            </Link>
            <div className="user">{user?.business_name} · {user?.email}</div>
          </div>
        </div>
        <div className="content">
          <Outlet />
        </div>
      </div>
    </div>
  )
}