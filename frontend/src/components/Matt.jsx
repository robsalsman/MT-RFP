import React, { useEffect, useState } from 'react'

// Matt — an 80s-rockstar avatar. Big teased blonde hair, red bandana, lightning
// face paint, hoop earring, leather collar. The mouth opens with `mouth` (0..1,
// driven by his voice); he blinks on his own; `state` adds a listening pulse or
// speaking glow.
export default function Matt({ state = 'idle', mouth = 0, size = 120 }) {
  const [blink, setBlink] = useState(0)

  useEffect(() => {
    let t
    const schedule = () => {
      t = setTimeout(() => {
        setBlink(1)
        setTimeout(() => setBlink(0), 120)
        schedule()
      }, 2200 + Math.random() * 3800)
    }
    schedule()
    return () => clearTimeout(t)
  }, [])

  const m = Math.max(0, Math.min(1, mouth))
  const mouthRy = 1.6 + m * 12
  const teethRy = Math.min(4.5, m * 7)
  const lid = blink * 8          // eyelid coverage
  const skin = '#e7b590'

  return (
    <div className={`matt matt-${state}`} style={{ width: size, height: size }}>
      <svg viewBox="0 0 200 210" width={size} height={size}
        xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#ff3d7f" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#ff3d7f" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* aura for speaking/listening (animated via CSS) */}
        <circle className="matt-aura" cx="100" cy="105" r="96" fill="url(#glow)" />

        {/* big teased hair (back) */}
        <path d="M100 8 C40 8 22 55 26 100 C10 96 14 150 40 156
                 C34 120 44 96 52 92 C40 130 60 150 70 150
                 C150 158 176 120 174 96 C182 150 168 156 160 156
                 C186 150 190 96 174 100 C178 55 160 8 100 8 Z"
              fill="#f0cf72" />
        <path d="M100 12 C52 12 34 52 36 92 C60 70 70 66 70 66
                 C64 92 92 60 100 60 C108 60 136 92 130 66
                 C130 66 140 70 164 92 C166 52 148 12 100 12 Z"
              fill="#dcb44e" />

        {/* leather jacket collar + studs */}
        <path d="M52 208 L64 168 L100 190 L136 168 L148 208 Z" fill="#26262e" />
        <path d="M64 168 L100 190 L100 208 L58 208 Z" fill="#33333d" />
        <path d="M136 168 L100 190 L100 208 L142 208 Z" fill="#1f1f27" />
        {[72, 84, 128, 116].map((x, i) => (
          <circle key={i} cx={x} cy={192 - (i % 2) * 10} r="2.4"
            fill="#cfd4da" />))}

        {/* neck */}
        <rect x="86" y="158" width="28" height="26" rx="10" fill="#d89e7e" />

        {/* ears + hoop earring */}
        <ellipse cx="50" cy="112" rx="9" ry="13" fill={skin} />
        <ellipse cx="150" cy="112" rx="9" ry="13" fill={skin} />
        <circle cx="150" cy="132" r="7" fill="none" stroke="#f4c542"
          strokeWidth="2.6" />

        {/* face */}
        <ellipse cx="100" cy="112" rx="50" ry="56" fill={skin} />
        {/* jaw stubble shading */}
        <path d="M62 132 Q100 176 138 132 Q100 158 62 132 Z" fill="#c98f6f"
          opacity="0.5" />

        {/* front hair sweeps framing the face */}
        <path d="M50 96 C44 60 66 40 78 40 C60 54 58 84 62 104 Z"
          fill="#f0cf72" />
        <path d="M150 96 C156 60 134 40 122 40 C140 54 142 84 138 104 Z"
          fill="#f0cf72" />

        {/* red bandana */}
        <path d="M52 84 Q100 66 148 84 L146 96 Q100 80 54 96 Z" fill="#d8352f" />
        <path d="M50 86 l-12 -6 l6 14 z" fill="#b81f1f" />
        <path d="M40 82 l-14 8 M42 90 l-16 10" stroke="#d8352f"
          strokeWidth="5" strokeLinecap="round" />

        {/* eyebrows */}
        <path d="M70 100 q12 -7 22 -1" stroke="#4a3a2a" strokeWidth="4"
          fill="none" strokeLinecap="round" />
        <path d="M108 99 q10 -6 22 1" stroke="#4a3a2a" strokeWidth="4"
          fill="none" strokeLinecap="round" />

        {/* eyes */}
        <g>
          <ellipse cx="82" cy="110" rx="11" ry="8" fill="#fff" />
          <circle cx="83" cy="111" r="4.6" fill="#6b4a2f" />
          <circle cx="83" cy="111" r="2.1" fill="#1a1410" />
          <circle cx="85" cy="109" r="1.1" fill="#fff" />
          {/* eyelid */}
          <ellipse cx="82" cy={102 + lid} rx="12" ry={lid} fill={skin} />
        </g>
        <g>
          <ellipse cx="118" cy="110" rx="11" ry="8" fill="#fff" />
          <circle cx="117" cy="111" r="4.6" fill="#6b4a2f" />
          <circle cx="117" cy="111" r="2.1" fill="#1a1410" />
          <circle cx="119" cy="109" r="1.1" fill="#fff" />
          <ellipse cx="118" cy={102 + lid} rx="12" ry={lid} fill={skin} />
        </g>

        {/* lightning-bolt face paint over his right eye */}
        <path d="M132 92 L123 108 L129 108 L120 126 L136 104 L130 104 L138 92 Z"
          fill="#ff2e88" stroke="#ffd23d" strokeWidth="1" />

        {/* nose */}
        <path d="M100 116 q-5 12 -7 18 q3 4 9 3" fill="none" stroke="#c98f6f"
          strokeWidth="2.5" strokeLinecap="round" />

        {/* mouth (opens with voice) */}
        <ellipse cx="100" cy="146" rx="16" ry={mouthRy} fill="#7a2f3a" />
        {m > 0.14 && (
          <ellipse cx="100" cy={146 - mouthRy + teethRy} rx="12" ry={teethRy}
            fill="#fbfbfb" />)}
        {m < 0.14 && (
          <path d="M86 146 q14 8 28 0" stroke="#8a4048" strokeWidth="2.5"
            fill="none" strokeLinecap="round" />)}
      </svg>
    </div>
  )
}
