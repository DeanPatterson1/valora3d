import { describe, it, expect } from "vitest";
import { ProjectSchema, deriveProjectState, CreditTransactionSchema, ScenePatchSchema } from "./index";

describe("schemas", () => {
  it("derives project state", () => {
    expect(deriveProjectState({ assetId: null, versionCount: 0 })).toBe("No model");
    expect(deriveProjectState({ assetId: "a", versionCount: 0 })).toBe("Model ready");
    expect(deriveProjectState({ assetId: "a", versionCount: 2 })).toBe("Scene ready");
  });
  it("validates a project", () => {
    expect(ProjectSchema.safeParse({ id: "p1", name: "Car", createdAt: 1, updatedAt: 1,
      assetId: null, analysis: null, selectedVersionId: null }).success).toBe(true);
  });
  it("validates a patch union", () => {
    expect(ScenePatchSchema.safeParse({ operation: "set_effect", effect: "rain", value: 0.5 }).success).toBe(true);
    expect(ScenePatchSchema.safeParse({ operation: "nope" }).success).toBe(false);
  });
  it("rejects a non-integer credit amount", () => {
    expect(CreditTransactionSchema.safeParse({ id: "t", amount: 1.5, reason: "prompt_edit",
      projectId: null, createdAt: 1 }).success).toBe(false);
  });
});
