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
// Matt's closet: pull an item out and he actually holds it. `hold` is his
// hold pose (frames.json poses key), `prop` the painted item shown as the
// drawer thumbnail. Grouped by `kind`.
const CLOSET = [
  { id: 'guitar_electric', label: 'Guitar', kind: 'Music', hold: 'hold_guitar_electric', prop: 'prop_music_guitar_electric' },
  { id: 'mic_handheld', label: 'Mic', kind: 'Music', hold: 'hold_mic_handheld', prop: 'prop_music_mic_handheld' },
  { id: 'headphones', label: 'Headphones', kind: 'Music', hold: 'hold_headphones', prop: 'prop_music_headphones' },
  { id: 'keytar', label: 'Keytar', kind: 'Music', hold: 'hold_keytar', prop: 'prop_music_keytar' },
  { id: 'cowbell', label: 'Cowbell', kind: 'Music', hold: 'hold_cowbell', prop: 'prop_flair_cowbell' },
  { id: 'laptop', label: 'Laptop', kind: 'Business', hold: 'hold_laptop', prop: 'prop_biz_laptop' },
  { id: 'clipboard', label: 'Clipboard', kind: 'Business', hold: 'hold_clipboard', prop: 'prop_biz_clipboard' },
  { id: 'document', label: 'RFP docs', kind: 'Business', hold: 'hold_document', prop: 'prop_biz_document_stack' },
  { id: 'pointer', label: 'Pointer', kind: 'Business', hold: 'hold_pointer', prop: 'prop_biz_pointer' },
  { id: 'coffee_mug', label: 'Coffee', kind: 'Business', hold: 'hold_coffee_mug', prop: 'prop_biz_coffee_mug' },
  { id: 'sunglasses', label: 'Shades', kind: 'Flair', hold: 'hold_sunglasses', prop: 'prop_flair_sunglasses' },
  { id: 'trophy', label: 'Trophy', kind: 'Flair', hold: 'hold_trophy', prop: 'prop_flair_trophy' },
  { id: 'confetti', label: 'Confetti', kind: 'Flair', hold: 'hold_confetti', prop: 'prop_flair_confetti' },
]
const CLOSET_KINDS = ['Music', 'Business', 'Flair']

