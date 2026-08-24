import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

// Matt's second brain: sticky notes straight into his memory (no chat),
// feed him files and URLs, and browse/edit everything he knows.

const SECTIONS = [
  ['', 'Everything'], ['inbox', 'Inbox'], ['accounts', 'Accounts'],
  ['playbook', 'Playbook'], ['journal', 'Journal'], ['library', 'Library'],
]

const STICKY_STYLE = {
  background: 'linear-gradient(180deg, #fef9c3, #fde68a)',
  color: '#713f12', borderRadius: '2px 12px 3px 3px',
  boxShadow: '2px 3px 8px rgba(0,0,0,.25)',
  padding: '10px 12px', fontSize: '.85rem',
  transform: 'rotate(-1deg)', whiteSpace: 'pre-wrap',
  overflowWrap: 'anywhere',
}

export default function Brain() {
  const [notes, setNotes] = useState([])
  const [prefs, setPrefs] = useState(null)
  const [section, setSection] = useState('')
  const [open, setOpen] = useState(null)      // {path, content}
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [sticky, setSticky] = useState('')
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')
  const [q, setQ] = useState('')
  const [hits, setHits] = useState(null)
  const fileRef = useRef(null)

  const load = () => api.vaultNotes(section).then((d) => {
    setNotes(d.notes); setPrefs(d.prefs)
  }).catch(() => {})
  useEffect(load, [section])

  const flash = (t) => { setMsg(t); setTimeout(() => setMsg(''), 4000) }

  const stickIt = () => {
    if (!sticky.trim()) return
    setBusy('sticky')
    api.vaultSticky(sticky).then(() => {
      setSticky(''); flash("🧠 Stuck in Matt's brain — he'll read it.")
      load()
    }).catch((e) => flash(e.message)).finally(() => setBusy(''))
  }

  const feedUrl = () => {
    if (!url.trim()) return
    setBusy('url')
    api.vaultUrl(url).then((r) => {
      setUrl(''); flash('🧠 Page ingested: ' + (r.summary || '').slice(0, 90))
      load()
    }).catch((e) => flash(e.message)).finally(() => setBusy(''))
  }

  const feedFile = (f) => {
    if (!f) return
    setBusy('file')
    api.vaultUpload(f).then((r) => {
      flash('🧠 File ingested: ' + (r.summary || '').slice(0, 90)); load()
    }).catch((e) => flash(e.message)).finally(() => {
      setBusy(''); if (fileRef.current) fileRef.current.value = ''
    })
  }

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

  const stickies = notes.filter((n) => n.path.startsWith('inbox/sticky-'))
  const shown = hits ?? notes

  return (
    <div>
      <div className="grid2">
        <div className="card">
          <h3>📝 Sticky note → Matt&apos;s brain</h3>
          <p className="small">Not a chat message — this goes straight into
            his memory. He reads it, acts on it, and folds it into what he
            knows about you overnight.</p>
          <textarea rows={4} style={{ width: '100%' }} value={sticky}
            placeholder={'e.g. "The Denver contact retired — new tech director starts in Sept."'}
            onChange={(e) => setSticky(e.target.value)} />
          <button className="primary" disabled={busy === 'sticky'}
            onClick={stickIt}>
            {busy === 'sticky' ? 'Sticking…' : '🧠 Stick it in his brain'}
          </button>
          {stickies.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10,
              marginTop: 12 }}>
              {stickies.slice(0, 6).map((n) => (
                <div key={n.path} style={{ ...STICKY_STYLE, maxWidth: 180,
                  cursor: 'pointer' }} onClick={() => openNote(n.path)}>
                  {n.title.slice(0, 90)}
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="card">
          <h3>🍽️ Feed him</h3>
          <p className="small">Files (PDF, DOCX, TXT, CSV) and web pages get
            read, summarized, and remembered forever.</p>
          <div className="formrow">
            <label>URL</label>
            <input value={url} placeholder="https://…"
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && feedUrl()} />
            <button disabled={busy === 'url'} onClick={feedUrl}>
              {busy === 'url' ? 'Reading…' : 'Ingest'}
            </button>
          </div>
          <div className="formrow">
            <label>File</label>
            <input type="file" ref={fileRef}
              accept=".pdf,.docx,.txt,.csv"
              onChange={(e) => feedFile(e.target.files?.[0])} />
            {busy === 'file' && <span className="small">Reading…</span>}
          </div>
          {prefs && (prefs.extra_terms.length || prefs.avoid_terms.length
            || prefs.priority_states.length) ? (
              <>
                <h3 style={{ marginTop: 14 }}>🎯 Kim&apos;s hunting tuning</h3>
                <p className="small">Set by telling Matt in chat
                  (&quot;also look for…&quot;, &quot;skip…&quot;,
                  &quot;focus on…&quot;).</p>
                {prefs.extra_terms.length > 0 && (
                  <p className="small">Also counts: <b>
                    {prefs.extra_terms.join(', ')}</b></p>)}
                {prefs.avoid_terms.length > 0 && (
                  <p className="small">Skips: <b>
                    {prefs.avoid_terms.join(', ')}</b></p>)}
                {prefs.priority_states.length > 0 && (
                  <p className="small">Priority states: <b>
                    {prefs.priority_states.join(', ')}</b></p>)}
              </>
            ) : (
              <p className="small" style={{ marginTop: 14 }}>🎯 No custom
                hunting tuning yet — tell Matt in chat, e.g. &quot;also
                count tablet carts as a signal&quot; or &quot;focus on
                Texas&quot;.</p>
            )}
        </div>
      </div>
      {msg && <p className="ok">{msg}</p>}

      <div className="card" style={{ marginTop: 14 }}>
        <h3>🗂️ What Matt knows</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap',
          alignItems: 'center', marginBottom: 10 }}>
          {SECTIONS.map(([id, label]) => (
            <button key={id} className={section === id && !hits ? 'active' : ''}
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
              <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere',
                fontSize: '.85rem' }}>{open.content}</pre>
            )}
          </div>
        ) : (
          <table>
            <thead><tr><th>Note</th><th>Section</th><th>Updated</th></tr>
            </thead>
            <tbody>
              {shown.map((n) => (
                <tr key={n.path} style={{ cursor: 'pointer' }}
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
                    + 'fills up as he works and as you feed it.'}</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
