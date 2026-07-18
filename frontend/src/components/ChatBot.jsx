import React, { useEffect, useRef, useState } from 'react'
import { authFetch, auth } from '../api.js'
import Matt from './Matt.jsx'
import MattStage from './MattStage.jsx'
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

export default function ChatBot() {
  const [view, setView] = useState('stage')      // 'stage' | 'min' | 'call'
  const [chatOpen, setChatOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [recording, setRecording] = useState(false)
  const [speakReplies, setSpeakReplies] = useState(true)
  const [voiceOk, setVoiceOk] = useState(false)
  const [avatar, setAvatar] = useState({ state: 'idle', mouth: 0 })
  const bodyRef = useRef(null)
  const recRef = useRef(null)
  const name = auth.name()

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
  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [messages, chatOpen, busy])

  // hands-free: start listening as soon as Matt is up (best-effort — needs
  // mic permission; falls back quietly to "tap Talk" if the browser blocks it)
  useEffect(() => { startRec(true) }, [])   // eslint-disable-line

  // after Matt finishes a spoken reply in a voice chat, re-arm listening
  useEffect(() => {
    const was = prevState.current; prevState.current = avatar.state
    if (was === 'speaking' && avatar.state === 'idle' && voiceMode.current
        && viewRef.current !== 'min' && !chatRef.current
        && !busyRef.current && !recRecording.current) {
      const id = setTimeout(() => {
        if (!recRecording.current && !busyRef.current) startRec(true)
      }, 500)
      return () => clearTimeout(id)
    }
  }, [avatar.state])

  const started = messages.some((m) => m.role === 'user')
  const history = (msgs) => msgs.filter((m) => !m._local)
    .map(({ role, content }) => ({ role, content }))
  const lastReply = [...messages].reverse()
    .find((m) => m.role === 'assistant' && !m._local)?.content
  const bubble = lastReply
    || `Hey ${name || 'there'}! I'm all ears — just talk, or hit Chat.`
  const statusLabel = recording ? 'listening…'
    : avatar.state === 'speaking' ? 'talking…'
      : busy ? 'thinking…' : 'online'

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

  async function startRec(auto) {
    if (busy || recRecording.current) return
    mattAudio.stop()
    try {
      recRef.current = createRecorder()
      await recRef.current.start()
      setRecording(true)
      mattAudio.setState('listening')
    } catch {
      if (!auto) setMessages((m) => [...m, { role: 'assistant', _local: true,
        content: 'Microphone was blocked — allow it and tap Talk.' }])
    }
  }

  const stopRecAndSend = async () => {
    setRecording(false); setBusy(true)
    mattAudio.setState('idle')
    voiceMode.current = true
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

  const toggleMic = () => (recording ? stopRecAndSend() : startRec(false))
  const cancelRec = () => {
    if (recording) { setRecording(false); try { recRef.current?.stop() } catch { /* */ } }
    mattAudio.stop()
  }
  const toggleSpeaker = () => { if (speakReplies) mattAudio.stop()
    setSpeakReplies(!speakReplies) }
  const minimize = () => { cancelRec(); voiceMode.current = false; setView('min') }
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
        </div>
      ))}
      {busy && <div className="chat-msg assistant">Working…</div>}
      {!started && !busy && (
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
          <Matt state={avatar.state} mouth={avatar.mouth} size={260} />
          <div className="call-name">Matt</div>
          <div className="call-status">{statusLabel}</div>
          {lastReply && <div className="call-caption">{lastReply}</div>}
        </div>
        <div className="call-controls">
          <button className={`call-btn mic ${recording ? 'rec' : ''}`}
            onClick={toggleMic} disabled={busy}>{recording ? '⏹' : '🎤'}</button>
          {voiceOk && <button className="call-btn" onClick={toggleSpeaker}>
            {speakReplies ? '🔊' : '🔇'}</button>}
          <button className="call-btn end" onClick={exitCall}>⤢</button>
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
    <div className={`matt-dock ${chatOpen ? 'with-chat' : ''}`}>
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
          <button className="stage-icon" title="Full-screen call"
            onClick={() => setView('call')}>⤢</button>
          <button className="stage-icon" title="Minimize Matt"
            onClick={minimize}>–</button>
        </div>

        {!chatOpen && <div className="stage-bubble">{bubble.slice(0, 180)}</div>}

        <MattStage state={avatar.state} mouth={avatar.mouth} height={300} />

        <div className="stage-name">Matt<span className="stage-status">
          {statusLabel}</span></div>

        <div className="stage-controls">
          {voiceOk && (
            <button className={`stage-btn mic ${recording ? 'rec' : ''}`}
              onClick={toggleMic} disabled={busy}
              title={recording ? 'Stop & send' : 'Talk to Matt'}>
              {recording ? '⏹' : '🎤'}<span>{recording ? 'Send' : 'Talk'}</span>
            </button>)}
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