// Matt periodically shows off closet gear while idle — {n} = user's name
const SHOWOFF = [
  { pose: 'hold_guitar_electric',
    line: "Check it, {n} — the axe. Land us the next deal and I'll write a riff about you." },
  { pose: 'hold_keytar',
    line: 'Keytar break! You close deals, {n}, I shred. Fair division of labour.' },
  { pose: 'hold_trophy',
    line: "Keeping this polished for you, {n} — the next win's got your name all over it." },
  { pose: 'hold_sunglasses',
    line: "Had to grab the shades, {n} — your pipeline's looking that bright today." },
  { pose: 'hold_cowbell',
    line: 'House rule, {n}: every meeting you book, I hit the cowbell. Ready when you are.' },
  { pose: 'hold_coffee_mug',
    line: "Brew's on, {n}. You do the hunting, I'll keep the band caffeinated." },
  { pose: 'hold_mic_handheld',
    line: 'Mic check — one, two. Say the word, {n}, and I\'ll sing your praises to a school district.' },
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
    .find((m) => m.role === 'assistant' && (!m._local || m._showoff))
  const lastReply = lastAsst?.content
  const bubble = lastReply
    || `Hey ${name || 'there'}! Give me a sec — pulling up the best RFPs for us…`
  const bubblePicks = (lastAsst?.picks) || []
  const bubbleDownloads = lastAsst?.downloads
  const statusLabel = recording ? 'listening — release to send'
    : avatar.state === 'speaking' ? 'talking…'
      : busy ? 'thinking…' : 'online'

  // Proactive open: Matt greets with BOTH pipelines — top mission-fit RFPs
  // and the best competitor-displacement targets — and asks which hunt
  // Kim fancies today.
  const proactiveDone = useRef(false)
  useEffect(() => {
    if (proactiveDone.current) return
    proactiveDone.current = true
    Promise.allSettled([
      api.rfps({ status: 'OPEN', mission_only: true }),
      api.competitorLeads({ sort: 'spend', limit: 150 }),
    ]).then(([rfpRes, leadRes]) => {
      const picks = []
      const rfps = rfpRes.status === 'fulfilled'
        ? (rfpRes.value.rfps || []).slice(0, 2) : []
      rfps.forEach((r) => picks.push({ kind: 'rfp',
        application_number: r.application_number,
        label: `${r.billed_entity_name} · ${r.state}`,
        entity: r.billed_entity_name }))
      const leads = leadRes.status === 'fulfilled'
        ? (leadRes.value.leads || []) : []
      // best displacement = big E-Rate spender whose contract comes up
      // within ~15 months (renewal window opening)
      const today = new Date().toISOString().slice(0, 10)
      const horizon = new Date(Date.now() + 456 * 864e5)
        .toISOString().slice(0, 10)
      const expiring = leads.filter((l) => l.source !== 'ecf'
        && l.next_expiration && l.next_expiration >= today
        && l.next_expiration <= horizon
        && l.status === 'new').sort((a, b) => b.spend - a.spend)
      if (expiring[0]) picks.push({ kind: 'lead', lead_id: expiring[0].id,
        label: `${expiring[0].org} — $${Math.round(expiring[0].spend)
          .toLocaleString()}/yr to ${expiring[0].competitor_label}, `
          + `expires ${expiring[0].next_expiration}` })
      // best win-back = biggest ECF account not yet contacted
      const winback = leads.filter((l) => l.source === 'ecf'
        && l.status === 'new').sort((a, b) => b.spend - a.spend)
      if (winback[0]) picks.push({ kind: 'lead', lead_id: winback[0].id,
        label: `${winback[0].org} — ${winback[0].competitor_label} `
          + `win-back ($${Math.round(winback[0].spend).toLocaleString()} ECF)` })
      if (leads.length) picks.push({ kind: 'nav',
        label: 'Open the full Leads board' })
      if (!picks.length) return
      const hi = name ? `Hey ${name}! ` : 'Hey! '
      const content = hi + 'What are we hunting today — fresh RFPs, or '
        + 'raiding competitor accounts? These are my best targets right '
        + 'now. Tap one and I\'ll get to work.'
      setMessages((m) => [...m, { role: 'assistant', _proactive: true,
        content, picks }])
      playSeq('wave', 2400)   // he waves hello when he greets you

      // one-time tour of the new hunting kit (per browser)
      const TOUR_KEY = 'mtrfp_tour_leadsources_v1'
      if (!localStorage.getItem(TOUR_KEY)) {
        localStorage.setItem(TOUR_KEY, '1')
        const who = name || 'mate'
        const tour = `Oh, and ${who} — while you were out I rebuilt the `
          + 'whole hunting kit. Seven new tricks, all yours:\n\n'
          + '🤝 CONSULTANT CHANNEL — I ranked every E-Rate consultant by '
          + 'client reach (E-Rate Central alone touches 139 of our '
          + 'targets). One partnership = a hundred doors. There\'s a '
          + 'Consultants view on the Leads page, and I\'ll draft the '
          + 'partnership pitch.\n'
          + '📚 LIBRARY HIT LIST — every public library in America, ranked '
          + 'by how many local families lost the ACP internet subsidy. '
          + 'That\'s your Project: Volume Up pipeline, sorted by real '
          + 'need.\n'
          + '⛔ DENIED FUNDING — districts whose E-Rate money got denied: '
          + 'documented need, no funding, and our nonprofit pricing works '
          + 'without E-Rate. Bonus: a bidding-violation denial means a '
          + 'fresh RFP is coming.\n'
          + '📉 ACP NEED STATS — I can tell you exactly how many '
          + 'households lost their internet subsidy in any zip, and I '
          + 'work it into your outreach emails automatically.\n'
          + '🗺️ REAL METRO TARGETING — "DFW" now means actual zip codes, '
          + 'not guesswork. Found Arlington ISD paying Verizon $413k/yr '
          + 'the first time I used it.\n'
          + '📰 FRESH NEWS + 📋 BID BOARDS — same-week news on competitor '
          + 'programs, and cellular/hotspot bids on procurement portals '
          + 'E-Rate never sees.\n\n'
          + 'Try one below — you\'re going to be dangerous with these.'
        setMessages((m) => [...m, { role: 'assistant', _proactive: true,
          content: tour, picks: [
            { kind: 'ask', icon: '🤝', label: 'Top consultants to partner with',
              prompt: 'Who are the top E-Rate consultants we should partner with?' },
            { kind: 'ask', icon: '📚', label: 'Library targets in Texas',
              prompt: 'Which Texas libraries need hotspot lending the most?' },
            { kind: 'ask', icon: '⛔', label: 'Who got denied funding?',
              prompt: 'Who got denied E-Rate funding in Texas this year?' },
            { kind: 'ask', icon: '📋', label: 'Bids outside E-Rate',
              prompt: 'Find open cellular or hotspot bids outside E-Rate' },
          ] }])
      }
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

  // Show-off loop: while idle on stage, Matt pulls something from his
  // closet, drops a line about it (and Kim), then puts it away. Never
  // interrupts work: skips when busy/recording/speaking or when a pose is
  // already held.
  const showOffIdx = useRef(Math.floor(Math.random() * SHOWOFF.length))
  useEffect(() => {
    let alive = true
    const timers = []
    const later = (fn, ms) => { const t = setTimeout(fn, ms); timers.push(t) }
    const tryShowOff = () => {
      if (!alive) return
      const idle = viewRef.current === 'stage' && !busyRef.current
        && !recRecording.current && !chatRef.current
      if (idle && framesReady) {
        setClosetPose((cur) => {
          if (cur) return cur          // she's holding something — don't touch
          const item = SHOWOFF[showOffIdx.current % SHOWOFF.length]
          showOffIdx.current += 1
          setMessages((m) => [...m, { role: 'assistant', _local: true,
            _showoff: true,
            content: item.line.replace(/\{n\}/g, name || 'mate') }])
          later(() => setClosetPose(
            (p) => (p === item.pose ? null : p)), 9000)
          return item.pose
        })
      }
      later(tryShowOff, 180000 + Math.random() * 180000)  // every 3-6 min
    }
    later(tryShowOff, 35000 + Math.random() * 20000)      // first: ~35-55s in
    return () => { alive = false; timers.forEach(clearTimeout) }
  }, [framesReady])   // eslint-disable-line

  // greeting picks are mixed-kind: RFP draft / competitor lead / board nav
  const goLeads = (leadId) => {
    if (leadId) window.__openLeadId = leadId
    window.dispatchEvent(new CustomEvent('mtrfp:navigate',
      { detail: { tab: 'leads' } }))
  }
  const pickClick = (p) => {
    if (p.kind === 'ask') { setChatOpen(true); send(p.prompt) }
    else if (p.kind === 'lead') goLeads(p.lead_id)
    else if (p.kind === 'nav') goLeads(null)
    else prepareReply(p.application_number, p.entity)
  }
  const pickIcon = (p) => p.icon || (p.kind === 'lead' ? '⚔️'
    : p.kind === 'nav' ? '📋' : '🎸')

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
              <button key={p.application_number || p.lead_id || p.label}
                className="opt pick" disabled={busy && p.kind !== 'nav'}
                onClick={() => pickClick(p)}>
                {pickIcon(p)} {p.kind === 'rfp' || !p.kind
                  ? `Draft reply — ${p.label}` : p.label}</button>))}
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
        {/* header is a normal flex row — never absolute, so the buttons can
            never overlap the tray/closet/bubble that render below it */}
        <div className="stage-head">
          {!isMobile && (
            <div className="stage-grab">⠿ drag Matt anywhere</div>)}
          <div className="stage-top">
            {!isMobile && dockStyle.left && (
              <button className="stage-icon" title="Reset Matt's position"
                onClick={resetPos}>⟲</button>)}
            <button className={`stage-icon ${closetOpen ? 'on' : ''}`}
              title="Matt's closet"
              onClick={() => setClosetOpen((o) => !o)}>🚪</button>
            <button className="stage-icon" title="Minimize Matt"
              onClick={minimize}>–</button>
          </div>
        </div>

        {closetOpen && (
          <div className="closet">
            <div className="closet-head">
              <span>Matt's closet</span>
              <button className="closet-put" disabled={!closetPose}
                onClick={() => setClosetPose(null)}>Put away</button>
            </div>
            <div className="closet-groups-scroll">
            {CLOSET_KINDS.map((kind) => (
              <div key={kind} className="closet-group">
                <div className="closet-kind">{kind}</div>
                <div className="closet-grid">
                  {CLOSET.filter((it) => it.kind === kind).map((it) => (
                    <button key={it.id}
                      className={`closet-item ${closetPose === it.hold ? 'sel' : ''}`}
                      title={`Matt grabs the ${it.label.toLowerCase()}`}
                      onClick={() => {
                        if (seqTimer.current) clearTimeout(seqTimer.current)
                        setSeqPlay(null); setClosetPose(it.hold)
                      }}>
                      <img className="prop" alt=""
                        src={`/matt-frames/props/${it.prop}.png`} />
                      <span>{it.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
            </div>
          </div>
        )}

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
                      <button key={p.application_number || p.lead_id || p.label}
                        className="stage-pick"
                        disabled={busy && p.kind !== 'nav'} title={p.label}
                        onClick={() => pickClick(p)}>
                        {pickIcon(p)} {p.label}</button>))}
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
