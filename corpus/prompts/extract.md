# Fill one valora.ref/1 record per clip

You study real 3D ads so Valora3D can set its renderer's parameters from evidence. You write one
JSON record per clip to `research/corpus/drafts/<id>.json`, then run `py -m corpus accept <file>`
and fix every problem it prints. The schema and every allowed value are in `corpus/schema.py`;
a complete valid example is `_rec()` in `corpus/tests/test_schema.py`. Read both first.

## Rules
1. **Observe, never guess.** A field you cannot see is `"unclear"` (enums) or `null`, and you list
   its path in `confidence.uncertainFields`. The pilot's manifest was wrong 5 times; guessing is
   the failure mode we measure you on.
2. **Cite evidence.** `evidence["format.cutTimesS"]` and `evidence["shots[i].cameraMove"]` (for every
   move that is not `"unclear"`) list the timestamps (`"t=4.2s"`) or frame files you used. A camera
   move needs two moments ~0.2 s apart; one frame is not evidence of motion.
3. **Shots tile the studied span** from 0 to `format.durationS`; `format.cutTimesS` equals each
   shot's `startS` after the first. Times are relative to `source.timestampsS[0]`.
4. **CG only.** If the clip is live action, a slideshow of stills, or AI-generated video (no tool
   credits, morphing geometry, Kling/Luma/Sora watermarks), do not write a record; report the id with
   reason `not_cg` or `ai_generated`.
5. `qualityEstimate` uses `research/craft/TIERS.md` §1 (T1 turntable … T3 professional ad).
6. `neverThoughtOf`: things a renderer would not think to do (e.g. "butterfly on the badge"). Short.
7. Copy nothing from the clip into Valora3D: no logos, music, footage. Records are observations.

## Method by source (the record's `method`)
- `local_frames`: frames were made for you with `py -c "from corpus.frames import *; ..."` under
  `research/corpus/local/<id>/`. Read them with the Read tool.
- `in_player` (YouTube/Vimeo, and stock not downloaded): use the owner's Chrome (Claude-in-Chrome
  tools). Open the clip's own page, play it at normal speed once, then pause and scrub to each
  moment you need; on YouTube press `.` to step one frame while paused. Take screenshots only to look
  at them; never save, download or record the video, never use a downloader. At most 20 clips per
  day, one tab. Set `source.downloaded: false`, `source.timestampsS` to the span you studied.
- If a page needs a login, is private or gone: reject with `login_wall` / `private` / `dead_link`.

## Output
The record JSON only, in the draft file. Then `py -m corpus accept` it. Report: ids accepted, ids
rejected with reasons, and any field you marked unclear on more than half the clips.
