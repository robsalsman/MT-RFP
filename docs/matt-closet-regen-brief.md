# Matt — Closet Re-gen Brief (props + hold poses ONLY)

**Paste this into ChatGPT (image generation) or Codex. Attach the Matt model
sheet.** This re-does the two batches that came back unusable in the first run.
Everything else in the roster is fine — do **not** regenerate it.

## Why the first attempt failed (do NOT repeat these)

1. **Props came back as flat clip-art with text labels baked into the image**
   (e.g. the word "Laptop" printed under a generic laptop). ❌
   → Props must be **painted in Matt's exact art style**, and contain
   **ZERO text, letters, words, watermarks, or captions**. Just the object.
2. **All 13 "hold" poses were the identical phone-look frame** — the generator
   defaulted every one to Matt looking at a phone. ❌
   → Each hold pose must show Matt **actually holding the specific, different
   item named**, clearly visible in his hands. No phone unless the item is a
   phone.

If you cannot render a specific item convincingly, say so for that one file
rather than substituting a generic object or a phone.

## Global specs (same as the master brief — restate every batch)

- **Style:** cartoon-realistic, matching the attached Matt model sheet exactly
  — same line weight, palette, shading. Props are painted in this same style,
  not flat vector icons.
- **Background:** transparent, or flat chroma green `#00b140`. Even lighting,
  no cast shadow on the background. **No text anywhere in the image.**
- **Canvas:** props `1024×1024` (object centered, ~85% of frame); hold poses
  `1024×1536` (full body, feet on the bottom margin, front 3/4, identical
  framing/scale to the model sheet — same as all the other figure frames).
- **Naming:** exactly as listed below. lower_snake_case, `.png`.
- **After each batch** emit the manifest fragment and a contact sheet, then
  STOP and wait for "next".

---

## BATCH A — Music props (18) · `prop_music_<name>.png`

Painted objects, no text. Each is a distinct, recognizable item:

- `guitar_electric` — a sleek 80s electric guitar (pointy superstrat), body at
  an angle, glossy finish, strings and pickups visible.
- `guitar_acoustic` — warm wooden dreadnought acoustic, sound hole, full body.
- `bass` — 4-string electric bass, longer neck than the guitar, darker finish.
- `keytar` — shoulder-strap keytar, black with colored keys, 80s stage vibe.
- `mic_handheld` — chrome dynamic vocal mic, no stand, slight highlight.
- `mic_stand` — full boom mic stand with the mic mounted, floor base.
- `headphones` — over-ear studio headphones, padded cups, coiled cable.
- `amp` — a single guitar combo amp, grille cloth, control knobs on top.
- `amp_stack` is in Batch D (studio). Keep this one a single small combo.
- `drumsticks` — a crossed pair of wooden drumsticks.
- `drum_kit` — a compact rock drum kit (kick, snare, two toms, hi-hat, cymbal).
- `synth` — a tabletop 80s synthesizer, keys plus knobs and sliders.
- `cable` — a coiled guitar/instrument cable with 1/4" jacks.
- `pick` — a single guitar plectrum, seen large, with a subtle logo-free face.
- `vinyl` — a black vinyl record, half out of a plain (text-free) sleeve.
- `cassette` — a retro audio cassette tape, text-free label area.
- `boombox` — an 80s twin-deck boombox with a carry handle and speakers.
- `gold_record` — a framed gold record award, blank (no engraved text) plate.
- `tour_case` — a black road/flight case with metal corners and latches.

## BATCH B — Business props (18) · `prop_biz_<name>.png`

- `laptop` — an open modern laptop, blank glowing screen (no logos/text).
- `tablet` — a slim tablet, blank screen.
- `smartphone` — a smartphone, blank screen.
- `clipboard` — a clipboard with a blank (line-free, text-free) sheet + clip.
- `document_stack` — a neat stack of blank white papers.
- `contract` — a single blank document page, corner slightly curled.
- `pen` — a sleek ballpoint pen.
- `briefcase` — a classic hard-shell business briefcase, handle up.
- `coffee_mug` — a plain ceramic mug with a wisp of steam, no printed text.
- `whiteboard` — a small whiteboard on legs, blank surface (no writing).
- `chart_easel` — a flip-chart easel showing a simple blank bar-chart shape
  (bars only, NO numbers, labels, or words).
