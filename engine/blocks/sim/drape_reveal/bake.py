"""drape_reveal bake (phase 6 Task 108, stage 4b only; METHODS SC-02). A cloth sheet (engine/physics/drape) is
pre-shaped as a tent two shell voxels above a height map ray-cast onto the subject's CLOSED SHELL, settles over the
pre-roll, and a hook drags its pinned edge (or lifts its top patch) off the subject. Colliders: the shell seen from
above as a height field (no undercuts to snag in; engine/physics/drape.heightfield) and a hidden ground plane at
z = 0; the shell itself is left to the probe. The one wind field (if the script has one) pushes the cloth by
the fabric's wind weight. Stepped with frame_set into cloth.pc2 + mesh.json (engine/blender/cloth.bake_pc2); the
report carries the stretch, speed and the share of the sheet still over the subject at revealS + 0.5. A subject
under 1 m is simulated enlarged by engine/physics/drape.sim_scale with gravity scaled alike, and written back at
real size."""
import math

FRICTION = {"silk": 0.4, "satin": 0.5, "canvas": 1.5}     # (eng) cloth-on-paint friction: a cover slides


def _heights(shell, xy, top):
    """Highest shell hit under each (x, y) (0 where the ray misses), ray-cast straight down from above."""
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    tree = BVHTree.FromObject(shell, dg)
    mw, inv = shell.matrix_world, shell.matrix_world.inverted()
    down = (inv.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
    out = []
    for x, y in xy:
        o = inv @ Vector((x, y, top))
        loc, _, _, _ = tree.ray_cast(o, down)
        out.append(max(0.0, (mw @ loc).z) if loc is not None else 0.0)
    return out


def bake(ctx):
    import bpy
    from mathutils import Matrix
    from engine.blender import cloth as BC
    from engine.blender.realism_rig import fcurves
    from engine.physics import drape as D
    from engine.physics import proxy as PX
    from engine.physics.sim_facts import nose_sign
    p, prof, b = ctx.params, ctx.profile, ctx.bake
    fr, sc = b["frames"], ctx.scene
    fps = sc.render.fps / sc.render.fps_base
    longest = max(prof.sizeM)
    S = D.sim_scale(prof)            # small subjects simulate enlarged, with gravity x S (see engine/physics/drape)
    nx, ny, sp, w, l, centre = D.sheet_grid(prof)
    xy = D.grid_xy(nx, ny, sp, centre)
    shell = b["proxy"]["shell"]
    top = prof.boundsMax[2] + 0.5 * longest
    hs = _heights(shell, xy, top)
    zs = D.preshape(hs, nx, ny, 2.0 * PX.voxel_m(prof, "shell"))
    _, faces = BC.grid_mesh(nx, ny, sp)
    cam = ctx.hero_pose.position if ctx.hero_pose is not None else None
    ns = nose_sign(prof, ctx.script.get("markers") or [])[0]
    d = D.pull_dir(p["pull"], prof, camera_xy=(cam[0], cam[1]) if cam is not None else None, nose_sign=ns)
    pin = D.pins(p["pull"], nx, ny, xy, zs, d)
    ob = BC.sheet("valora_drape", [(x * S, y * S, z * S) for (x, y), z in zip(xy, zs)], faces, pins=pin)
    # the hook: an empty at the pinned vertices' centroid; a HOOK modifier before the cloth moves them
    anchor = [sum((xy[i][0], xy[i][1], zs[i])[k] for i in pin) / len(pin) for k in range(3)]
    hook = bpy.data.objects.new("valora_drape_hook", None)
    sc.collection.objects.link(hook)
    hook.location = [a * S for a in anchor]
    hm = ob.modifiers.new("valora_hook", "HOOK")
    hm.object = hook
    hm.vertex_group = "pin"
    hm.center = hook.location
    hm.matrix_inverse = Matrix.Translation(hook.location).inverted()     # at rest the hook moves nothing
    first, last = fr["bake_first"], fr["bake_last"]
    win0 = first + fr["preroll"]                                  # bake frame of the window's start
    keys = D.pull_keys(p["pull"], prof, win0, fps, p["revealS"], d, (w, l), anchor, end_s=(last - win0) / fps)
    hook.keyframe_insert("location", frame=first)
    for f, off in keys:
        if f > last:
            break
        hook.location = [(a + o) * S for a, o in zip(anchor, off)]
        hook.keyframe_insert("location", frame=f)
    for c in fcurves(hook.animation_data.action):
        for kp in c.keyframe_points:
            kp.interpolation = "LINEAR"
    sc.use_gravity = True
    sc.gravity = (0.0, 0.0, -9.81 * S)
    settings = BC.apply_cloth(ob, p["fabric"], sp * S, longest=longest * S, time_scale=p["timeScale"],
                              self_collision=True, frame_range=(first, last))
    ww = BC.wind_response(ob, p["fabric"])
    fx, fy = 2 * nx - 1, 2 * ny - 1                               # the collider: twice as fine as the sheet
    fxy = D.grid_xy(fx, fy, sp / 2, centre)
    hz = D.heightfield(_heights(shell, fxy, top), fx, fy)
    _, ffaces = BC.grid_mesh(fx, fy, sp / 2)
    hf = BC.sheet("valora_drape_collider", [(x * S, y * S, z * S) for (x, y), z in zip(fxy, hz)], ffaces)
    hf.hide_render = True
    BC.collider(hf, longest * S, friction=FRICTION[p["fabric"]])
    BC.ground_collider(8.0 * max(w, l) * S)
    off_frame = win0 + int(math.ceil((p["revealS"] + 0.5) * fps))
    probe = {}

    def on_frame(f):
        if f == off_frame:
            ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
            probe["offShare"] = D.off_subject_share([tuple(c / S for c in v.co) for v in ev.data.vertices], prof)

    stats = BC.bake_pc2(sc, ob, first, last, b["dir"], faces, on_frame=on_frame, scale=1.0 / S)
    return {**stats, "grid": [nx, ny], "spacingM": round(sp, 5), "sheetM": [round(w, 4), round(l, 4)],
            "simScale": S, "pins": len(pin), "pullDir": [round(d[0], 4), round(d[1], 4)], "cloth": settings,
            "windWeight": ww, "offFrame": off_frame, "overSubjectShareAtRevealEnd": probe.get("offShare"),
            "fabric": p["fabric"], "pull": p["pull"]}
