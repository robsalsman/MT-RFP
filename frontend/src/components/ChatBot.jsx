import React, { useEffect, useRef, useState } from 'react'
import { api, authFetch, auth } from '../api.js'
import { useIsMobile } from '../useMediaQuery.js'
import { useMattPhysics } from '../useMattPhysics.js'
import Matt from './Matt.jsx'
import MattStage from './MattStage.jsx'
import MattPuppet from './MattPuppet.jsx'
import MattFrames from './MattFrames.jsx'
import StageGear from './StageGear.jsx'
import * as mattAudio from '../mattAudio.js'

// 16-bit mono WAV recorder (Riva ASR wants real WAV, not webm). Mic is routed
// through a silent gain node so the ScriptProcessor keeps firing without
// monitoring your own voice back to the speakers (no echo during a call).
function createRecorder() {
  let ctx, source, proc, gain, stream, chunks = [], sampleRate = 48000
  return {
    async start() {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      ctx = new (window.AudioContext || window.webkitAudioContext)()
      sampleRate = ctx.sampleRate
      source = ctx.createMediaStreamSource(stream)
      proc = ctx.createScriptProcessor(4096, 1, 1)
      gain = ctx.createGain(); gain.gain.value = 0
      chunks = []
      proc.onaudioprocess = (e) =>
        chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)))
      source.connect(proc); proc.connect(gain); gain.connect(ctx.destination)
    },
    stop() {
      proc?.disconnect(); gain?.disconnect(); source?.disconnect()
      stream?.getTracks().forEach((t) => t.stop())
      ctx?.close()
      const total = chunks.reduce((n, c) => n + c.length, 0)
      const pcm = new Int16Array(total)
      let off = 0
      for (const c of chunks) {
        for (let i = 0; i < c.length; i++) {
          const s = Math.max(-1, Math.min(1, c[i]))
          pcm[off++] = s < 0 ? s * 0x8000 : s * 0x7fff
        }
      }
      const buf = new ArrayBuffer(44 + pcm.length * 2)
      const v = new DataView(buf)
      const ws = (o, s) => { for (let i = 0; i < s.length; i++)
        v.setUint8(o + i, s.charCodeAt(i)) }
      ws(0, 'RIFF'); v.setUint32(4, 36 + pcm.length * 2, true); ws(8, 'WAVE')
      ws(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true)
      v.setUint16(22, 1, true); v.setUint32(24, sampleRate, true)
      v.setUint32(28, sampleRate * 2, true); v.setUint16(32, 2, true)
      v.setUint16(34, 16, true); ws(36, 'data')
      v.setUint32(40, pcm.length * 2, true)
      new Int16Array(buf, 44).set(pcm)
      return new Blob([buf], { type: 'audio/wav' })
    },
  }
}

// Matt's closet — driven by the quality full-body poses (the generator's
// standalone props + hold poses came back unusable, so each item just strikes
// the matching painted pose). id -> label + pose key in frames.json.
const CLOSET = [
  { id: 'guitar', label: '🎸 Guitar', pose: 'guitar_strum', kind: 'Music' },
  { id: 'solo', label: '🎸 Solo', pose: 'guitar_solo', kind: 'Music' },
  { id: 'air', label: '🤘 Air guitar', pose: 'air_guitar', kind: 'Music' },
  { id: 'mic', label: '🎤 Sing', pose: 'mic_sing', kind: 'Music' },
  { id: 'headphones', label: '🎧 Headphones', pose: 'headphones_on', kind: 'Music' },
  { id: 'drums', label: '🥁 Drums', pose: 'drumming', kind: 'Music' },
  { id: 'laptop', label: '💻 Laptop', pose: 'typing', kind: 'Business' },
  { id: 'docs', label: '📄 RFP docs', pose: 'reading_doc', kind: 'Business' },
  { id: 'clipboard', label: '📋 Clipboard', pose: 'clipboard', kind: 'Business' },
  { id: 'present', label: '📊 Present', pose: 'present_chart', kind: 'Business' },
  { id: 'coffee', label: '☕ Coffee', pose: 'coffee_sip', kind: 'Business' },
  { id: 'trophy', label: '🏆 Trophy', pose: 'present_win', kind: 'Flair' },
  { id: 'horns', label: '🤘 Rock horns', pose: 'rock_horns', kind: 'Flair' },
  { id: 'relaxed', label: '😎 Chill', pose: 'idle_relaxed', kind: 'Flair' },
]

