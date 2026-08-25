import React, { useEffect, useState } from 'react'
import { api } from '../api.js'

// His Memory — browse, search, edit, or delete everything Matt knows.
// (Putting things IN happens on the Teach Him page.)

const goTab = (tab) =>
  window.dispatchEvent(new CustomEvent('mtrfp:navigate', { detail: { tab } }))

const SECTIONS = [
  ['', 'Everything'], ['inbox', 'Inbox'], ['accounts', 'Accounts'],
  ['playbook', 'Playbook'], ['journal', 'Journal'], ['library', 'Library'],
]

export default function Brain() {
  const [notes, setNotes] = useState([])
  const [section, setSection] = useState('')
  const [open, setOpen] = useState(null)      // {path, content}
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [msg, setMsg] = useState('')
  const [q, setQ] = useState('')
  const [hits, setHits] = useState(null)

  const load = () => api.vaultNotes(section)
    .then((d) => setNotes(d.notes)).catch(() => {})
  useEffect(() => { load() }, [section])

  const flash = (t) => { setMsg(t); setTimeout(() => setMsg(''), 4000) }

  const openNote = (path) => api.vaultNote(path).then((n) => {
    setOpen(n); setEditing(false); setDraft(n.content || '')
  })

  const saveNote = () => api.vaultSave(open.path, draft).then(() => {
    setOpen({ ...open, content: draft }); setEditing(false)
    flash('Saved.'); load()
  })

  const removeNote = () => {
    if (!window.confirm('Delete this note from Matt’s memory?')) return
    api.vaultDelete(open.path).then((r) => {
      if (r.error) { flash(r.error); return }
      setOpen(null); load()
    })
  }

  const doSearch = () => {
    if (!q.trim()) { setHits(null); return }
    api.vaultSearch(q).then((d) => setHits(d.hits))
  }

  const shown = hits ?? notes

  return (
    <div>
      <div className="card">
        <h3>🧠 His Memory — everything Matt knows, zero mystery</h3>
        <p className="small">Notes about you, every account he's worked,
          playbook lessons, his daily journal, and everything you've taught
          him. Browse it, edit any note, or make him forget. Want to put
          something in? That's the{' '}
          <a href="#" onClick={(e) => { e.preventDefault(); goTab('teach') }}>
            Teach Him</a> page.</p>
      </div>
      {msg && <p className="ok">{msg}</p>}
      <div className="card">
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap',
          alignItems: 'center', marginBottom: 10 }}>
          {SECTIONS.map(([id, label]) => (
            <button key={id}
              className={section === id && !hits ? 'primary' : ''}
              onClick={() => { setSection(id); setHits(null); setQ('') }}>
              {label}
            </button>
          ))}
          <input value={q} placeholder="Search his memory…"
            style={{ marginLeft: 'auto', minWidth: 180 }}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && doSearch()} />
          <button onClick={doSearch}>🔎</button>
        </div>
        {open ? (
          <div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <button onClick={() => setOpen(null)}>← Back</button>
              {!editing && <button onClick={() => setEditing(true)}>
                ✏️ Edit</button>}
              {editing && <button className="primary" onClick={saveNote}>
                💾 Save</button>}
              <button onClick={removeNote}>🗑️ Forget</button>
              <span className="small" style={{ alignSelf: 'center' }}>
                {open.path}</span>
            </div>
            {editing ? (
              <textarea rows={18} style={{ width: '100%',
                fontFamily: 'monospace' }} value={draft}
                onChange={(e) => setDraft(e.target.value)} />
            ) : (
              <pre style={{ whiteSpace: 'pre-wrap',
                overflowWrap: 'anywhere', fontSize: '.85rem' }}>
                {open.content}</pre>
            )}
          </div>
        ) : (
          <table className="rfps">
            <thead><tr><th>Note</th><th>Section</th><th>Updated</th></tr>
            </thead>
            <tbody>
              {shown.map((n) => (
                <tr key={n.path} className="row"
                  onClick={() => openNote(n.path)}>
                  <td>{n.title.slice(0, 80)}
                    {n.snippet && <div className="small">…{n.snippet}…</div>}
                  </td>
                  <td>{n.section}</td>
                  <td className="small">{n.updated}</td>
                </tr>
              ))}
              {shown.length === 0 && (
                <tr><td colSpan={3} className="small">
                  {hits ? 'No matches.' : 'Nothing here yet — his brain '
                    + 'fills up as he works and as you teach him.'}</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
