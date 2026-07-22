import React, { useEffect, useRef, useState } from 'react'

// Frame-based Matt: plays painted pose frames (green-screen PNGs) and swaps a
// "talking" frame by voice amplitude for lip-sync. Chroma-keys #00b140 to
// transparent in-browser so the art drops in with no editing. Renders nothing
// until at least the idle frame loads — so the app keeps showing the vector
// puppet until real frames are added to /public/matt-frames.
const BASE = '/matt-frames'
const level = (m) => (m < 0.08 ? 'closed' : m < 0.34 ? 'mid' : 'open')

// Amplitude-driven lip-sync for the chest-up viseme busts. We only have voice
// loudness (not phonemes), so we map openness → a band of mouth shapes and
// rotate within the band over time so it reads as varied talking, not one
// repeating frame. Bands are ordered closed → wide.
const VISEME_BANDS = [
  ['rest', 'MBP'],        // ~silent / lips together
  ['WQ', 'U', 'O', 'FV'], // small / rounded
  ['E', 'etc', 'L'],      // mid-open
  ['AI', 'wide'],         // wide open
]
function pickViseme(mouth, tick, has) {
  const bi = mouth < 0.08 ? 0 : mouth < 0.2 ? 1 : mouth < 0.4 ? 2 : 3
  const band = VISEME_BANDS[bi].filter((k) => has(k))
  if (!band.length) return 'rest'
  return band[tick % band.length]
}

// When the amplitude signal is dead (autoplay policy blocked the analyser,
// muted tab, etc.) the mouth would freeze at 0 — instead we synthesize a
// natural-looking talk cadence so Matt visibly speaks whenever TTS plays.
const SYNTH_MOUTH = [0.12, 0.5, 0.3, 0.72, 0.22, 0.55, 0.1, 0.42, 0.66,
  0.28, 0.05, 0.48]

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const im = new Image()
    im.crossOrigin = 'anonymous'
    im.onload = () => resolve(im)
    im.onerror = reject
    im.src = url
  })
}

// green-screen key + light despill -> transparent PNG data URL
async function keyGreen(url) {
  const img = await loadImage(url)
  const c = document.createElement('canvas')
  c.width = img.naturalWidth; c.height = img.naturalHeight
  const ctx = c.getContext('2d')
  ctx.drawImage(img, 0, 0)
  const d = ctx.getImageData(0, 0, c.width, c.height)
  const p = d.data
  for (let i = 0; i < p.length; i += 4) {
    const r = p[i], g = p[i + 1], b = p[i + 2]
    if (g > 90 && g > r * 1.35 && g > b * 1.35) p[i + 3] = 0        // key green
    else if (g > r && g > b) p[i + 1] = Math.round((r + b) / 2)     // despill
  }
  ctx.putImageData(d, 0, 0)
  return c.toDataURL('image/png')
}