export default function ChatBot() {
  const [view, setView] = useState('stage')      // 'stage' | 'min' | 'call'
  const [chatOpen, setChatOpen] = useState(false)
  const [puppetFailed, setPuppetFailed] = useState(false)
  const [framesReady, setFramesReady] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [recording, setRecording] = useState(false)
  const [speakReplies, setSpeakReplies] = useState(true)
  const [voiceOk, setVoiceOk] = useState(false)
  const [avatar, setAvatar] = useState({ state: 'idle', mouth: 0 })
  const [closetOpen, setClosetOpen] = useState(false)
  // greeting/picks tray: open on desktop (room to spare), collapsed on mobile
  const [trayOpen, setTrayOpen] = useState(
    () => typeof window === 'undefined'
      || !window.matchMedia('(max-width: 720px)').matches)
  const [bubbleExp, setBubbleExp] = useState(false)    // expand clamped bubble
  const [closetPose, setClosetPose] = useState(null)   // persistent held pose
  const [seqPlay, setSeqPlay] = useState(null)          // one-shot animation
  const seqTimer = useRef(null)
  const bodyRef = useRef(null)
  const recRef = useRef(null)
  const name = auth.name()
  const isMobile = useIsMobile()
  const { style: dockStyle, phys, onPointerDown: onDockDown, dragging, resetPos }
    = useMattPhysics(!isMobile)

  // refs so the auto-relisten effect reads live values, not stale closures
  const viewRef = useRef(view); const chatRef = useRef(chatOpen)
  const busyRef = useRef(busy); const recRecording = useRef(recording)
  const voiceMode = useRef(false); const prevState = useRef('idle')
  useEffect(() => { viewRef.current = view }, [view])
  useEffect(() => { chatRef.current = chatOpen }, [chatOpen])
  useEffect(() => { busyRef.current = busy }, [busy])
  useEffect(() => { recRecording.current = recording }, [recording])

  useEffect(() => {
    fetch('/api/health').then((r) => r.json())
      .then((h) => setVoiceOk(!!h.voice_available)).catch(() => {})
  }, [])
  useEffect(() => mattAudio.subscribe(setAvatar), [])

  // play a one-shot animation for `ms`, then let Matt settle back
  const playSeq = (name, ms = 2600) => {
    if (seqTimer.current) clearTimeout(seqTimer.current)
    setSeqPlay(name)
    seqTimer.current = setTimeout(() => setSeqPlay(null), ms)
  }
  useEffect(() => () => seqTimer.current && clearTimeout(seqTimer.current), [])

  // what pose Matt holds: a playing animation wins; else while he's working he
  // reads the screen (typing); else whatever you pulled from the closet.
  const effSequence = seqPlay
  const effPose = seqPlay ? null : (busy ? 'typing' : closetPose)
  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [messages, chatOpen, busy])

  // Spacebar = push-to-talk on desktop (hold Space to talk, release to send),
  // unless you're typing in a field.
  useEffect(() => {
    const typing = () => {
      const el = document.activeElement
      return el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')
    }
    const down = (e) => {
      if (e.code === 'Space' && !e.repeat && voiceOk && !typing()
          && viewRef.current !== 'min') { e.preventDefault(); pttDown() }
    }
    const up = (e) => {
      if (e.code === 'Space' && !typing()) { e.preventDefault(); pttUp() }
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
    }
  }, [voiceOk])   // eslint-disable-line

  const started = messages.some((m) => m.role === 'user')
  const history = (msgs) => msgs.filter((m) => !m._local)
    .map(({ role, content }) => ({ role, content }))
  const lastAsst = [...messages].reverse()
    .find((m) => m.role === 'assistant' && !m._local)
  const lastReply = lastAsst?.content
  const bubble = lastReply
    || `Hey ${name || 'there'}! Give me a sec — pulling up the best RFPs for us…`
  const bubblePicks = (lastAsst?.picks) || []
  const bubbleDownloads = lastAsst?.downloads
  const statusLabel = recording ? 'listening — release to send'
    : avatar.state === 'speaking' ? 'talking…'
      : busy ? 'thinking…' : 'online'

  // Proactive open: as soon as Matt is up, he pulls the top mission-fit RFPs
  // and offers to draft one — instead of waiting to be asked.
  const proactiveDone = useRef(false)
  useEffect(() => {
    if (proactiveDone.current) return
    proactiveDone.current = true
    api.rfps({ status: 'OPEN', mission_only: true }).then((d) => {
      const top = (d.rfps || []).slice(0, 3)
      if (!top.length) return
      const picks = top.map((r) => ({ application_number: r.application_number,
        label: `${r.billed_entity_name} · ${r.state}`,
        entity: r.billed_entity_name }))
      const hi = name ? `Hey ${name}! ` : 'Hey! '
      const content = hi + "I went through the open RFPs — these look like our "
        + 'strongest shots right now. Want me to prepare a reply for one? '
        + 'Tap it and I\'ll draft it.'
      setMessages((m) => [...m, { role: 'assistant', _proactive: true,
        content, picks }])
      playSeq('wave', 2400)   // he waves hello when he greets you
    }).catch(() => { /* no data yet — the default greeting stands */ })
  }, [])   // eslint-disable-line

  const prepareReply = async (an, label) => {
    if (busy) return
    setBusy(true)
    setMessages((m) => [...m, { role: 'user', content: `Draft ${label}'s reply` }])
    try {
      const r = await api.generateResponse(an)
      const extra = r.unmatched_count
        ? ` ${r.unmatched_count} item(s) need manual pricing (flagged in red).` : ''
      const reply = `Done${name ? `, ${name}` : ''}! I drafted ${label}'s `
        + `reply — it's a DRAFT, so give it a human once-over before it goes `
        + `out.${extra}`
      setMessages((m) => [...m, { role: 'assistant', content: reply,
        downloads: { id: r.id, entity: label } }])
      playSeq('celebrate', 3000)   // draft's ready — Matt celebrates the win
      window.dispatchEvent(new CustomEvent('mtrfp:navigate',
        { detail: { tab: 'dashboard', open_application_number: an } }))
      if (speakReplies && voiceOk) speakText(reply)
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', _local: true,
        content: `Couldn't draft that one: ${e.message}` }])
    } finally { setBusy(false) }
  }

  const downloadDraft = async (id, fmt) => {
    try {
      const r = await authFetch(`/api/responses/${id}/download?fmt=${fmt}`)
      if (!r.ok) return
      const blob = await r.blob()
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `MissionTelecom_Response.${fmt}`
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(a.href), 5000)
    } catch { /* ignore */ }
  }

  const openRfp = (an) => {
    setView('stage')
    setChatOpen(true)
    window.dispatchEvent(new CustomEvent('mtrfp:navigate',
      { detail: { tab: 'dashboard', open_application_number: an } }))
  }

  const applyResult = (d, next) => {
    setMessages([...next, {
      role: 'assistant', content: d.reply, toolLog: d.tool_log,
      options: d.options || [],
    }])
    if (d.navigate) {
      if (viewRef.current === 'call') setView('stage')
      window.dispatchEvent(
        new CustomEvent('mtrfp:navigate', { detail: d.navigate }))
    }
    if (d.audio_b64) mattAudio.play(`data:audio/wav;base64,${d.audio_b64}`)
    else if (speakReplies && voiceOk && d.reply) speakText(d.reply)
  }

  const speakText = async (text) => {
    try {
      const r = await authFetch('/api/voice/speak', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      if (!r.ok) return
      mattAudio.play(URL.createObjectURL(await r.blob()))
    } catch { /* voice is best-effort */ }
  }

  const send = async (preset) => {
    const text = (preset ?? input).trim()
    if (!text || busy) return
    voiceMode.current = false
    const next = [...messages, { role: 'user', content: text }]
    setMessages(next); setInput(''); setBusy(true)
    try {
      const r = await authFetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history(next) }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || 'request failed')
      applyResult(d, next)
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', _local: true,
        content: `Something went wrong: ${e.message}` }])
    } finally { setBusy(false) }
  }

  // ---- push-to-talk: hold the mic to talk, release to send ----
  const pttHeld = useRef(false)

  async function pttDown() {
    if (busyRef.current || recRecording.current) return
    pttHeld.current = true
    mattAudio.stop()
    try {
      recRef.current = createRecorder()
      await recRef.current.start()
      if (!pttHeld.current) {   // released before the mic even opened
        try { recRef.current.stop() } catch { /* */ }
        return
      }
      recRecording.current = true
      setRecording(true)
      mattAudio.setState('listening')
    } catch {
      pttHeld.current = false
      setMessages((m) => [...m, { role: 'assistant', _local: true,
        content: 'Microphone was blocked — allow mic access and try again.' }])
    }
  }

  function pttUp() {
    if (!pttHeld.current) return
    pttHeld.current = false
    if (recRecording.current) stopRecAndSend()
  }

  const stopRecAndSend = async () => {
    recRecording.current = false
    setRecording(false); setBusy(true)
    mattAudio.setState('idle')
    const wav = recRef.current.stop()
    try {
      const fd = new FormData()
      fd.append('audio', wav, 'speech.wav')
      fd.append('messages', JSON.stringify(history(messages)))
      fd.append('speak_reply', speakReplies ? 'true' : 'false')
      const r = await authFetch('/api/voice/converse', { method: 'POST', body: fd })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || 'voice request failed')
      const next = d.transcript
        ? [...messages, { role: 'user', content: `🎤 ${d.transcript}` }]
        : messages
      applyResult(d, next)
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', _local: true,
        content: `Voice error: ${e.message}` }])
    } finally { setBusy(false) }
  }

  const cancelRec = () => {
    pttHeld.current = false
    if (recRecording.current) {
      recRecording.current = false; setRecording(false)
      try { recRef.current?.stop() } catch { /* */ }
    }
    mattAudio.stop()
  }
  const toggleSpeaker = () => { if (speakReplies) mattAudio.stop()
    setSpeakReplies(!speakReplies) }
  const minimize = () => { cancelRec(); setView('min') }

  // props for a push-to-talk mic button (pointer + touch)
  const pttProps = {
    onPointerDown: (e) => {
      e.preventDefault()
      try { e.currentTarget.setPointerCapture(e.pointerId) } catch { /* */ }
      pttDown()
    },
    onPointerUp: pttUp,
    onPointerCancel: pttUp,
    onContextMenu: (e) => e.preventDefault(),
  }
  const exitCall = () => { setView('stage') }

  const msgList = (
    <div className="chat-body" ref={bodyRef}>
      {messages.map((m, i) => (
        <div key={i} className={`chat-msg ${m.role}`}>
          {m.content}
          {m.toolLog?.length > 0 && (
            <div className="chat-tools">{m.toolLog.map((t, j) => (
              <span key={j} className={t.ok ? '' : 'err'}>⚙ {t.tool}</span>))}
            </div>)}
          {m.options?.length > 0 && (
            <div className="chat-options">{m.options.map((o) => (
              <button key={o.application_number}
                className={`opt ${o.biddable ? '' : 'opt-no'}`}
                onClick={() => openRfp(o.application_number)}>
                {o.label} ›</button>))}
            </div>)}
          {m.picks?.length > 0 && (
            <div className="chat-options">{m.picks.map((p) => (
              <button key={p.application_number} className="opt pick"
                disabled={busy}
                onClick={() => prepareReply(p.application_number, p.entity)}>
                🎸 Draft reply — {p.label}</button>))}
            </div>)}
          {m.downloads && (
            <div className="chat-options">
              <button className="opt" onClick={() =>
                downloadDraft(m.downloads.id, 'docx')}>⬇ DOCX</button>
              <button className="opt" onClick={() =>
                downloadDraft(m.downloads.id, 'pdf')}>⬇ PDF</button>
            </div>)}
        </div>
      ))}
      {busy && <div className="chat-msg assistant">Working…</div>}
      {!started && !busy && !messages.some((m) => m.picks?.length) && (
        <div className="chat-msg assistant">Ask me anything, or tap a chip:
          <div className="cta-chips">
            {['Which deals close this week?', 'Show open libraries',
              "What's our best RFP right now?"].map((q) => (
              <button key={q} className="chip" disabled={busy}
                onClick={() => send(q)}>{q}</button>))}
          </div>
        </div>)}
    </div>
  )

  // ---- full-screen "video call" (opt-in via the ⤢ control) ----
  if (view === 'call') {
    return (
      <div className="matt-call">
        <button className="call-min" onClick={exitCall}
          title="Exit full screen">⤢ Exit full screen</button>
        <div className="call-stage">
          <div className="call-face">
            {/* painted viseme lip-sync when frames are ready, SVG until then */}
            <MattFrames state={avatar.state} mouth={avatar.mouth} closeup
              onReady={() => setFramesReady(true)} onFail={() => {}} />
            {!framesReady && (
              <Matt state={avatar.state} mouth={avatar.mouth} size={260} />)}
          </div>
          <div className="call-name">Matt</div>
          <div className="call-status">{statusLabel}</div>
          {lastReply && <div className="call-caption">{lastReply}</div>}
        </div>
        <div className="call-controls">
          <button className={`call-btn mic ptt ${recording ? 'rec' : ''}`}
            {...pttProps} disabled={busy}
            title="Hold to talk, release to send">🎤</button>
          {voiceOk && <button className="call-btn" onClick={toggleSpeaker}>
            {speakReplies ? '🔊' : '🔇'}</button>}
          <button className="call-btn end" onClick={exitCall}>⤢</button>
        </div>
        <div className="call-status" style={{ marginTop: '4px' }}>
          {recording ? 'listening — release to send' : 'hold the mic to talk'}
        </div>
      </div>
    )
  }

  // ---- minimized: small floating Matt button ----
  if (view === 'min') {
    return (
      <button className="chat-fab" onClick={() => setView('stage')}
        title="Bring Matt back">
        <Matt state={avatar.state} mouth={avatar.mouth} size={48} />
      </button>
    )
  }

  // ---- stage (default): full-body Matt in a spotlight, chat slides out ----
  return (
    <div className={`matt-dock ${chatOpen ? 'with-chat' : ''} `
      + `${!isMobile ? 'draggable' : ''} ${dragging ? 'dragging' : ''}`}
      style={dockStyle} onPointerDown={onDockDown}>
      {chatOpen && (
        <div className="chat-side">
          <div className="chat-head">
            <span className="chat-title">Matt — chat</span>
            <button className="chat-close" title="Close chat"
              onClick={() => setChatOpen(false)}>✕</button>
          </div>
          {msgList}
          <div className="chat-input">
            <input value={input} disabled={busy}
              placeholder="Message Matt…"
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()} />
            <button className="primary" onClick={() => send()}
              disabled={busy || !input.trim()}>Send</button>
          </div>
        </div>
      )}

      <div className="stage-card">
        <div className="stage-top">
          {!isMobile && dockStyle.left && (
            <button className="stage-icon" title="Reset Matt's position"
              onClick={resetPos}>⟲</button>)}
          <button className={`stage-icon ${closetOpen ? 'on' : ''}`}
            title="Matt's closet" onClick={() => setClosetOpen((o) => !o)}>🚪</button>
          <button className="stage-icon" title="Minimize Matt"
            onClick={minimize}>–</button>
        </div>

        {closetOpen && (
          <div className="closet">
            <div className="closet-head">
              <span>Matt's closet</span>
              <button className="closet-put" disabled={!closetPose}
                onClick={() => setClosetPose(null)}>Put away</button>
            </div>
            <div className="closet-grid">
              {CLOSET.map((it) => (
                <button key={it.id}
                  className={`closet-item ${closetPose === it.pose ? 'sel' : ''}`}
                  title={`${it.kind} — ${it.label}`}
                  onClick={() => {
                    if (seqTimer.current) clearTimeout(seqTimer.current)
                    setSeqPlay(null); setClosetPose(it.pose)
                  }}>
                  <img src={`/matt-frames/poses/matt_pose_${it.pose}.png`} alt="" />
                  <span>{it.label}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {!isMobile && (
          <div className="stage-grab">⠿ drag Matt anywhere</div>)}

        {!chatOpen && (
          <div className={`stage-tray ${trayOpen ? 'open' : ''}`}>
            <button className="tray-toggle" onClick={() => setTrayOpen((o) => !o)}
              title={trayOpen ? 'Hide' : 'Show what Matt found'}>
              <span className="tray-title">💬 Matt{bubblePicks.length
                ? ` · ${bubblePicks.length} pick${bubblePicks.length > 1 ? 's' : ''}`
                : bubbleDownloads ? ' · draft ready' : ''}</span>
              <span className="tray-chev">{trayOpen ? '▾' : '▸'}</span>
            </button>
            {trayOpen && (
              <div className="tray-body">
                <div className={`stage-bubble ${bubbleExp ? 'exp' : ''}`}
                  onClick={() => setBubbleExp((e) => !e)}
                  title="Tap to expand">{bubble}</div>
                {bubblePicks.length > 0 && (
                  <div className="stage-picks">
                    {bubblePicks.map((p) => (
                      <button key={p.application_number} className="stage-pick"
                        disabled={busy} title={`Draft reply — ${p.label}`}
                        onClick={() => prepareReply(p.application_number, p.entity)}>
                        🎸 {p.label}</button>))}
                  </div>)}
                {bubbleDownloads && (
                  <div className="stage-picks stage-dl">
                    <button className="stage-pick" onClick={() =>
                      downloadDraft(bubbleDownloads.id, 'docx')}>⬇ DOCX</button>
                    <button className="stage-pick" onClick={() =>
                      downloadDraft(bubbleDownloads.id, 'pdf')}>⬇ PDF</button>
                  </div>)}
              </div>)}
          </div>)}

        <div className="puppet-wrap">
          {/* painted frames (top tier) — activate once real art is dropped in */}
          <MattFrames state={avatar.state} mouth={avatar.mouth} lean={phys.lean}
            pose={effPose} sequence={effSequence}
            onReady={() => setFramesReady(true)} onFail={() => {}} />
          {/* until frames are ready: vector puppet, then hand-drawn fallback */}
          {!framesReady && (puppetFailed ? (
            <MattStage state={avatar.state} mouth={avatar.mouth} height={300}
              lean={phys.lean} stumble={phys.stumble} props={phys.props} />
          ) : (
            <MattPuppet state={avatar.state} mouth={avatar.mouth}
              lean={phys.lean} onFail={() => setPuppetFailed(true)} />
          ))}
          {/* the painted poses have their own props, so only overlay the
              toppleable gear on the vector puppet / hand-drawn fallback */}
          {!framesReady && <StageGear props={phys.props} />}
        </div>

        <div className="stage-name">Matt<span className="stage-status">
          {statusLabel}</span></div>

        <div className="stage-controls">
          {voiceOk && (
            <button className={`stage-btn mic ptt ${recording ? 'rec' : ''}`}
              {...pttProps} disabled={busy}
              title="Hold to talk, release to send">
              🎤<span>{recording ? 'Release' : 'Hold to talk'}</span>
            </button>)}
          <button className="stage-btn call" onClick={() => setView('call')}
            title="Zoom into Matt's face — full-screen video call">
            📹<span>Call</span></button>
          <button className={`stage-btn ${chatOpen ? 'on' : ''}`}
            onClick={() => setChatOpen(!chatOpen)} title="Type a message">
            💬<span>Chat</span></button>
          {voiceOk && (
            <button className="stage-btn" onClick={toggleSpeaker}
              title={speakReplies ? 'Mute Matt' : 'Unmute Matt'}>
              {speakReplies ? '🔊' : '🔇'}<span>{speakReplies ? 'Mute' : 'Unmute'}</span>
            </button>)}
        </div>
      </div>
    </div>
  )
}
