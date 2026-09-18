import { describe, it, expect } from "vitest";
import { editFromPrompt } from "./editFromPrompt";
import { defaultPlan } from "../defaultPlan";

const base = defaultPlan("car");

describe("editFromPrompt", () => {
  it("returns two patches for two intents", () => {
    const r = editFromPrompt("darker and add rain", base);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.patches).toEqual([
      { operation: "update_lighting", exposureDelta: -0.7 },
      { operation: "set_effect", effect: "rain", value: 0.5 },
    ]);
  });
  it("maps closer to a distance multiplier", () => {
    const r = editFromPrompt("move the camera closer", base);
    expect(r.ok && r.patches[0]).toEqual({ operation: "modify_camera", distanceMultiplier: 0.75 });
  });
  it("steps lenses", () => {
    const r = editFromPrompt("tighter lens", base); // base 50 -> 85
    expect(r.ok && r.patches[0]).toEqual({ operation: "modify_camera", lensMm: 85 });
  });
  it("targets the last shot for actions", () => {
    const r = editFromPrompt("orbit instead", base);
    expect(r.ok && r.patches[0]).toEqual({ operation: "set_shot_action", shotId: "shot-1", action: "slow_orbit" });
  });
  it("reports not understood with hints", () => {
    const r = editFromPrompt("make it pop", base);
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.error.code).toBe("edit_not_understood");
    expect(r.error.hints?.length).toBe(3);
  });
  it("reports at_limit when nothing can change", () => {
    const dark = { ...base, lighting: { ...base.lighting, exposure: -3 } };
    const r = editFromPrompt("darker", dark);
    expect(!r.ok && r.error.code).toBe("at_limit");
  });
  it("mixed intents: applies what it can and names the limited ones", () => {
    const dark = { ...base, lighting: { ...base.lighting, exposure: -3 } };
    const r = editFromPrompt("darker and add rain", dark);
    expect(r).toEqual({ ok: true, patches: [{ operation: "set_effect", effect: "rain", value: 0.5 }], limited: ["darker"] });
  });
  it("omits limited when nothing was limited", () => {
    const r = editFromPrompt("add rain", base);
    expect(r.ok && "limited" in r).toBe(false);
  });
  it("studio white yields exactly one studio_white patch", () => {
    const r = editFromPrompt("studio white", base);
    expect(r.ok && r.patches).toEqual([{ operation: "set_scene", environment: "studio_white", ground: "studio_floor" }]);
  });
  it("does not treat 'brain' as rain", () => {
    const r = editFromPrompt("the brain of the operation", base);
    expect(!r.ok && r.error.code).toBe("edit_not_understood");
  });
  it("wet ground adds the effect at the spec step of 0.5", () => {
    const r = editFromPrompt("wet ground", base);
    expect(r.ok && r.patches).toEqual([{ operation: "set_effect", effect: "wetGround", value: 0.5 }]);
  });
  it("remove / no / less wet ground turns the effect off, and only once", () => {
    for (const phrase of ["remove wet ground", "no wet road", "less wet street"]) {
      const r = editFromPrompt(phrase, base);
      const wet = r.ok ? r.patches.filter((p) => p.operation === "set_effect" && p.effect === "wetGround") : [];
      expect(wet, phrase).toEqual([{ operation: "set_effect", effect: "wetGround", value: 0 }]);
    }
  });
  it("accepts plural streets, roads and highways", () => {
    expect(editFromPrompt("city streets", base)).toEqual({ ok: true, patches: [{ operation: "set_scene", environment: "urban_night" }] });
    expect(editFromPrompt("on the roads", base)).toEqual({ ok: true, patches: [{ operation: "set_scene", environment: "outdoor_road" }] });
    expect(editFromPrompt("on the highways", base)).toEqual({ ok: true, patches: [{ operation: "set_scene", environment: "outdoor_road" }] });
    expect(editFromPrompt("through the cities", base)).toEqual({ ok: true, patches: [{ operation: "set_scene", environment: "urban_night" }] });
  });
  it("accepts 'walk towards'", () => {
    const r = editFromPrompt("walk towards it", base);
    expect(r.ok && r.patches[0]).toEqual({ operation: "set_shot_action", shotId: "shot-1", action: "handheld_walk_toward" });
  });
  it("longer steps duration", () => {
    const r = editFromPrompt("make it longer", base); // 10 -> 15
    expect(r.ok && r.patches[0]).toEqual({ operation: "set_output", output: { durationS: 15 } });
  });
  it("maps further, lower, higher, wider, shorter and dry ground", () => {
    const one = (prompt: string) => {
      const r = editFromPrompt(prompt, base);
      expect(r.ok, prompt).toBe(true);
      return r.ok ? r.patches : [];
    };
    expect(one("further away")).toEqual([{ operation: "modify_camera", distanceMultiplier: 1.33 }]);
    expect(one("lower the camera")).toEqual([{ operation: "modify_camera", heightDelta: -0.3 }]);
    expect(one("higher")).toEqual([{ operation: "modify_camera", heightDelta: 0.3 }]);
    expect(one("wider lens")).toEqual([{ operation: "modify_camera", lensMm: 35 }]); // 50 -> 35
    expect(one("shorter")).toEqual([{ operation: "set_output", output: { durationS: 5 } }]); // 10 -> 5
    expect(one("dry ground")).toEqual([{ operation: "set_effect", effect: "wetGround", value: 0 }]);
  });
  it("wider at the widest lens is at_limit", () => {
    const wide = { ...base, camera: { ...base.camera, lensMm: 24 } };
    expect(editFromPrompt("wider", wide)).toEqual({ ok: false, error: { code: "at_limit", message: expect.any(String) } });
  });
  it("shorter at 5 s is at_limit", () => {
    const short = { ...base, output: { ...base.output, durationS: 5 as const } };
    expect(editFromPrompt("shorter", short)).toEqual({ ok: false, error: { code: "at_limit", message: expect.any(String) } });
  });
  it("closer when every shot is at the minimum distance is at_limit", () => {
    const near = { ...base, shots: base.shots.map((s) => ({ ...s, distanceMultiplier: 0.4 })) };
    expect(editFromPrompt("closer", near)).toMatchObject({ ok: false, error: { code: "at_limit" } });
  });
  it("shares vocabulary with plan: downtown at night", () => {
    const r = editFromPrompt("downtown at night", base);
    expect(r.ok && r.patches).toEqual([
      { operation: "set_scene", environment: "urban_night" },
      { operation: "set_scene", time: "night" },
    ]);
    expect(editFromPrompt("mountain road", base)).toMatchObject({ ok: true, patches: [{ operation: "set_scene", environment: "outdoor_road" }] });
  });
  it("collects output mentions into one set_output patch", () => {
    const r = editFromPrompt("4k at 60 fps", base);
    expect(r.ok && r.patches).toEqual([{ operation: "set_output", output: { resolution: "4k", fps: 60 } }]);
  });
});
