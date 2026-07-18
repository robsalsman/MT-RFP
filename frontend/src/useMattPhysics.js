import { useCallback, useEffect, useRef, useState } from 'react'

// Drag Matt's stage around the screen (desktop), with velocity-reactive
// physics: he leans into fast motion and his weight springs back (with a bit
// of overshoot = a stagger/re-adjust) when you stop; fling him hard and his
// stage props (mic stand, bottle) topple over, then right themselves.
//
// The lean integrates on each pointer-move (event-driven) so it responds even
// when requestAnimationFrame is throttled; RAF then handles the settle/recover
// after you let go.
const clamp = (v, a, b) => Math.max(a, Math.min(b, v))

export function useMattPhysics(enabled) {
  const [pos, setPos] = useState(() => {
    try {
      const s = JSON.parse(localStorage.getItem('mtrfp_matt_pos') || 'null')
      if (s && typeof s.left === 'number') return s
    } catch { /* ignore */ }
    return null
  })
  const [dragging, setDragging] = useState(false)
  const [phys, setPhys] = useState({
    lean: 0, stumble: false,
    mic: { angle: 0, down: false }, bottle: { angle: 0, down: false },
  })

  const drag = useRef({ active: false, offX: 0, offY: 0,
    lastX: 0, lastT: 0, vx: 0 })
  const sim = useRef({ lean: 0, leanVel: 0, mic: 0, micVel: 0,
    bottle: 0, bottleVel: 0, micDown: false, bottleDown: false,
    micUntil: 0, bottleUntil: 0 })
  const raf = useRef(0)

  // advance the physics one tick; returns true when everything has settled
  const integrate = useCallback(() => {
    const d = drag.current, s = sim.current
    if (!d.active) d.vx *= 0.82           // velocity bleeds off after release
    const speed = Math.abs(d.vx)
    const now = Date.now()

    // body lean: opposite to motion, on a spring (overshoot = weight re-adjust)
    const leanTarget = clamp(-d.vx * 0.5, -26, 26)
    s.leanVel += (leanTarget - s.lean) * 0.18
    s.leanVel *= 0.76
    s.lean += s.leanVel

    // topple props past a hard fling; they self-right after a beat
    if (speed > 36) {
      if (!s.micDown) { s.micDown = true; s.micUntil = now + 1700 }
      if (!s.bottleDown) { s.bottleDown = true; s.bottleUntil = now + 2200 }
    }
    if (s.micDown && now > s.micUntil) s.micDown = false
    if (s.bottleDown && now > s.bottleUntil) s.bottleDown = false
    const spring = (a, v, t) => { v += (t - a) * 0.16; v *= 0.8; return [a + v, v] }
    ;[s.mic, s.micVel] = spring(s.mic, s.micVel,
      s.micDown ? -84 : clamp(-d.vx * 0.7, -22, 22))
    ;[s.bottle, s.bottleVel] = spring(s.bottle, s.bottleVel,
      s.bottleDown ? 86 : clamp(-d.vx * 0.6, -20, 20))

    setPhys({ lean: s.lean, stumble: speed > 22,
      mic: { angle: s.mic, down: s.micDown },
      bottle: { angle: s.bottle, down: s.bottleDown } })

    return !d.active && speed < 0.5
      && Math.abs(s.lean) < 0.3 && Math.abs(s.leanVel) < 0.3
      && !s.micDown && !s.bottleDown
      && Math.abs(s.mic) < 0.5 && Math.abs(s.bottle) < 0.5
  }, [])

  // RAF loop drives the settle/recovery after release (and prop self-righting)
  const step = useCallback(() => {
    if (integrate()) { raf.current = 0; return }
    raf.current = requestAnimationFrame(step)
  }, [integrate])
  const startSettle = useCallback(() => {
    if (!raf.current) raf.current = requestAnimationFrame(step)
  }, [step])

  const onMove = useCallback((e) => {
    const d = drag.current
    if (!d.active) return
    const now = performance.now()
    const dt = Math.max(1, now - d.lastT)
    const inst = (e.clientX - d.lastX) * (16 / dt)   // ~px per 60fps frame
    d.vx = d.vx * 0.5 + inst * 0.5
    d.lastX = e.clientX; d.lastT = now
    const W = window.innerWidth, H = window.innerHeight
    setPos({ left: clamp(e.clientX - d.offX, -60, W - 120),
      top: clamp(e.clientY - d.offY, 6, H - 120) })
    integrate()   // event-driven lean/topple (robust under RAF throttling)
  }, [integrate])

  const onUp = useCallback(() => {
    drag.current.active = false
    setDragging(false)
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    setPos((p) => {
      if (p) { try { localStorage.setItem('mtrfp_matt_pos', JSON.stringify(p)) } catch { /* */ } }
      return p
    })
    startSettle()   // spring the lean back / stand the props up
  }, [onMove, startSettle])

  const onPointerDown = useCallback((e) => {
    if (!enabled) return
    // grab Matt himself, not the buttons / chat panel
    if (e.target.closest('button, input, textarea, a, .stage-controls, '
      + '.stage-top, .chat-side')) return
    const rect = e.currentTarget.getBoundingClientRect()
    const d = drag.current
    d.active = true
    d.offX = e.clientX - rect.left; d.offY = e.clientY - rect.top
    d.lastX = e.clientX; d.lastT = performance.now(); d.vx = 0
    setDragging(true)
    setPos({ left: rect.left, top: rect.top })
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }, [enabled, onMove, onUp])

  useEffect(() => () => {
    if (raf.current) cancelAnimationFrame(raf.current)
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
  }, [onMove, onUp])

  const style = pos
    ? { left: `${pos.left}px`, top: `${pos.top}px`, right: 'auto', bottom: 'auto' }
    : {}
  return { style, phys, onPointerDown, dragging, resetPos: () => {
    localStorage.removeItem('mtrfp_matt_pos'); setPos(null)
  } }
}
