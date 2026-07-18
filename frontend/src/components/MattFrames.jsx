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
  closeup = false, onReady, onFail }) {
  const [manifest, setManifest] = useState(null)
  const [frames, setFrames] = useState(null)   // { filename: dataURL }
  const tickRef = useRef(0)

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
        Object.values(mf.actions || {}).forEach((a) => add(a.src))
        const out = {}
        if (mf.preKeyed) {
          await loadImage(url(idle))          // confirms it exists (else fall back)
          refs.forEach((s) => { out[s] = url(s) })
          // warm the state frames so swaps are instant
          for (const s of [mf.states?.listening?.src, mf.states?.speaking?.src]) {
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
    let key = 'rest'
    if (state === 'speaking') {
      tickRef.current++
      key = pickViseme(mouth, tickRef.current, has)
    } else if (state === 'listening') {
      key = has('E') ? 'E' : 'rest'   // a soft, attentive half-smile
    }
    const burl = frames[vis[key]] || frames[vis.rest]
    return (
      <div className="matt-bust-host">
        <img src={burl} alt="Matt" draggable={false} />
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
  const url = frames[src] || frames[idleSrc]
  // a subtle voice-driven bob while he talks (until real viseme frames exist)
  const bob = state === 'speaking' ? -Math.min(mouth, 1) * 3 : 0

  return (
    <div className="matt-frames-host"
      style={{ transform: `translateY(${bob.toFixed(1)}px) rotate(${lean.toFixed(2)}deg)`,
        transformOrigin: '50% 95%' }}>
      <img src={url} alt="Matt" draggable={false} />
    </div>
  )
}
