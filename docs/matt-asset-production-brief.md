# Matt — Master Asset Production Brief (batched)

**Paste this whole file into ChatGPT (with image generation) or Codex.**
Attach the approved **Matt model sheet** image before you send it. The tool
will then generate the full animation roster **one batch at a time**, in the
exact format the RFP Rockstar app already loads.

You are producing a **2D frame-animation asset library** for an on-screen
animated host named **Matt** — an 80s rock-star mascot for a business app.
This is not a handful of poses; it is a proper roster (target **~200–320
files**): lip-sync visemes, blinks, expressions, body poses, multi-frame action
sequences, and a whole **closet of props** Matt can pull out (music gear,
business gear, stage/studio pieces, flair).

---

## 0) How to work — EXECUTION PROTOCOL (read first)

1. **Work in batches, one per turn.** The batch list is in §6. Do **exactly
   one batch**, then **STOP** and print: `Batch N complete — X files. Reply
   "next" for Batch N+1.` Wait for me to say **next**.
2. **Re-anchor every batch.** At the top of each batch, restate the Character
   Bible (§2) in one line and re-reference the attached model sheet, so Matt
   looks identical across all files. Consistency > variety.
3. **If you can output transparent PNGs, do.** Alpha background preferred. If
   the tool cannot do alpha, use a **flat chroma green `#00b140`** background
   (the app keys it out). Never a white/photo background.
4. **Name every file exactly** per §4. Filenames are load-bearing — the app
   finds assets by name.
5. **After each batch, also emit the manifest fragment** (§5) for the files you
   just made, so I can paste it into the app.
6. **Keep a running checklist** at the end of every turn: which batches are
   done, which remain, total files so far.
7. If a request is ambiguous, **pick the choice that best matches the model
   sheet and keeps framing consistent** — don't ask, just note the assumption.

---

## 1) The character (attach the model sheet)

Matt — friendly 80s hard-rock front-man reimagined as a helpful business
mascot. Big, warm, a little theatrical. **Dark hair** (tousled 80s volume),
expressive face, stage presence but approachable. Wardrobe: rock but
work-friendly (band tee or henley, leather or denim jacket, boots). He hosts a
software app that finds and answers RFPs for schools and libraries, so he
oscillates between **rock-star flair** and **competent business helper** — the
prop closet reflects both worlds.

> The attached model sheet is the single source of truth for face, hair,
> proportions, palette, and wardrobe. Match it in every frame.

---

## 2) Character Bible — restate at the top of EVERY batch

- **Same face, same hair, same body proportions, same palette** every time.
- **Same camera and scale** for all *figure* frames: full body, front-ish 3/4,
  **feet resting on the bottom margin**, head near the top, centered
  horizontally. A viewer flipping between any two figure frames should see only
  Matt's pose/expression change — never his size, framing, or position jump.
- **Even, flat lighting.** No dramatic cast shadows on the background, no
  gradient backdrops, no floor reflections that bleed into the key color.
- **Clean silhouette** — nothing cropped at the frame edge (except deliberate
  full-bleed background pieces in Batch 15).
- **Cartoon-realistic** rendering consistent with the model sheet — same line
  weight, same shading style, same color grading across the whole library.

---

## 3) Canvas & technical specs

| Asset type            | Canvas (px)   | Framing                                             |
|-----------------------|---------------|-----------------------------------------------------|
| Full-body figure      | **1024×1536** | Full body, feet on bottom margin, identical scale   |
| Talking bust (visemes)| **1024×1024** | Chest-up, head centered, **fixed** eye/mouth anchor |
| Face-only overlays    | **512×512**   | Head centered, same anchor as the bust              |
| Standalone prop/item  | **1024×1024** | Object centered, ~85% of frame, slight contact only |
| Background / studio    | **1920×1080** | Full-bleed room, no character                        |

- Transparent alpha **or** flat `#00b140`. No drop shadows onto the background.
- Export **PNG**. Keep file sizes reasonable (the app downscales for display).
- **Registration matters** for anything meant to overlay (visemes, face
  overlays, blinks): the head must sit at the *same pixel position and size* in
  every file of that set so they can be swapped without the face jumping.

---

## 4) Naming convention (exact)

```
matt_viseme_<shape>.png            e.g. matt_viseme_AI.png
matt_blink_<state>.png             open | half | closed
matt_expr_<name>.png               neutral | smile | grin | laugh | surprised …
matt_pose_<name>.png               single hold pose (full body)
matt_seq_<action>_<NN>.png         numbered frames of one action, 01-based
prop_music_<name>.png              standalone music gear
prop_biz_<name>.png                standalone business gear
prop_studio_<name>.png            standalone stage/studio piece
prop_flair_<name>.png              wearable / fun items
matt_hold_<prop>.png               Matt actively using/holding that prop
bg_<name>.png                      background / studio room
```

- lower_snake_case, no spaces, no capitals except the fixed `matt_`/`prop_`
  prefixes shown. Sequence numbers are zero-padded two digits (`_01`, `_02`).

---

## 5) Manifest — emit after each batch

For visemes/expressions/poses/sequences, output a JSON fragment like:

