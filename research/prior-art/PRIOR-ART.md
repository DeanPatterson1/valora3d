# Valora3D prior art: reusable open work

Researched 2026-09-24 via web search and page fetches. Every URL below was returned by a search or fetched directly. Licence and activity figures are what the page showed on that date. Where a licence was not visible, it is marked "not stated", so check before shipping.

Verdicts: **USE** = adopt directly · **MINE** = extract knowledge/parameters, do not ship the thing itself · **SKIP** = not worth it for us.

## Ranked table

| # | Name | URL | What it gives Valora3D | Licence / commercial | Maturity | Verdict |
|---|---|---|---|---|---|---|
| 1 | Poly Haven (assets + API) | https://polyhaven.com , https://polyhaven.com/our-api | ~980 HDRIs, ~780 PBR textures, ~520 models; public keyless API | Assets CC0. Commercial API use is allowed with a "Powered by Poly Haven" credit and a unique User-Agent | Very mature, growing | **USE** |
| 2 | ambientCG | https://ambientcg.com , https://docs.ambientcg.com/license/ | 2,800+ CC0 PBR materials and HDRIs, up to 8K. Floors, backdrops and surfaces for worlds | CC0, commercial OK | Mature (since 2017) | **USE** |
| 3 | Blender AgX + ACES OCIO config | https://github.com/blender/blender/blob/main/release/datafiles/colormanagement/config.ocio , https://github.com/EaryChow/AgX , https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/ | Filmic sigmoid display transform with 16.5 stops, shipped in Blender. ACES OCIO configs as an alternative pipeline | Ships with Blender (GPL app; see `ocio-license.txt`); ACES config is BSD-3-Clause | Production-grade | **USE** |
| 4 | spectral_film_lut | https://github.com/JanLohse/spectral_film_lut | Builds film-stock `.cube` LUTs (negative + print stages; Kodak/Fuji, motion picture and still) from datasheets. `pip install spectral-film-lut` | MIT | 102★, 521 commits | **USE** (generate our own grade LUTs; the output belongs to us) |
| 5 | BlenderMCP | https://github.com/ahujasid/blender-mcp | Claude-to-Blender bridge that runs code, pulls Poly Haven/Sketchfab assets and takes viewport screenshots. Useful for authoring and testing blocks, not the render farm | MIT | Very popular, active | **USE** (dev tool for authoring blocks) |
| 6 | video-shotcraft | https://github.com/Vincentwei1021/video-shotcraft , gallery https://vincentwei1021.github.io/video-shotcraft/library.html | 152 product-video "shot recipe cards" in 10 categories, each with purpose/energy, suggested duration, easing/timing, pitfalls, and TSX demos holding the real easing numbers. Includes exploded assembly, subject-locked rotation and drone dive | Apache-2.0 (sourcing notes in `references/shots/ATTRIBUTION.md`) | 9.4k★ per page, active | **MINE** (closest existing product-ad shot taxonomy; port cards to our block catalog) |
| 7 | CameraBench | https://github.com/sy77777en/CameraBench , https://linzhiqiu.github.io/papers/camerabench/ | Taxonomy of 50+ camera-motion primitives designed with cinematographers. ~3k expert-labelled videos | Repo LICENSE is CC BY 4.0. Videos come from the internet, so use the taxonomy only | NeurIPS 2025 Spotlight, 313★ | **MINE** (camera-move vocabulary for the director's schema) |
| 8 | CinemaTraj | https://github.com/Pangolin112/CinemaTraj , https://cinematraj.github.io/ , https://arxiv.org/abs/2607.26910 | LLM agent splits a prompt into atomic moves (orbit full/half/quarter, pan, dolly in/out, crane, tilt, zoom, static hold, arc). Each move is parametric, with an SDF optimizer that avoids collisions and occlusion. Very close to our director-to-block design | MIT | Jul 2026, 6★, needs CUDA + OpenAI | **MINE** (copy the parametric move maths and collision/occlusion idea) |
| 9 | LensCraft | https://github.com/ZahraDehghanian97/LensCraft , https://arxiv.org/pdf/2506.00988 | "Standardized Cinematography Language": each instruction = camera movement + easing + initial angle + initial shot type, plus a simulated dataset (30-frame sims with subject position/size) | Not stated | Research code + data + weights public | **MINE** (the SCL schema is a ready-made JSON vocabulary) |
| 10 | E.T. / DIRECTOR | https://github.com/robincourant/the-exceptional-trajectories , https://github.com/robincourant/DIRECTOR , https://www.lix.polytechnique.fr/vista/projects/2024_et_courant/ | 115K film camera trajectories (11M frames, 120 h) with camera and camera-to-subject captions. Motion split into static/lateral/vertical/depth. Data on HF `robin-courant/et-data` | Repo MIT, but built on CondensedMovies (film clips), so the source-data terms apply | ECCV 2024 | **MINE** (distributions of speed, duration and move type; do not ship the data) |
| 11 | GenDoP / DataDoP | https://github.com/3DTopia/GenDoP , https://arxiv.org/abs/2504.07083 | 29K real shots with free-moving trajectories, depth, and captions in 3 layers (movement / scene interaction / directorial intent). Auto-regressive trajectory generator | Code Apache-2.0. Dataset reported as CC BY 4.0 **research-only, no commercial use**; it ships YouTube IDs, not video | ICCV 2025, 130★ | **MINE** (the 3-layer caption scheme = good director-prompt structure) |
| 12 | cc-blender-skill | https://github.com/RobLe3/cc-blender-skill | Claude Code skills for Blender 5.x: lighting profiles per subject class (metal, glass, product…), camera/DoF, Cycles/EEVEE with quality gates, pro workflow | MIT | 68★, v1.3.0, validated on 6 scene classes | **MINE** (lighting-profile + QA-gate ideas) |
| 13 | kevinbadi/blender-skills | https://github.com/kevinbadi/blender-skills | Product camera-animation presets: turntable, slow-zoom, dolly-rotate, crane-shot, dynamic-full-loop (speed-ramped), perfect-loop. Output ProRes 4444 with alpha | Not stated | 123★, few commits | **MINE** (preset list; check code before copying anything) |
| 14 | arjun988/blender-skills | https://github.com/arjun988/blender-skills | 94 MCP-driven Blender skills incl. lighting, camera-cinematography, rendering, compositing, lookdev | MIT | 215★ | **MINE** (scan lighting/camera/compositing skills) |
| 15 | DirectorSKILL / visual-skills / fal cinematography | https://github.com/wuwangzhang1216/DirectorSKILL , https://github.com/smixs/visual-skills , https://www.skills.sh/fal-ai-community/skills/cinematography | Prompt packs covering shot scale, lens psychology, lighting ratios, 30° rule, beats/rhythm. Written for gen-video models, not Blender | Not checked / not stated | Community | **MINE** (vocabulary for director system prompt only) |
| 16 | SceneCraft | https://arxiv.org/abs/2403.01248 | LLM → scene graph → Blender Python; VLM render-critique loop; "library learning" turns repeated scripts into reusable functions | Paper CC BY 4.0; no official code repo found | ICML 2024 | **MINE** (render → VLM critique → fix loop; library-learning = our block catalog growth) |
| 17 | BlenderAlchemy | https://github.com/ianhuang0630/BlenderAlchemyOfficial | VLM search over Blender edits, including a **lighting-for-product-render** task (lotion bottle) | Not stated | ECCV 2024, 95★ | **MINE** (auto-lighting refinement loop idea) |
| 18 | Infinigen | https://github.com/princeton-vl/infinigen , https://infinigen.org/ | Procedural Blender terrain, plants, creatures, indoor scenes. Unlimited unique natural worlds | BSD-3-Clause, commercial OK | Very mature. Heavy: Linux/macOS, source build, slow generation | **MINE / optional USE** for outdoor worlds, pre-generated offline, not per render |
| 19 | BlenderKit | https://www.blenderkit.com/docs/licenses/licensing-faq/ | 48K+ models, materials, HDRIs | CC0 + Royalty-Free (renders/animations may be sold; models may not be resold) | Mature | **USE with care** (keep to CC0 and pre-cleared assets; RF is fine for rendered video) |
| 20 | RealEstate10K | https://google.github.io/realestate10k/download.html | ~80K clips of SLAM camera poses (timestamps + poses) | Pose data CC BY 4.0 (Google); videos under YouTube terms | Mature | **MINE** (real handheld/gimbal motion noise, speed statistics) |
| 21 | Cinematographic Camera Diffusion Model | https://github.com/jianghd1996/Camera-control , https://arxiv.org/abs/2402.16143 | Diffusion model for cinematic camera trajectories + dataset | Not stated | CGF 2024 | **MINE** (low priority) |
| 22 | 3D-GPT | https://github.com/Chuny1/3DGPT | Multi-agent (dispatch / conceptualise / model) LLM that drives Infinigen functions via documented prompts | Not stated | 855★, only partial code released | **MINE** (per-function doc templates for the LLM ≈ our block cards) |
| 23 | FilmAgent → VideoClaw | https://github.com/HITsz-TMG/FilmAgent , https://arxiv.org/abs/2501.12909 | Multi-agent director/cinematographer roles; storyboard planning | MIT | 1.8k★. Repo now a web gen-video pipeline with no Blender | **SKIP** (paper's role split is the only takeaway) |
| 24 | MovieShots (MovieNet) | https://movienet.github.io/projects/eccv20shot.html | 46K trailer shots labelled with 5 scale classes (LS/FS/MS/CS/ECS) + 5 movement classes (static/motion/push/pull/multi) | CC BY-NC-SA 4.0, non-commercial | ECCV 2020 | **MINE only the class definitions**; data is off-limits commercially |
| 25 | CineScale | https://cinescale.github.io/ , https://github.com/CineScale/CineScale.github.io | 9-class shot-scale scheme (ECU…ELS, FS, IS), 124 films, 1 fps frames | Research-only on registration | Academic | **SKIP** (the taxonomy alone is available elsewhere) |
| 26 | Cinemetrics | https://cinemetrics.uchicago.edu/how-to-use | Shot-length data (ASL, median, SD) for 20K+ films; raw submissions downloadable | Open submissions, "freely available"; no formal licence seen | Long-running | **MINE** (shot-length/cut-rhythm priors; note these are feature films, not ads) |
| 27 | G'MIC Film-Luts | https://github.com/YahiaAngelo/Film-Luts | Collection of film-emulation LUTs | Repo MIT, but README warns LUTs "might be subject to copyrights… of their respective owners" | 270★ | **SKIP** (licence unclear; generate our own with #4) |
| 28 | BlenderGPT | https://github.com/gd3kr/BlenderGPT | Early English → bpy add-on | No licence in README | 2023, stale | **SKIP** |
| 29 | shotops | https://github.com/Grigoriy-V/shotops | Shots as JSON config → headless Blender blockout → video-model restyle; diffs/revert per shot | MIT | 1★, one shot | **MINE** (concept only: shot JSON as versioned patches) |

