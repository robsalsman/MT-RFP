import React, { useEffect, useState } from 'react'
import { api, auth } from '../api.js'

// Matt HQ — Kim's landing page: one-glance morning status plus the
// capability grid ("everything Matt does for you"). Every card carries a
// magic-words chip that literally sends that phrase to Matt.

const goTab = (tab) =>
  window.dispatchEvent(new CustomEvent('mtrfp:navigate', { detail: { tab } }))
const askMatt = (text) =>
  window.dispatchEvent(new CustomEvent('mtrfp:ask', { detail: { text } }))

const CAPS = [
  ['🏃', 'Daily Run', 'He pre-works your 20 best leads overnight — you just hit Send, tweak, or Skip. 15 seconds a lead.', 'start my daily run', 'run'],
  ['📚', 'Library Leads', '7,000+ US libraries ranked by real need (lost ACP homes, bookmobiles, budgets). Never runs dry.', 'get me more library leads', 'leads'],
  ['🥊', 'Competitor Takeaways', 'Who pays Kajeet, AT&T, Verizon — how much, and when the contract expires. Timing is everything.', 'find the AT&T libraries', 'leads'],
  ['✉️', 'Outreach & Follow-ups', 'Emails from THEIR real numbers — and he remembers the last one, so #2 never repeats #1.', 'draft a follow-up for my hottest lead', null],
  ['🧠', 'His Second Brain', 'He remembers everything: you, every account, what works. Browse or edit it all — zero mystery.', null, 'brain', 'brainy'],
  ['🍎', 'Teach Him', 'Sticky notes, PDFs, spreadsheets, any web link — he reads it, files it, and uses it forever.', null, 'teach', 'brainy'],
  ['🎛️', 'Retune His Hunting', 'Change what he looks for by just telling him — no developer. Current tuning shows on the Teach Him page.', 'from now on skip anything with "academy" in the name', null, 'brainy'],
  ['🌐', 'Live Web Search', 'Grants, news, people, phone numbers — he searches the real web and can memorize any page.', 'search the web for library hotspot grant programs', null],
  ['💼', 'LinkedIn Wingman', 'Scored contact queue with ready messages on a cadence. He aims, you send — always your account.', 'who should I connect with today?', 'linkedin'],
  ['📄', 'Closing Docs', 'Savings sheet, board champion kit, case study — the paperwork that turns "maybe" into signed.', 'make a savings sheet for my closest deal', 'deals'],
  ['🛡️', 'Objection Counters', 'Paste any "no" — he names the objection and writes the reply that keeps the door open.', 'they said they doubt T-Mobile coverage — help me answer', null],
  ['🤝', 'Consultant Channel', 'One consultant = 80+ districts. He drafts the partnership pitch that makes THEM look good.', 'pitch the top E-Rate consultants', null],
]

function partOfDay() {
  const h = new Date().getHours()
  if (h < 12) return ['Morning', 'best send window 8–10am']
  if (h < 15) return ['Afternoon', 'midday check-in — keep the streak']
  if (h < 18) return ['Afternoon', 'second send window 3–5pm']
  return ['Evening', 'wind down — tomorrow’s run builds itself']
}

