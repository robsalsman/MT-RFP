import React, { useEffect, useState } from 'react'

// Matt — an 80s rocker dude: big teased DARK hair, strong jaw, heavy stubble,
// thick brows, sideburns, red bandana, hoop earring. The mouth opens with
// `mouth` (0..1, driven by his voice); he blinks on his own; `state` adds a
// listening pulse or speaking glow.
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
  const lid = blink * 8
  const skin = '#d8a074'
  const skinShade = '#bd845b'
  const hair = '#2b211c'
  const hairDark = '#180f0b'
  const stubble = '#241a13'

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

        <circle className="matt-aura" cx="100" cy="105" r="96" fill="url(#glow)" />

        {/* big teased dark hair (back) */}
        <path d="M100 6 C36 6 20 56 26 104 C8 98 12 152 40 158
                 C33 120 45 96 53 92 C40 132 62 152 72 152
                 C150 160 178 120 172 96 C182 152 166 158 158 158
                 C188 152 190 96 174 104 C180 56 164 6 100 6 Z"
              fill={hair} />
        <path d="M100 10 C50 10 32 54 34 96 C58 72 70 68 70 68
                 C63 96 92 60 100 60 C108 60 137 96 130 68
                 C130 68 142 72 166 96 C168 54 150 10 100 10 Z"
              fill={hairDark} />

        {/* leather jacket collar + studs */}
        <path d="M50 208 L64 166 L100 190 L136 166 L150 208 Z" fill="#22222a" />
        <path d="M64 166 L100 190 L100 208 L56 208 Z" fill="#30303a" />
        <path d="M136 166 L100 190 L100 208 L144 208 Z" fill="#1b1b23" />
        {[72, 84, 128, 116].map((x, i) => (
          <circle key={i} cx={x} cy={192 - (i % 2) * 10} r="2.4"
            fill="#cfd4da" />))}

        {/* neck */}
        <rect x="85" y="156" width="30" height="28" rx="10" fill={skinShade} />

        {/* ears + hoop earring */}
        <ellipse cx="52" cy="112" rx="9" ry="13" fill={skin} />
        <ellipse cx="148" cy="112" rx="9" ry="13" fill={skin} />
        <circle cx="148" cy="132" r="7" fill="none" stroke="#f4c542"
          strokeWidth="2.6" />

        {/* strong-jawed face */}
        <path d="M54 104 C54 74 70 56 100 56 C130 56 146 74 146 104
                 C146 130 138 150 122 164 C114 170 106 173 100 173
                 C94 173 86 170 78 164 C62 150 54 130 54 104 Z"
              fill={skin} />

        {/* heavy stubble: jaw, cheeks, upper lip, chin */}
        <path d="M58 120 C64 156 84 172 100 172 C116 172 136 156 142 120
                 C126 150 74 150 58 120 Z" fill={stubble} opacity="0.32" />
        <path d="M84 136 q16 9 32 0 q-16 5 -32 0 Z" fill={stubble}
          opacity="0.45" />
        <ellipse cx="100" cy="162" rx="9" ry="6" fill={stubble} opacity="0.4" />

        {/* sideburns */}
        <path d="M56 96 q-2 34 8 50 q6 -6 6 -22 q-8 -12 -6 -30 Z" fill={hair} />
        <path d="M144 96 q2 34 -8 50 q-6 -6 -6 -22 q8 -12 6 -30 Z" fill={hair} />

        {/* front hair sweeps + widow's peak */}
        <path d="M52 92 C46 58 66 40 80 40 C62 54 58 82 60 100 Z" fill={hair} />
        <path d="M148 92 C154 58 134 40 120 40 C138 54 142 82 140 100 Z"
          fill={hair} />
        <path d="M78 62 Q100 50 122 62 Q100 58 78 62 Z" fill={hair} />

        {/* red bandana */}
        <path d="M52 82 Q100 64 148 82 L146 95 Q100 78 54 95 Z" fill="#c62f28" />
        <path d="M50 84 l-12 -6 l6 14 z" fill="#9c1a1a" />
        <path d="M40 80 l-14 8 M42 88 l-16 10" stroke="#c62f28"
          strokeWidth="5" strokeLinecap="round" />

        {/* thick eyebrows */}
        <path d="M68 99 q13 -8 25 -2" stroke="#211712" strokeWidth="5.5"
          fill="none" strokeLinecap="round" />
        <path d="M107 97 q12 -6 25 2" stroke="#211712" strokeWidth="5.5"
          fill="none" strokeLinecap="round" />

        {/* eyes */}
        <g>
          <ellipse cx="82" cy="110" rx="11" ry="7.5" fill="#fff" />
          <circle cx="83" cy="111" r="4.4" fill="#4a352a" />
          <circle cx="83" cy="111" r="2" fill="#140d09" />
          <circle cx="85" cy="109" r="1.1" fill="#fff" />
          <ellipse cx="82" cy={102 + lid} rx="12" ry={lid} fill={skin} />
        </g>
        <g>
          <ellipse cx="118" cy="110" rx="11" ry="7.5" fill="#fff" />
          <circle cx="117" cy="111" r="4.4" fill="#4a352a" />
          <circle cx="117" cy="111" r="2" fill="#140d09" />
          <circle cx="119" cy="109" r="1.1" fill="#fff" />
          <ellipse cx="118" cy={102 + lid} rx="12" ry={lid} fill={skin} />
        </g>

        {/* stronger nose */}
        <path d="M100 114 q-6 14 -9 20 q4 5 11 4" fill="none" stroke={skinShade}
          strokeWidth="3" strokeLinecap="round" />

        {/* mouth (opens with voice) */}
        <ellipse cx="100" cy="148" rx="16" ry={mouthRy} fill="#7a2f3a" />
        {m > 0.14 && (
          <ellipse cx="100" cy={148 - mouthRy + teethRy} rx="12" ry={teethRy}
            fill="#fbfbfb" />)}
        {m < 0.14 && (
          <path d="M85 148 q15 7 30 0" stroke="#5c3128" strokeWidth="3"
            fill="none" strokeLinecap="round" />)}
      </svg>
    </div>
  )
}
