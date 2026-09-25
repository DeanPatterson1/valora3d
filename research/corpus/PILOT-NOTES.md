# valora.ref/1 pilot: 11 clips (ref07 skipped as a duplicate)

## 1. Hard to fill from 6 frames
- **cameraMove:** mostly guesses. Needs frame pairs 0.2 s apart or optical flow.
- **Cuts:** ffmpeg scene score 0.3 missed split-screen ref01; 0.12 misfires on FPV blur. Use both, then one frame per shot midpoint.
- **Frame-to-shot mapping:** ref03 has 8 shots, ref11 about 11.
- **musicSyncCuts:** needs beat tracking (ref05 cuts every 2.5 s).
- **Sim state** (running drops, moving animals) needs frames every 0.5 s.
- **The manifest was wrong 5 times** (ref08 space, ref12 clear liquid, ref10 setup and rain, ref09 no rain, ref02 dry grass). Cite frames.

## 2. Missing fields
- `renderPass` per shot: final, viewport, clay or split. 9 of 11 show clay/viewport footage (ref11 only as an overlay).
- `layout`: container vs content aspect, split-screen, rotated landscape, blurred fill.
- `overlays`: hook text, watermark, end card, 2D graphics.
- `transitions`, `surfaceState` (droplets, dust, frost), `secondarySubjects` (animals, traffic).
- `evidence`: frame ids for each field, plus cut-detector settings.
- `motionBlur`, `lensDistortion`, `audio`.

## 3. Patterns to catalog
- **Clay-to-final reveal is the dominant format** (01, 02, 03, 04, 06, 09, 10, 12), same cameras both passes.
- **No turntables.** Ground-height camera, often tilted, with defocused foreground foliage.
- **Car blocks:** low rear chase, side slide with streaks, top-down, macro on lights or badge, FPV through traffic.
- **Product blocks:** fluid pour with a locked camera; floating product with falling particles; macro on a raking softbox.
- **Rule: the world carries realism** (fog, snow, rain, space, animals, flowers).
- **Rule: grade per mood.** Cool, desaturated, crushed blacks (03, 06, 08, 09) or punchy saturated (05). Emissive lights are the accent.

## 4. Never thought of
- Blurred-copy 9:16 fill (01)
- 2D doodles on a 3D product (02)
- Empty tunnel-portal establishing shot (03)
- Deer or bear for scale; action-cam distortion; "you can't" hook caption (04)
- Butterfly on the badge; dust visible in the sun reflection; local number plate (05)
- Airplane reflected in the hood; fallen leaves (06)
- Car in orbit lit by the planet; pixel-mosaic intro; frost crust (08)
- Traffic as the whole environment (09)
- Light-card setup shown as content (10)
- Rotated landscape inside a vertical post; OEM-style end card (11)
- One sim shown clay, then final (12)
