import React, { useEffect, useRef, useState } from 'react'
import { authFetch, auth } from '../api.js'
import Matt from './Matt.jsx'
import * as mattAudio from '../mattAudio.js'

// ---- 16-bit mono WAV recorder (Riva ASR wants real WAV, not webm) ----
function createRecorder() {
  let ctx, source, proc, stream, chunks = [], sampleRate = 48000
  return {
    async start() {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      ctx = new (window.AudioContext || window.webkitAudioContext)()
      sampleRate = ctx.sampleRate
      source = ctx.createMediaStreamSource(stream)
      proc = ctx.createScriptProcessor(4096, 1, 1)
      chunks = []
      proc.onaudioprocess = (e) =>
        chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)))
      source.connect(proc)
      proc.connect(ctx.destination)
    },
    stop() {
      proc?.disconnect(); source?.disconnect()
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
  const [open, setOpen] = useState(true)   // Matt drives — he's up on login
  const [callMode, setCallMode] = useState(false)  // full-screen "video call"
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

  useEffect(() => {
    fetch('/api/health').then((r) => r.json())
      .then((h) => setVoiceOk(!!h.voice_available)).catch(() => {})
  }, [])

  useEffect(() => mattAudio.subscribe(setAvatar), [])

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [messages, open, busy])

  const started = messages.some((m) => m.role === 'user')
  const history = (msgs) => msgs.filter((m) => !m._local)
    .map(({ role, content }) => ({ role, content }))
  const lastReply = [...messages].reverse()
    .find((m) => m.role === 'assistant' && !m._local)?.content || ''

  const openRfp = (an) => {
    setCallMode(false)
    window.dispatchEvent(new CustomEvent('mtrfp:navigate',
      { detail: { tab: 'dashboard', open_application_number: an } }))
  }

  const applyResult = (d, next) => {
    setMessages([...next, {
      role: 'assistant', content: d.reply, toolLog: d.tool_log,
      options: d.options || [],
    }])
    if (d.navigate) {
      setCallMode(false)  // leave the call so they can see what he pulled up
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
    const next = [...messages, { role: 'user', content: text }]
    setMessages(next)
    setInput('')
    setBusy(true)
    try {
      const r = await authFetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history(next) }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || 'request failed')
      applyResult(d, next)
    } catch (e) {
      setMessages((m) => [...m, {
        role: 'assistant', _local: true,
        content: `Something went wrong: ${e.message}` }])
    } finally { setBusy(false) }
  }

  const toggleMic = async () => {
    if (busy) return
    if (!recording) {
      mattAudio.stop()
      try {
        recRef.current = createRecorder()
        await recRef.current.start()
        setRecording(true)
        mattAudio.setState('listening')
      } catch {
        setMessages((m) => [...m, { role: 'assistant', _local: true,
          content: 'Microphone access was blocked — allow it and try again.' }])
      }
      return
    }
    setRecording(false)
    setBusy(true)
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
      setMessages((m) => [...m, {
        role: 'assistant', _local: true,
        content: `Voice error: ${e.message}` }])
    } finally { setBusy(false) }
  }

  const startCall = () => { setCallMode(true); toggleMic() }
  const exitCall = () => {
    if (recording) { setRecording(false); try { recRef.current?.stop() } catch { /* */ } }
    mattAudio.stop()
    setCallMode(false)
  }
  const toggleSpeaker = () => { if (speakReplies) mattAudio.stop()
    setSpeakReplies(!speakReplies) }

  const statusLabel = recording ? 'listening…'
    : avatar.state === 'speaking' ? 'talking…'
      : busy ? 'thinking…' : 'online'

  // ---- full-screen "video call" ----
  if (open && callMode) {
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
            onClick={toggleMic} disabled={busy}
            title={recording ? 'Stop & send' : 'Talk to Matt'}>
            {recording ? '⏹' : '🎤'}
          </button>
          {voiceOk && (
            <button className="call-btn" onClick={toggleSpeaker}
              title={speakReplies ? 'Mute Matt' : 'Unmute Matt'}>
              {speakReplies ? '🔊' : '🔇'}
            </button>)}
          <button className="call-btn end" onClick={exitCall}
            title="Exit full screen">⤢</button>
        </div>
      </div>
    )
  }

  return (
    <>
      <button className={`chat-fab ${open ? 'open' : ''}`}
        onClick={() => setOpen(!open)} title="Matt — your RFP sidekick">
        {open ? '✕'
          : <Matt state={avatar.state} mouth={avatar.mouth} size={46} />}
      </button>
      {open && (
        <div className="chat-panel">
          <div className="chat-head">
            <span className="chat-title">
              <Matt state={avatar.state} mouth={avatar.mouth} size={40} />
              <span>Matt<span className="chat-status">{statusLabel}</span></span>
            </span>
            <span className="chat-head-controls">
              {voiceOk && (
                <button className={`chat-speaker ${speakReplies ? 'on' : ''}`}
                  title={speakReplies ? 'Voice replies on' : 'Voice replies off'}
                  onClick={toggleSpeaker}>
                  {speakReplies ? '🔊' : '🔇'}
                </button>
              )}
              <button className="chat-close" title="Close"
                onClick={() => setOpen(false)}>✕</button>
            </span>
          </div>

          <div className="chat-body" ref={bodyRef}>
            {!started && (
              <div className="matt-hero">
                <Matt state={avatar.state} mouth={avatar.mouth} size={132} />
                <div className="matt-hero-title">
                  Hey {name || 'there'}! I'm Matt.</div>
                <div className="small">Talk to me or type — I'll pull up open
                  RFPs, score them for us, draft responses, and take you right
                  to what you need.</div>
                {voiceOk && (
                  <button className="primary cta-voice" onClick={startCall}
                    disabled={busy}>🎤  Start a voice conversation</button>)}
                <div className="cta-chips">
                  {['Which deals close this week?',
                    'Show open libraries', "What's our best RFP right now?"]
                    .map((q) => (
                      <button key={q} className="chip" disabled={busy}
                        onClick={() => send(q)}>{q}</button>))}
                </div>
                <div className="small">…or type / dictate in the box below.</div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`chat-msg ${m.role}`}>
                {m.content}
                {m.toolLog?.length > 0 && (
                  <div className="chat-tools">
                    {m.toolLog.map((t, j) => (
                      <span key={j} className={t.ok ? '' : 'err'}>
                        ⚙ {t.tool}</span>))}
                  </div>
                )}
                {m.options?.length > 0 && (
                  <div className="chat-options">
                    {m.options.map((o) => (
                      <button key={o.application_number}
                        className={`opt ${o.biddable ? '' : 'opt-no'}`}
                        onClick={() => openRfp(o.application_number)}>
                        {o.label} ›</button>))}
                  </div>
                )}
              </div>
            ))}
            {busy && <div className="chat-msg assistant">Working…</div>}
            {recording && started && <div className="chat-msg assistant rec">
              ● Recording — tap the mic again to send</div>}
          </div>

          <div className="chat-input">
            {voiceOk && (
              <button className={`mic ${recording ? 'rec' : ''}`}
                onClick={toggleMic} disabled={busy}
                title={recording ? 'Stop & send' : 'Talk / dictate'}>
                🎤
              </button>
            )}
            <input value={input} disabled={busy || recording}
              placeholder={recording ? 'Listening…' : 'Message Matt…'}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()} />
            <button className="primary" onClick={() => send()}
              disabled={busy || recording || !input.trim()}>Send</button>
          </div>
        </div>
      )}
    </>
  )
}
