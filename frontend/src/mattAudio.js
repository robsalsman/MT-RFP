// Drives Matt's mouth from the assistant's actual voice. When TTS audio
// plays, it's routed through a Web Audio analyser and the real-time
// amplitude becomes the mouth-open amount — so Matt lip-syncs to what he's
// literally saying. State (idle / listening / speaking) is broadcast to the
// avatar component.

let ctx = null
let analyser = null
let data = null
let raf = null
let currentAudio = null
const listeners = new Set()
let current = { state: 'idle', mouth: 0 }

function emit() { for (const l of listeners) l(current) }

export function subscribe(cb) {
  listeners.add(cb)
  cb(current)
  return () => listeners.delete(cb)
}

export function setState(state) {
  current = { state, mouth: state === 'speaking' ? current.mouth : 0 }
  emit()
}

function ensureCtx() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext
    ctx = AC ? new AC() : null
  }
  if (ctx && ctx.state === 'suspended') ctx.resume().catch(() => {})
  return ctx
}

export function play(src) {
  stop()
  const audio = new Audio(src)
  currentAudio = audio
  const c = ensureCtx()
  if (c) {
    try {
      const source = c.createMediaElementSource(audio)
      analyser = c.createAnalyser()
      analyser.fftSize = 512
      data = new Uint8Array(analyser.fftSize)
      source.connect(analyser)
      analyser.connect(c.destination)
    } catch { analyser = null }  // fall back to plain playback, no lip-sync
  }
  current = { state: 'speaking', mouth: 0 }
  emit()
  loop()
  const done = () => { if (currentAudio === audio) stop() }
  audio.onended = done
  audio.onerror = done
  audio.play().catch(done)
  return audio
}

function loop() {
  if (raf) return
  const tick = () => {
    if (analyser && data) {
      analyser.getByteTimeDomainData(data)
      let sum = 0
      for (let i = 0; i < data.length; i++) {
        const v = (data[i] - 128) / 128
        sum += v * v
      }
      const rms = Math.sqrt(sum / data.length)
      const target = Math.min(1, rms * 3.4)
      // smooth so the jaw doesn't chatter
      current = { state: 'speaking', mouth: current.mouth * 0.45 + target * 0.55 }
      emit()
    }
    raf = requestAnimationFrame(tick)
  }
  raf = requestAnimationFrame(tick)
}

export function stop() {
  if (raf) { cancelAnimationFrame(raf); raf = null }
  if (currentAudio) { try { currentAudio.pause() } catch { /* ignore */ } }
  currentAudio = null
  analyser = null
  data = null
  current = { state: 'idle', mouth: 0 }
  emit()
}

// debug handle — lets automated checks (and console debugging) drive Matt's
// state without playing real audio
if (typeof window !== 'undefined') {
  window.__mattAudio = { setState, stop }
}