## Per-item notes

**1–2. Poly Haven, ambientCG.** Our world/backdrop and HDRI supply. Everything is CC0, so we can bundle it. Poly Haven's API is fine for a commercial product if we credit it and send a User-Agent. Safest path: pre-download a curated set into our block library so we don't depend on the live API at render time. The Blender MCP already installed has `download_polyhaven_asset` for curation.

**3. AgX / ACES.** Blender's shipped AgX is already a film-grade tone-mapper, so no third-party dependency is needed. Build our "colour grade" blocks as AgX look + a LUT (from #4) + small compositor tweaks. Keep the ACES config as an option for film-grade jobs.

**4. spectral_film_lut.** Generates LUTs from film datasheets, so the output is our own data and not someone else's copyrighted LUT pack. We can produce a named stock library (e.g. print + negative combos) as grade blocks.

**5. BlenderMCP.** Authoring aid only. The production compiler should stay a deterministic bpy script, not a live MCP session.

**6. video-shotcraft.** Built for Remotion/2.5D, not Blender, but its cards are what we need: per-shot purpose, energy, duration and easing for product films, under Apache-2.0. Treat each card as a candidate camera/motion block and re-implement it as 3D.

**7–11. Camera taxonomies and trajectory data.** Recommended stack:
- CameraBench primitives → the enum of move types.
- LensCraft SCL → the JSON shape (move + easing + start angle + start shot type).
- CinemaTraj → the maths for each parametric move plus collision/occlusion avoidance around an arbitrary uploaded mesh. This directly addresses "any model" framing.
- E.T. and DataDoP → offline statistics only (speed and duration distributions, how often each move type appears). Both sit on film/YouTube footage, so never ship or train a commercial model on them without legal review.
- DataDoP's caption layers (movement / interaction / intent) are a good template for how the director explains a shot.

