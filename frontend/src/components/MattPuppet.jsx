import React, { useEffect, useRef, useState } from 'react'
import { createMattAvatar } from '../mattAvatarRuntime.js'

// The real Codex puppet, mounted via its runtime. We drive its MOUTH from our
// existing audio amplitude (its own say() would open a second AudioContext on
// the same element and throw), and its CLIP from the assistant's state. Drag
// lean is a CSS rotate around his feet.
const bucketOf = (m) => (m < 0.08 ? 'closed' : m < 0.34 ? 'smallOpen' : 'wideOpen')

export default function MattPuppet({ state = 'idle', mouth = 0, lean = 0,
  onFail, onReady }) {
  const hostRef = useRef(null)
  const mattRef = useRef(null)
  const [ready, setReady] = useState(false)
  const lastBucket = useRef('closed')
  const lastClip = useRef('idle_sit_stool')

  useEffect(() => {
    let alive = true
    createMattAvatar(hostRef.current, {
      assetBaseUrl: '/matt-avatar/assets', width: 512, height: 768,
      autoBlink: true,
    }).then((m) => {
      if (!alive) { m.destroy(); return }
      mattRef.current = m; setReady(true); onReady && onReady()
    }).catch((e) => {
      console.warn('Matt puppet failed to load', e)
      if (alive && onFail) onFail()
    })
    return () => { alive = false; mattRef.current?.destroy(); mattRef.current = null }
  }, [])   // eslint-disable-line

  // assistant state -> animation clip
  useEffect(() => {
    const m = mattRef.current
    if (!m || !ready) return
    const clip = state === 'speaking' ? 'talking_gesture'
      : state === 'listening' ? 'listening' : 'idle_sit_stool'
    if (clip !== lastClip.current) { lastClip.current = clip; m.play(clip) }
  }, [state, ready])

  // voice amplitude -> mouth shape (only when the bucket changes)
  useEffect(() => {
    const m = mattRef.current
    if (!m || !ready || state !== 'speaking') return
    const b = bucketOf(mouth)
    if (b !== lastBucket.current) { lastBucket.current = b; m.setMouth(b) }
  }, [mouth, state, ready])

  return (
    <div className="matt-puppet-host" ref={hostRef}
      style={{ transform: `rotate(${lean.toFixed(2)}deg)`,
        transformOrigin: '50% 95%' }} />
  )
}
