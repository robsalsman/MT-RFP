# Matt — painted frame assets (drop-in)

Put the painted PNGs here and the app automatically switches Matt from the
vector puppet to your art. No code changes, no editing — the app keys out the
green background in the browser.

## Rules
- **512 × 768 px**, portrait, full body, feet near the bottom, **same framing
  and scale in every frame** (so poses don't jump).
- **Flat green background `#00b140`** (the app makes it transparent).
- Keep the character identical to the approved model sheet.

## Files the app looks for (names must match `frames.json`)

Minimum to activate (idle):
- `pose_idle_sit_stool.png`

Lip-sync while he talks — the SAME talking pose in three mouth openings:
- `talk_closed.png`   (mouth closed)
- `talk_mid.png`      (mouth slightly open)
- `talk_open.png`     (mouth wide open)

Other states / actions (optional, add any time):
- `pose_listening.png`, `pose_thinking.png`, `pose_phone_look.png`,
  `pose_point.png`, `pose_guitar.png`, `pose_celebrate.png`,
  `pose_wave.png`, `pose_shrug.png`

As soon as `pose_idle_sit_stool.png` is present, Matt becomes the painted
figure; the drag-lean, toppling gear, and proactive RFP picks all keep working.
Add the three `talk_*` frames and his mouth moves with his voice.
