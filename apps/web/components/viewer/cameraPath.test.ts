import { describe, it, expect } from "vitest";
import { handheldOffset, lensToFov, shotAt, shotPathPoint, subjectCentre } from "./cameraPath";
import { defaultPlan } from "@/lib/scene/defaultPlan";

describe("shotPathPoint", () => {
  const plan = defaultPlan("car");
  const bounds = { radius: 2.5, height: 1.4 };
  const dist = (p: { x: number; z: number }) => Math.hypot(p.x, p.z);

  it("orbit keeps constant distance", () => {
    const a = shotPathPoint(plan, plan.shots[0], 0, bounds);
    const b = shotPathPoint(plan, plan.shots[0], 0.5, bounds);
    expect(dist(a)).toBeCloseTo(dist(b));
  });
  it("push in gets closer over time", () => {
    const shot = { ...plan.shots[0], action: "hero_push_in" as const };
    const a = shotPathPoint(plan, shot, 0, bounds);
    const b = shotPathPoint(plan, shot, 1, bounds);
    expect(dist(b)).toBeLessThan(dist(a));
  });
  it("respects camera height", () => {
    expect(shotPathPoint(plan, plan.shots[0], 0.3, bounds).y).toBeCloseTo(plan.camera.heightM);
  });
  it("low tracking never rises above 0.6 m and travels sideways", () => {
    const shot = { ...plan.shots[0], action: "low_tracking" as const };
    const a = shotPathPoint(plan, shot, 0, bounds);
    const b = shotPathPoint(plan, shot, 1, bounds);
    expect(a.y).toBeLessThanOrEqual(0.6);
    expect(a.z).toBeCloseTo(b.z);
    expect(b.x).toBeGreaterThan(a.x);
  });
  it("walk toward closes in", () => {
    const shot = { ...plan.shots[0], action: "handheld_walk_toward" as const };
    expect(dist(shotPathPoint(plan, shot, 1, bounds))).toBeLessThan(dist(shotPathPoint(plan, shot, 0, bounds)));
  });
  it("longer lenses back the camera off", () => {
    const wide = { ...plan, camera: { ...plan.camera, lensMm: 24 } };
    const tele = { ...plan, camera: { ...plan.camera, lensMm: 85 } };
    expect(dist(shotPathPoint(tele, plan.shots[0], 0, bounds))).toBeGreaterThan(
      dist(shotPathPoint(wide, plan.shots[0], 0, bounds)),
    );
  });
  it("distance multiplier scales the path", () => {
    const far = { ...plan.shots[0], distanceMultiplier: 2 };
    expect(dist(shotPathPoint(plan, far, 0, bounds))).toBeCloseTo(2 * dist(shotPathPoint(plan, plan.shots[0], 0, bounds)));
  });
});

describe("shotAt", () => {
  const plan = defaultPlan("car");
  const two = {
    ...plan,
    shots: [
      { id: "a", start: 0, end: 4, action: "slow_orbit" as const, distanceMultiplier: 1 },
      { id: "b", start: 4, end: 10, action: "hero_push_in" as const, distanceMultiplier: 1 },
    ],
  };
  it("finds the shot containing the time and its local t", () => {
    expect(shotAt(two, 1)).toEqual({ shot: two.shots[0], t: 0.25 });
    expect(shotAt(two, 7)).toEqual({ shot: two.shots[1], t: 0.5 });
  });
  it("clamps past the end to the last shot", () => {
    const r = shotAt(two, 99);
    expect(r.shot.id).toBe("b");
    expect(r.t).toBe(1);
  });
  it("clamps negatives to the first shot start", () => {
    const r = shotAt(two, -3);
    expect(r.shot.id).toBe("a");
    expect(r.t).toBe(0);
  });
});

describe("handheldOffset", () => {
  it("is zero at zero strength", () => {
    expect(handheldOffset(3.7, 0)).toEqual({ x: 0, y: 0, roll: 0 });
  });
  it("scales with strength and stays small", () => {
    const a = handheldOffset(1.3, 0.5);
    const b = handheldOffset(1.3, 1);
    expect(b.x).toBeCloseTo(a.x * 2);
    expect(Math.abs(b.x)).toBeLessThanOrEqual(0.02);
    expect(b.y).toBeGreaterThanOrEqual(0);
    expect(b.y).toBeLessThanOrEqual(0.03);
  });
});

describe("lensToFov", () => {
  it("gives the vertical fov for a 35 mm sensor", () => {
    expect(lensToFov(50)).toBeCloseTo(26.99, 1);
    expect(lensToFov(24)).toBeGreaterThan(lensToFov(85));
  });
});

describe("subjectCentre", () => {
  it("sits at half the subject height", () => {
    expect(subjectCentre({ radius: 2, height: 1.4 })).toEqual({ x: 0, y: 0.7, z: 0 });
  });
});
