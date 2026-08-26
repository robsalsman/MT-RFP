import React, { useEffect, useState } from 'react'
import { api, authFetch } from '../api.js'

// Competitor displacement board: every district paying a Mission Telecom
// competitor for mobile broadband (nationwide USAC 471 sweep). Fully
// filterable (competitor / state / status / min spend) and sortable by any
// column — click a header to sort, click again to flip direction.
const fmtUsd = (n) => (n || n === 0)
  ? '$' + Math.round(n).toLocaleString() : '—'

const COLS = [
  ['org', 'Organization'],
  ['competitor', 'Competitor'],
  ['spend', 'Annual spend'],
  ['expiration', 'Contract ends'],
  ['status', 'Status'],
]

export default function Leads() {
  const [data, setData] = useState(null)
  const [competitor, setCompetitor] = useState('')
  const [state, setState] = useState('')
  const [status, setStatus] = useState('')       // '' = active (not dismissed)
  const [minSpend, setMinSpend] = useState('')
  const [librariesOnly, setLibrariesOnly] = useState(false)
  const [sort, setSort] = useState({ field: 'spend', dir: 'desc' })
  const [open, setOpen] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [sweeping, setSweeping] = useState(false)
  const [view, setView] = useState('accounts')   // 'accounts' | 'consultants'
  const [consultants, setConsultants] = useState(null)
  const [pitch, setPitch] = useState({})          // name -> {draft,to}|'busy'

  useEffect(() => {
    if (view === 'consultants' && !consultants) {
      api.consultants(30).then((d) =>
        setConsultants(d.consultants || [])).catch(() => {})
    }
  }, [view])   // eslint-disable-line

  const draftPitch = async (name) => {
    setPitch((p) => ({ ...p, [name]: 'busy' }))
    try {
      const d = await api.consultantPitch(name)
      setPitch((p) => ({ ...p, [name]: d }))
    } catch { setPitch((p) => ({ ...p, [name]: null })) }
  }

  const load = () => api.competitorLeads({
    competitor, state, status, min_spend: minSpend || 0,
    libraries_only: librariesOnly || '',
    sort: sort.field, direction: sort.dir, limit: 100,
  }).then(setData).catch(() => {})
  useEffect(() => { load() },   // eslint-disable-line
    [competitor, state, status, minSpend, librariesOnly, sort])

  // deep-link from Matt's greeting: open the lead he recommended
  useEffect(() => {
    if (window.__openLeadId) {
      setOpen(window.__openLeadId)
      window.__openLeadId = null
    }
  }, [])

  const clickSort = (field) => setSort((s) => ({
    field,
    dir: s.field === field ? (s.dir === 'asc' ? 'desc' : 'asc')
      : (field === 'spend' ? 'desc' : 'asc'),
  }))

  const sweep = async () => {
    setSweeping(true)
    try { await api.competitorSweep() } catch { /* ignore */ }
    setTimeout(load, 15000); setTimeout(() => { load(); setSweeping(false) }, 45000)
  }

  const act = async (id, fn) => {
    setBusyId(id)
    try { await fn(); await load() } catch { /* ignore */ }
    setBusyId(null)
  }

  const copyDraft = (text) => navigator.clipboard?.writeText(text)

  const STAGES = ['new', 'contacted', 'replied', 'meeting', 'quote',
    'verbal', 'won', 'lost']
  const [liBusy, setLiBusy] = useState(null)

  // build this lead's LinkedIn targets, then jump to the LinkedIn tab
  const addToLinkedIn = async (id) => {
    setLiBusy(id)
    try {
      await api.leadLinkedIn(id)
      window.dispatchEvent(new CustomEvent('mtrfp:navigate',
        { detail: { tab: 'linkedin' } }))
    } catch { /* ignore */ }
    setLiBusy(null)
  }

  const downloadDoc = async (id, kind) => {
    setBusyId(id)
    try {
      const r = await authFetch(`/api/competitor-leads/${id}/doc?kind=${kind}`)
      if (!r.ok) return
      const blob = await r.blob()
      const cd = r.headers.get('Content-Disposition') || ''
      const m = cd.match(/filename="?([^\";]+)/)
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = (m && m[1]) || `${kind}.docx`
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(a.href), 5000)
    } catch { /* ignore */ }
    setBusyId(null)
  }

  if (!data) return (
    <div className="leads-page"><p className="muted">
      Loading the competitor board…</p></div>)

  if (view === 'consultants') {
    return (
      <div className="leads-page">
        <div className="leads-filters">
          <button className="lead-sum" onClick={() => setView('accounts')}>
            ← Back to accounts</button>
          <span className="muted">E-Rate consultants ranked by client
            reach — one relationship opens every door on their roster.</span>
        </div>
        <div className="leads-list">
          {(consultants || []).map((c) => (
            <div key={c.name} className="lead-card">
              <button className="lead-row" onClick={() =>
                setOpen(open === c.name ? null : c.name)}>
                <span className="lr-org">{c.name}</span>
                <span className="lr-comp">{c.states.slice(0, 4).join(' ')}
                  {c.states.length > 4 ? '…' : ''}</span>
                <span className="lr-spend">{c.client_count} clients</span>
                <span className="lr-exp">{fmtUsd(c.competitor_spend)}</span>
              </button>
              {open === c.name && (
                <div className="lead-detail">
                  <div className="ld-contacts"><b>Email:</b>{' '}
                    {c.emails.join(', ') || '—'}</div>
                  <div className="ld-facts">
                    {c.top_clients.map((t) => (
                      <span key={t.org}>{t.org} ({fmtUsd(t.spend)})</span>))}
                  </div>
                  <div className="ld-actions">
                    <button disabled={pitch[c.name] === 'busy'}
                      onClick={() => draftPitch(c.name)}>
                      ✍️ {pitch[c.name] && pitch[c.name] !== 'busy'
                        ? 'Redraft pitch' : 'Draft partnership pitch'}</button>
                    {pitch[c.name] === 'busy' && (
                      <span className="muted">drafting…</span>)}
                  </div>
                  {pitch[c.name] && pitch[c.name] !== 'busy'
                    && pitch[c.name].draft && (
                    <div className="ld-draft">
                      <textarea readOnly value={pitch[c.name].draft}
                        rows={10} />
                      <div className="ld-draft-btns">
                        <button onClick={() => navigator.clipboard
                          ?.writeText(pitch[c.name].draft)}>📋 Copy</button>
                      </div>
                    </div>)}
                </div>)}
            </div>
          ))}
          {!consultants && <p className="muted">Loading consultants…</p>}
        </div>
      </div>
    )
  }

  return (
    <div className="leads-page">
      <div className="leads-summary">
        {(data.summary || []).map((s) => (
          <button key={s.competitor}
            className={`lead-sum ${competitor === s.competitor ? 'sel' : ''}`}
            onClick={() => setCompetitor(
              competitor === s.competitor ? '' : s.competitor)}>
            <span className="ls-label">{s.label}</span>
            <span className="ls-big">{s.accounts}</span>
            <span className="ls-sub">{fmtUsd(s.total_spend)}/yr
              {s.contacted ? ` · ${s.contacted} contacted` : ''}</span>
          </button>
        ))}
        <button className="lead-sum sweep" onClick={sweep} disabled={sweeping}
          title="Re-run the nationwide USAC sweep">
          {sweeping ? '⏳ Sweeping…' : '🔄 Refresh sweep'}</button>
        <button className="lead-sum" title="E-Rate consultant channel"
          onClick={() => setView('consultants')}>
          <span className="ls-label">Channel</span>
          <span className="ls-big">🤝</span>
          <span className="ls-sub">Consultants</span>
        </button>
      </div>

      <div className="leads-filters">
        <label className={`libtoggle${librariesOnly ? ' on' : ''}`}>
          <input type="checkbox" checked={librariesOnly}
            onChange={(e) => setLibrariesOnly(e.target.checked)} />
          {' '}Libraries only
        </label>
        <select value={competitor}
          onChange={(e) => setCompetitor(e.target.value)}>
          <option value="">All competitors</option>
          {Object.entries(data.competitors || {}).map(([k, label]) => (
            <option key={k} value={k}>{label}</option>))}
        </select>
        <select value={state} onChange={(e) => setState(e.target.value)}>
          <option value="">All states</option>
          {(data.states || []).map((s) => (
            <option key={s} value={s}>{s}</option>))}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Active (not dismissed)</option>
          <option value="new">New</option>
          <option value="contacted">Contacted</option>
          <option value="replied">Replied</option>
          <option value="meeting">Meeting</option>
          <option value="quote">Quote out</option>
          <option value="verbal">Verbal yes</option>
          <option value="won">Won</option>
          <option value="lost">Lost</option>
          <option value="dismissed">Dismissed</option>
          <option value="all">Everything</option>
        </select>
        <input type="number" min="0" step="1000" placeholder="Min $/yr"
          value={minSpend} onChange={(e) => setMinSpend(e.target.value)} />
        <span className="muted">{(data.leads || []).length} accounts</span>
      </div>

      <div className="leads-head">
        {COLS.map(([field, label]) => (
          <button key={field} className={`lh-col lh-${field} `
            + (sort.field === field ? 'on' : '')}
            onClick={() => clickSort(field)}>
            {label}{sort.field === field
              ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}
          </button>
        ))}
      </div>

      <div className="leads-list">
        {(data.leads || []).map((l) => (
          <div key={l.id} className={`lead-card ${l.status}`}>
            <button className="lead-row" onClick={() =>
              setOpen(open === l.id ? null : l.id)}>
              <span className="lr-org">{l.org}
                <span className="lr-state">{l.state}</span>
                {l.source === 'ecf' && (
                  <span className="lr-tag ecf"
                    title="Found via the Emergency Connectivity Fund — the
 program ended, so this is a win-back target">ECF</span>)}
                {l.status === 'dismissed' ? (
                  <span className="lr-tag dim">✕ dismissed</span>
                ) : l.status === 'won' ? (
                  <span className="lr-tag won">🏆 won</span>
                ) : l.status && l.status !== 'new' && (
                  <span className="lr-tag">{l.status}</span>)}
              </span>
              <span className="lr-comp">{l.competitor_label}</span>
              <span className="lr-spend">{l.competitor === 'greenfield'
                ? `${fmtUsd(l.budget)} budget`
                : `${fmtUsd(l.spend)}${l.source === 'ecf' ? ' total' : '/yr'}`}</span>
              <span className="lr-exp">{l.next_expiration
                ? `exp ${l.next_expiration}` : ''}</span>
            </button>

            {open === l.id && (
              <div className="lead-detail">
                <div className="ld-facts">
                  {l.entity_type && <span>{l.entity_type}</span>}
                  {l.source === 'ecf' && (
                    <span>ECF-funded (program ended — win-back)</span>)}
                  {l.devices ? <span>{l.devices.toLocaleString()} hotspot
                    lines</span> : null}
                  {l.enrollment && (
                    <span>~{l.enrollment.toLocaleString()} students</span>)}
                  {l.budget && <span>budget {fmtUsd(l.budget)}</span>}
                  {l.spins.length > 0 && (
                    <span>billed by {l.spins.join('; ')}</span>)}
                </div>
                {l.narratives.length > 0 && (
                  <div className="ld-nar">“{l.narratives[0]}”</div>)}

                <div className="ld-contacts">
                  <b>Contacts:</b>{' '}
                  {l.extra_contacts.length > 0
                    ? l.extra_contacts.map((c, i) => (
                      <span key={i} className="ld-person">
                        {c.name || c.email}{c.title ? ` (${c.title})` : ''}
                        {c.email && c.name ? ` — ${c.email}` : ''}</span>))
                    : l.contacts.map((c) => (
                      <span key={c} className="ld-person">{c}</span>))}
                  {l.consultants.length > 0 && (
                    <span className="muted"> · consultant: {
                      l.consultants[0]}</span>)}
                </div>

                <div className="ld-actions">
                  <label className="ld-stage">Stage:{' '}
                    <select value={STAGES.includes(l.status) ? l.status : 'new'}
                      disabled={busyId === l.id}
                      onChange={(e) =>
                        act(l.id, () => api.competitorStatus(l.id, e.target.value))}>
                      {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </label>
                  <button disabled={busyId === l.id} onClick={() =>
                    act(l.id, () => api.competitorContacts(l.id))}>
                    🔎 Find contacts</button>
                  <button disabled={busyId === l.id} onClick={() =>
                    act(l.id, () => api.competitorDraft(l.id))}>
                    ✍️ {l.email_draft ? 'Redraft email' : 'Draft email'}</button>
                  <button disabled={liBusy === l.id}
                    title="Builds per-person targets (known contacts +
 decision-maker titles) with messages, and opens the LinkedIn queue"
                    onClick={() => addToLinkedIn(l.id)}>
                    💼 {liBusy === l.id ? 'Building…' : 'LinkedIn'}</button>
                  <button disabled={busyId === l.id}
                    title="One-page savings sheet from their real numbers"
                    onClick={() => downloadDoc(l.id, 'savings')}>
                    💰 Savings sheet</button>
                  <button disabled={busyId === l.id}
                    title="Board briefing your contact presents internally"
                    onClick={() => downloadDoc(l.id, 'champion')}>
                    🏛️ Board kit</button>
                  {l.status === 'won' && (
                    <button disabled={busyId === l.id}
                      onClick={() => downloadDoc(l.id, 'case')}>
                      🏆 Case study</button>)}
                  {l.status === 'dismissed' ? (
                    <button disabled={busyId === l.id} onClick={() =>
                      act(l.id, () => api.competitorStatus(l.id, 'new'))}>
                      ↩ Restore</button>
                  ) : (
                    <button className="danger" disabled={busyId === l.id}
                      onClick={() =>
                        act(l.id, () => api.competitorStatus(l.id, 'dismissed'))}>
                      ✕ Dismiss</button>)}
                  {busyId === l.id && <span className="muted">working…</span>}
                </div>
                {(l.notes || []).length > 0 && (
                  <div className="ld-nar">Latest note ({
                    (l.notes[l.notes.length - 1].at || '').slice(0, 10)}): {
                    l.notes[l.notes.length - 1].text.slice(0, 200)}</div>)}


                {l.email_draft && (
                  <div className="ld-draft">
                    <textarea readOnly value={l.email_draft} rows={10} />
                    <div className="ld-draft-btns">
                      <button onClick={() => copyDraft(l.email_draft)}>
                        📋 Copy</button>
                      <a className="btn" href={`mailto:${
                        (l.extra_contacts.find((c) => c.email)?.email)
                        || l.contacts[0] || ''}?subject=${
                        encodeURIComponent((l.email_draft.split('\n')[0] || '')
                          .replace(/^subject:\s*/i, ''))}&body=${
                        encodeURIComponent(l.email_draft.split('\n')
                          .slice(1).join('\n').trim())}`}>
                        ✉️ Open in mail</a>
                    </div>
                  </div>)}
              </div>
            )}
          </div>
        ))}
        {(data.leads || []).length === 0 && (
          <p className="muted">No accounts match — run the sweep or clear
            filters.</p>)}
      </div>
    </div>
  )
}
