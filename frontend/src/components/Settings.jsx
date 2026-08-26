import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Settings() {
  const [settings, setSettings] = useState(null)
  const [msg, setMsg] = useState('')
  const [vibe, setVibe] = useState(null)

  useEffect(() => { api.settings().then(setSettings) }, [])
  useEffect(() => {
    api.getVibe().then((d) => setVibe(d.vibe)).catch(() => {})
  }, [])
  const saveVibe = (v) => {
    setVibe(v)
    api.setVibe(v).catch(() => {})
  }
  const [focus, setFocus] = useState(null)
  useEffect(() => {
    api.runFocus().then((d) => setFocus(d.focus)).catch(() => {})
  }, [])
  const [focusMsg, setFocusMsg] = useState('')
  const saveFocus = (f) => {
    setFocus(f)
    api.setRunFocus(f).then(() => {
      // today's run was built under the old focus — Matt refills the
      // slots you haven't worked yet, in the background
      setFocusMsg('Refilling today\u2019s run\u2026 check the Run tab.')
      setTimeout(() => setFocusMsg(''), 6000)
    }).catch(() => {})
  }
  if (!settings) return <div>Loading…</div>

  const w = settings.scoring_weights
  const sf = settings.strategic_fit

  const save = () => {
    api.saveSettings(settings).then((s) => {
      setSettings(s); setMsg('Saved — all open RFPs rescored.')
      setTimeout(() => setMsg(''), 3000)
    })
  }
  const setW = (k, v) => setSettings({ ...settings,
    scoring_weights: { ...w, [k]: Number(v) || 0 } })
  const setSF = (k, v) => setSettings({ ...settings,
    strategic_fit: { ...sf, [k]: v } })

  return (
    <div className="grid2">
      <div className="card">
        <h3>Matt&apos;s vibe — pick your rating</h3>
        <p className="small">How Matt talks to <b>you</b>. Personal
          setting, applies only to your account, change it any time.
          (Heads up: like everything in the app, chats are stored in the
          app&apos;s database.)</p>
        {[
          ['professional', 'G', 'Strictly professional — crisp, courteous, zero showmanship'],
          ['classic', 'PG', 'Rockstar teammate (default) — warm, hype, big compliments'],
          ['flirty', 'PG-13', 'Charming & flirty — playful rom-com banter; tasteful, and the work still comes first'],
        ].map(([v, rating, desc]) => (
          <label key={v} style={{ display: 'block', margin: '7px 0' }}>
            <input type="radio" name="vibe" checked={vibe === v}
              onChange={() => saveVibe(v)} />{' '}
            <b>{rating}</b> — {desc}
          </label>
        ))}
        <p className="small">That&apos;s the whole scale — it tops out at
          PG-13 by design.</p>
        {vibe === null && <p className="small">Loading…</p>}
      </div>
      <div className="card">
        <h3>Daily Run focus</h3>
        <p className="small">What Matt loads into the Daily Run.</p>
        {[['all', 'Everything - best leads regardless of type'],
          ['libraries', 'Libraries only - schools stay off the run']]
          .map(([f, desc]) => (
            <label key={f} style={{ display: 'block', margin: '6px 0' }}>
              <input type="radio" name="runfocus" checked={focus === f}
                onChange={() => saveFocus(f)} /> {desc}
            </label>
          ))}
        {focusMsg && <p className="small">{focusMsg}</p>}
      </div>
      <div className="card">
        <h3>Scoring weights</h3>
        <p className="small">Points per bucket (default 40/20/20/20 = 100).</p>
        {Object.entries(w).map(([k, v]) => (
          <div className="formrow" key={k}>
            <label>{k.replace('_', ' ')}</label>
            <input type="number" value={v}
              onChange={(e) => setW(k, e.target.value)} />
          </div>))}
        <div className="formrow">
          <label>Deal size: full points at annual spend ($)</label>
          <input type="number"
            value={settings.deal_size.full_points_at_annual_spend}
            onChange={(e) => setSettings({ ...settings, deal_size:
              { ...settings.deal_size,
                full_points_at_annual_spend: Number(e.target.value) || 0 } })} />
        </div>
      </div>
      <div className="card">
        <h3>Strategic fit</h3>
        <div className="formrow">
          <label>Priority states (comma-separated)</label>
          <input value={(sf.priority_states || []).join(', ')}
            onChange={(e) => setSF('priority_states',
              e.target.value.split(',').map((s) => s.trim().toUpperCase())
                .filter(Boolean))} />
        </div>
        <div className="formrow">
          <label>Points for priority state</label>
          <input type="number" value={sf.priority_state_points}
            onChange={(e) => setSF('priority_state_points',
              Number(e.target.value) || 0)} />
        </div>
        <div className="formrow">
          <label>Min contract years for multi-year bonus</label>
          <input type="number" value={sf.preferred_contract_years_min}
            onChange={(e) => setSF('preferred_contract_years_min',
              Number(e.target.value) || 0)} />
        </div>
        <div className="formrow">
          <label>Multi-year bonus points</label>
          <input type="number" value={sf.multi_year_points}
            onChange={(e) => setSF('multi_year_points',
              Number(e.target.value) || 0)} />
        </div>
        <button className="primary" onClick={save}>Save & rescore</button>
        {' '}<span className="ok">{msg}</span>
      </div>
    </div>
  )
}
