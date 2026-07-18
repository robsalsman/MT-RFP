import React, { useState } from 'react'
import { auth } from '../api.js'
import Matt from './Matt.jsx'

export default function Login({ onSuccess }) {
  const [username, setUsername] = useState('')
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = (e) => {
    e.preventDefault()
    if (!username || pin.length !== 4 || busy) return
    setBusy(true)
    setError('')
    auth.login(username, pin)
      .then(() => onSuccess())
      .catch((err) => { setError(err.message); setPin('') })
      .finally(() => setBusy(false))
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="login-matt"><Matt state="idle" mouth={0} size={110} /></div>
        <h1>🎸 RFP Rockstar</h1>
        <p className="small">Hey, I'm Matt — sign in and let's find you some
          RFPs.</p>
        <input placeholder="Your name" autoFocus value={username}
          onChange={(e) => setUsername(e.target.value)} />
        <input placeholder="4-digit PIN" inputMode="numeric" type="password"
          maxLength={4} value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))} />
        <button className="primary" type="submit"
          disabled={busy || !username || pin.length !== 4}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
        {error && <div className="err">{error}</div>}
      </form>
    </div>
  )
}
