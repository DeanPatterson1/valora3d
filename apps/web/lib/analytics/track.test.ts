import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _forceAnalytics, _queued, _resetTracking, analyticsEnabled, flush, sessionId, track } from "./track";

beforeEach(() => {
  _resetTracking();
  _forceAnalytics(true);
  window.sessionStorage.clear();
  vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));
});
afterEach(() => {
  _forceAnalytics(null);
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("browser tracking", () => {
  it("is off in tests unless forced", () => {
    _forceAnalytics(null);
    expect(analyticsEnabled()).toBe(false);
    track("landing_view");
    expect(_queued()).toHaveLength(0);
  });

  it("keeps one random session id per tab in sessionStorage, never a cookie", () => {
    const id = sessionId();
    expect(id).toMatch(/^[A-Za-z0-9_-]{16,64}$/);
    expect(sessionId()).toBe(id);
    expect(window.sessionStorage.getItem("v3d_sid")).toBe(id);
    expect(document.cookie).not.toContain(id);
  });

  it("batches events with the page's route template and sends them together", async () => {
    vi.useFakeTimers();
    window.history.pushState({}, "", "/projects/3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f?x=1");
    track("cta_click", { cta: "signup:/" });
    track("help_search", { q_len: 4 });
    expect(fetch).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(2100);
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("/api/events");
    const body = JSON.parse(String(init?.body));
    expect(body.session_id).toBe(sessionId());
    expect(body.events).toEqual([
      { event: "cta_click", props: { cta: "signup:/" }, path: "/projects/[id]" },
      { event: "help_search", props: { q_len: 4 }, path: "/projects/[id]" },
    ]);
    window.history.pushState({}, "", "/");
  });

  it("uses sendBeacon (text/plain, no preflight) when the page is going away", () => {
    const beacon = vi.fn(() => true);
    vi.stubGlobal("navigator", Object.assign(Object.create(navigator), { sendBeacon: beacon }));
    track("landing_view");
    flush(true);
    expect(beacon).toHaveBeenCalledTimes(1);
    const [, blob] = beacon.mock.calls[0] as unknown as [string, Blob];
    expect(blob.type).toBe("text/plain;charset=utf-8");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("caps events per page load", () => {
    for (let i = 0; i < 150; i++) track("landing_view");
    flush();
    const sent = vi.mocked(fetch).mock.calls.reduce((n, [, init]) => n + JSON.parse(String(init?.body)).events.length, 0);
    expect(sent).toBe(100);
  });
});
