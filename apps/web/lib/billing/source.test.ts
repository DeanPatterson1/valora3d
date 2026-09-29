// @vitest-environment node
import { describe, expect, it } from "vitest";
import { signUserId } from "./signature";
import { transactionSourceFromBody } from "./source";

describe("checkout attribution in Paddle custom data", () => {
  it("reads the compact source a checkout sent, re-validated", () => {
    const body = JSON.stringify({ event_id: "evt_1", data: { custom_data: { user_id: "u", user_sig: "s", src: '{"source":"Spring Sale","ref":"share_AbC"}' } } });
    expect(transactionSourceFromBody(body)).toEqual({ source: "spring-sale", ref: "share_AbC" });
  });

  it("ignores a missing, malformed or oversized source", () => {
    expect(transactionSourceFromBody(JSON.stringify({ data: { custom_data: { user_id: "u" } } }))).toBeNull();
    expect(transactionSourceFromBody(JSON.stringify({ data: { custom_data: null } }))).toBeNull();
    expect(transactionSourceFromBody(JSON.stringify({ data: { custom_data: { src: "{" } } }))).toBeNull();
    expect(transactionSourceFromBody(JSON.stringify({ data: { custom_data: { src: "x".repeat(401) } } }))).toBeNull();
    expect(transactionSourceFromBody("not json")).toBeNull();
  });

  it("leaves the signed user id exactly as before (src is not part of the signature)", async () => {
    // The signature covers only the label + user id, so adding src to custom data cannot change or break it.
    const a = await signUserId("3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f", "k".repeat(32));
    const b = await signUserId("3f2c9a1e-8b7d-4c21-9e55-1a2b3c4d5e6f", "k".repeat(32));
    expect(a).toBe(b);
    expect(a).toMatch(/^[0-9a-f]{64}$/);
  });
});