export default function MattFrames({ state = 'idle', mouth = 0, lean = 0,
  closeup = false, pose = null, sequence = null, seqFps = 12,
  onReady, onFail }) {
  const [manifest, setManifest] = useState(null)
  const [frames, setFrames] = useState(null)   // { filename: dataURL }
  const [seqIdx, setSeqIdx] = useState(0)
  const [talkTick, setTalkTick] = useState(0)  // close-up talk clock
  const [blink, setBlink] = useState('open')   // close-up blink state
  const mouthAlive = useRef(0)                 // last time real amplitude seen
  const prevBustRef = useRef(null)             // previous close-up frame (fade)
  const pendingBustRef = useRef(null)
  useEffect(() => { prevBustRef.current = null }, [closeup])
  // after each paint, the frame just shown becomes the next fade underlay
  useEffect(() => { prevBustRef.current = pendingBustRef.current })

  // amplitude liveness: if the analyser feeds us real mouth values we use
  // them; if it's dead we fall back to the synthesized cadence
  useEffect(() => {
    if (mouth > 0.04) mouthAlive.current = Date.now()
  }, [mouth])

  // talk clock: ~12.5fps viseme cadence (the animation "on 12s" sweet spot —
  // faster discrete swaps read as churn, not smoothness; the 60fps feel
  // comes from the crossfade + amplitude motion layers on top)
  useEffect(() => {
    if (!closeup || state !== 'speaking') { setTalkTick(0); return }
    const id = setInterval(() => setTalkTick((t) => t + 1), 80)
    return () => clearInterval(id)
  }, [closeup, state])

  // blink scheduler: every few seconds, half -> closed -> open
  useEffect(() => {
    if (!closeup) return
    let alive = true
    const timers = []
    const later = (fn, ms) => { const t = setTimeout(fn, ms); timers.push(t) }
    const schedule = () => {
      if (!alive) return
      later(() => {
        setBlink('half')
        later(() => {
          setBlink('closed')
          later(() => { setBlink('open'); schedule() }, 130)
        }, 70)
      }, 2600 + Math.random() * 3400)
    }
    schedule()
    return () => { alive = false; timers.forEach(clearTimeout) }
  }, [closeup])

  // Sequence playback: loop the named sequence's frames at seqFps. The caller
  // controls how long it runs by clearing the `sequence` prop.
  useEffect(() => {
    if (!manifest || !sequence) { setSeqIdx(0); return }
    const arr = manifest.sequences?.[sequence]
    if (!Array.isArray(arr) || !arr.length) return
    arr.forEach((s) => { const im = new Image(); im.src = `${BASE}/${s}` }) // prewarm
    let i = 0; setSeqIdx(0)
    const id = setInterval(() => { i = (i + 1) % arr.length; setSeqIdx(i) },
      Math.round(1000 / Math.max(1, seqFps)))
    return () => clearInterval(id)
  }, [sequence, manifest, seqFps])

  useEffect(() => {
    let alive = true
    const url = (s) => `${BASE}/${s}`
    fetch(`${BASE}/frames.json`)
      .then((r) => { if (!r.ok) throw new Error('no manifest'); return r.json() })
      .then(async (mf) => {
        const idle = mf.states?.idle?.src
        if (!idle) throw new Error('no idle frame')
        const refs = new Set()
        const add = (s) => s && refs.add(s)
        add(mf.states?.idle?.src); add(mf.states?.listening?.src)
        add(mf.states?.speaking?.src)
        Object.values(mf.states?.speaking?.mouths || {}).forEach(add)
        Object.values(mf.visemes || {}).forEach(add)
        Object.values(mf.blinks || {}).forEach(add)
        Object.values(mf.expressions || {}).forEach(add)
        Object.values(mf.actions || {}).forEach((a) => add(a.src))
        Object.values(mf.poses || {}).forEach(add)
        Object.values(mf.sequences || {}).forEach((arr) =>
          Array.isArray(arr) && arr.forEach(add))
        const out = {}
        if (mf.preKeyed) {
          await loadImage(url(idle))          // confirms it exists (else fall back)
          refs.forEach((s) => { out[s] = url(s) })
          // warm the frames used in animation so swaps are instant
          const warm = [mf.states?.listening?.src, mf.states?.speaking?.src,
                        ...Object.values(mf.visemes || {}),
                        ...Object.values(mf.blinks || {})]
          for (const s of warm) {
            if (s) { const i = new Image(); i.src = url(s) }
          }
        } else {
          out[idle] = await keyGreen(url(idle))   // required
          refs.delete(idle)
          await Promise.all([...refs].map(async (s) => {
            try { out[s] = await keyGreen(url(s)) } catch { /* optional */ }
          }))
        }
        if (!alive) return
        setManifest(mf); setFrames(out); onReady && onReady()
      })
      .catch(() => { if (alive && onFail) onFail() })
    return () => { alive = false }
  }, [])   // eslint-disable-line

  if (!frames || !manifest) return null

  // ---- close-up call view: chest-up viseme busts with amplitude lip-sync ----
  const vis = manifest.visemes
  if (closeup && vis && frames[vis.rest]) {
    const has = (k) => !!frames[vis[k]]
    let src = vis.rest
    if (state === 'speaking') {
      // real amplitude when the analyser is alive; synthesized cadence when
      // it isn't (so the mouth always moves while TTS plays)
      const live = Date.now() - mouthAlive.current < 500
      const m = live ? mouth : SYNTH_MOUTH[talkTick % SYNTH_MOUTH.length]
      src = vis[pickViseme(m, talkTick, has)] || vis.rest
    } else if (blink !== 'open' && manifest.blinks?.[blink]
               && frames[manifest.blinks[blink]]) {
      src = manifest.blinks[blink]     // mid-blink frame
    } else if (state === 'listening') {
      const attentive = manifest.expressions?.look_screen
      src = (attentive && frames[attentive]) ? attentive
        : (has('E') ? vis.E : vis.rest)
    }
    const burl = frames[src] || frames[vis.rest]
    // crossfade: the previous frame sits underneath while the new one fades
    // in (~90ms) — hides render-to-render detail differences so the swaps
    // read as motion, not flicker
    pendingBustRef.current = burl
    const under = prevBustRef.current || burl
    // 60fps motion layer: amplitude drives a continuous micro head-bob and
    // lean (updates every analyser emit, smoothed by a CSS transition) —
    // this is what makes him feel alive BETWEEN the discrete mouth frames
    const bob = state === 'speaking' ? Math.min(mouth, 1) : 0
    const motion = `translateY(${(-bob * 5).toFixed(1)}px) `
      + `rotate(${(bob * 0.7 - 0.35).toFixed(2)}deg) `
      + `scale(${(1 + bob * 0.01).toFixed(3)})`
    return (
      <div className={`matt-bust-host ${state === 'listening' ? 'listen' : ''}`}>
        <div className="bust-motion"
          style={{ transform: state === 'speaking' ? motion : undefined }}>
          <img src={under} alt="" aria-hidden draggable={false} />
          <img key={burl} src={burl} alt="Matt" draggable={false}
            className="bust-top" />
        </div>
      </div>
    )
  }

  const idleSrc = manifest.states.idle.src
  let src = idleSrc
  const sp = manifest.states.speaking
  if (state === 'speaking' && sp?.mouths) {
    src = sp.mouths[level(mouth)] || sp.mouths.mid || sp.mouths.closed || idleSrc
  } else if (state === 'speaking' && sp?.src) {
    src = sp.src
  } else if (state === 'listening' && manifest.states.listening?.src) {
    src = manifest.states.listening.src
  }
  // pose override (closet / action), then sequence override (animation) win
  if (pose && manifest.poses?.[pose]) src = manifest.poses[pose]
  if (sequence && manifest.sequences?.[sequence]?.length) {
    const arr = manifest.sequences[sequence]
    src = arr[Math.min(seqIdx, arr.length - 1)]
  }
  const url = frames[src] || frames[idleSrc]
  // a subtle voice-driven bob while he talks (until real viseme frames exist)
  const bob = state === 'speaking' && !pose && !sequence
    ? -Math.min(mouth, 1) * 3 : 0

  return (
    <div className="matt-frames-host"
      style={{ transform: `translateY(${bob.toFixed(1)}px) rotate(${lean.toFixed(2)}deg)`,
        transformOrigin: '50% 95%' }}>
      <img src={url} alt="Matt" draggable={false} />
    </div>
  )
}
