import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { register, login } from '../api'
import './LeadLogin.css'

export default function LeadLogin() {
  const navigate = useNavigate()
  const [mode, setMode] = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const token = localStorage.getItem('token')
  if (token) {
    navigate('/chat', { replace: true })
    return null
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mode === 'register') {
        if (!name.trim() || !email.trim()) {
          setError('Name and email required')
          return
        }
        const data = await register({ username, name: name.trim(), email: email.trim(), password })
        localStorage.setItem('token', data.session_token)
        localStorage.setItem('user', JSON.stringify(data.user))
        navigate('/chat', { replace: true })
      } else {
        const data = await login({ username, password })
        localStorage.setItem('token', data.session_token)
        localStorage.setItem('user', JSON.stringify(data.user))
        navigate('/chat', { replace: true })
      }
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="lead-login">
      <div className="lead-login-card">
        <h1>Broker Chat</h1>
        <p className="lead-login-sub">Sign in or register to chat with your broker</p>
        <form onSubmit={handleSubmit}>
          {mode === 'register' && (
            <>
              <input
                type="text"
                placeholder="Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
              />
              <input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
              />
            </>
          )}
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoComplete="username"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          />
          {error && <p className="lead-login-error">{error}</p>}
          <button type="submit" disabled={loading}>
            {loading ? '...' : mode === 'login' ? 'Log in' : 'Register'}
          </button>
        </form>
        <p className="lead-login-toggle">
          {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
          <button type="button" className="link" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}>
            {mode === 'login' ? 'Register' : 'Log in'}
          </button>
        </p>
      </div>
      <p className="lead-login-broker">
        <a href="/broker">Broker dashboard →</a>
      </p>
    </div>
  )
}
