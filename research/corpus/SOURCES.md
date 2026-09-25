# 3D Ad / Showcase Reference Corpus: Sources

Compiled 2026-09-24 by web search (5 parallel research passes, one per category).
Purpose: study only (extract camera, lighting, timing and material parameters). Never reuse footage.

## Verification level (read first)
- **Every URL below appeared in a real search result or fetched page. None were invented.**
- **They were NOT opened or played.** "Verified" here means the URL exists in the search index with a matching title/snippet. Expect a few dead links, private videos or pages that turn out to be stills. Run a `yt-dlp --simulate` / HEAD pass before bulk study.
- `Vert` column: `y` = Shorts/Reels/TikTok URL (vertical by platform format, not checked per clip); `n` = known or very likely 16:9; `?` = unknown. Probe with `yt-dlp -j` (width/height) before trusting it.
- Quality varies. The top tier is ManvsMachine, Buck, Tendril, Simon Holmedal, Wannerstedt, Mondlicht, Mackevision, Tax Free Film, Superplastic and LEGO. Many Behance/ArtStation pieces are spec/portfolio work, not official brand ads. Some YouTube/TikTok items are tutorials or making-ofs (marked).
- Since 2025, AI-generated "CGI ads" (Kling/Luma/etc.) flood TikTok/Instagram results. Filter with "blender", "octane", "houdini", "redshift" in queries and check the credits.

## Terms of service / automated access
| Platform | Automated access | Practical fetch notes |
|---|---|---|
| Vimeo | ToS bans scraping and downloading without owner permission (download toggle) | yt-dlp works on most public clips; some are embed/referer-locked |
| YouTube | ToS bans downloading outside official features | yt-dlp works reliably |
| Behance (Adobe) | Adobe terms ban automated scraping; search page returned 403 to our fetcher | pull the embedded Vimeo/YouTube/MP4 source from each project page instead |
| ArtStation (Epic) | ToS bans scraping; Cloudflare bot checks; many artists tag NoAI | native MP4 asset URLs or YouTube/Vimeo embeds |
| Instagram (Meta) | Meta terms ban automated collection | login wall after a few views; yt-dlp needs cookies |
| TikTok | ToS bans scraping | yt-dlp works per video but rate-limits; discover pages are JS-only (empty shell) |
| Motionographer / studio sites | no explicit block seen | fetch the embedded player URL, not the article |

Study-only use of a small, manually curated set is low-risk, but **any bulk automated fetch conflicts with the ToS of all six major platforms above**. Prefer manual/low-rate access, and record the source for each clip.

---

## 1. Source channels

