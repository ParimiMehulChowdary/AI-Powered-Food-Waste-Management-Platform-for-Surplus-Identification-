import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function RegisterPage() {
  const { register, login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ business_name: '', email: '', password: '', contact: '', address: '', role: 'business' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function onChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await register(form)
      await login(form.email, form.password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <h2>Create your account</h2>
        <p className="sub">Register your food business to manage inventory</p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <label>Business name</label>
          <input name="business_name" value={form.business_name} onChange={onChange} required />
          <label>Email</label>
          <input type="email" name="email" value={form.email} onChange={onChange} required />
          <label>Contact</label>
          <input name="contact" value={form.contact} onChange={onChange} />
          <label>Address</label>
          <input name="address" value={form.address} onChange={onChange} />
          <label>Password</label>
          <input type="password" name="password" value={form.password} onChange={onChange} required minLength={6} />
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Creating...' : 'Create account'}
          </button>
        </form>
        <div className="auth-switch">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  )
}
