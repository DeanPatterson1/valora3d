import { describe, expect, it } from "vitest";
import type { ScenePlan, Shot } from "@/lib/schema";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { handheldOffset, lensToFov, shotAt, shotPathPoint, type Bounds } from "./cameraPath";

/**
 * The render pipeline traces this same path in Blender
 * (`tools/render-studio/scene_plan_camera.py`). Every number here is asserted there
 * too, to the same precision. If one side changes alone the preview and the video
 * stop agreeing, and one of these two files will fail.
 */

const SUBJECT: Bounds = { radius: 2.4, height: 1.45 };

function plan(over: Partial<ScenePlan["camera"]> = {}): ScenePlan {
  const base = defaultPlan("car");
  return {
    ...base,
    camera: { style: "smooth", lensMm: 50, heightM: 1.4, motionStrength: 0, ...over },
    shots: [
      { id: "a", start: 0, end: 4, action: "slow_orbit", distanceMultiplier: 1 },
      { id: "b", start: 4, end: 10, action: "hero_push_in", distanceMultiplier: 1 },
    ],
    output: { ...base.output, durationS: 10 },
  };
}

const radial = (p: { x: number; z: number }) => Math.hypot(p.x, p.z);

describe("shotAt", () => {
  it("finds the running shot", () => {
    const { shot, t } = shotAt(plan(), 1);
    expect(shot.id).toBe("a");
    expect(t).toBeCloseTo(0.25, 12);
  });

  it("clamps before the first shot", () => {
    const { shot, t } = shotAt(plan(), -5);
    expect(shot.id).toBe("a");
    expect(t).toBe(0);
  });

  it("clamps past the last shot", () => {
    const { shot, t } = shotAt(plan(), 99);
    expect(shot.id).toBe("b");
    expect(t).toBe(1);
  });

  it("gives a boundary to the earlier shot", () => {
    expect(shotAt(plan(), 4).shot.id).toBe("a");
  });
});

describe("shotPathPoint", () => {
  it("places the orbit start where Blender places it", () => {
    const point = shotPathPoint(plan(), plan().shots[0], 0, SUBJECT);
    expect(point.x).toBeCloseTo(-6.788225099390855, 12);
    expect(point.y).toBeCloseTo(1.4, 12);
    expect(point.z).toBeCloseTo(6.788225099390856, 12);
  });

  it("moves a push-in closer", () => {
    const shot = plan().shots[1];
    expect(radial(shotPathPoint(plan(), shot, 1, SUBJECT))).toBeLessThan(
      radial(shotPathPoint(plan(), shot, 0, SUBJECT)),
    );
  });

  it("caps low tracking below eye height", () => {
    const shot: Shot = { id: "c", start: 0, end: 1, action: "low_tracking", distanceMultiplier: 1 };
    expect(shotPathPoint(plan(), shot, 0.5, SUBJECT).y).toBeCloseTo(0.6, 12);
  });

  it("backs a longer lens off", () => {
    const shot = plan().shots[0];
    expect(radial(shotPathPoint(plan({ lensMm: 100 }), shot, 0, SUBJECT))).toBeGreaterThan(
      radial(shotPathPoint(plan(), shot, 0, SUBJECT)),
    );
  });
});

describe("handheldOffset", () => {
  it("is still at zero strength", () => {
    expect(handheldOffset(3, 0)).toEqual({ x: 0, y: 0, roll: 0 });
  });

  it("sways on absolute time", () => {
    const sway = handheldOffset(2, 1);
    expect(sway.x).toBeCloseTo(Math.sin(2 * 7.3) * 0.02, 12);
    expect(sway.y).toBeCloseTo(Math.abs(Math.sin(2 * 5.1)) * 0.03, 12);
    expect(sway.roll).toBeCloseTo(Math.sin(2 * 2.1) * 0.01, 12);
  });

  it("never dips below the path", () => {
    for (let step = 0; step < 50; step++) expect(handheldOffset(step / 7, 1).y).toBeGreaterThanOrEqual(0);
  });
});

describe("lensToFov", () => {
  it("matches the Blender sensor at 50mm", () => {
    expect(lensToFov(50)).toBeCloseTo(26.991466561591626, 12);
  });

  it("matches the Blender sensor at 24mm", () => {
    expect(lensToFov(24)).toBeCloseTo(53.13010235415598, 12);
  });
});
