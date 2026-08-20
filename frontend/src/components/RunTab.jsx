import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

// The Daily Run: Matt pre-worked the leads overnight (contacts found,
// drafts written, warm replies queued first) — Kim reviews one card at a
// time. Send it / tweak-and-send / skip. Fifteen seconds a lead.
const fmtUsd = (n) => (n || n === 0)
  ? '$' + Math.round(n).toLocaleString() : '—'

export default function RunTab() {
  const [run, setRun] = useState(null)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [curId, setCurId] = useState(null)

  const load = () => api.dailyRun().then(setRun).catch(() => {})
  useEffect(() => { load() }, [])

  // poll while the build is running
  useEffect(() => {
    if (!run?.building) return undefined
    const id = setInterval(load, 8000)
    return () => clearInterval(id)
  }, [run?.building])   // eslint-disable-line

  const pending = (run?.items || []).filter((i) => i.state === 'pending')
  const cur = pending[0] || null

  // reset the editable draft when the current card changes
  useEffect(() => {
    if (cur && cur.lead_id !== curId) {
      setCurId(cur.lead_id)
      setDraft(cur.draft || '')
    }
  }, [cur, curId])

  const act = async (action) => {
    if (!cur || busy) return
    setBusy(true)
    try {
      if (action === 'sent') {
        const body = draft.replace(/^subject:\s*(.+)$/im, '').trim()
        const subjMatch = draft.match(/^subject:\s*(.+)$/im)
        const subj = subjMatch ? subjMatch[1].trim()
          : `Mission Telecom — ${cur.org}`
        window.location.href = `mailto:${cur.to_email || ''}`
          + `?subject=${encodeURIComponent(subj)}`
          + `&body=${encodeURIComponent(body)}`
      }
      await api.dailyRunAction(cur.lead_id, action)
      await load()
    } catch { /* ignore */ }
    setBusy(false)
  }

  const rebuild = async () => {
    setBusy(true)
    try { await api.dailyRunBuild(20); await load() } catch { /* ignore */ }
    setBusy(false)
  }

  if (!run) return <div className="leads-page">
    <p className="muted">Loading the run…</p></div>

  if (run.building && !run.items.length) {
    return <div className="leads-page run-center">
      <h2>🏃 Matt&apos;s prepping your run…</h2>
      <p className="muted">Finding contacts and writing drafts for the
        best {run.total || 20} untouched leads. Usually ready in a few
        minutes — this page refreshes itself.</p>
    </div>
  }

  const routed = Object.entries(run.consultant_routed || {})
  const pace = run.pace || {}

  if (!cur) {
    return <div className="leads-page run-center">
      <h2>🎉 Run cleared{run.total ? ` — ${run.done}/${run.total}` : ''}!</h2>
      {pace.touched_this_month != null && (
        <p className="muted">{pace.touched_this_month} accounts touched
          this month (~{pace.per_day}/day).
          {pace.days_to_clear_board
            ? ` At this pace the whole board is cleared in ~${pace.days_to_clear_board} days.`
            : ''}</p>)}
      {routed.length > 0 && (
        <p className="muted">Auto-routed to the consultant channel
          (no district contact): {routed.map(([c, n]) =>
            `${c} (${n})`).join(', ')} — see the 🤝 Consultants view.</p>)}
      <button className="primary" onClick={rebuild} disabled={busy}>
        ⚡ Build another run</button>
    </div>
  }

  return (
    <div className="leads-page run-wrap">
      <div className="run-progress">
        <b>🏃 Daily Run</b> · {run.done + 1} of {run.total}
        {cur.kind === 'warm' && <span className="lr-tag won">🔥 they
          replied — priority</span>}
        {run.building && <span className="muted"> · still prepping the
          rest…</span>}
      </div>

      <div className="lead-card run-card">
        <div className="run-head">
          <h2>{cur.org} <span className="lr-state">{cur.state_code}</span></h2>
          <div className="ld-facts">
            <span>{cur.competitor}</span>
            <span>{fmtUsd(cur.spend)}{cur.source === 'ecf'
              ? ' ECF (win-back)' : '/yr'}</span>
            {cur.devices ? <span>{cur.devices.toLocaleString()} lines</span> : null}
            {cur.expires && <span>contract ends {cur.expires}</span>}
          </div>
          <div className="ld-contacts">
            <b>To:</b> {cur.to_name ? `${cur.to_name} — ` : ''}
            {cur.to_email || 'no email on file'}
          </div>
          {cur.notes?.length > 0 && (
            <div className="ld-nar">Note: {cur.notes[0].text.slice(0, 160)}</div>)}
        </div>

        <div className="ld-draft">
          <textarea value={draft} rows={12}
            onChange={(e) => setDraft(e.target.value)} />
        </div>

        <div className="run-actions">
          <button className="run-send" disabled={busy || !cur.to_email}
            onClick={() => act('sent')}>
            📤 Send it</button>
          <button disabled={busy} onClick={() =>
            navigator.clipboard?.writeText(draft)}>📋 Copy</button>
          <button disabled={busy} onClick={() => act('skipped')}>
            ⏭️ Skip</button>
        </div>
        {!cur.to_email && <p className="muted">No direct email — copy the
          draft and send via LinkedIn, or skip.</p>}
      </div>
    </div>
  )
}
