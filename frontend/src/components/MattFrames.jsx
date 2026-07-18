import React, { useEffect, useState } from 'react'

// Frame-based Matt: plays painted pose frames (green-screen PNGs) and swaps a
// "talking" frame by voice amplitude for lip-sync. Chroma-keys #00b140 to
// transparent in-browser so the art drops in with no editing. Renders nothing
// until at least the idle frame loads — so the app keeps showing the vector
// puppet until real frames are added to /public/matt-frames.
const BASE = '/matt-frames'
const level = (m) => (m < 0.08 ? 'closed' : m < 0.34 ? 'mid' : 'open')

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
  onReady, onFail }) {
  const [manifest, setManifest] = useState(null)
  const [frames, setFrames] = useState(null)   // { filename: dataURL }

  useEffect(() => {
    let alive = true
    fetch(`${BASE}/frames.json`)
      .then((r) => { if (!r.ok) throw new Error('no manifest'); return r.json() })
      .then(async (mf) => {
        const idle = mf.states?.idle?.src
        if (!idle) throw new Error('no idle frame')
        // idle is required — this throws (and we fall back) until it exists
        const out = { [idle]: await keyGreen(`${BASE}/${idle}`) }
        const rest = new Set()
        const add = (s) => s && rest.add(s)
        add(mf.states?.listening?.src)
        Object.values(mf.states?.speaking?.mouths || {}).forEach(add)
        Object.values(mf.actions || {}).forEach((a) => add(a.src))
        rest.delete(idle)
        await Promise.all([...rest].map(async (s) => {
          try { out[s] = await keyGreen(`${BASE}/${s}`) } catch { /* optional */ }
        }))
        if (!alive) return
        setManifest(mf); setFrames(out); onReady && onReady()
      })
      .catch(() => { if (alive && onFail) onFail() })
    return () => { alive = false }
  }, [])   // eslint-disable-line

  if (!frames || !manifest) return null

  const idleSrc = manifest.states.idle.src
  let src = idleSrc
  const sp = manifest.states.speaking?.mouths
  if (state === 'speaking' && sp) {
    src = sp[level(mouth)] || sp.mid || sp.closed || idleSrc
  } else if (state === 'listening' && manifest.states.listening?.src) {
    src = manifest.states.listening.src
  }
  const url = frames[src] || frames[idleSrc]

  return (
    <div className="matt-frames-host"
      style={{ transform: `rotate(${lean.toFixed(2)}deg)`,
        transformOrigin: '50% 95%' }}>
      <img src={url} alt="Matt" draggable={false} />
    </div>
  )
}
