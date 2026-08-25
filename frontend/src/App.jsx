import React, { useEffect, useState } from 'react'
import Dashboard from './components/Dashboard.jsx'
import RunTab from './components/RunTab.jsx'
import Guide from './components/Guide.jsx'
import Leads from './components/Leads.jsx'
import LinkedInTab from './components/LinkedInTab.jsx'
import Uploads from './components/Uploads.jsx'
import Settings from './components/Settings.jsx'
import Brain from './components/Brain.jsx'
import Home from './components/Home.jsx'
import SignalsTab from './components/SignalsTab.jsx'
import DealsTab from './components/DealsTab.jsx'
import ClosetTab from './components/ClosetTab.jsx'
import TeachTab from './components/TeachTab.jsx'
import ChatBot from './components/ChatBot.jsx'
import Login from './components/Login.jsx'
import { api, auth } from './api.js'
import { getPref, setPref, watchSystem } from './theme.js'

const THEME_ICON = { auto: '🌗', light: '☀️', dark: '🌙' }
const THEME_NEXT = { auto: 'light', light: 'dark', dark: 'auto' }

// Sidebar: grouped by Kim's workday, not by data source.
const NAV = [
  ['TODAY', [
    ['home', '🏠', 'Matt HQ'],
    ['run', '🏃', 'Daily Run'],
    ['signals', '🔔', 'Signals'],
  ]],
  ['HUNT', [
    ['dashboard', '📋', 'RFP Board'],
    ['leads', '🥊', 'Lead Board'],
    ['linkedin', '💼', 'LinkedIn'],
  ]],
  ['CLOSE', [
    ['deals', '🤝', 'Deals & Docs'],
  ]],
  ["MATT'S BRAIN", [
    ['brain', '🧠', 'His Memory'],
    ['teach', '🍎', 'Teach Him'],
  ]],
  ['SETUP', [
    ['closet', '👕', "Matt's Closet"],
    ['uploads', '📦', 'Price List & Profile'],
    ['settings', '⚙️', 'Settings'],
    ['guide', '📖', 'Guide'],
  ]],
]

const PAGES = {
  home: Home, run: RunTab, signals: SignalsTab, dashboard: Dashboard,
  leads: Leads, linkedin: LinkedInTab, deals: DealsTab, brain: Brain,
  teach: TeachTab, closet: ClosetTab, uploads: Uploads, settings: Settings,
  guide: Guide,
}

export default function App() {
  const [tab, setTab] = useState('home')
  const [health, setHealth] = useState(null)
  const [awake, setAwake] = useState(null)
  const [themePref, setThemePref] = useState(getPref())
  const [counts, setCounts] = useState({})   // live nav badges
  const [navOpen, setNavOpen] = useState(false)  // mobile drawer

  useEffect(() => watchSystem(() => setThemePref((p) => p)), [])
  const cycleTheme = () => {
    const next = THEME_NEXT[themePref] || 'auto'
    setPref(next); setThemePref(next)
  }
  const [authed, setAuthed] = useState(null)

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

  // live badge counts (cheap; refreshed every 5 min + when authed flips)
  useEffect(() => {
    if (!authed) return
    const load = () => {
      api.dailyRun().then((d) => setCounts((c) => ({ ...c,
        run: d.exists ? d.total - d.done : 0 }))).catch(() => {})
      api.alerts().then((d) => setCounts((c) => ({ ...c,
        signals: (d.alerts || []).length }))).catch(() => {})
      api.liQueue({ due_only: 1, limit: 50 }).then((d) => setCounts((c) =>
        ({ ...c, linkedin: (d.targets || []).length }))).catch(() => {})
    }
    load()
    const id = setInterval(load, 5 * 60 * 1000)
    const bump = () => load()
    window.addEventListener('mtrfp:counts', bump)
    return () => { clearInterval(id)
      window.removeEventListener('mtrfp:counts', bump) }
  }, [authed])

  // keep-awake state: poll so automatic holds (during sync/generation) show
  useEffect(() => {
    if (!authed) return undefined   // no point polling the login screen
    const tick = () => api.keepAwake().then(setAwake).catch(() => {})
    tick()
    const id = setInterval(tick, 5000)
    return () => clearInterval(id)
  }, [authed])

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

  // tell Matt which tab Kim is on (he greets tabs + answers in context)
  useEffect(() => {
    window.dispatchEvent(new CustomEvent('mtrfp:tab', { detail: { tab } }))
    setNavOpen(false)
  }, [tab])

  if (authed === null) return null
  if (!authed) return <Login onSuccess={() => setAuthed(true)} />

  const Page = PAGES[tab] || Home
  const badge = (id) => {
    const n = counts[id]
    return n > 0 ? <span className="navbadge">{id === 'run'
      ? `${n} left` : n}</span> : null
  }

  return (
    <div className="shell">
      <button className="navburger" onClick={() => setNavOpen((o) => !o)}>
        {navOpen ? '✕' : '☰'} <b>🎸 RFP Rockstar</b>
      </button>
      <aside className={`sidebar ${navOpen ? 'open' : ''}`}>
        <div className="brand">
          <div className="brand-title">🎸 RFP <em>Rockstar</em></div>
          <div className="brand-sub">
            {auth.name() ? `${auth.name()} · ` : ''}Matt, your personal
            assistant</div>
        </div>
        {NAV.map(([group, items]) => (
          <div className="navgroup" key={group}>
            <h4>{group}</h4>
            {items.map(([id, icon, label]) => (
              <button key={id}
                className={`navitem ${tab === id ? 'active' : ''}`}
                onClick={() => setTab(id)}>
                <span className="navico">{icon}</span> {label} {badge(id)}
              </button>
            ))}
          </div>
        ))}
        <div className="sidefoot">
          <button className="theme" onClick={cycleTheme}
            title={`Theme: ${themePref} (auto follows your computer)`}>
            {THEME_ICON[themePref]} {themePref[0].toUpperCase()
              + themePref.slice(1)}
          </button>
          {awake?.supported && (
            <button className={`keepawake ${awake.on ? 'on' : ''}`}
              onClick={toggleAwake}
              title={autoHold
                ? 'Staying awake automatically while a job runs'
                : awake.on
                  ? 'Keep-awake on — click to turn off.'
                  : 'Prevent this machine from sleeping'}>
              {awake.on ? '☕ Awake' : '☀ Keep awake'}
              {autoHold ? ' (auto)' : ''}
            </button>
          )}
          {health && !health.ai_provider && (
            <div className="small warn">AI off — set NEMOTRON_API_KEY</div>)}
        </div>
      </aside>
      <main className="content">
        <Page />
      </main>
      <ChatBot />
    </div>
  )
}
