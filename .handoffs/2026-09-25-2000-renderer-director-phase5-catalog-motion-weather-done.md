---
track: renderer-director
date: 2026-09-25
branch: renderer/director
---
# Director phase 5 done (chunk 8): harness recall, look command, review fixes, premium car look

## State
- Plan `docs/superpowers/plans/2026-09-25-director-phase5-catalog-motion-weather.md` chunks 0-8 done. Register rows
  "Chunk 8 measured" and "Corpus re-rank" hold every chunk-8 number (population + date).
- Review chunk 6 (9 items) and chunk 7 (8 items): all real, all fixed with tests (commits 2008e34..98d14e9).
- Gates 2026-09-25: frozen baseline 90/90 (111 in the three gate files); non-Blender suite 2921 passed / 0 failed
  (19.4 min); full `-m "not live"` 3033 passed, 3 failed (2 realism-lane Blender tests: rain velocity probe,
  tyre/rotor trim values - their files changed mid-run; 1 mine, fixed in 1240b80).

## New
- `py -m harness look --script P --profile M --frames N<=3 --at t,...` (reserve before render, never refunded).
- `slow` marker: `engine/tests/test_blocks_phase5_blender.py` (47 compiles) runs only with `-m slow` / VALORA_SLOW=1.
- TG-47 premium outdoor car look in `fallback.premium_look` (low 0.3-0.7 m camera, 35-50 mm, f/5.6, ~82% width,
  85 mm details, wet mirror ground). Held variety restored: 0.139 / 1.83 near-dups (chunk 7 0.115 / 4.33).
- `capabilities.slot_missed`: a sun under another light and lens drops without rain are reported.

## Open / next
- deliveredRecall 0.748: the fallback ignores explicit camera asks (dutch, handheld, crane, slide), dewy,
  rain-on-lens, and lighting under a rolled world. Next: honour detected camera/effect asks in the fallback.
- 6 T2 fallbacks: lounge-chair toss and studio drive_studio land on last-resort plans.
- Suite time is load-bound (other lanes' Blender renders ran concurrently); re-time on a quiet box.

## Owner look-check
- `harness/out/look/4ced996ae31ad2f6/beauty/0271.png` (sports_car, night_street wet, hero at 9 s): look for a
  low eye-level car-ad angle and wet reflections. Known issue: the low camera sits behind the pavement slab,
  which fills the bottom ~40% of the frame - the street needs the low hero on the road side of the kerb.
- Earlier phase-5 look-checks: `harness/out/look/artpass_*` (realism lane). Every `golden` stays null.
