import React, { useEffect, useState } from 'react'

// Full-body Matt on a spotlit stage — an 80s rocker: big dark hair, bandana,
// leather jacket, guitar, ripped jeans, boots. Rim-lit by the spotlight so he
// pops against the dark stage. Mouth opens with `mouth` (0..1, his voice);
// blinks on his own; `state` adds a speaking/listening pulse.
export default function MattStage({ state = 'idle', mouth = 0, height = 300,
  lean = 0, stumble = false, mic = { angle: 0, down: false },
  bottle = { angle: 0, down: false } }) {
  const [blink, setBlink] = useState(0)
  useEffect(() => {
    let t
    const loop = () => {
      t = setTimeout(() => {
        setBlink(1); setTimeout(() => setBlink(0), 120); loop()
      }, 2200 + Math.random() * 3600)
    }
    loop()
    return () => clearTimeout(t)
  }, [])

  const m = Math.max(0, Math.min(1, mouth))
  const mouthRy = 0.8 + m * 6
  const lid = blink * 5
  const skin = '#d8a074'
  const hair = '#2b211c'
  const hairDk = '#170f0b'

  return (
    <div className={`mattstage matt-${state} ${stumble ? 'matt-stumble' : ''}`}>
      <svg viewBox="0 0 260 440" width="100%" height={height} preserveAspectRatio="xMidYMax meet"
        xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="beam" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#fff6d8" stopOpacity=".5" />
            <stop offset="1" stopColor="#fff6d8" stopOpacity="0" />
          </linearGradient>
          <radialGradient id="pool" cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="#ffe9a8" stopOpacity=".5" />
            <stop offset="1" stopColor="#ffe9a8" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="rimg" cx="50%" cy="34%" r="60%">
            <stop offset="0" stopColor="#fff4cf" stopOpacity=".85" />
            <stop offset="1" stopColor="#fff4cf" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* spotlight */}
        <polygon className="beam" points="130,2 66,352 194,352" fill="url(#beam)" />
        <ellipse className="pool" cx="130" cy="410" rx="92" ry="24" fill="url(#pool)" />
        <ellipse cx="130" cy="150" rx="70" ry="150" fill="url(#rimg)" opacity=".45" />

        {/* stage props — they topple if you fling Matt too fast */}
        <g transform={`rotate(${mic.angle.toFixed(1)} 50 410)`}>
          <rect x="47" y="300" width="6" height="112" rx="3" fill="#2b2b33" />
          <ellipse cx="50" cy="296" rx="9" ry="12" fill="#15151b" />
          <ellipse cx="50" cy="296" rx="5.5" ry="8" fill="#39404d" />
          <path d="M36 410 L50 402 L64 410 Z" fill="#1c1c22" />
        </g>
        <g transform={`rotate(${bottle.angle.toFixed(1)} 210 410)`}>
          <rect x="204" y="382" width="12" height="28" rx="4" fill="#2f7d5b"
            opacity=".92" />
          <rect x="207" y="374" width="6" height="10" rx="2" fill="#1f5a41" />
          <rect x="205" y="390" width="10" height="8" rx="2" fill="#d9ead0"
            opacity=".5" />
        </g>

        {/* whoosh streaks when he stumbles */}
        {stumble && (
          <g stroke="#fff4cf" strokeOpacity=".5" strokeWidth="3" fill="none"
            strokeLinecap="round">
            <path d={lean < 0 ? 'M198 150 q16 40 6 90' : 'M62 150 q-16 40 -6 90'} />
            <path d={lean < 0 ? 'M212 172 q14 34 6 72' : 'M48 172 q-14 34 -6 72'} />
          </g>)}

        <g transform={`rotate(${lean.toFixed(2)} 130 410)`}>
        <g transform="translate(130 0)">
          {/* legs — dark ripped jeans */}
          <path d="M-30 250 L-36 388 L-14 388 L-8 256 Z" fill="#20283f" />
          <path d="M30 250 L36 388 L14 388 L8 256 Z" fill="#20283f" />
          <path d="M-30 312 l14 4 M28 316 l-14 4" stroke="#39456a" strokeWidth="2.5" />
          {/* boots */}
          <path d="M-37 388 L-38 410 L-10 410 L-13 388 Z" fill="#0d0d12" />
          <path d="M37 388 L38 410 L10 410 L13 388 Z" fill="#0d0d12" />

          {/* torso: band tee + open leather jacket */}
          <path d="M-34 168 Q0 158 34 168 L40 256 L-40 256 Z" fill="#1b1e28" />
          <path d="M-9 168 L0 250 L9 168 Z" fill="#b8143f" opacity=".85" />
          <path d="M-34 166 L-46 256 L-22 256 L-16 172 Z" fill="#0f0f16" />
          <path d="M34 166 L46 256 L22 256 L16 172 Z" fill="#0f0f16" />
          <path d="M-34 166 L-18 172 L-15 214 Z M34 166 L18 172 L15 214 Z" fill="#373742" />

          {/* arms */}
          <path d="M-34 172 L-52 244 L-40 250 L-24 184 Z" fill="#12121a" />
          <path d="M34 174 L50 214 L34 228 L20 190 Z" fill="#12121a" />

          {/* guitar slung across */}
          <g transform="rotate(-22)">
            <ellipse cx="40" cy="250" rx="26" ry="19" fill="#c0392b" />
            <ellipse cx="40" cy="250" rx="14" ry="10" fill="#7a2018" />
            <rect x="-70" y="245" width="112" height="8" rx="3" fill="#2a1a10" />
            <rect x="-78" y="241" width="14" height="16" rx="2" fill="#141014" />
            <circle cx="40" cy="250" r="3" fill="#efe3c8" />
          </g>

          {/* neck */}
          <rect x="-9" y="120" width="18" height="26" rx="7" fill="#b07b52" />

          {/* head */}
          <g transform="translate(0 82)">
            {/* big dark hair */}
            <path d="M0 -46 C-40 -46 -52 -12 -44 24 C-58 20 -52 54 -34 56
                     C-40 30 -28 16 -22 14 C-32 46 -10 58 -2 58
                     C52 60 66 30 64 12 C70 52 60 56 52 56
                     C70 52 74 16 60 26 C66 -12 52 -46 0 -46 Z" fill={hair} />
            <path d="M0 -40 C-34 -40 -46 -12 -42 20 C-24 2 -12 -2 0 -2
                     C12 -2 24 2 42 20 C46 -12 34 -40 0 -40 Z" fill={hairDk} />
            {/* face */}
            <path d="M-26 -6 C-26 -30 -14 -40 0 -40 C14 -40 26 -30 26 -6
                     C26 14 18 34 0 36 C-18 34 -26 14 -26 -6 Z" fill={skin} />
            {/* rim light on spotlight side */}
            <path d="M-26 -6 C-26 -26 -16 -38 -4 -39 C-16 -30 -22 -12 -20 8 Z"
              fill="#f4d3a8" opacity=".5" />
            {/* bandana */}
            <path d="M-27 -16 Q0 -30 27 -16 L25 -6 Q0 -19 -25 -6 Z" fill="#c62f28" />
            {/* stubble */}
            <path d="M-19 10 Q0 34 19 10 Q0 24 -19 10 Z" fill="#1c140d" opacity=".4" />
            {/* brows */}
            <path d="M-17 -8 q8 -4 15 -1 M2 -9 q8 -3 15 1" stroke="#1c130d"
              strokeWidth="3" fill="none" strokeLinecap="round" />
            {/* eyes */}
            <ellipse cx="-9" cy="0" rx="6.5" ry="4.6" fill="#fff" />
            <circle cx="-9" cy="1" r="2.6" fill="#3f2c22" />
            <circle cx="-9" cy="1" r="1.2" fill="#100a07" />
            <ellipse cx="-9" cy={-4 + lid} rx="7" ry={lid} fill={skin} />
            <ellipse cx="9" cy="0" rx="6.5" ry="4.6" fill="#fff" />
            <circle cx="9" cy="1" r="2.6" fill="#3f2c22" />
            <circle cx="9" cy="1" r="1.2" fill="#100a07" />
            <ellipse cx="9" cy={-4 + lid} rx="7" ry={lid} fill={skin} />
            {/* nose */}
            <path d="M0 4 q-4 8 -6 11 q3 3 6 2" fill="none" stroke="#bd845b"
              strokeWidth="2" strokeLinecap="round" />
            {/* mouth (lip-sync) */}
            <ellipse cx="0" cy="22" rx="8" ry={mouthRy} fill="#7a2f3a" />
            {m < 0.12 && (
              <path d="M-8 22 q8 4 16 0" stroke="#5c3128" strokeWidth="2"
                fill="none" strokeLinecap="round" />)}
          </g>
        </g>
        </g>
      </svg>
    </div>
  )
}
