import { useCallback, useEffect, useRef, useState } from 'react'

// Drag Matt's stage around the screen (desktop), with velocity-reactive
// physics: he leans into fast motion and his weight springs back (with a bit
// of overshoot = a stagger/re-adjust) when you stop; fling him hard and his
// stage gear topples over, then rights itself.
//
// Lean + props integrate on each pointer-move (event-driven) so they respond
// even when requestAnimationFrame is throttled; rAF handles the settle/recover.
const clamp = (v, a, b) => Math.max(a, Math.min(b, v))

// Each prop: base pivot (in MattStage's 260x440 space), how much it sways with
// motion, the fling speed that topples it, the angle it falls to, and how long
// it stays down before Matt stands it back up. Heavier gear (amp) is sturdier.
const PROP_CFG = {
  amp:         { pivot: [36, 410],  sway: 0.16, maxSway: 6,  toppleAt: 64, down: -84, recover: 2400 },
  laptop:      { pivot: [38, 362],  sway: 0.5,  maxSway: 15, toppleAt: 30, down: 72,  recover: 1500 },
  micStand:    { pivot: [66, 410],  sway: 0.7,  maxSway: 22, toppleAt: 34, down: -80, recover: 1700 },
  guitarStand: { pivot: [206, 410], sway: 0.6,  maxSway: 20, toppleAt: 34, down: 80,  recover: 2000 },
  bottle:      { pivot: [232, 410], sway: 0.6,  maxSway: 20, toppleAt: 30, down: 86,  recover: 2200 },
}
const PROP_IDS = Object.keys(PROP_CFG)

export function useMattPhysics(enabled) {
  const [pos, setPos] = useState(() => {
    try {
      const s = JSON.parse(localStorage.getItem('mtrfp_matt_pos') || 'null')
      if (s && typeof s.left === 'number') return s
    } catch { /* ignore */ }
    return null
  })
  const [dragging, setDragging] = useState(false)
  const [phys, setPhys] = useState(() => ({
    lean: 0, stumble: false,
    props: Object.fromEntries(PROP_IDS.map((id) => [id, { angle: 0, down: false }])),
  }))

  const drag = useRef({ active: false, offX: 0, offY: 0, lastX: 0, lastT: 0, vx: 0 })
  const sim = useRef({
    lean: 0, leanVel: 0,
    props: Object.fromEntries(PROP_IDS.map((id) =>
      [id, { angle: 0, vel: 0, down: false, until: 0 }])),
  })
  const raf = useRef(0)

  const integrate = useCallback(() => {
    const d = drag.current, s = sim.current
    if (!d.active) d.vx *= 0.82
    const speed = Math.abs(d.vx)
    const now = Date.now()

    // body lean (spring; overshoot on the way back = weight re-adjust)
    const leanTarget = clamp(-d.vx * 0.5, -26, 26)
    s.leanVel += (leanTarget - s.lean) * 0.18
    s.leanVel *= 0.76
    s.lean += s.leanVel

    // each prop: sway with motion, topple past its threshold, then recover
    const propsOut = {}
    let anyDown = false; let anyMoving = false
    for (const id of PROP_IDS) {
      const c = PROP_CFG[id], p = s.props[id]
      if (speed > c.toppleAt && !p.down) { p.down = true; p.until = now + c.recover }
      if (p.down && now > p.until) p.down = false
      const target = p.down ? c.down : clamp(-d.vx * c.sway, -c.maxSway, c.maxSway)
      p.vel += (target - p.angle) * 0.16
      p.vel *= 0.8
      p.angle += p.vel
      if (p.down) anyDown = true
      if (Math.abs(p.angle) > 0.5 || Math.abs(p.vel) > 0.5) anyMoving = true
      propsOut[id] = { angle: p.angle, down: p.down }
    }

    setPhys({ lean: s.lean, stumble: speed > 22, props: propsOut })

    return !d.active && speed < 0.5
      && Math.abs(s.lean) < 0.3 && Math.abs(s.leanVel) < 0.3
      && !anyDown && !anyMoving
  }, [])

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
    const inst = (e.clientX - d.lastX) * (16 / dt)
    d.vx = d.vx * 0.5 + inst * 0.5
    d.lastX = e.clientX; d.lastT = now
    const W = window.innerWidth, H = window.innerHeight
    setPos({ left: clamp(e.clientX - d.offX, -60, W - 120),
      top: clamp(e.clientY - d.offY, 6, H - 120) })
    integrate()
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
    startSettle()
  }, [onMove, startSettle])

  const onPointerDown = useCallback((e) => {
    if (!enabled) return
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

  // Only honor a saved drag position when dragging is enabled (desktop).
  // On mobile the box is docked bottom-right by CSS — a stale desktop
  // coordinate must not pin it off-screen.
  const style = (enabled && pos)
    ? { left: `${pos.left}px`, top: `${pos.top}px`, right: 'auto', bottom: 'auto' }
    : {}
  return { style, phys, propCfg: PROP_CFG, onPointerDown, dragging,
    resetPos: () => { localStorage.removeItem('mtrfp_matt_pos'); setPos(null) } }
}
