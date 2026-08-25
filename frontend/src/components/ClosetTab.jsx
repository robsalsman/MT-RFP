import React, { useEffect, useState } from 'react'
import { CLOSET, CLOSET_KINDS, KIND_ICONS, thumbSrc } from '../closet.js'
import { auth } from '../api.js'

// Matt's Closet — the full-page, video-game-inventory view of every look
// he owns. Tapping a slot dresses him live in his dock/studio everywhere
// (the ChatBot listens for mtrfp:wear) and he says his caption line.

export default function ClosetTab() {
  const [filter, setFilter] = useState('All')
  const [wearing, setWearing] = useState(null)   // closet item id

  useEffect(() => {
    const onWearing = (e) => setWearing(e.detail?.id || null)
    window.addEventListener('mtrfp:wearing', onWearing)
    return () => window.removeEventListener('mtrfp:wearing', onWearing)
  }, [])

  const wear = (it) => {
    setWearing(it.id)
    window.dispatchEvent(new CustomEvent('mtrfp:wear',
      { detail: { id: it.id } }))
  }
  const surprise = () =>
    wear(CLOSET[Math.floor(Math.random() * CLOSET.length)])

  const current = CLOSET.find((c) => c.id === wearing)
  const kinds = filter === 'All' ? CLOSET_KINDS : [filter]
  const name = auth.name() || 'mate'

  return (
    <div>
      <div className="card">
        <h3>👕 Matt's Closet <span className="small">· {CLOSET.length} looks
          unlocked · tap any look to put it on him — he'll comment,
          obviously</span></h3>
        <div className="closet-filters">
          <button className={filter === 'All' ? 'primary' : ''}
            onClick={() => setFilter('All')}>All {CLOSET.length}</button>
          {CLOSET_KINDS.map((k) => (
            <button key={k} className={filter === k ? 'primary' : ''}
              onClick={() => setFilter(k)}>
              {KIND_ICONS[k]} {k} {CLOSET.filter((c) => c.kind === k).length}
            </button>
          ))}
        </div>
      </div>
      <div className="closet-body">
        <div className="card closet-equip">
          <h4>NOW WEARING</h4>
          {current ? (<>
            <img className="closet-hero" alt={current.label}
              src={thumbSrc(current)} />
            <div className="closet-name">{current.label}
              <span className="small"> · {current.kind}</span></div>
            {current.line && (
              <p className="small closet-flavor">“{current.line
                .replace(/\{n\}/g, name)}”</p>)}
          </>) : (
            <p className="small">Matt's in his classic bandana look. Tap
              anything on the right and watch his dock — he changes
              instantly, everywhere in the app.</p>
          )}
          <button className="primary" onClick={surprise}>🎲 Surprise me
          </button>
        </div>
        <div className="closet-inv">
          {kinds.map((kind) => (
            <div key={kind} className="card">
              <h4 className="closet-sec">{KIND_ICONS[kind]} {kind}
                <span className="small"> · {CLOSET.filter((c) =>
                  c.kind === kind).length} looks</span></h4>
              <div className="closet-slots">
                {CLOSET.filter((c) => c.kind === kind).map((it) => (
                  <button key={it.id}
                    className={`closet-slot ${wearing === it.id ? 'on' : ''}`}
                    title={it.line ? it.line.replace(/\{n\}/g, name)
                      : `Matt grabs the ${it.label.toLowerCase()}`}
                    onClick={() => wear(it)}>
                    {wearing === it.id && (
                      <span className="wearing-tag">WEARING</span>)}
                    <img alt={it.label} loading="lazy" src={thumbSrc(it)} />
                    <span>{it.label}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