**12–15. Skills.** None of these covers our case (automated ad-grade Blender video from an arbitrary model), so there is nothing to adopt wholesale. cc-blender-skill's per-material lighting profiles and quality gates, and kevinbadi's product move presets, are worth reading before writing our own lighting and camera blocks. Cinematography prompt packs target gen-video models; use them only for director vocabulary.

**16–17, 22. SceneCraft, BlenderAlchemy, 3D-GPT.** The shared idea we should copy is render → VLM critique → adjust parameters → re-render. This is how to make vague prompts still look great, as an automatic QA pass on a low-res preview. 3D-GPT's per-function documentation for the LLM is the same pattern as our block catalog cards.

**18. Infinigen.** Commercial-friendly and gives unlimited natural environments, but it is heavy (source build, Linux/macOS, slow). Use it offline to pre-bake a pool of terrain/nature worlds, not per request.

**20, 26. RealEstate10K, Cinemetrics.** RealEstate10K gives real pose tracks for adding believable handheld/gimbal micro-motion. Cinemetrics gives cut-rhythm priors, but it covers feature films, so ad pacing needs its own tuning.

## Gaps (nothing good found)

- **No open taxonomy or parameter database of 3D car-ad or product-ad techniques.** Searches returned only blog tips (hero shot, FPV dive, tracking/process trailer, gimbal reveal, e.g. https://www.soundstripe.com/blogs/how-to-shoot-a-car-commercial , https://www.drivenfilms.tv/blog/car-videography-how-to-film-cars). video-shotcraft (#6) is the closest thing for products. **For cars we must build the taxonomy ourselves**, e.g. by breaking down reference ads (the `watch` skill can extract frames) into our block schema.
- No official SceneCraft code repo was found.
- Licence not verified for: LensCraft, kevinbadi/blender-skills, BlenderAlchemy, 3D-GPT, Camera-control, DirectorSKILL, fal skills. Check each LICENSE file before copying code (mining ideas is fine).
