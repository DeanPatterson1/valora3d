"""Where a camera path's foreground card goes (profile_slide foreground, Task 83), pure; the Blender builder
(engine/blender/foreground.py) only builds what this returns.

The card is built from the profile the camera itself is solved against (engine/compiler/timeline._pose_at): the
subject's posed profile at camera_t (the mid-shot pose for an anchor camera), not the rest profile, so a car that
drove or slid away before or during the shot keeps its card between the lens and itself. Then every frame of the
shot is checked against the subject's LIVE posed bounds (the pose the render shows that frame): the card never
stands inside them (+ margin) and stays in front of the lens and nearer than the subject's nearest corner. A card
that fails anywhere in its shot is dropped, as the path's own foreground() drops one that fails at rest."""
from engine.camera_context import camera_sampler
from engine.geometry import _basis, point_in_box
from engine.motion_path import camera_t, is_moving, pose_fn, posed_profile, shot_t

BOX_MARGIN = 0.10     # = checker.BOX_MARGIN


def _corners(lo, hi):
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def _shot_us(sh, fps):
    """u of every frame of the shot (the timeline's shot_u), the last frame at u = 1."""
    first, last = int(round(sh["startS"] * fps)) + 1, int(round(sh["endS"] * fps))
    n = max(last - first, 0)
    return [k / n for k in range(n + 1)] if n else [0.0]


def clear_throughout(card, sh, profile, sample, cam_profile, live_at, fps):
    """True when the card stays clear of the live subject and between lens and subject at every frame."""
    pts = list(card["corners"]) + [tuple(card["center"])]
    for u in _shot_us(sh, fps):
        cam = sample(sh["camera"]["params"], cam_profile(u), u)
        live = live_at(u)
        fwd, _, _ = _basis(cam)
        depth = lambda q: sum((q[i] - cam.position[i]) * fwd[i] for i in range(3))  # noqa: E731
        near = min(depth(q) for q in _corners(live.boundsMin, live.boundsMax))
        if not all(0.0 < depth(q) < near for q in card["corners"]):
            return False
        if any(point_in_box(q, live.boundsMin, live.boundsMax, BOX_MARGIN) for q in pts):
            return False
    return True


def plan_foreground(script, profile, catalog, outdoor=True, pose_override=None):
    """[(shot index, card)] for every shot whose camera path.py foreground() returns a card that holds up
    against the posed subject for the whole shot. pose_override: a pose_at(t, shot) to use (tests)."""
    fps, out = script["format"]["fps"], []
    moving = pose_override is not None or is_moving(script, profile, catalog)
    pose_at = pose_override or (pose_fn(script, profile, catalog) if moving else None)
    for i, sh in enumerate(script["shots"]):
        bid = sh["camera"]["id"]
        catalog.load_camera_path(bid)
        fn = catalog._module_attr("camera", bid, "path.py", "foreground")
        if fn is None:
            continue
        if moving:
            follows = (catalog.get("camera", bid) or {}).get("follows", "anchor")
            dur = float(script["format"].get("durationS", sh["endS"]))
            cam_profile = lambda u, sh=sh, i=i, f=follows: posed_profile(  # noqa: E731
                profile, pose_at(camera_t(sh, f, u, fps), i))
            live_at = lambda u, sh=sh, i=i: posed_profile(  # noqa: E731
                profile, pose_at(min(max(shot_t(sh, u, fps), 0.0), dur), i))
            sample = camera_sampler(catalog, sh, profile, (pose_at, fps))
        else:
            cam_profile = live_at = lambda u: profile  # noqa: E731
            sample = camera_sampler(catalog, sh, profile)
        card = fn(sh["camera"]["params"], cam_profile(0.5), bool(outdoor))
        if card is None:
            continue
        if clear_throughout(card, sh, profile, sample, cam_profile, live_at, fps):
            out.append((i, card))
    return out