- `calculator` — a desk calculator with blank/neutral display.
- `desk_phone` — an office desk phone with handset and keypad.
- `name_badge` — a lanyard badge with a blank (text-free) card.
- `pointer` — a slim presentation pointer/wand.
- `folder` — a manila file folder, closed, no tab text.
- `sticky_notes` — a small stack/fan of blank square sticky notes.
- `filing_box` — a cardboard file box with a lid, no label text.

## BATCH C — Flair props (8) · `prop_flair_<name>.png`

- `sunglasses` — 80s aviator/wayfarer shades, dark lenses, glossy frame.
- `leather_jacket` — Matt's black moto jacket on its own, zippers/studs.
- `scarf` — a draped rock scarf, subtle pattern (no words).
- `hat` — a rock-style hat (fedora or bandana-wrapped trilby).
- `cowbell` — a metal cowbell with a drumstick beside it.
- `trophy` — a gold trophy cup on a base, blank (no engraving).
- `confetti` — a burst of colorful confetti and streamers, mid-air.
- `backstage_pass` — a laminated pass on a lanyard, blank card (no text).

## BATCH D — Studio props (14) · `prop_studio_<name>.png`

Furniture/room pieces for Matt's box (painted, no text/signage words):

- `stool` — the wooden bar stool Matt sits on.
- `couch` — a worn leather two-seat couch.
- `rug` — a patterned area rug, top-down-ish angle.
- `floor_lamp` — a tall floor lamp, warm shade.
- `neon_sign` — a glowing neon sign in an abstract lightning-bolt shape
  (a SHAPE only — absolutely no letters or words).
- `plant` — a leafy potted floor plant.
- `poster` — a framed band-style poster with abstract art (no text).
- `standing_desk` — a standing desk with a monitor.
- `monitor` — a computer monitor on a stand, blank screen.
- `desk_chair` — an office desk chair.
- `spotlight` — a stage spotlight/par can on a stand.
- `amp_stack` — a tall stacked guitar amp cabinet (full/half stack).
- `closet_closed` — a wardrobe closet, doors closed (Matt's gear closet).
- `closet_open` — the SAME wardrobe with doors open, gear visible inside
  (guitars, jackets, boxes) — this is the on-screen "closet" affordance.

## BATCH E — Hold poses (13) · `matt_hold_<name>.png`

**Full-body Matt, same framing as all figure frames, actually holding/using
the named item. Each must be visibly different — the item defines the pose.**

- `guitar_electric` — Matt playing the electric guitar, both hands on it,
  strap over shoulder, mid-strum.
- `mic_handheld` — Matt singing, one hand gripping the chrome mic near his
  mouth, other arm out.
- `headphones` — Matt wearing the over-ear headphones, one hand on a cup,
  nodding into the music.
- `keytar` — Matt with the shoulder keytar strapped on, one hand on the keys.
- `laptop` — Matt holding an open laptop on one forearm, typing with the other
  hand, looking at its screen (NOT a phone).
- `clipboard` — Matt holding a clipboard, pen in the other hand, reviewing it.
- `document` — Matt holding up a sheaf of papers, reading it.
- `pointer` — Matt gesturing at an unseen screen with a presentation pointer.
- `coffee_mug` — Matt holding a coffee mug near chest height, relaxed.
- `sunglasses` — Matt in the act of putting on / lowering his shades, cool grin.
- `cowbell` — Matt holding the cowbell up in one hand, drumstick in the other,
  mid-hit, grinning.
- `trophy` — Matt hoisting the gold trophy overhead in triumph, big grin.
- `confetti` — Matt with arms up as confetti bursts around him, celebrating.

---

## Deliverable

- Batches A–E, one per turn, then a combined `closet.json` update:
  ```json
  { "music":[{"id":"guitar_electric","file":"prop_music_guitar_electric.png","label":"Electric guitar","hold":"matt_hold_guitar_electric.png"}], "biz":[...], "flair":[...], "studio":[...] }
  ```
- Zip of the new PNGs, foldered `props/` and `poses/` (hold poses go with poses).
- A `CONTACT_SHEET.png` of all 13 hold poses so the "each holds a different
  item" fix is verifiable at a glance.

Begin with **Batch A** now.
