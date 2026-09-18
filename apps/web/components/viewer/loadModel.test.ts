import { describe, it, expect } from "vitest";
import { validateFile } from "./loadModel";
import { MAX_UPLOAD_BYTES } from "@/lib/pricing";

const f = (name: string, size = 10) => new File([new Uint8Array(size)], name);

describe("validateFile", () => {
  it("accepts supported formats", () => {
    expect(validateFile(f("a.glb"))).toEqual({ ok: true, value: "glb" });
    expect(validateFile(f("a.FBX"))).toEqual({ ok: true, value: "fbx" });
  });
  it("rejects unsupported", () => {
    expect(validateFile(f("a.stl")).ok).toBe(false);
  });
  it("rejects oversize", () => {
    const big = { name: "a.glb", size: MAX_UPLOAD_BYTES + 1 } as File;
    const r = validateFile(big);
    expect(!r.ok && r.error.code).toBe("too_large");
  });
});
