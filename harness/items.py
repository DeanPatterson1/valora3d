"""Every TIERS.md §2 checklist item, one line each, with its tier and method tag exactly as TIERS
tags it. Special cases: T3-01 is M but our own renders read cut times from the script (S);
T2-08 is M with an S fallback; T4-01 is V with an S half; V-C02 (vehicles.md) is an extra S item
scored at T3."""

ITEMS = [
    {"id": "B-01", "tier": "B", "method": "M", "text": "No black/empty frame: mean luminance > 0.02 and subject visible"},
    {"id": "B-02", "tier": "B", "method": "M", "text": "Clipping: < 2% pixels >= 0.99, < 5% <= 0.01 (bg excluded on black worlds)"},
    {"id": "B-03", "tier": "B", "method": "M", "text": "Flicker: no unexplained frame-to-frame luminance jump > 3%"},
    {"id": "B-04", "tier": "B", "method": "S", "text": "Camera outside subject bounds; subject in frame at 12 samples per shot"},
    {"id": "B-05", "tier": "B", "method": "M", "text": "Subject covers >= 25% of the frame along its dominant axis"},
    {"id": "T1-X1", "tier": "T1", "method": "S", "text": "Single shot, constant-rate rotation sweeping > 180 deg (turntable)"},
    {"id": "T1-X2", "tier": "T1", "method": "M", "text": "Uniform background and no ground contact shadow"},
    {"id": "T1-X3", "tier": "T1", "method": "S", "text": "One static preset, key:fill < 1.5:1 and no rim (flat)"},
    {"id": "T2-01", "tier": "T2", "method": "S", "text": "World has ground or environment; subject grounded"},
    {"id": "T2-02", "tier": "T2", "method": "M", "text": "Environment visible in reflections: gloss luminance std >= 0.08"},
    {"id": "T2-03", "tier": "T2", "method": "S", "text": "Every camera move eased unless linearByDesign"},
    {"id": "T2-04", "tier": "T2", "method": "S", "text": "Operator feel: shake layer or motivated path on every shot"},
    {"id": "T2-05", "tier": "T2", "method": "S", "text": "Motion blur on, 180-degree shutter"},
    {"id": "T2-06", "tier": "T2", "method": "M", "text": "Focus on subject: subject sharpness >= 1.5x background at f <= 5.6"},
    {"id": "T2-07", "tier": "T2", "method": "S+M", "text": "Atmosphere present; far bg local contrast <= 0.8x near"},
    {"id": "T2-08", "tier": "T2", "method": "M", "text": "Mood grade present (not identity)"},
    {"id": "T2-09", "tier": "T2", "method": "V", "text": "Looks like one real place shot with a real camera"},
    {"id": "T3-01", "tier": "T3", "method": "M", "text": "3-7 shots per 10 s (cut detection; script cut times for our renders)"},
    {"id": "T3-02", "tier": "T3", "method": "S", "text": "Shot lengths: median 1.0-3.0 s, none < 0.5 s, last >= 1.5 s"},
    {"id": "T3-03", "tier": "T3", "method": "S+M", "text": ">= 2 shot scales and a detail shot covering >= 60% or exceeding the frame"},
    {"id": "T3-04", "tier": "T3", "method": "S", "text": "30-degree rule or >= 1.5x screen size across every cut"},
    {"id": "T3-05", "tier": "T3", "method": "S", "text": "Screen direction held for a moving subject"},
    {"id": "T3-06", "tier": "T3", "method": "M", "text": "Highlights are elongated strips, not blobs"},
    {"id": "T3-07", "tier": "T3", "method": "M", "text": "Planned darks >= 25% and highlights >= 15% of gloss"},
    {"id": "T3-08", "tier": "T3", "method": "M", "text": "No blown speculars: gloss share >= 0.99 < 0.5%"},
    {"id": "T3-09", "tier": "T3", "method": "M", "text": "Silhouette separation >= 0.1 on >= 60% of the boundary"},
    {"id": "T3-10", "tier": "T3", "method": "V", "text": "Reflections follow body lines as long gradients with clean darks"},
    {"id": "T3-11", "tier": "T3", "method": "S", "text": "One dominant CameraBench primitive per shot"},
    {"id": "T3-12", "tier": "T3", "method": "M", "text": "Smoothness: no optical-flow jump > 25% of range within a shot"},
    {"id": "T3-13", "tier": "T3", "method": "S", "text": "Ends still: final 1.0 s camera speed < 2% of peak"},
    {"id": "T3-14", "tier": "T3", "method": "S", "text": "Physical caps: arc <= 80 deg/s, vertical and wheel limits"},
    {"id": "T3-15", "tier": "T3", "method": "M", "text": "Hook: subject >= 10% of frame by 0.5 s"},
    {"id": "T3-16", "tier": "T3", "method": "S", "text": "Last shot is a hero framing >= 1.5 s"},
    {"id": "T3-17", "tier": "T3", "method": "M", "text": ">= 1 motivated cut (flow match or declared transition)"},
    {"id": "T3-18", "tier": "T3", "method": "M", "text": "9:16 subject centroid inside the TikTok and Reels safe boxes"},
    {"id": "T3-19", "tier": "T3", "method": "M", "text": "Subject chroma >= 1.10x background (luminance for monochrome looks)"},
    {"id": "T3-20", "tier": "T3", "method": "M", "text": "Per-shot background Lab within dE 10 of the clip mean"},
    {"id": "T3-21", "tier": "T3", "method": "S", "text": "Anti-miniature DOF on full vehicle frames"},
    {"id": "T3-22", "tier": "T3", "method": "M", "text": "Detail shots (>= 85 mm) shallow: bg sharpness <= 0.5x subject"},
    {"id": "T3-23", "tier": "T3", "method": "V", "text": "Passes as a frame from a paid commercial"},
    {"id": "V-C02", "tier": "T3", "method": "S", "text": "Vehicle full frames use a lens >= 28 mm"},
    {"id": "T4-01", "tier": "T4", "method": "V", "text": "Continuity of light, time, weather, surface state (S half: same world and lighting)"},
    {"id": "T4-02", "tier": "T4", "method": "S", "text": "Vehicle dynamics: roll, pitch, secondary bounce"},
    {"id": "T4-03", "tier": "T4", "method": "S", "text": "Simulation touches the subject"},
    {"id": "T4-04", "tier": "T4", "method": "M", "text": "Lens realism: halation placement and temporal grain"},
    {"id": "T4-05", "tier": "T4", "method": "V", "text": "Lookdev micro-detail without a CG-clean look"},
    {"id": "T4-06", "tier": "T4", "method": "V", "text": "Viewers cannot tell which shots are CG (>= 90%)"},
]

_BY_ID = {i["id"]: i for i in ITEMS}


def by_id(iid):
    return _BY_ID[iid]
