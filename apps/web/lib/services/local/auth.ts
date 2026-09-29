import { z } from "zod";
import { clear as clearIdb } from "idb-keyval";
import { DEFAULT_PREFS, UserSchema, type User } from "@/lib/schema";
import { fail, failFrom, ok, type Result } from "../result";
import type { AuthFeatures, AuthProvider, AuthService, ProfilePatch } from "../types";
import { KEYS, KEY_PREFIX, newId, readJson, writeJson } from "./storage";
import { GUEST_ID, LOCAL_AUTH_FEATURES, MIN_PASSWORD, isValidEmail, normaliseEmail } from "../backend";

export { GUEST_ID, MIN_PASSWORD, isValidEmail, normaliseEmail };

/**
 * Prototype auth, entirely in this browser.
 *
 * PASSWORDS ARE NOT STORED OR CHECKED. Sign-up and sign-in accept any password of
 * MIN_PASSWORD characters or more (lib/services/backend.ts); sign-in only checks that the email has an account.
 * There is no server, so nothing here is a security boundary. The real service
 * replaces this class behind the same `AuthService` interface.
 */
const Users = z.array(UserSchema);
const Session = z.object({ userId: z.string() }).nullable();


/** Demo identities the provider buttons sign in as. Same account every time. */
const PROVIDER_USERS: Record<AuthProvider, { email: string; name: string }> = {
  google: { email: "you@gmail.com", name: "You" },
  apple: { email: "you@icloud.com", name: "You" },
};

function nameFromEmail(email: string): string {
  const local = email.split("@")[0] ?? "";
  const word = local.split(/[._-]/)[0] ?? "";
  return word ? word.charAt(0).toUpperCase() + word.slice(1) : "You";
}

export class LocalAuthService implements AuthService {
  readonly features: AuthFeatures = LOCAL_AUTH_FEATURES;

  private readUsers(): User[] {
    return readJson(KEYS.users, Users, []).value;
  }

  private writeUsers(users: User[]): Result<void> {
    return writeJson(KEYS.users, users);
  }

  private findByEmail(email: string): User | undefined {
    const e = normaliseEmail(email);
    return this.readUsers().find((u) => u.email === e);
  }

  private makeUser(fields: { id?: string; email: string; name: string }): User {
    return {
      id: fields.id ?? newId(),
      email: normaliseEmail(fields.email),
      name: fields.name.trim() || nameFromEmail(fields.email),
      avatarSeed: newId(),
      plan: "free",
      createdAt: Date.now(),
      prefs: DEFAULT_PREFS,
    };
  }

  /** Persists a new user and opens a session for them. */
  private register(user: User): Result<User> {
    const w = this.writeUsers([...this.readUsers(), user]);
    if (!w.ok) return failFrom(w.error);
    return this.openSession(user);
  }

  private openSession(user: User): Result<User> {
    const w = writeJson(KEYS.session, { userId: user.id });
    return w.ok ? ok(user) : failFrom(w.error);
  }

  async current(): Promise<Result<User | null>> {
    const { value: session } = readJson(KEYS.session, Session, null);
    if (!session) return ok(null);
    const user = this.readUsers().find((u) => u.id === session.userId);
    if (!user) {
      // A session without an account (data was cleared) is treated as signed out.
      writeJson(KEYS.session, null);
      return ok(null);
    }
    return ok(user);
  }

  async signIn(email: string, password: string): Promise<Result<User>> {
    if (!isValidEmail(email)) return fail("invalid_email", "Enter a valid email address.");
    if (password.length < MIN_PASSWORD) return fail("invalid_password", `Password must be at least ${MIN_PASSWORD} characters.`);
    const user = this.findByEmail(email);
    if (!user) return fail("not_found", "No account with that email", ["Check the spelling, or sign up."]);
    // Prototype: the password is not checked (see the class comment).
    return this.openSession(user);
  }

  async signUp(email: string, password: string, name: string): Promise<Result<User>> {
    if (!isValidEmail(email)) return fail("invalid_email", "Enter a valid email address.");
    if (password.length < MIN_PASSWORD) return fail("invalid_password", `Password must be at least ${MIN_PASSWORD} characters.`);
    if (!name.trim()) return fail("invalid_name", "Enter your name.");
    if (this.findByEmail(email)) return fail("exists", "An account with that email already exists", ["Log in instead."]);
    return this.register(this.makeUser({ email, name }));
  }

  async signInWith(provider: AuthProvider): Promise<Result<User>> {
    const demo = PROVIDER_USERS[provider];
    const existing = this.findByEmail(demo.email);
    if (existing) return this.openSession(existing);
    return this.register(this.makeUser({ id: `demo-${provider}`, ...demo }));
  }

  async continueAsGuest(): Promise<Result<User>> {
    const existing = this.readUsers().find((u) => u.id === GUEST_ID);
    if (existing) return this.openSession(existing);
    return this.register(this.makeUser({ id: GUEST_ID, email: "guest@local", name: "Guest" }));
  }

  async requestPasswordReset(_email: string): Promise<Result<void>> {
    return fail("unsupported", "Password reset needs the real account service.");
  }

  async updatePassword(_password: string): Promise<Result<void>> {
    return fail("unsupported", "Passwords are not stored in this prototype.");
  }

  async signOut(): Promise<Result<void>> {
    return writeJson(KEYS.session, null);
  }

  async updateProfile(patch: ProfilePatch): Promise<Result<User>> {
    const cur = await this.current();
    if (!cur.ok) return failFrom(cur.error);
    if (!cur.value) return fail("signed_out", "You are signed out.");
    const name = patch.name?.trim();
    if (patch.name !== undefined && !name) return fail("invalid_name", "Enter your name.");
    const next: User = {
      ...cur.value,
      ...(name ? { name } : {}),
      ...(patch.emailRenderReady !== undefined ? { emailRenderReady: patch.emailRenderReady } : {}),
      ...(patch.emailProductTips !== undefined ? { emailProductTips: patch.emailProductTips } : {}),
      prefs: { ...cur.value.prefs, ...(patch.prefs ?? {}) },
    };
    const w = this.writeUsers(this.readUsers().map((u) => (u.id === next.id ? next : u)));
    return w.ok ? ok(next) : failFrom(w.error);
  }

  async deleteAllData(): Promise<Result<void>> {
    try {
      const keys: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k?.startsWith(KEY_PREFIX)) keys.push(k);
      }
      keys.forEach((k) => localStorage.removeItem(k));
      await clearIdb();
      return ok(undefined);
    } catch {
      return fail("storage_unavailable", "Browser storage is unavailable. Use a normal, non-private browser window.");
    }
  }
}
