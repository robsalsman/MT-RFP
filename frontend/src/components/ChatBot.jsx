import React, { useEffect, useRef, useState } from 'react'
import { authFetch } from '../api.js'

const WELCOME = {
  role: 'assistant',
  content: "Hi — I'm the MT-RFP Assistant. Ask me anything about the app, " +
    'your RFP pipeline, or Mission Telecom itself — by text or voice (🎤). ' +
    'Try: "show open RFPs in Ohio", "which deals close this week?", ' +
    '"what do our broadband plans cost?", "take me to the price list upload".',
}

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
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([WELCOME])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [recording, setRecording] = useState(false)
  const [speakReplies, setSpeakReplies] = useState(true)
  const [voiceOk, setVoiceOk] = useState(false)
  const bodyRef = useRef(null)
  const recRef = useRef(null)
  const audioRef = useRef(null)

  useEffect(() => {
    fetch('/api/health').then((r) => r.json())
      .then((h) => setVoiceOk(!!h.voice_available)).catch(() => {})
  }, [])

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [messages, open, busy])

  const history = (msgs) => msgs.filter((m) => m !== WELCOME)
    .map(({ role, content }) => ({ role, content }))

  const applyResult = (d, next) => {
    setMessages([...next, {
      role: 'assistant', content: d.reply, toolLog: d.tool_log,
    }])
    if (d.navigate) window.dispatchEvent(
      new CustomEvent('mtrfp:navigate', { detail: d.navigate }))
    if (d.audio_b64) playB64(d.audio_b64)
    else if (speakReplies && voiceOk && d.reply) speakText(d.reply)
  }

  const playB64 = (b64) => {
    stopAudio()
    audioRef.current = new Audio(`data:audio/wav;base64,${b64}`)
    audioRef.current.play().catch(() => {})
  }
  const speakText = async (text) => {
    try {
      const r = await authFetch('/api/voice/speak', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      if (!r.ok) return
      const blob = await r.blob()
      stopAudio()
      audioRef.current = new Audio(URL.createObjectURL(blob))
      audioRef.current.play().catch(() => {})
    } catch { /* voice is best-effort */ }
  }
  const stopAudio = () => {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null }
  }

  const send = async () => {
    const text = input.trim()
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
        role: 'assistant', content: `Something went wrong: ${e.message}` }])
    } finally { setBusy(false) }
  }

  const toggleMic = async () => {
    if (busy) return
    if (!recording) {
      stopAudio()
      try {
        recRef.current = createRecorder()
        await recRef.current.start()
        setRecording(true)
      } catch {
        setMessages((m) => [...m, { role: 'assistant',
          content: 'Microphone access was blocked — allow it and try again.' }])
      }
      return
    }
    setRecording(false)
    setBusy(true)
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
        role: 'assistant', content: `Voice error: ${e.message}` }])
    } finally { setBusy(false) }
  }

  return (
    <>
      <button className={`chat-fab ${open ? 'open' : ''}`}
        onClick={() => setOpen(!open)} title="MT-RFP Assistant">
        {open ? '✕' : '💬'}
      </button>
      {open && (
        <div className="chat-panel">
          <div className="chat-head">
            <span className="chat-title">MT-RFP Assistant</span>
            <span className="chat-head-controls">
              {voiceOk && (
                <button className={`chat-speaker ${speakReplies ? 'on' : ''}`}
                  title={speakReplies ? 'Voice replies on' : 'Voice replies off'}
                  onClick={() => { if (speakReplies) stopAudio()
                    setSpeakReplies(!speakReplies) }}>
                  {speakReplies ? '🔊' : '🔇'}
                </button>
              )}
              <button className="chat-close" title="Close"
                onClick={() => setOpen(false)}>✕</button>
            </span>
          </div>
          <div className="chat-body" ref={bodyRef}>
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
              </div>
            ))}
            {busy && <div className="chat-msg assistant">Working…</div>}
            {recording && <div className="chat-msg assistant rec">
              ● Recording — click the mic again to send</div>}
          </div>
          <div className="chat-input">
            {voiceOk && (
              <button className={`mic ${recording ? 'rec' : ''}`}
                onClick={toggleMic} disabled={busy}
                title={recording ? 'Stop & send' : 'Speak to the assistant'}>
                🎤
              </button>
            )}
            <input value={input} disabled={busy || recording}
              placeholder={recording ? 'Listening…'
                : 'e.g. "what closes this week?"'}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()} />
            <button className="primary" onClick={send}
              disabled={busy || recording || !input.trim()}>Send</button>
          </div>
        </div>
      )}
    </>
  )
}
