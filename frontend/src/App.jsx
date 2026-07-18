import React, { useEffect, useState } from 'react'
import Dashboard from './components/Dashboard.jsx'
import Uploads from './components/Uploads.jsx'
import Settings from './components/Settings.jsx'
import ChatBot from './components/ChatBot.jsx'
import Login from './components/Login.jsx'
import { api, auth } from './api.js'

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [health, setHealth] = useState(null)
  const [awake, setAwake] = useState(null)
  const [authed, setAuthed] = useState(null)  // null=unknown, bool once known

  useEffect(() => {
    api.health().then((h) => {
      setHealth(h)
      setAuthed(!h.auth_required || auth.isSet())
    }).catch(() => setAuthed(true))
  }, [])

  useEffect(() => {
    const onUnauth = () => setAuthed(false)
    window.addEventListener('mtrfp:unauthorized', onUnauth)
    return () => window.removeEventListener('mtrfp:unauthorized', onUnauth)
  }, [])

  // keep-awake state: poll so automatic holds (during sync/generation) show
  useEffect(() => {
    const tick = () => api.keepAwake().then(setAwake).catch(() => {})
    tick()
    const id = setInterval(tick, 5000)
    return () => clearInterval(id)
  }, [])

  const toggleAwake = () => {
    const next = !(awake?.on)
    api.setKeepAwake(next).then(setAwake).catch(() => {})
  }
  const autoHold = (awake?.holds || []).some((h) => h !== 'manual')

  // assistant-driven navigation (tab switch; Dashboard handles the rest)
  useEffect(() => {
    const onNav = (e) => { if (e.detail?.tab) setTab(e.detail.tab) }
    window.addEventListener('mtrfp:navigate', onNav)
    return () => window.removeEventListener('mtrfp:navigate', onNav)
  }, [])

  if (authed === null) return null  // brief: waiting on /api/health
  if (!authed) return <Login onSuccess={() => setAuthed(true)} />

  return (
    <>
      <header className="topbar">
        <h1>🎸 RFP Rockstar</h1>
        <span className="sub">
          {auth.name() ? `Hey ${auth.name()} · ` : ''}Mission Telecom
          &middot; E-Rate &amp; K-12/Library RFP Intelligence</span>
        {health && !health.ai_provider && (
          <span className="sub warn">AI analysis off — set NEMOTRON_API_KEY
            in .env</span>
        )}
        {health?.ai_provider && (
          <span className="sub">AI: {health.ai_provider}</span>
        )}
        <nav>
          {[['dashboard', 'Dashboard'], ['uploads', 'Price List & Profile'],
            ['settings', 'Settings']].map(([id, label]) => (
            <button key={id} className={tab === id ? 'active' : ''}
              onClick={() => setTab(id)}>{label}</button>
          ))}
          {awake?.supported && (
            <button className={`keepawake ${awake.on ? 'on' : ''}`}
              onClick={toggleAwake}
              title={autoHold
                ? 'Staying awake automatically while a job runs'
                : awake.on
                  ? 'Keep-awake on — the machine will not sleep. Click to turn off.'
                  : 'Prevent this machine from sleeping while the assistant works'}>
              {awake.on ? '☕ Awake' : '☀ Keep awake'}
              {autoHold ? ' (auto)' : ''}
            </button>
          )}
        </nav>
      </header>
      <main className="wrap">
        {tab === 'dashboard' && <Dashboard />}
        {tab === 'uploads' && <Uploads />}
        {tab === 'settings' && <Settings />}
      </main>
      <ChatBot />
    </>
  )
}
