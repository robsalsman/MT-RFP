import React from 'react'

// Toppleable stage gear that overlays the puppet, in the puppet's own 512x768
// space so it lines up. Art is the same as the puppet package's props; each
// piece rotates around its floor pivot, driven by the drag physics (props map
// from useMattPhysics). It sits in front of the figure at the floor line.
export default function StageGear({ props = {} }) {
  const a = (id) => (props[id]?.angle || 0).toFixed(1)
  return (
    <svg className="stage-gear" viewBox="0 0 512 768"
      preserveAspectRatio="xMidYMax meet" xmlns="http://www.w3.org/2000/svg">
      {/* amp (heavy — topples only on a hard fling) */}
      <g transform={`rotate(${a('amp')} 103 656)`}>
        <rect x="44" y="538" width="118" height="118" rx="10" fill="#0d0d12" />
        <rect x="58" y="554" width="90" height="72" fill="#373742" />
        <circle cx="82" cy="590" r="24" fill="#171923" />
        <circle cx="124" cy="590" r="18" fill="#171923" />
        <path stroke="#fff6d8" strokeWidth="4" d="M62 640h82" />
      </g>
      {/* mic boom stand */}
      <g transform={`rotate(${a('micStand')} 366 641)`}>
        <path stroke="#0d0d12" strokeWidth="8" strokeLinecap="round"
          d="M262 216l106 35M366 251v390" />
        <ellipse cx="250" cy="213" rx="22" ry="12" fill="#171923"
          transform="rotate(10 250 213)" />
      </g>
      {/* water bottle (tips easily) */}
      <g transform={`rotate(${a('bottle')} 403 670)`}>
        <path fill="#bde8ff" d="M386 586h34l9 84h-52z" />
        <path fill="#79d7ff" d="M392 612h31l4 42h-39z" />
        <path fill="#0d0d12" d="M392 574h22v15h-22z" />
      </g>
    </svg>
  )
}
