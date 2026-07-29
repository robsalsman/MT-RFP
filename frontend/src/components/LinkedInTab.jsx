import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

// The LinkedIn workspace: a scored queue of contacts, one button per
// cadence step. Press ▶ and three things happen at once: the message is
// on the clipboard, the pre-filtered search opens in Kim's own logged-in
// Sales Navigator, and after she sends she taps ✓ — the touch is logged
// on the lead, the next step gets a due date, the funnel moves.
const fmtUsd = (n) => (n || n === 0)
  ? '$' + Math.round(n).toLocaleString() : '—'

const STEP_ICON = { connect: '🤝', dm1: '💬', dm2: '🎁', dm3: '👋',
  inmail: '📧' }

export default function LinkedInTab() {
  const [data, setData] = useState(null)
  const [dueOnly, setDueOnly] = useState(false)
  const [open, setOpen] = useState(null)
  const [busy, setBusy] = useState(false)
  const [fired, setFired] = useState({})    // target_id -> copied+opened

  const load = () => api.liQueue({ due_only: dueOnly, limit: 50 })
    .then(setData).catch(() => {})
  useEffect(() => { load() }, [dueOnly])   // eslint-disable-line

  const buildTop = async () => {
    setBusy(true)
    try { await api.liBuildTop(8); await load() } catch { /* ignore */ }
    setBusy(false)
  }

  const doStep = (t) => {
    navigator.clipboard?.writeText(t.message || '')
    window.open(t.sales_nav_url, '_blank', 'noopener')
    setFired((f) => ({ ...f, [t.target_id]: true }))
  }

  const markSent = async (t) => {
    setBusy(true)
    try { await api.liStep(t.target_id, t.next_step); await load() }
    catch { /* ignore */ }
    setFired((f) => ({ ...f, [t.target_id]: false }))
    setBusy(false)
  }

  if (!data) return <div className="leads-page">
    <p className="muted">Loading the LinkedIn queue…</p></div>

  const targets = data.targets || []
  const dueNow = targets.filter((t) => t.due_now).length

  return (
    <div className="leads-page">
      <div className="leads-summary">
        <div className="lead-sum sel">
          <span className="ls-label">Today's touches</span>
          <span className="ls-big">{dueNow}</span>
          <span className="ls-sub">{targets.length} in the queue</span>
        </div>
        <button className="lead-sum" onClick={buildTop} disabled={busy}>
          <span className="ls-label">Feed the queue</span>
          <span className="ls-big">⚡</span>
          <span className="ls-sub">add targets from top leads</span>
        </button>
        <button className={`lead-sum ${dueOnly ? 'sel' : ''}`}
          onClick={() => setDueOnly(!dueOnly)}>
          <span className="ls-label">Filter</span>
          <span className="ls-big">📅</span>
          <span className="ls-sub">{dueOnly ? 'due today only' : 'showing all'}</span>
        </button>
      </div>

      <p className="muted li-doctrine">How it works: ▶ copies the message
        and opens the search in <b>your</b> Sales Navigator — find the
        person, paste, personalize one line, send, then tap ✓ Sent. Matt
        logs the touch and schedules the next one. (You send everything —
        automating LinkedIn accounts breaks their rules.)</p>

      <div className="leads-list">
        {targets.map((t) => (
          <div key={t.target_id}
            className={`lead-card ${t.due_now ? '' : 'contacted'}`}>
            <button className="lead-row" onClick={() =>
              setOpen(open === t.target_id ? null : t.target_id)}>
              <span className="lr-org">{t.person}
                <span className="lr-state">{t.title}</span>
              </span>
              <span className="lr-comp">{t.org} ({t.state})</span>
              <span className="lr-spend">{STEP_ICON[t.next_step] || '•'}{' '}
                {t.next_step_label}</span>
              <span className={`lr-exp ${t.due_now ? 'li-due' : ''}`}>
                {t.due_now ? 'DUE NOW' : `due ${t.due}`}</span>
            </button>

            {open === t.target_id && (
              <div className="lead-detail">
                <div className="ld-facts">
                  <span>{t.competitor} account</span>
                  <span>{fmtUsd(t.spend)}{t.source === 'ecf'
                    ? ' ECF total (win-back)' : '/yr'}</span>
                  {t.expires && <span>contract ends {t.expires}</span>}
                  <span>deal stage: {t.lead_stage}</span>
                  <span>steps done: {Object.keys(t.steps_done).length
                    ? Object.keys(t.steps_done).join(' → ') : 'none yet'}</span>
                </div>

                <div className="ld-draft">
                  <textarea readOnly rows={5} value={t.message
                    || '(no message for this step)'} />
                </div>

                <div className="ld-actions">
                  <button className="li-go" disabled={busy}
                    onClick={() => doStep(t)}>
                    ▶ Copy message + open Sales Nav</button>
                  <a className="btn" href={t.linkedin_url} target="_blank"
                    rel="noreferrer">plain LinkedIn</a>
                  {fired[t.target_id] && (
                    <button className="li-sent" disabled={busy}
                      onClick={() => markSent(t)}>
                      ✓ Sent — schedule next step</button>)}
                </div>
              </div>
            )}
          </div>
        ))}
        {targets.length === 0 && (
          <p className="muted">Queue's empty — hit ⚡ to pull targets from
            your top leads, or open any lead on the Leads board and press
            💼.</p>)}
      </div>
    </div>
  )
}
