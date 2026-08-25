import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

// Signals: the buying signals Matt watches for — new Form 470s from
// engaged districts (they legally entered the market) and deals gone quiet.

const askMatt = (text) =>
  window.dispatchEvent(new CustomEvent('mtrfp:ask', { detail: { text } }))

const KIND = {
  form470: ['📋', 'Buying signal', 'A district Kim is talking to just filed a Form 470 — they are legally in the market right now.'],
  stale: ['💤', 'Gone quiet', 'An engaged deal has sat past its stage threshold — silence never gets to kill a deal.'],
}

export default function SignalsTab() {
  const [alerts, setAlerts] = useState(null)

  const load = () => api.alerts()
    .then((d) => setAlerts(d.alerts || [])).catch(() => setAlerts([]))
  useEffect(() => { load() }, [])

  const dismiss = (id) => api.alertsSeen([id]).then(() => {
    setAlerts((a) => a.filter((x) => x.id !== id))
    window.dispatchEvent(new Event('mtrfp:counts'))
  })

  if (alerts === null) return <div>Loading…</div>

  return (
    <div>
      <div className="card">
        <h3>🔔 Signals — what Matt is watching for you</h3>
        <p className="small">Every engaged district's BEN is watched for new
          Form 470 filings (the legal "we're buying" signal), and quiet
          deals get resurfaced before silence kills them. Checks run all
          day; each signal fires exactly once.</p>
      </div>
      {alerts.length === 0 && (
        <div className="card"><p className="small">All quiet right now. When
          a watched district files a 470 or a deal goes stale, it lands
          here — and Matt will bring it up himself.</p></div>)}
      {alerts.map((a) => {
        const [icon, label, why] = KIND[a.kind] || ['🔔', a.kind, '']
        return (
          <div className="card signal" key={a.id}>
            <div className="signal-head">
              <span className="signal-kind">{icon} {label}</span>
              <span className="small">{(a.created_at || '').slice(0, 16)
                .replace('T', ' ')}</span>
            </div>
            <p>{a.message}</p>
            {why && <p className="small">{why}</p>}
            <div className="signal-actions">
              {a.kind === 'form470' && (
                <button className="primary" onClick={() =>
                  askMatt(`A 470 alert just fired: "${a.message}" — what's `
                    + 'the play? Draft what I need.')}>
                  💬 Ask Matt for the play</button>)}
              {a.kind !== 'form470' && a.lead_id && (
                <button className="primary" onClick={() =>
                  askMatt(`Draft a follow-up for the quiet deal: `
                    + `"${a.message}"`)}>💬 Draft the follow-up</button>)}
              <button onClick={() => dismiss(a.id)}>✓ Seen it</button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