| Name | URL | Platform | Category focus | Typical format | Approx. usable volume | Notes |
|---|---|---|---|---|---|---|
| ManvsMachine | https://vimeo.com/mvsm | Vimeo | Product (Nike, Apple), sim-heavy | 16:9 | ~100 videos | top-tier reference; yt-dlp OK |
| Ars Thanea | https://vimeo.com/arsthanea | Vimeo | Product/commercial CGI | 16:9 | dozens | yt-dlp OK |
| Vimeo 3D category | https://vimeo.com/categories/animation/3d/videos | Vimeo | Mixed | 16:9 mostly | thousands | discovery feed |
| Vimeo "best of the best CGI" channel | https://vimeo.com/channels/76914 | Vimeo | Mixed CGI | 16:9 | hundreds | yt-dlp can list the whole channel |
| Vimeo Staff Picks | https://vimeo.com/channels/staffpicks | Vimeo | Award-level motion design | 16:9 | several/day (few pure CGI ads) | curated quality filter |
| Danthree Studio | https://www.danthree.studio/en/3d-visualization/3d-animation-video-product | Studio site | Product, furniture (Interlübke, Natuzzi, BORA) | 16:9 + vertical | a portfolio page | player loaded by JS; open in a browser |
| @productshade | https://www.instagram.com/productshade/ | Instagram | Product CGI reels | 9:16 | dozens+ | login wall |
| YouTube Shorts (#productanimation, #cgi) | https://www.youtube.com/hashtag/productanimation | YouTube | Product | 9:16 | very high | best vertical source that yt-dlp handles well |
| TikTok discover: 3d-product-commercial | https://www.tiktok.com/discover/3d-product-commercial | TikTok | Product | 9:16 | very high | heavy AI-slop contamination |
| CGIFurniture | https://vimeo.com/cgifurniture/videos (+ instagram.com/cgifurniture, behance.net/cgi-furniture) | Vimeo/IG/Behance | Furniture, home decor | 16:9 + vertical reels | dozens | richest single furniture source |
| Kühl & Han | https://vimeo.com/kuhlandhan | Vimeo | Furniture brand films (HAY, Muuto) | 16:9 | medium | page JS-rendered |
| Muuto | https://vimeo.com/muutodesign | Vimeo | Furniture brand films, some fully CGI | 16:9 | medium | public |
| render.friends / renders.trenders | https://www.instagram.com/render.friends/ | Instagram | Furniture/interior CGI reels | 9:16 | high | login wall |
| Vimeo architectural 3D animation channel | https://vimeo.com/channels/119308 | Vimeo | Archviz interiors | 16:9 | high | public |
| iMeshh Blender archviz playlist | https://www.youtube.com/playlist?list=PLhoTTOn45sUDfcSPqDUOADGhxpmpRI_68 | YouTube | Interiors | 16:9 | medium | yt-dlp OK |
| Mackevision / Accenture Song | https://vimeo.com/mackevision | Vimeo | Vehicles (OEM CG films) | 16:9 | large archive | top automotive reference |
| Vimeo Cars category | https://vimeo.com/categories/art/cars/videos | Vimeo | Vehicles | 16:9 | high | mix of live action and CG; filter for "CGI" |
| Framestore work | https://www.framestore.com/work | Studio site | Vehicles, VFX | 16:9 | low, premium | mostly CG integrated into live action |
| Post Processed | https://www.instagram.com/postprocessed/ | Instagram (+Behance) | Vehicles in Unreal | 9:16 reels | medium | login wall |
| Daniel Vesterbaek | https://www.instagram.com/daniel_vesterbaek/ | Instagram | Blender car animation | 9:16 | medium | login wall |
| TikTok discover: 3d-car-render | https://www.tiktok.com/discover/3d-car-render | TikTok | Vehicles | 9:16 | very high | JS-only |
| Superplastic | https://www.tiktok.com/@superplastic | TikTok (+YouTube) | Characters / designer toys | 9:16 | high, ongoing series | best vertical character source |
| Deep Sky Studios | https://deepskystudios.com/project/superplastic-janky-guggimon-3d-tiktok-animation-production/ | Studio site | Characters (Superplastic production) | 9:16 | low | case study |
| Mighty Jaxx | https://www.youtube.com/@MightyJaxx | YouTube | Collectibles | 16:9 + Shorts | medium | not yet mined for CG clips |
| McFarlane Toys | https://vimeo.com/mcfarlanetoys | Vimeo | Action figures | 16:9 | low-medium | |
| Original Funko | https://www.youtube.com/c/OriginalFunko | YouTube | Collectibles | 16:9 + Shorts | high | only some clips are CG |
| Animo VFX / IKM 3D / Halon | https://vimeo.com/animovfx , https://vimeo.com/ikm3d , https://vimeo.com/halon | Vimeo | CG TV spots incl. toys/mascots | 16:9 | medium | |
| Maxon C4D Instagram | https://www.instagram.com/maxonc4d/ | Instagram | Mixed incl. characters | 9:16 | high | login wall |
| ArtStation turntable search | https://www.artstation.com/search?query=turntable | ArtStation | Characters | 16:9, <30 s | very high | Cloudflare |
| SideFX Houdini (Vimeo) | https://vimeo.com/goprocedural | Vimeo | Abstract/sim reels | 16:9 | hundreds | |
| SideFX Houdini (Instagram) | https://www.instagram.com/sidefxhoudini/ | Instagram | Community sim reposts | mostly 9:16/4:5 | several/week | login wall; good discovery of creators |
| Andreas Wannerstedt | https://vimeo.com/wannerstedt , https://www.instagram.com/wannerstedt/ | Vimeo/IG | Satisfying loops | square/16:9 | ~97 Vimeo videos | profile JS-rendered |
| Simon Holmedal | https://vimeo.com/simonholmedal | Vimeo | Abstract Houdini | 16:9 | dozens | |
| Tendril | https://vimeo.com/tendril | Vimeo | Sim reels, brand films | 16:9 | dozens | |
| Vimeo "Houdini Abstract" group | https://vimeo.com/groups/754155 | Vimeo | Abstract sims | 16:9 | medium | |
| Motionographer fluid-simulation tag | https://motionographer.com/tag/fluid-simulation/ | Web articles | Award-curated motion design | mixed | ~10 per tag, large overall site | fetch the embed |
| TikTok @renderx20 | https://www.tiktok.com/@renderx20 | TikTok | Blender physics sims | 9:16 | high | lower craft, strong hooks |
| Behance searches | https://www.behance.net/search/projects/3d%20product%20animation (swap in: furniture animation, automotive cgi, toy collectibles, fluid simulation) | Behance | All | mixed; Vimeo/YouTube/MP4 embeds | 10k+ each | 403 to bots; Adobe terms |
| ArtStation searches | https://www.artstation.com/search?query=product%20animation | ArtStation | All | mixed | thousands | Cloudflare |

---

## 2. Candidate clip list

Counts: Product 47 · Furniture/interiors 51 · Vehicles 44 · Characters/toys 38 · Abstract/sim 50 = **230 URLs** (duplicates across categories removed; channel/profile pages excluded).

### 2.1 Product / e-commerce (47)
| # | URL | Platform | Vert | Description |
|---|---|---|---|---|
| P1 | https://vimeo.com/1114583666 | Vimeo | ? | Kasra Design: "Este" beauty product commercial, hyper-real cosmetic hero shots |
| P2 | https://vimeo.com/224906636 | Vimeo | n | Sacha cosmetics product film (Houdini + Redshift) |
| P3 | https://vimeo.com/668522894 | Vimeo | ? | Animodestudio: product visualization reel |
| P4 | https://vimeo.com/987640076 | Vimeo | n | Product animation reel (multiple products) |
| P5 | https://vimeo.com/1012740707 | Vimeo | ? | "Precision in Motion": watch, robotic arm, hi-fi turntable |
| P6 | https://vimeo.com/1183873072 | Vimeo | ? | Givenchy-inspired luxury animation, dramatic light |
| P7 | https://vimeo.com/595935297 | Vimeo | ? | Headphones commercial (C4D + Redshift) |
| P8 | https://vimeo.com/661390929 | Vimeo | ? | Coffee liquid simulation, studio piece |
| P9 | https://vimeo.com/261623443 | Vimeo | ? | Chocolate/caramel look-dev (3ds Max + Corona) |
| P10 | https://vimeo.com/80251525 | Vimeo | n | "Chocolate Crown": liquid chocolate forming shapes |
| P11 | https://vimeo.com/240082554 | Vimeo | ? | RealFlow slow-motion chocolate splash |
| P12 | https://vimeo.com/165443420 | Vimeo | n | ManvsMachine: Nike Flyknit "Infinite Possibilities" |
| P13 | https://vimeo.com/259336658 | Vimeo | n | ManvsMachine: Nike "Born Mercurial" boot launch |
| P14 | https://vimeo.com/192130017 | Vimeo | n | ManvsMachine: Nike Air Max (bubbles and shoe sims) |
| P15 | https://vimeo.com/162826208 | Vimeo | n | ManvsMachine: Nike Flyknit |
| P16 | https://vimeo.com/260279525 | Vimeo | n | ManvsMachine: Apple iMac Pro artist film |
| P17 | https://vimeo.com/273782257 | Vimeo | n | Buck: iMac Pro artist film |
| P18 | https://www.behance.net/gallery/244324717/Belle-dOr-3D-CGI-Perfume-Animation | Behance | ? | Belle d'Or perfume, cinematic lighting |
| P19 | https://www.behance.net/gallery/127909887/Chanel-Bleu-De-Chanel-3D-CGI-Perfume-Animation | Behance | ? | Bleu de Chanel perfume CGI (spec) |
| P20 | https://www.behance.net/gallery/229749421/TOM-FORD-3D-PERFUME-ANIMATION-CGI | Behance | ? | Tom Ford perfume animation |
| P21 | https://www.behance.net/gallery/201334621/Perfume-Product-Video-3D-Animation-for-Website | Behance | ? | Perfume product video for a website |
| P22 | https://www.behance.net/gallery/205690657/Nike-Air-Presto-CGI-Film | Behance | ? | Nike Air Presto CGI film |
| P23 | https://www.behance.net/gallery/206029463/Nike-Bounce-3D-Motion-Video-and-Design | Behance | ? | Nike Bounce shoe motion |
| P24 | https://www.behance.net/gallery/187192071/Nike-Shoes-Commercial-3D-Animation-Design | Behance | ? | Nike shoe commercial |
| P25 | https://www.behance.net/gallery/246957339/IWC-Watch-CGI | Behance | ? | IWC watch (C4D, Houdini, Redshift) |
| P26 | https://www.behance.net/gallery/250297403/Veylor-Watch-3D-Animation | Behance | ? | Kinematiq: Veylor luxury watch film |
| P27 | https://www.behance.net/gallery/188202339/3D-Product-Animation-Watch-Commercial-Amazon-Video | Behance | ? | Watch commercial for Amazon listing |
| P28 | https://www.behance.net/gallery/189885153/BoldRX-3D-Product-Animation | Behance | ? | BoldRX product (C4D + Redshift) |
| P29 | https://www.behance.net/gallery/122481097/Drink-Ads-3D-Animation | Behance | ? | Full-CGI drink ads (Blender Cycles) |
| P30 | https://www.behance.net/gallery/202447865/3D-Animation-Beverage-Product | Behance | ? | Pixis Creative: beverage animation (Blender) |
| P31 | https://www.behance.net/gallery/188499061/3D-BEER-COMMERCIAL-CGI | Behance | ? | Beer commercial (Blender) |
| P32 | https://www.behance.net/gallery/193323705/NOTHING-ear-(2) | Behance | ? | Nothing Ear (2) earbuds commercial |
| P33 | https://www.behance.net/gallery/238511691/Headphones-3D-Product-Animation | Behance | ? | Headphones commercial |
| P34 | https://www.behance.net/gallery/170186769/Earbuds-3d-product-animation | Behance | ? | Earbuds animation |
| P35 | https://www.artstation.com/artwork/XgNnvn | ArtStation | ? | Luxury perfume commercial |
| P36 | https://www.artstation.com/artwork/bldYzm | ArtStation | ? | Valentino Uomo perfume animation |
| P37 | https://www.artstation.com/artwork/1nq8wG | ArtStation | ? | CodeChaos/Freise Brothers: Adidas golf shoe campaign |
| P38 | https://www.youtube.com/shorts/gEJncZLWsJE | YT Shorts | y | Pepsi MAX can animation (Blender) |
| P39 | https://www.youtube.com/shorts/GwBavGUHFPk | YT Shorts | y | Perfume (C4D, Redshift, X-Particles) |
| P40 | https://www.youtube.com/shorts/pQUraV7Gwtg | YT Shorts | y | Skincare product animation |
| P41 | https://www.youtube.com/shorts/_UHAfWyd1fM | YT Shorts | y | Nike Mercurial boot animation |
| P42 | https://www.youtube.com/shorts/rchOmpbBRY4 | YT Shorts | y | Blender product animation |
| P43 | https://www.youtube.com/watch?v=WjrkOGb_-Cw | YouTube | n | Byredo Rouge Chaotique perfume CGI |
| P44 | https://www.youtube.com/watch?v=x6jXgRxrQDk | YouTube | n | Hyper-real luxury perfume ad |
| P45 | https://www.youtube.com/watch?v=iFv_sdgk0Zs | YouTube | ? | anigem Studio: 10 s Nike sneaker ad (a good length match) |
| P46 | https://www.youtube.com/watch?v=jnBCdL_D9a4 | YouTube | n | CG Viz Studio: luxury watch animation |
| P47 | https://www.instagram.com/p/DMVn3igyFK5/ | Instagram | y? | Cosmetics product animation post |

### 2.2 Furniture / interiors (51)
| # | URL | Platform | Vert | Description |
|---|---|---|---|---|
| F1 | https://vimeo.com/894583058 | Vimeo | ? | CGIFurniture: office seating animation |
| F2 | https://vimeo.com/894582757 | Vimeo | ? | CGIFurniture: seating configuration switching |
| F3 | https://vimeo.com/893729308 | Vimeo | ? | CGIFurniture: lighting cinemagraph |
| F4 | https://vimeo.com/891815681 | Vimeo | ? | CGIFurniture: flatlay animation of finishes |
| F5 | https://vimeo.com/870828174 | Vimeo | ? | CGIFurniture: kitchen hardware |
| F6 | https://vimeo.com/850862654 | Vimeo | ? | CGIFurniture: chair self-assembly |
| F7 | https://vimeo.com/850861867 | Vimeo | ? | CGIFurniture: bed assembly |
| F8 | https://vimeo.com/850852904 | Vimeo | ? | CGIFurniture: desk assembly |
| F9 | https://vimeo.com/1045357206 | Vimeo | ? | CGIFurniture: cinematic marketing visual |
| F10 | https://vimeo.com/1045339429 | Vimeo | ? | CGIFurniture: candle render (home decor) |
| F11 | https://vimeo.com/855308537 | Vimeo | y? | CGIFurniture: product animation made for an Instagram Reel |
| F12 | https://vimeo.com/754298073 | Vimeo | n | CGIFurniture: product animation showreel |
| F13 | https://vimeo.com/761419945 | Vimeo | n | CGIFurniture: promo-video showreel |
| F14 | https://vimeo.com/737978701 | Vimeo | ? | CGIFurniture: black kitchen set self-assembly |
| F15 | https://vimeo.com/644021046 | Vimeo | ? | Sofa assembly animation |
| F16 | https://vimeo.com/519493026 | Vimeo | ? | Feature furniture animation |
| F17 | https://vimeo.com/903583113 | Vimeo | ? | CHAIRA chair (C4D + Octane) |
| F18 | https://vimeo.com/891493115 | Vimeo | ? | Digital Bunch: "Your dream sofa" configurator animation |
| F19 | https://vimeo.com/836524912 | Vimeo | ? | Blansable: "The Kitchen", fast-cut kitchen CGI |
| F20 | https://vimeo.com/478179875 | Vimeo | ? | ENARC: kitchen animation |
| F21 | https://vimeo.com/677598943 | Vimeo | ? | Mallorca kitchen interior (3ds Max + Corona) |
| F22 | https://vimeo.com/947418839 | Vimeo | ? | GENENSE: minimalist pastel interior |
| F23 | https://vimeo.com/57954397 | Vimeo | n | "The M apartment" walkthrough |
| F24 | https://vimeo.com/425912823 | Vimeo | n | Unreal 4.25 ray-traced interior test |
| F25 | https://vimeo.com/410546111 | Vimeo | n | Muuto 2020 collection launch (digital-only film) |
| F26 | https://vimeo.com/1150868857 | Vimeo | ? | High-end product showcase (category unconfirmed) |
| F27 | https://www.behance.net/gallery/115565865/Herman-Miller-Sayl-Gaming-Chair-Animation | Behance | ? | Herman Miller Sayl chair (Blender EEVEE) |
| F28 | https://www.behance.net/gallery/172648979/HAWORTH-X-HALO-Fern-Gaming-Chair | Behance | ? | Steelworks: Haworth x Halo Fern chair |
| F29 | https://www.behance.net/gallery/92345623/CGI-product-animation | Behance | ? | Martin Pitonak: product animation |
| F30 | https://www.behance.net/gallery/142156943/Product-Animation-Sofa-Cushion | Behance | ? | Sofa cushion animation |
| F31 | https://www.behance.net/gallery/128663949/Modular-sofa-MOON-160-3D-model-Animation | Behance | ? | MOON 160 modular sofa |
| F32 | https://www.behance.net/gallery/84503705/CGI-Roomset-for-a-Sofa-Design | Behance | ? | Sofa roomset (may be stills) |
| F33 | https://www.behance.net/gallery/149346217/CGI-Chair-Texture-Supply-Demo | Behance | ? | Chair demo for Texture Supply (may be stills) |
| F34 | https://www.behance.net/gallery/178110919/CGI-CHAIR-DESIGN | Behance | ? | Chair design CGI |
| F35 | https://www.behance.net/gallery/75893507/Charlie-Pommier-Tea-Chair-3D-CGI-furniture | Behance | ? | Tea Chair (may be stills) |
| F36 | https://www.youtube.com/shorts/IkJdFeDYUdU | YT Shorts | y | Dreamfoot: chair animation for e-commerce |
| F37 | https://www.youtube.com/shorts/pzkfbQF31ZQ | YT Shorts | y | Blender product animation short |
| F38 | https://www.youtube.com/shorts/EdWld1JBObc | YT Shorts | y | Blender product animation short |
| F39 | https://www.youtube.com/watch?v=IzPdhCfPQoU | YouTube | n | Furniture showreel |
| F40 | https://www.youtube.com/watch?v=c4DdAt7YA48 | YouTube | ? | Furniture product animation |
| F41 | https://www.youtube.com/watch?v=wwimnkx75E8 | YouTube | ? | Convertible furniture function demo |
| F42 | https://www.youtube.com/watch?v=hTIUvfvhMak | YouTube | n | UE4 cinematic interior archviz |
| F43 | https://www.youtube.com/watch?v=EpQVfMaq2ik | YouTube | n | Cinematic interior (Unreal) |
| F44 | https://www.youtube.com/watch?v=mJfLZvRMKIs | YouTube | n | iMeshh: Blender interior animation |
| F45 | https://www.instagram.com/cgifurniture/reel/DDH1nZpojy5/ | Instagram | y | CGIFurniture reel |
| F46 | https://www.instagram.com/render.friends/reel/C3a1k1oMlx-/ | Instagram | y | render.friends furniture/interior reel |
| F47 | https://www.instagram.com/renders.trenders/reel/DBWe-vpIwZq/ | Instagram | y | "Chairmood" chair reel |
| F48 | https://www.instagram.com/reel/CzrkG5GPYvo/ | Instagram | y | Archviz (3ds Max + Corona + tyFlow) |
| F49 | https://www.instagram.com/reel/C56JXtRMe6Q/ | Instagram | y | Archviz interior/exterior reel |
| F50 | https://www.artstation.com/artwork/b502wk | ArtStation | ? | Ergonomic desk and chair animation |
| F51 | https://www.danthree.studio/en/projects-cgi/3d-product-animation-table-lamp | Studio site | ? | Danthree: designer lamp animation |

### 2.3 Vehicles (44)
| # | URL | Platform | Vert | Description |
|---|---|---|---|---|
| V1 | https://vimeo.com/1128004006 | Vimeo | n | Audi studio-style visualization, dramatic lighting |
| V2 | https://vimeo.com/72913905 | Vimeo | n | Full-CG car animation test |
| V3 | https://vimeo.com/102218317 | Vimeo | n | Tax Free Film CG Automotive Reel 2015 |
| V4 | https://www.youtube.com/watch?v=DSxrwfGcDE4 | YouTube | n | Tax Free Film CG Automotive Reel 2014 |
| V5 | https://vimeo.com/171939943 | Vimeo | n | The Mill Blackbird (CG car body over live-action rig) |
| V6 | https://www.youtube.com/watch?v=VHLtPJnZo3Q | YouTube | n | The Mill Blackbird explainer |
| V7 | https://vimeo.com/491565868 | Vimeo | n | "Gullwing": full-CGI Mercedes 300SL short |
| V8 | https://vimeo.com/138655385 | Vimeo | n | Making-of: full-CGI Porsche 911 Carrera S |
| V9 | https://vimeo.com/195433329 | Vimeo | n | Borgward BX5 premiere film (studio unconfirmed) |
| V10 | https://vimeo.com/160705850 | Vimeo | n | "Motionbox by Mackevision" |
| V11 | https://vimeo.com/311697883 | Vimeo | n | MILLARC full-CGI reel (vehicle content unconfirmed) |
| V12 | https://vimeo.com/274988018 | Vimeo | ? | C4D + Octane car scene |
| V13 | https://vimeo.com/938553211 | Vimeo | ? | XO3D for Flash Motors: electric scooter film (CES 2024) |
| V14 | https://www.behance.net/gallery/224734393/PEUGEOT-LE-0-DAKKAR-Blender-Animation-CGI | Behance | ? | Peugeot LE-0 Dakar (Blender) |
| V15 | https://www.behance.net/gallery/128107077/Concept-car-full-cgi-scene | Behance | ? | Concept car full-CGI scene |
| V16 | https://www.behance.net/gallery/56478609/Mercedes-Redshift3D-Renders-Animation(full-CGI) | Behance | n | Mercedes (C4D + Redshift) |
| V17 | https://www.behance.net/gallery/191516303/Mercedes-Benz-E-Class-Full-CGI | Behance | ? | E-Class in an abstract curvilinear world |
| V18 | https://www.behance.net/gallery/160867803/BMW-5-SERIES-MARS-Full-CGI | Behance | ? | BMW 5 Series "MARS" |
| V19 | https://www.behance.net/gallery/232526167/Unreal-Engine-Car-Animation-Luxury-3D-Visualization | Behance | ? | Maverick Frame: luxury car (Unreal) |
| V20 | https://www.behance.net/gallery/167842829/Ford-Mustang-Unreal-Engine-animation | Behance | n | Post Processed: Mustang ad recreation (Unreal) |
| V21 | https://www.behance.net/gallery/165854977/Unreal-Engine-Custom-Vehicle-Animation-Rig | Behance | n | Unreal vehicle animation rig demo |
| V22 | https://www.behance.net/gallery/165042941/Mercedes-Benz-Cinematic-Unreal-Engine-5 | Behance | ? | Mercedes cinematic (UE5) |
| V23 | https://www.behance.net/gallery/166602191/Mercedes-300-SL-Unreal-Engine | Behance | ? | Mercedes 300 SL (Unreal) |
| V24 | https://www.behance.net/gallery/130083613/Making-of-car-animation-render-UE5 | Behance | n | AMG S65 animation plus making-of (UE5) |
| V25 | https://www.behance.net/gallery/169635297/BMW-M5-CS-Full-CGI-(Unreal-5) | Behance | ? | BMW M5 CS (UE5) |
| V26 | https://www.behance.net/gallery/55624359/UE4-Cinematic-Car-Demo | Behance | n | UE4 cinematic car demo |
| V27 | https://www.behance.net/gallery/214858927/Skoda-Packshot-Generator-(Unreal-Engine) | Behance | ? | Punctum: Škoda packshot/TV-spot generator (**very close to our product idea**) |
| V28 | https://www.artstation.com/artwork/PXwJPo | ArtStation | n | Ferrari 330 P4, 16mm Le Mans look (UE5) |
| V29 | https://www.artstation.com/artwork/39Dm6J | ArtStation | ? | 250 GTO-style car scenes (Blender) |
| V30 | https://www.artstation.com/artwork/05KAV | ArtStation | ? | Porsche Cayman GT4 in heavy rain |
| V31 | https://www.artstation.com/artwork/zPKKkm | ArtStation | n | Unreal car VFX (flames, smoke, nitrous) |
| V32 | https://greenwayanimation.artstation.com/projects/qJY3dy | ArtStation | ? | Greenway: "Car War" (Blender) |
| V33 | https://www.youtube.com/shorts/Z86xQFMm9Qs | YT Shorts | y | Blender BMW M4 G82 animation (making-of) |
| V34 | https://www.youtube.com/shorts/ZUBfYw1dVzs | YT Shorts | y | McLaren texturing, lighting, animation (Blender) |
| V35 | https://www.youtube.com/shorts/0O83BTSfN7Y | YT Shorts | y | KeyShot car render (tutorial-ish) |
| V36 | https://www.youtube.com/watch?v=hD76qczEagM | YouTube | n | "Stunning CGI Car Render" (Blender) |
| V37 | https://www.youtube.com/watch?v=3keTBzQLalc | YouTube | n | CGI car compilation (Blender/Unreal) |
| V38 | https://www.youtube.com/watch?v=6bSO3la_q9c | YouTube | n | "Arctic Supercar" (Blender + Unreal) |
| V39 | https://www.youtube.com/watch?v=9rZZlh8rGyg | YouTube | n | Unreal car cinematic demo |
| V40 | https://www.tiktok.com/@vladislav.art/video/7368907610034081057 | TikTok | y | Full-CGI supercar ad in a night city (Blender Cycles) |
| V41 | https://www.instagram.com/reel/COpuOLSH7ZQ/ | Instagram | y | Houdini / 3ds Max car reel (Audi, Ferrari) |
| V42 | https://www.instagram.com/reel/C76hAbkP3nA/ | Instagram | y | PixelPulseVFX: car crash (Blender) |
| V43 | https://www.instagram.com/rentionedits/reel/CuFd-LPoMUk/ | Instagram | y | Blender Cycles car render reel |
| V44 | https://www.instagram.com/reel/DRzxIiBE1tY/ | Instagram | y | "Car in Space" (Blender) |
| V45 | https://www.instagram.com/reel/DScVwKVDqU4/ | Instagram | y | Chasing Illusions Studio: automotive reel |
| V46 | https://www.framestore.com/work/gmexhibitzero | Studio site | n | Framestore GM #GMExhibitZero: CG vehicle off-road spot |

Note: V11 and V12 are weakly confirmed. Counting only confirmed vehicle clips gives **44** (V1–V46 minus V11 and V12). Motorcycles and bikes are nearly absent (only V13); run the bike recipe below.

### 2.4 Characters / collectibles / toys (38)
| # | URL | Platform | Vert | Description |
|---|---|---|---|---|
| C1 | https://vimeo.com/1071744841 | Vimeo | ? | supaCGI: Vaillant rabbit mascot animated in 3D |
| C2 | https://vimeo.com/1071762049 | Vimeo | ? | supaCGI: "Vaillant Live" brand ambassador |
| C3 | https://vimeo.com/573735855 | Vimeo | ? | Kinder Surprise: 3D toy comes to life |
| C4 | https://vimeo.com/360760182 | Vimeo | n | LEGO "Rebuild the World" (BETC / Traktor) |
| C5 | https://vimeo.com/360295043 | Vimeo | n | LEGO #RebuildTheWorld (ad cut) |
| C6 | https://vimeo.com/868258419 | Vimeo | n | LEGO "Play Is Your Superpower" |
| C7 | https://vimeo.com/231598749 | Vimeo | ? | LEGO CG minifig spot |
| C8 | https://vimeo.com/241055531 | Vimeo | ? | Maxim Swinton: LEGO commercial |
| C9 | https://vimeo.com/127628756 | Vimeo | ? | LEGO "Adventure in the City" |
| C10 | https://vimeo.com/666879056 | Vimeo | n | Blippi figure toy commercial (may be partly live action) |
| C11 | https://vimeo.com/189231021 | Vimeo | ? | C4D + Octane character animation |
| C12 | https://vimeo.com/419566602 | Vimeo | n | Asymmetric VFX: character turntable |
| C13 | https://vimeo.com/151776279 | Vimeo | n | Sculpt turntable (V-Ray for Maya) |
| C14 | https://www.behance.net/gallery/187947215/Vans-x-PopMart-x-Labubu | Behance | ? | GUMLAB: Vans x Pop Mart x Labubu character motion |
| C15 | https://www.behance.net/gallery/92039577/Red-Monster-3D | Behance | ? | Adobe Red Monster mascot (C4D + Redshift) |
| C16 | https://www.behance.net/gallery/157191583/Agoda-Agojis | Behance | ? | Arcade Studio: Agoda "Agojis" characters |
| C17 | https://www.behance.net/gallery/231402065/MASCOT-3D-Funny-life-of-Bananies | Behance | ? | Animated mascot series "Bananies" |
| C18 | https://www.behance.net/gallery/134599987/Commercial-3D-Illustrations-Mascot | Behance | ? | Commercial mascot (mostly stills; check) |
| C19 | https://www.youtube.com/watch?v=1xof7z3BqLA | YouTube | n | Superplastic "The Janky Heist" trailer |
| C20 | https://www.youtube.com/watch?v=dnyAzyJVuqc | YouTube | n | Superplastic "Road Tripz" |
| C21 | https://www.tiktok.com/@superplastic/video/7242052086215560454 | TikTok | y | Superplastic: Janky & Guggimon slip-n-slide |
| C22 | https://www.tiktok.com/@guggimam/video/7323717259354967326 | TikTok | y | Janky & Guggimon clip (fan repost) |
| C23 | https://www.tiktok.com/@keelanjon/video/7368425715630361889 | TikTok | y | First art toy in Blender, reveal/turn |
| C24 | https://www.tiktok.com/@untiler_3d/video/7471659854856310022 | TikTok | y | Toy product animation (Blender) |
| C25 | https://www.youtube.com/shorts/_KUlZHKGLCw | YT Shorts | y | Animated collectible figures showcase |
| C26 | https://www.youtube.com/shorts/7r5A5MWfwDw | YT Shorts | y | Cute Blender character animation |
| C27 | https://deepskystudios.com/project/superplastic-janky-guggimon-3d-tiktok-animation-production/ | Studio site | y | Deep Sky: Superplastic TikTok production case study |
| C28 | https://www.artstation.com/artwork/BQRyr | ArtStation | n | Character turntables (Maya/ZBrush) |
| C29 | https://www.artstation.com/artwork/NGmQVD | ArtStation | n | Joshua Allen: 360 turntables |
| C30 | https://www.artstation.com/artwork/OG4er8 | ArtStation | n | Turntable (3ds Max) |
| C31 | https://www.artstation.com/artwork/EvKLlv | ArtStation | n | Character turntable |
| C32 | https://www.artstation.com/artwork/PmnWmy | ArtStation | n | "From the 80s" head turntable |
| C33 | https://www.artstation.com/artwork/ZaL60N | ArtStation | n | David Vicich: turntables |
| C34 | https://www.artstation.com/artwork/B3Vd6m | ArtStation | n | Character design turntable |
| C35 | https://www.artstation.com/artwork/Jve9o0 | ArtStation | n | Character turntable |
| C36 | https://www.artstation.com/artwork/1wAdZ | ArtStation | ? | Panzer Ace vinyl toy (possibly stills) |
| C37 | https://www.artstation.com/artwork/d0zRRJ | ArtStation | ? | Vinyl toy render (motion unconfirmed) |
| C38 | https://www.artstation.com/artwork/EvBWkN | ArtStation | ? | Vivo toy in Blender (motion unconfirmed) |

Gap: no CGI clips found yet for Pop Mart/Labubu direct, Mighty Jaxx, Bearbrick or Hot Toys. Mine their own YouTube/Instagram accounts next.

### 2.5 Abstract / simulation (50)
| # | URL | Platform | Vert | Description |
|---|---|---|---|---|
| A1 | https://vimeo.com/311694987 | Vimeo | n | Wannerstedt "Oddly Satisfying 94": kinetic loops (marbles, sand, slime) |
| A2 | https://www.behance.net/gallery/58531729/Oddly-Satisfying-vol2 | Behance | ? | Wannerstedt: Oddly Satisfying vol.2 |
| A3 | https://www.instagram.com/reel/DRSJSbnjKko/ | Instagram | y? | Repost of a Wannerstedt loop |
| A4 | https://vimeo.com/511101501 | Vimeo | ? | "Synchronism": satisfying synced loop |
| A5 | https://vimeo.com/channels/1032257/237163361 | Vimeo | n | Simon Holmedal: "Procedural in Motion" |
| A6 | https://vimeo.com/760590514 | Vimeo | n | Simon Holmedal: ReConnect 2022 |
| A7 | https://vimeo.com/1060638322 | Vimeo | n | Tendril: Sims Reel 2025 |
| A8 | https://vimeo.com/676811098 | Vimeo | n | Tendril: "life #1" simulated growth |
| A9 | https://vimeo.com/350376905 | Vimeo | n | Tendril: Houdini experiments |
| A10 | https://vimeo.com/754045523 | Vimeo | n | ManvsMachine: Nike Zoom Mercurial |
| A11 | https://vimeo.com/164698304 | Vimeo | n | ManvsMachine: Nike Flyknit (sim + animation) |
| A12 | https://vimeo.com/groups/729025/videos/245246589 | Vimeo | n | Nike Vapormax: soft-body touchdown |
| A13 | https://vimeo.com/101359522 | Vimeo | n | Nike Mercurial "Revolution of Speed": shattering |
| A14 | https://vimeo.com/264966490 | Vimeo | n | Nike Air Max Day '18: sims |
| A15 | https://vimeo.com/345193348 | Vimeo | n | Stylised matte fluid (Houdini) |
| A16 | https://vimeo.com/129450242 | Vimeo | n | Viscous FLIP with bubbles |
| A17 | https://vimeo.com/351291409 | Vimeo | n | Procedural bottle pour (Houdini) |
| A18 | https://vimeo.com/801327793 | Vimeo | n | "The Beauty of Transparency": small-scale FLIP water |
| A19 | https://vimeo.com/374288005 | Vimeo | n | "Fluids": 30-million-particle meshed fluid |
| A20 | https://vimeo.com/225987030 | Vimeo | n | X-Particles fluid test |
| A21 | https://vimeo.com/159029570 | Vimeo | n | RealFlow soft bodies with SSS (Redshift) |
| A22 | https://vimeo.com/642577470 | Vimeo | n | Brad Dawson: soft-body test |
| A23 | https://vimeo.com/424617839 | Vimeo | n | Paulius Tarvydas: infinite abstract tunnel loop |
| A24 | https://vimeo.com/349658557 | Vimeo | n | SideFX 2019 Film & TV reel |
| A25 | https://www.behance.net/gallery/123749811/Houdini-Fluid-Motion-FX | Behance | ? | Houdini FLIP motion FX |
| A26 | https://www.behance.net/gallery/161922527/Fluid-splash-FX-CGI | Behance | ? | Water splash (Houdini + Redshift) |
| A27 | https://www.behance.net/gallery/108377495/Houdini-Liquid-Flow | Behance | ? | Liquid flow study |
| A28 | https://www.behance.net/gallery/137765249/Fluid-Simulation-Houdini | Behance | ? | Fluid simulation |
| A29 | https://www.artstation.com/artwork/lDG6lG | ArtStation | ? | Looping Vellum sim |
| A30 | https://www.artstation.com/artwork/vDbezO | ArtStation | ? | Slow-motion wrecking-ball RBD |
| A31 | https://www.artstation.com/artwork/mDOYaZ | ArtStation | ? | RBD plus particles |
| A32 | https://www.artstation.com/artwork/d8nRKK | ArtStation | ? | RBD destruction with smart activation |
| A33 | https://www.instagram.com/reel/DIEiDqGuYAB/ | Instagram | y? | SideFX repost: "Fluens #2" abstract fluid |
| A34 | https://www.instagram.com/reel/DILbTTVIb0U/ | Instagram | y? | SideFX repost: softfocus.digital |
| A35 | https://www.instagram.com/reel/DIvROTDsejz/ | Instagram | y? | SideFX repost: carlkrause "Trapped" |
| A36 | https://www.instagram.com/reel/DKIHD5PC7eH/ | Instagram | y? | SideFX repost: paper sim |
| A37 | https://www.instagram.com/sidefxhoudini/reel/C-M0ZqDqu_v/ | Instagram | y? | SideFX repost: RBD test |
| A38 | https://www.instagram.com/sidefxhoudini/reel/DIB2bwTvnWm/ | Instagram | y? | SideFX repost: large Houdini sim |
| A39 | https://www.instagram.com/reel/DJXBHhBK6cB/ | Instagram | y? | Cloth sim (Houdini, rendered in Cycles) |
| A40 | https://www.youtube.com/shorts/I5P-jVxBQe4 | YT Shorts | y | Water-splash ring (POP/FLIP) |
| A41 | https://m.youtube.com/shorts/r6OjlVa4iQs | YT Shorts | y | Stavros Sofianos: liquid sim |
| A42 | https://m.youtube.com/shorts/A4jNka-XZRk | YT Shorts | y | Vellum grains |
| A43 | https://www.youtube.com/shorts/7L1ddeHvW2M | YT Shorts | y | Cloth sim (Blender) |
| A44 | https://www.youtube.com/shorts/pupgT2R8MOE | YT Shorts | y | "0% vs 100% softness" soft body |
| A45 | https://www.youtube.com/shorts/aTmf1-7SbTA | YT Shorts | y | Soft-body cylinder through a spiral tube |
| A46 | https://www.youtube.com/shorts/lJ_zmLCmRZY | YT Shorts | y | Haribo gummy soft body (Blender) |
| A47 | https://www.tiktok.com/@renderx20/video/7562903006174366989 | TikTok | y | Wooden physics sim (Blender) |
| A48 | https://www.youtube.com/watch?v=vcUzl3kLwmU | YouTube | n | EmberGen fire test |
| A49 | https://motionographer.com/quickie/mondlicht-studios-endless-luxury-liquid-metal-simulation/ | Motionographer | ? | Mondlicht: "Endless Luxury" liquid-metal loop |
| A50 | https://motionographer.com/2013/05/08/dvein-the-veinmagma/ | Motionographer | n | Dvein "The Vein/Magma" |
| A51 | https://motionographer.com/2008/10/15/velvet-for-mattoni/ | Motionographer | n | Velvet for Mattoni: liquid brand spot (old; embed may be dead) |

Note: A51 is likely dead. Counting only live-likely rows gives **50**.

---

## 3. Search recipes (to scale to 500)

**Productive query patterns**
- `site:vimeo.com "3D product animation" <product>` (perfume, watch, headphones, sneaker, sofa, chair, lamp, kitchen)
- `site:behance.net/gallery "Full CGI" <brand>` (Porsche, BMW, AMG, Nike, Chanel): the most productive vehicle/product query
- `site:behance.net/gallery "<product> 3D CGI animation"` / `"CGI" chair animation` / `"art toy" animation`
- `site:artstation.com/artwork <topic> animation` / `turntable character` / `houdini "vellum loop" OR "rigid body" OR FLIP`
- `site:youtube.com/shorts "3d product animation" blender OR "cinema 4d"`: the best source of verified-vertical clips
- `site:instagram.com/reel "SideFX Houdini | Repost"`: reliable sim discovery
- `site:instagram.com/reel archviz corona animation` / `CGI car 3D animation`
- `vimeo "CG Automotive Reel"`, `vimeo "full CGI" car <brand>`
- Brand + "CGI commercial" on Vimeo (LEGO, Kinder, Funko, Pop Mart, Superplastic, HAY, Muuto, Vitra), then follow the studio credits
- Motorcycles/bikes gap: `CGI e-bike OR "electric scooter" product animation vimeo`, `"SCOTT SPARK" CGI behance`
- Motionographer: `motionographer.com/tag/<liquid|fluid-simulation|houdini|particles|cgi>`

**Channel-walking (highest yield per request)**
Take a top clip, open the studio's Vimeo user page, list its videos (e.g. `yt-dlp --flat-playlist https://vimeo.com/mvsm`), then walk the credited studios. The best seeds are ManvsMachine, Tendril, Mackevision, CGIFurniture, Superplastic and SideFX.

**Hashtags**
- Product: #productanimation #3dproductanimation #cgiad #octanerender #redshift3d #blendercgi #c4d
- Furniture: #furnitureanimation #cgifurniture #archvizanimation #interiordesign3d #coronarender
- Vehicles: #automotivecgi #cgicar #blendercar #3dcarrender #unrealengine5 #cyclesrender
- Characters: #arttoy #designertoy #arttoy3d #c4dcharacter #blindbox #characteranimation #turntable
- Abstract: #houdinifx #sidefxhoudini #vellum #xparticles #oddlysatisfying #simulation #cgloop #embergen

**Filters**
- Append a tool name (blender/octane/houdini/redshift) to exclude AI-generated fakes.
- Keep clips of 30 s or less for timing studies (the target is 8–12 s). Longer reels are still useful for per-shot lighting and camera reference.
- Vertical priority: YouTube Shorts > TikTok > Instagram Reels (login wall) > Vimeo (rarely vertical).