```json
{
  "poses": { "typing": "matt_pose_typing.png", "clap": "matt_pose_clap.png" },
  "sequences": { "wave": ["matt_seq_wave_01.png","matt_seq_wave_02.png","matt_seq_wave_03.png","matt_seq_wave_04.png"] },
  "visemes": { "rest": "matt_viseme_rest.png", "AI": "matt_viseme_AI.png" }
}
```

For the closet, output `closet.json` entries:

```json
{
  "music":  [{ "id":"guitar_electric","file":"prop_music_guitar_electric.png","label":"Electric guitar","hold":"matt_hold_guitar_electric.png" }],
  "biz":    [{ "id":"laptop","file":"prop_biz_laptop.png","label":"Laptop","hold":"matt_hold_laptop.png" }],
  "studio": [{ "id":"stool","file":"prop_studio_stool.png","label":"Stool" }],
  "flair":  [{ "id":"sunglasses","file":"prop_flair_sunglasses.png","label":"Shades","hold":"matt_hold_sunglasses.png" }]
}
```

`hold` is optional — include it only when you also generated a "Matt using it"
pose in the same or a later batch.

---

## 6) THE BATCHES (do one per turn, in order)

> Batches 1–3 are the **lip-sync + life** core — they matter most; do them
> first and carefully with a fixed head anchor.

### Batch 1 — Visemes (talking bust, fixed anchor) — 11 files
Same chest-up talking pose, neutral-happy, **only the mouth changes**. Preston
Blair mouth set:
- `matt_viseme_rest` (relaxed closed), `matt_viseme_MBP` (lips pressed),
  `matt_viseme_AI` (open, "ah/eye"), `matt_viseme_E` (mid, smiling),
  `matt_viseme_O` (rounded medium), `matt_viseme_U` (rounded tight "oo"),
  `matt_viseme_FV` (top teeth on lower lip), `matt_viseme_L` (tongue up),
  `matt_viseme_WQ` (small round), `matt_viseme_etc` (neutral talk),
  `matt_viseme_wide` (big open, singing/laughing).
Keep eyes identical across all 11 (mouth is the only variable).

### Batch 2 — Blinks & eye life (face overlays, fixed anchor) — 6 files
`matt_blink_open`, `matt_blink_half`, `matt_blink_closed`, plus look variants
`matt_expr_look_left`, `matt_expr_look_right`, `matt_expr_look_screen`
(eyes pointed at the app UI). Same head registration as Batch 1.

### Batch 3 — Expressions (talking bust) — 12 files
`matt_expr_neutral`, `_smile`, `_grin`, `_laugh`, `_surprised`, `_thoughtful`,
`_skeptical` (one brow up), `_focused`, `_wink`, `_concerned`, `_stoked`
(excited), `_reassuring`. Same framing/anchor as Batch 1 so they interchange.

### Batch 4 — Core idle & state poses (full body) — 12 files
`matt_pose_idle_stand`, `_idle_sit_stool`, `_idle_relaxed` (leaning),
`_listening` (leaning in, attentive), `_thinking` (hand to chin),
`_thinking_pace`, `_arms_crossed`, `_hands_hips`, `_welcome` (arms open),
`_lean_in`, `_nod_yes`, `_shrug`.

### Batch 5 — Business action poses (full body) — 14 files
`matt_pose_typing` (at laptop), `_reading_doc`, `_present_chart` (gesturing at
a board), `_point_to_screen`, `_point_up`, `_thumbs_up`, `_counting_fingers`,
`_clipboard`, `_handshake_offer`, `_checking_watch`, `_coffee_sip`,
`_phone_look`, `_phone_call`, `_facepalm`.

### Batch 6 — Rock-star action poses (full body) — 14 files
`matt_pose_guitar_strum`, `_guitar_solo` (knee up), `_air_guitar`,
`_mic_sing`, `_mic_point` (points mic at audience), `_rock_horns` (\m/),
`_jump`, `_fist_pump`, `_drumming`, `_headphones_on`, `_dance`, `_bow`,
`_kick`, `_kneel_slide`.

### Batch 7 — Reaction & emote poses (full body) — 12 files
`matt_pose_celebrate`, `_clap`, `_wave_hello`, `_wave_bye`, `_stumble`
(off-balance, for the drag-physics), `_catch_balance`, `_wince`, `_confused`,
`_lightbulb` (idea), `_present_win` (holding a trophy), `_facewall`,
`_stretch`.

> Batches 8–11 are **multi-frame sequences** — the real animation. Each frame in
> a sequence keeps identical framing; only the body progresses. 3–6 frames each.

### Batch 8 — Greeting & talk sequences — ~20 files
`matt_seq_wave_01..04` (arm rises, waves, returns),
`matt_seq_nod_01..03`, `matt_seq_shrug_01..04`,
`matt_seq_lean_in_01..03`, `matt_seq_thumbs_up_01..03`,
`matt_seq_point_screen_01..03`.

