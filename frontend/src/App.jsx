import React, { useEffect, useState } from 'react'
import Dashboard from './components/Dashboard.jsx'
import Uploads from './components/Uploads.jsx'
import Settings from './components/Settings.jsx'
import ChatBot from './components/ChatBot.jsx'
import { api } from './api.js'

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [health, setHealth] = useState(null)

  useEffect(() => { api.health().then(setHealth).catch(() => {}) }, [])

  // assistant-driven navigation (tab switch; Dashboard handles the rest)
  useEffect(() => {
    const onNav = (e) => { if (e.detail?.tab) setTab(e.detail.tab) }
    window.addEventListener('mtrfp:navigate', onNav)
    return () => window.removeEventListener('mtrfp:navigate', onNav)
  }, [])

  return (
    <>
      <header className="topbar">
        <h1>MT-RFP</h1>
        <span className="sub">Mission Telecom &middot; E-Rate &amp; K-12/Library
          RFP Intelligence</span>
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
