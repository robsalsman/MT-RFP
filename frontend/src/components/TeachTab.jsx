import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

// Teach Him — put things INTO Matt's brain: sticky notes (not chat),
// file uploads, and URLs. Shows the no-mystery pipeline and receipts.

const goTab = (tab) =>
  window.dispatchEvent(new CustomEvent('mtrfp:navigate', { detail: { tab } }))

const STICKY_STYLE = {
  background: 'linear-gradient(180deg, #fef9c3, #fde68a)',
  color: '#713f12', borderRadius: '2px 12px 3px 3px',
  boxShadow: '2px 3px 8px rgba(0,0,0,.25)',
  padding: '10px 12px', fontSize: '.85rem',
  whiteSpace: 'pre-wrap', overflowWrap: 'anywhere',
}

export default function TeachTab() {
  const [notes, setNotes] = useState([])
  const [prefs, setPrefs] = useState(null)
  const [sticky, setSticky] = useState('')
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')
  const fileRef = useRef(null)

  const load = () => api.vaultNotes().then((d) => {
    setNotes(d.notes); setPrefs(d.prefs)
  }).catch(() => {})
  useEffect(() => { load() }, [])

  const flash = (t) => { setMsg(t); setTimeout(() => setMsg(''), 5000) }

  const stickIt = () => {
    if (!sticky.trim()) return
    setBusy('sticky')
    api.vaultSticky(sticky).then(() => {
      setSticky(''); flash("🧠 Stuck in his brain — he'll read it and file "
        + 'it tonight.')
      load()
    }).catch((e) => flash(e.message)).finally(() => setBusy(''))
  }

  const feedUrl = () => {
    if (!url.trim()) return
    setBusy('url')
    api.vaultUrl(url).then((r) => {
      setUrl(''); flash('🧠 He read it. His take: '
        + (r.summary || '').slice(0, 120))
      load()
    }).catch((e) => flash('⚠️ ' + e.message))
      .finally(() => setBusy(''))
  }

  const feedFile = (f) => {
    if (!f) return
    setBusy('file')
    api.vaultUpload(f).then((r) => {
      flash('🧠 He read it. His take: ' + (r.summary || '').slice(0, 120))
      load()
    }).catch((e) => flash('⚠️ ' + e.message)).finally(() => {
      setBusy(''); if (fileRef.current) fileRef.current.value = ''
    })
  }

  // receipts: what Kim fed him lately + where it stands
  const fed = notes.filter((n) => n.section === 'inbox'
    || n.section === 'library').slice(0, 10)

  return (
    <div>
      <div className="card">
        <h3>🍎 Teach Him — give Matt something to remember</h3>
        <p className="small">Three ways in. Everything lands in his inbox,
          gets read and summarized on the spot, and files into his memory
          overnight — always visible on
          {' '}<a href="#" onClick={(e) => { e.preventDefault()
            goTab('brain') }}>His Memory</a>.</p>
      </div>
      <div className="teach-row">
        <div className="card teach-card">
          <div className="teach-ico">📝</div>
          <h4>Stick a note</h4>
          <p className="small">A thought for Matt without starting a chat.
            Type it, stick it, done.</p>
          <textarea rows={4} style={{ ...STICKY_STYLE, width: '100%',
            border: 'none' }} value={sticky}
            placeholder={'e.g. "Elyria\'s board meets the 2nd Tuesday — time proposals the week before."'}
            onChange={(e) => setSticky(e.target.value)} />
          <button className="primary" disabled={busy === 'sticky'}
            onClick={stickIt}>
            {busy === 'sticky' ? 'Sticking…' : '🧠 Stick it in his brain'}
          </button>
        </div>
        <div className="card teach-card">
          <div className="teach-ico">📎</div>
          <h4>Drop a file</h4>
          <p className="small">Rate sheets, board minutes, a competitor
            flyer — he reads the whole thing.</p>
          <label className="dropzone">
            ⬇️ Click to pick a file
            <span className="small">PDF · DOCX · TXT · CSV (25 MB max)</span>
            <input type="file" ref={fileRef} style={{ display: 'none' }}
              accept=".pdf,.docx,.txt,.csv"
              onChange={(e) => feedFile(e.target.files?.[0])} />
          </label>
          {busy === 'file' && <p className="small">📖 Reading it…</p>}
        </div>
        <div className="card teach-card">
          <div className="teach-ico">🔗</div>
          <h4>Paste a link</h4>
          <p className="small">Any web page — a grant program, a library's
            news, an article worth keeping.</p>
          <input value={url} placeholder="https://…"
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && feedUrl()} />
          <button className="primary" disabled={busy === 'url'}
            onClick={feedUrl}>
            {busy === 'url' ? 'Reading…' : '🌐 He learns the page'}</button>
          <p className="small">(Pasting a link to him in chat works too.)</p>
        </div>
      </div>
      {msg && <p className="ok">{msg}</p>}

      <div className="card">
        <h3>WHAT HAPPENS WHEN YOU TEACH HIM — NO MYSTERY</h3>
        <div className="teach-steps">
          <div className="teach-step"><b>1 · Lands in his inbox 📥</b>
            He summarizes it on the spot and shows you the summary here.</div>
          <div className="teach-arrow">→</div>
          <div className="teach-step"><b>2 · He uses it immediately 💬</b>
            It's in his head for every chat, draft, and hunt from that
            moment.</div>
          <div className="teach-arrow">→</div>
          <div className="teach-step"><b>3 · Filed overnight 🌙</b>
            Sorted into his memory: about you, an account, or his playbook.
            See it anytime in His Memory.</div>
        </div>
      </div>

      {prefs && (
        <div className="card">
          <h3>🎛️ His current hunting tuning</h3>
          {(prefs.extra_terms.length || prefs.avoid_terms.length
            || prefs.priority_states.length) ? (<>
              {prefs.extra_terms.length > 0 && (
                <p className="small">Also counts as a signal: <b>
                  {prefs.extra_terms.join(', ')}</b></p>)}
              {prefs.avoid_terms.length > 0 && (
                <p className="small">Skips: <b>
                  {prefs.avoid_terms.join(', ')}</b></p>)}
              {prefs.priority_states.length > 0 && (
                <p className="small">Priority states: <b>
                  {prefs.priority_states.join(', ')}</b></p>)}
            </>) : (
              <p className="small">No custom tuning yet — just tell him in
                chat: "also count tablet carts as a signal", "skip anything
                with academy in the name", "focus on Texas".</p>)}
        </div>
      )}

      <div className="card">
        <h3>RECENTLY TAUGHT · where it went</h3>
        {fed.length === 0 && (
          <p className="small">Nothing yet — stick your first note above.
          </p>)}
        {fed.map((n) => (
          <div className="teach-receipt" key={n.path}>
            <span>{n.path.includes('url-') ? '🔗'
              : n.section === 'library' ? '📎' : '📝'}</span>
            <div><b>{n.title.slice(0, 80)}</b>
              <div className="small">{n.updated}</div></div>
            <span className={`teach-status ${n.section === 'inbox'
              ? 'inbox' : 'done'}`}>
              {n.section === 'inbox' ? '🕐 IN HIS INBOX — files tonight'
                : '✅ FILED · library'}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