export default function Home() {
  const [run, setRun] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [q, setQ] = useState('')
  const name = auth.name() || 'Kim'
  const [pod, tip] = partOfDay()

  useEffect(() => {
    api.dailyRun().then(setRun).catch(() => {})
    api.alerts().then((d) => setAlerts(d.alerts || [])).catch(() => {})
  }, [])

  const total = run?.total || 0
  const done = run?.done || 0
  const left = total - done
  const next = (run?.items || []).find((i) => i.state === 'pending')
  const pace = run?.pace
  const pct = total ? Math.round((done / total) * 100) : 0
  const date = new Date().toLocaleDateString(undefined,
    { weekday: 'short', month: 'short', day: 'numeric' })

  const ask = () => { if (q.trim()) { askMatt(q.trim()); setQ('') } }

  return (
    <div className="hq">
      <div className="hq-top">
        <h2 className="hq-hi">{pod === 'Evening' ? 'Evening' : pod === 'Afternoon' ? 'Afternoon' : 'Morning'}, <span>{name}</span>! 🎤</h2>
        <span className="hq-clock">{date} · <b>{pod} set</b> — {tip}</span>
        <div className="hq-ask">
          <input value={q} placeholder="Ask Matt anything — leads, his memory, the web…"
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && ask()} />
          <button className="primary" onClick={ask}>Ask</button>
        </div>
      </div>

      <div className="hq-row">
        <div className="card hq-card" style={{ flex: 1.35 }}>
          <h3>🏃 TODAY'S RUN</h3>
          {run?.building ? (
            <p className="small">Matt's building today's run — contacts and
              drafts are being prepped right now. Check back in a few
              minutes.</p>
          ) : total ? (
            <div className="hq-runline">
              <div className="hq-ring"
                style={{ background: `conic-gradient(var(--accent) ${pct * 3.6}deg, var(--line) 0deg)` }}>
                <div><b>{done}</b><small>of {total}</small></div>
              </div>
              <div className="hq-runtext">
                {left > 0 ? (<>
                  <b>{left} lead{left === 1 ? '' : 's'} left, all
                  pre-worked</b> — contact found, draft written.<br />
                  {next && <>Next up: <b>{next.org}</b>
                    {next.competitor ? ` · ${next.competitor}` : ''}<br /></>}
                </>) : <><b>Run cleared — that's a platinum record. 🏆</b>
                  <br /></>}
                <button className="primary" onClick={() => goTab('run')}>
                  {left > 0 ? '▶ Continue the run' : '⚡ Build another run'}
                </button>
              </div>
            </div>
          ) : (
            <p className="small">No run yet today — open the Daily Run and
              Matt will build one.
              {' '}<button onClick={() => goTab('run')}>Go</button></p>
          )}
        </div>
        <div className="card hq-card" style={{ flex: 1.15 }}>
          <h3>🔔 BUYING SIGNALS</h3>
          {alerts.length === 0 && (
            <p className="small">All quiet — no new signals. Matt watches
              every engaged district's Form 470s around the clock.</p>)}
          {alerts.slice(0, 3).map((a) => (
            <div className="hq-alert" key={a.id}>
              {a.kind === 'form470' ? '📋' : '💤'} <span>{a.message}</span>
            </div>
          ))}
          {alerts.length > 0 && (
            <button onClick={() => goTab('signals')}>
              View all {alerts.length}</button>)}
        </div>
        <div className="card hq-card" style={{ flex: 0.8 }}>
          <h3>📈 PACE</h3>
          <div className="hq-pace">{pace?.touched_this_month ?? '—'}</div>
          <p className="small">touches this month
            {pace?.per_day ? <> · <b>{pace.per_day}/day</b></> : null}
            {pace?.days_to_clear_board ? (<><br />Board clear in
              ~<b>{pace.days_to_clear_board} days</b> 🏆</>) : null}
            {pace ? (<><br />{pace.untouched_leads?.toLocaleString()} leads
              still untouched — plenty of encore.</>) : null}
          </p>
        </div>
      </div>

      <div className="hq-caphead">
        <h2>Everything Matt does for you</h2>
        <span>— click a card to go there, or the 💬 chip to just say the
          magic words</span>
      </div>
      <div className="hq-grid">
        {CAPS.map(([icon, title, desc, phrase, tab, cls]) => (
          <div key={title} className={`hq-cap ${cls || ''}`}
            onClick={() => tab ? goTab(tab) : phrase && askMatt(phrase)}>
            <div className="hq-ico">{icon}</div>
            <h5>{title}</h5>
            <p>{desc}</p>
            {phrase && (
              <button className="hq-try" onClick={(e) => {
                e.stopPropagation(); askMatt(phrase)
              }}>💬 “{phrase}”</button>)}
            {!phrase && tab === 'brain' && (
              <button className="hq-try" onClick={(e) => {
                e.stopPropagation(); goTab('brain')
              }}>🧠 browse his memory</button>)}
            {!phrase && tab === 'teach' && (
              <button className="hq-try" onClick={(e) => {
                e.stopPropagation(); goTab('teach')
              }}>🍎 teach him something</button>)}
          </div>
        ))}
      </div>
    </div>
  )
}
