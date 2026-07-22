# Matt — Talking-Head Sheet (single-master, grid spec)

**Paste into ChatGPT (image generation/editing). Attach the reference bust:
`frontend/public/matt-frames/visemes/matt_viseme_rest.png` (Matt chest-up,
red bandana, leather jacket, transparent background).**

## The goal (read carefully — this is the whole point)

We are animating a talking face by swapping frames. The previous batch was
generated as 29 INDEPENDENT renders — every frame had slightly different
hair, jacket folds, lighting, and head size, so playback flickers.

This time: **ONE master image, edited.** Every frame must be the SAME
image, pixel-for-pixel — same hair strands, same jacket folds, same
lighting, same head size and position — with ONLY the mouth (and for a few
frames the eyes/eyebrows) changed, the way a 2D animator redraws just the
mouth on a held cel. Treat it as inpainting the mouth region of the
attached master, never as re-rendering the character.

**Consistency test before you output:** flipping between any two cells must
look like the character moved their mouth — nothing else in the image may
change. If hair, collar, shading, or framing shifts, redo the cell.

## Output format — a labeled grid, exact geometry

- One PNG, **4096×4096**, a **4×4 grid of 1024×1024 cells**, no gutters,
  no borders, no labels inside cells (numbering below is by position).
- Background: flat chroma green **#00b140** in every cell (or full
  transparency if you can).
- The bust is identically framed in every cell: head centered horizontally,
  bandana at the same height, chest-up crop.

Cell order (row-major):

| # | Frame | Change from master |
|---|-------|--------------------|
| 1 | rest | master as-is: mouth relaxed closed, eyes open |
| 2 | MBP | lips pressed together |
| 3 | WQ | small tight rounded mouth ("w/oo") |
| 4 | O | rounded medium-open mouth ("oh") |
| 5 | E | mouth mid-open, slight smile ("eh/ee") |
| 6 | etc | neutral mid-open talking mouth |
| 7 | L | mouth open, tongue tip up behind teeth |
| 8 | FV | top teeth on lower lip |
| 9 | AI | wide-open mouth ("ah") |
| 10 | wide | biggest open mouth (yell/sing) |
| 11 | blink_half | eyes half closed (mouth = rest) |
| 12 | blink_closed | eyes fully closed (mouth = rest) |
| 13 | smile | warm closed-mouth smile, eyes open |
| 14 | grin | big open grin showing teeth |
| 15 | look_screen | eyes glance down-left toward a screen, slight smile |
| 16 | surprised | eyebrows up, mouth small "o", eyes wide |

## Anatomical constants (hard requirements, will be measured)

These are fixed properties of a real face — they cannot change between
frames of the same person at the same camera distance:

- **Pupillary distance**: the distance between the centers of his two
  eyes must be IDENTICAL (to the pixel) in every cell where the eyes are
  open. This is the primary check the frames will be verified against.
- The **red bandana** must sit at the same height and width in every cell.
- The nose tip, ear positions, and jawline hinge point do not move; only
  the jaw OPENS (rotates down) for open-mouth frames.

## Rules

1. Frames 1–10: ONLY the mouth/jaw area changes. Eyes identical in all ten
   (same pupils, same pixel positions).
2. Frames 11–12: ONLY the eyelids change (mouth stays as rest; the eye
   sockets stay in place — lids close over the same spots).
3. Frames 13–16: mouth + eyes/eyebrows may change; nothing else. Pupil
   spacing stays constant even when the gaze direction shifts (frame 15 —
   the eyes rotate, they don't migrate).
4. No global relight, no new hair strands, no camera drift, no zoom.
5. If the tool cannot hold the rest of the image constant, say so rather
   than delivering drifting frames.

## What matters (priority order)

1. **Zero drift** between cells — this is fatal if violated. A slightly
   imperfect mouth shape is fine; a frame where the hair/jacket/head moved
   is useless and playback will flicker.
2. Exact cell geometry (I slice programmatically).
3. Beauty of individual mouth shapes — least important; frames are
   crossfaded in playback, so minor shape imperfections disappear.

## Delivery

Preferred: the single 4096×4096 grid PNG (one canvas helps you keep all 16
consistent). **Fallback:** if you cannot guarantee exact grid geometry,
deliver 16 individual 1024×1024 PNGs instead, named
`matt_face_01_rest.png` … `matt_face_16_surprised.png` per the table —
but the zero-drift rule still applies across all 16.

Before delivering, self-check: overlay any two cells in your mind — do the
pupils, bandana, hair silhouette, and jacket land on the same pixels? If
not, redo the offending cell. State plainly if you cannot maintain this.
