import { describe, it, expect, beforeEach } from "vitest";
import { get, set } from "idb-keyval";
import { GUEST_ID, LocalAuthService, isValidEmail } from "./auth";
import { LocalCreditService } from "./credits";
import { KEYS } from "./storage";

const PW = "correct horse";

describe("LocalAuthService", () => {
  let auth: LocalAuthService;
  beforeEach(() => {
    localStorage.clear();
    auth = new LocalAuthService();
  });

  it("starts signed out", async () => {
    const r = await auth.current();
    expect(r.ok && r.value).toBeNull();
  });

  it("signs up, persists the session, and signs out", async () => {
    const r = await auth.signUp("Ada@Example.com", PW, "Ada");
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.value).toMatchObject({ email: "ada@example.com", name: "Ada", plan: "free" });
    expect(r.value.prefs.defaultOutput.resolution).toBe("1080p");
    expect(r.value.avatarSeed).toBeTruthy();

    const cur = await new LocalAuthService().current();
    expect(cur.ok && cur.value?.id).toBe(r.value.id);

    await auth.signOut();
    const after = await auth.current();
    expect(after.ok && after.value).toBeNull();
    // The account remains; only the session is gone.
    const again = await auth.signIn("ada@example.com", PW);
    expect(again.ok && again.value.id).toBe(r.value.id);
  });

  it("validates sign-up input", async () => {
    expect((await auth.signUp("nope", PW, "A")).ok).toBe(false);
    const short = await auth.signUp("a@b.co", "short", "A");
    expect(!short.ok && short.error.code).toBe("invalid_password");
    const noName = await auth.signUp("a@b.co", PW, "  ");
    expect(!noName.ok && noName.error.code).toBe("invalid_name");
    await auth.signUp("a@b.co", PW, "A");
    const dup = await auth.signUp("A@B.CO", PW, "A");
    expect(!dup.ok && dup.error.code).toBe("exists");
  });

  it("sign-in with an unknown email fails with not_found", async () => {
    const r = await auth.signIn("nobody@example.com", PW);
    expect(!r.ok && r.error.code).toBe("not_found");
    expect(!r.ok && r.error.message).toBe("No account with that email");
    const short = await auth.signIn("nobody@example.com", "abc");
    expect(!short.ok && short.error.code).toBe("invalid_password");
  });

  it("provider sign-in creates a deterministic demo user once", async () => {
    const a = await auth.signInWith("google");
    expect(a.ok && a.value.email).toBe("you@gmail.com");
    await auth.signOut();
    const b = await auth.signInWith("google");
    expect(b.ok && b.value.id).toBe(a.ok ? a.value.id : "");
    const apple = await auth.signInWith("apple");
    expect(apple.ok && apple.value.email).toBe("you@icloud.com");
    const users = JSON.parse(localStorage.getItem(KEYS.users)!) as unknown[];
    expect(users).toHaveLength(2);
  });

  it("guest is a fixed user named Guest", async () => {
    const r = await auth.continueAsGuest();
    expect(r.ok && r.value).toMatchObject({ id: GUEST_ID, name: "Guest" });
    const again = await auth.continueAsGuest();
    expect(again.ok && again.value.id).toBe(GUEST_ID);
  });

  it("updates name and prefs, refusing an empty name", async () => {
    await auth.signUp("a@b.co", PW, "A");
    const r = await auth.updateProfile({ name: " Ada Lovelace ", prefs: { defaultOutput: { fps: 60, durationS: 5, resolution: "4k", quality: "ultra" } } });
    expect(r.ok && r.value.name).toBe("Ada Lovelace");
    expect(r.ok && r.value.prefs.defaultOutput.fps).toBe(60);
    expect(r.ok && r.value.prefs.localAgent).toBe("not_connected");
    const cur = await auth.current();
    expect(cur.ok && cur.value?.name).toBe("Ada Lovelace");
    const bad = await auth.updateProfile({ name: "" });
    expect(!bad.ok && bad.error.code).toBe("invalid_name");
    await auth.signOut();
    const out = await auth.updateProfile({ name: "X" });
    expect(!out.ok && out.error.code).toBe("signed_out");
  });

  it("treats a session whose user is missing as signed out", async () => {
    localStorage.setItem(KEYS.session, JSON.stringify({ userId: "ghost" }));
    const r = await auth.current();
    expect(r.ok && r.value).toBeNull();
  });

  it("deleteAllData clears every rs.* key and IndexedDB, keeping other keys", async () => {
    await auth.signUp("a@b.co", PW, "A");
    await new LocalCreditService().balance();
    localStorage.setItem("other.key", "keep");
    await set("blob-1", "x");
    const r = await auth.deleteAllData();
    expect(r.ok).toBe(true);
    expect(localStorage.getItem(KEYS.users)).toBeNull();
    expect(localStorage.getItem(KEYS.session)).toBeNull();
    expect(localStorage.getItem(KEYS.ledger)).toBeNull();
    expect(localStorage.getItem("other.key")).toBe("keep");
    expect(await get("blob-1")).toBeUndefined();
    const cur = await auth.current();
    expect(cur.ok && cur.value).toBeNull();
  });
});

describe("isValidEmail", () => {
  it("accepts ordinary addresses and rejects the rest", () => {
    expect(isValidEmail("a@b.co")).toBe(true);
    expect(isValidEmail(" a@b.co ")).toBe(true);
    expect(isValidEmail("a@b")).toBe(false);
    expect(isValidEmail("ab.co")).toBe(false);
    expect(isValidEmail("")).toBe(false);
  });
});
