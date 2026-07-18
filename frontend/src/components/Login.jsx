import React, { useState } from 'react'
import { auth } from '../api.js'

export default function Login({ onSuccess }) {
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = (e) => {
    e.preventDefault()
    if (!password || busy) return
    setBusy(true)
    setError('')
    auth.login(password)
      .then(() => onSuccess())
      .catch((err) => setError(err.message))
      .finally(() => setBusy(false))
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <h1>MT-RFP</h1>
        <p className="small">Mission Telecom RFP Intelligence — team access</p>
        <input type="password" autoFocus placeholder="Team password"
          value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="primary" type="submit"
          disabled={busy || !password}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
        {error && <div className="err">{error}</div>}
      </form>
    </div>
  )
}