### Batch 9 — Rock sequences — ~22 files
`matt_seq_guitar_strum_01..04`, `matt_seq_air_guitar_01..05`,
`matt_seq_fist_pump_01..03`, `matt_seq_headbang_01..04`,
`matt_seq_rock_horns_01..03`, `matt_seq_jump_01..04`.

### Batch 10 — Celebration & reaction sequences — ~20 files
`matt_seq_celebrate_01..06`, `matt_seq_clap_01..04`,
`matt_seq_lightbulb_01..03`, `matt_seq_facepalm_01..03`,
`matt_seq_stumble_01..04` (for dragging him too fast).

### Batch 11 — Business sequences — ~18 files
`matt_seq_typing_01..04` (loopable), `matt_seq_present_chart_01..04`,
`matt_seq_handshake_01..03`, `matt_seq_coffee_01..03`,
`matt_seq_phone_check_01..04`.

> Batches 12–14 are **THE CLOSET** — standalone items on transparent/green,
> plus a matching "Matt holding it" pose for the ones he'd actively use.

### Batch 12 — Closet: music gear — ~18 items (+ holds)
Standalone: `prop_music_guitar_electric`, `_guitar_acoustic`, `_bass`,
`_keytar`, `_mic_handheld`, `_mic_stand`, `_headphones`, `_amp`,
`_drumsticks`, `_drum_kit`, `_synth`, `_cable`, `_pick`, `_vinyl`,
`_cassette`, `_boombox`, `_gold_record`, `_tour_case`.
Holds (Matt using): `matt_hold_guitar_electric`, `matt_hold_mic_handheld`,
`matt_hold_headphones`, `matt_hold_keytar`.

### Batch 13 — Closet: business gear — ~18 items (+ holds)
Standalone: `prop_biz_laptop`, `_tablet`, `_smartphone`, `_clipboard`,
`_document_stack` (an RFP), `_contract`, `_pen`, `_briefcase`, `_coffee_mug`,
`_whiteboard`, `_chart_easel`, `_calculator`, `_desk_phone`, `_name_badge`,
`_pointer` (presentation), `_folder`, `_sticky_notes`, `_filing_box`.
Holds: `matt_hold_laptop`, `matt_hold_clipboard`, `matt_hold_document`,
`matt_hold_pointer`, `matt_hold_coffee_mug`.

### Batch 14 — Closet: studio pieces & flair — ~20 items (+ holds)
Studio (furniture Matt's box is built from): `prop_studio_stool`, `_couch`,
`_rug`, `_floor_lamp`, `_neon_sign` ("On Air"), `_plant`, `_poster`,
`_standing_desk`, `_monitor`, `_desk_chair`, `_spotlight`, `_amp_stack`.
Flair (wearables/fun): `prop_flair_sunglasses`, `_leather_jacket`, `_scarf`,
`_hat`, `_cowbell`, `_trophy`, `_confetti`, `_backstage_pass`.
Holds: `matt_hold_sunglasses` (putting them on), `matt_hold_cowbell`,
`matt_hold_trophy`, `matt_hold_confetti` (cannon fires).

### Batch 15 — Studio backgrounds & the closet door — ~8 files
Full-bleed rooms behind Matt (no character): `bg_studio_day`, `bg_studio_night`
(neon), `bg_office`, `bg_stage`, `bg_gradient_light`, `bg_gradient_dark`,
plus `prop_studio_closet_closed` and `prop_studio_closet_open` (the wardrobe he
pulls items from — an on-screen affordance).

---

## 7) Per-image prompt template (use for each file)

> **Matt** — [one-line Character Bible]. **Pose/expression:** <describe the one
> thing this frame shows>. **Framing:** [figure = full body, feet on bottom
> margin, front 3/4, centered, identical scale to the model sheet | bust =
> chest-up, head centered on the fixed anchor | prop = object centered on
> transparent/green]. **Background:** transparent (or flat `#00b140`), even flat
> lighting, no cast shadow. **Style:** cartoon-realistic, matching the attached
> model sheet exactly — same hair, face, palette, line weight. Output PNG at
> [canvas size].

For a **sequence**, add: *"Frame N of M in a <action> animation; keep body
framing and scale identical to the other frames; only advance the motion by one
step — [describe this step]."*

---

## 8) Final deliverable

When all 15 batches are done:
1. A single **zip** of every PNG, foldered by type
   (`visemes/ blinks/ expressions/ poses/ sequences/ props/ backgrounds/`).
2. A combined **`manifest.json`** merging every fragment from §5 (states,
   sequences, visemes, and the full `closet` object).
3. A short **`CONTACT_SHEET.png`** thumbnail grid so I can eyeball consistency.

Print the running checklist after every batch. Begin with **Batch 1** now.

---

## Notes for the app side (for me/Rob, not the image tool)

- App keys green **or** takes transparent — either export works
  (`preKeyed:true` in `frames.json` skips keying).
- The current player buckets mouth to closed/mid/open; when the 11 visemes
  arrive I'll widen the viseme mapping and add a blink/expression overlay layer
  and a sequence player (play `matt_seq_*` at ~8–12fps on the matching event).
- The closet becomes a UI drawer driven by `closet.json`: click an item →
  Matt swaps to the matching `matt_hold_*` pose.
