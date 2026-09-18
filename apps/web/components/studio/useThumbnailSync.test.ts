// @vitest-environment jsdom
import { cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { useThumbnailSync } from "./useThumbnailSync";

type Args = { assetId: string | null; versions: number; labouring: boolean };

function mount(initial: Args) {
  return renderHook(({ assetId, versions, labouring }: Args) => useThumbnailSync(assetId, versions, labouring), { initialProps: initial });
}

describe("useThumbnailSync", () => {
  afterEach(cleanup);

  it("bumps once per appended version and never on re-renders or a model load", () => {
    const h = mount({ assetId: null, versions: 0, labouring: false });
    expect(h.result.current.captureKey).toBe(0);

    // The viewer captures the model load itself; no bump here.
    h.rerender({ assetId: "a1", versions: 0, labouring: false });
    h.rerender({ assetId: "a1", versions: 0, labouring: false });
    expect(h.result.current.captureKey).toBe(0);

    h.rerender({ assetId: "a1", versions: 1, labouring: false });
    expect(h.result.current.captureKey).toBe(1);
    h.rerender({ assetId: "a1", versions: 1, labouring: false });
    expect(h.result.current.captureKey).toBe(1);
    h.rerender({ assetId: "a1", versions: 2, labouring: false });
    expect(h.result.current.captureKey).toBe(2);
  });

  it("waits for labour to end and then bumps once, not once per toggle", () => {
    const h = mount({ assetId: "a1", versions: 1, labouring: false });
    h.rerender({ assetId: "a1", versions: 1, labouring: true });
    h.rerender({ assetId: "a1", versions: 2, labouring: true });
    expect(h.result.current.captureKey).toBe(0);
    h.rerender({ assetId: "a1", versions: 2, labouring: false });
    expect(h.result.current.captureKey).toBe(1);

    // A labour sequence with nothing appended (e.g. a rejected prompt) captures nothing.
    h.rerender({ assetId: "a1", versions: 2, labouring: true });
    h.rerender({ assetId: "a1", versions: 2, labouring: false });
    expect(h.result.current.captureKey).toBe(1);
  });

  it("does not bump when a project opens with history or when the count drops", () => {
    const h = mount({ assetId: "a1", versions: 3, labouring: false });
    expect(h.result.current.captureKey).toBe(0);
    h.rerender({ assetId: "a1", versions: 1, labouring: false });
    expect(h.result.current.captureKey).toBe(0);
    // Another project's model and history arriving together is a load, not an append.
    h.rerender({ assetId: "a2", versions: 4, labouring: false });
    expect(h.result.current.captureKey).toBe(0);
    h.rerender({ assetId: "a2", versions: 5, labouring: false });
    expect(h.result.current.captureKey).toBe(1);
  });
});
