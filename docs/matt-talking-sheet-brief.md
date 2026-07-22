# Matt — Talking-Head Sheet (single-master, grid spec)

**Paste into ChatGPT (image generation/editing). Attach the reference bust
(`matt_viseme_rest.png` — Matt chest-up, red bandana, leather jacket).**

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

## Rules

1. Frames 1–10: ONLY the mouth/jaw area changes. Eyes identical in all ten.
2. Frames 11–12: ONLY the eyelids change (mouth stays as rest).
3. Frames 13–16: mouth + eyes/eyebrows may change; nothing else.
4. No global relight, no new hair strands, no camera drift, no zoom.
5. If the tool cannot hold the rest of the image constant, say so rather
   than delivering drifting frames.

Deliver the single 4096×4096 grid PNG. I will slice it programmatically —
cell geometry matters more than beauty of any one mouth shape.
