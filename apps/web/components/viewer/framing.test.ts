import { describe, expect, it } from "vitest";
import { defaultPlan } from "@/lib/scene/defaultPlan";
import { HERO_DIRECTION, heroFraming, type Framing } from "./framing";
import { shotPathPoint } from "./cameraPath";

const FOV = 35;
const ASPECT = 16 / 9;
const car = { radius: 2.25, height: 1.4 };
const product = { radius: 0.13, height: 0.08 };

const direction = (f: Framing) => ({
  x: (f.position.x - f.target.x) / f.distance,
  y: (f.position.y - f.target.y) / f.distance,
  z: (f.position.z - f.target.z) / f.distance,
});

/** Fraction of the half-frame (vertical or horizontal, whichever is larger) a point projects to. */
function frameShare(p: { x: number; y: number; z: number }, f: Framing) {
  const tanV = Math.tan((FOV * Math.PI) / 360);
  const dir = direction(f);
  const q = { x: p.x - f.target.x, y: p.y - f.target.y, z: p.z - f.target.z };
  const along = q.x * dir.x + q.y * dir.y + q.z * dir.z;
  const depth = f.distance - along;
  const fwd = { x: -dir.x, y: -dir.y, z: -dir.z };
  const rl = Math.hypot(fwd.z, fwd.x);
  const right = { x: -fwd.z / rl, y: 0, z: fwd.x / rl };
  const up = { x: right.y * fwd.z - right.z * fwd.y, y: right.z * fwd.x - right.x * fwd.z, z: right.x * fwd.y - right.y * fwd.x };
  const x = Math.abs(q.x * right.x + q.y * right.y + q.z * right.z) / (depth * tanV * ASPECT);
  const y = Math.abs(q.x * up.x + q.y * up.y + q.z * up.z) / (depth * tanV);
  return Math.max(x, y);
}

describe("heroFraming", () => {
  it("aims at the subject centre from the hero direction", () => {
    const f = heroFraming(car, null, FOV, ASPECT);
    expect(f.target).toEqual({ x: 0, y: 0.7, z: 0 });
    const d = direction(f);
    expect(d.x).toBeCloseTo(HERO_DIRECTION.x);
    expect(d.y).toBeCloseTo(HERO_DIRECTION.y);
    expect(d.z).toBeCloseTo(HERO_DIRECTION.z);
  });
  it("backs off to include the camera path, keeping it inside the frame", () => {
    const plan = defaultPlan("car");
    const alone = heroFraming(car, null, FOV, ASPECT);
    const withPath = heroFraming(car, plan, FOV, ASPECT);
    expect(withPath.distance).toBeGreaterThan(alone.distance);
    for (let i = 0; i <= 20; i++) {
      const p = shotPathPoint(plan, plan.shots[0], i / 20, car);
      expect(frameShare(p, withPath)).toBeLessThanOrEqual(0.93);
    }
  });
  it("frames the model alone when the path is hidden, even with a plan", () => {
    const plan = defaultPlan("car");
    const hidden = heroFraming(car, plan, FOV, ASPECT, { showPath: false });
    expect(hidden).toEqual(heroFraming(car, null, FOV, ASPECT));
    expect(hidden.distance).toBeLessThan(heroFraming(car, plan, FOV, ASPECT).distance);
    expect(hidden.modelHeightFraction).toBeGreaterThan(0.4);
  });
  it("keeps the model readable next to its orbit path", () => {
    expect(heroFraming(car, null, FOV, ASPECT).modelHeightFraction).toBeGreaterThan(0.4);
    // A full 50 mm orbit is ~4x the car's width, so the car gives up size to keep the whole ring in frame.
    expect(heroFraming(car, defaultPlan("car"), FOV, ASPECT).modelHeightFraction).toBeGreaterThan(0.2);
  });
  it("looks down on a path that runs above a small subject instead of seeing it edge-on", () => {
    const plan = defaultPlan("product");
    const f = heroFraming(product, plan, FOV, ASPECT);
    expect(f.position.y).toBeGreaterThan(plan.camera.heightM + 0.1);
    expect(direction(f).y).toBeGreaterThan(HERO_DIRECTION.y);
    expect(f.distance).toBeLessThan(5);
    expect(f.distance).toBeGreaterThan(0.5);
    for (let i = 0; i <= 20; i++) expect(frameShare(shotPathPoint(plan, plan.shots[0], i / 20, product), f)).toBeLessThanOrEqual(0.93);
  });
});
