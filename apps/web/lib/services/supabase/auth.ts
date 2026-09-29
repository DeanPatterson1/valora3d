import type { SupabaseClient } from "@supabase/supabase-js";
import { clear as clearIdb } from "idb-keyval";
import { markEmailFlowStarted } from "@/lib/auth/emailFlow";
import { DEFAULT_NEXT, authCallbackUrl } from "@/lib/nav/next";
import type { User } from "@/lib/schema";
import { MIN_PASSWORD, SUPABASE_AUTH_FEATURES, isValidEmail, normaliseEmail } from "../backend";
import { KEY_PREFIX } from "../local/storage";
import { apiFetch, supabaseErrorToResult } from "../http";
import { fail, failFrom, ok, type Result } from "../result";
import type { AuthFeatures, AuthProvider, AuthService, ProfilePatch } from "../types";
import { profileToUser, type ProfileRow } from "./rows";

type Origin = () => string;
const browserOrigin: Origin = () => window.location.origin;

/** Supabase Auth: email + password with verification, Google OAuth, reset, server-side deletion. */
export class SupabaseAuthService implements AuthService {
  readonly features: AuthFeatures = SUPABASE_AUTH_FEATURES;

  constructor(
    private readonly db: () => SupabaseClient,
    private readonly origin: Origin = browserOrigin,
  ) {}

  private async loadProfile(userId: string): Promise<Result<User>> {
    const { data, error } = await this.db().from("profiles").select("*").eq("id", userId).maybeSingle<ProfileRow>();
    if (error) return supabaseErrorToResult(error);
    if (!data) return fail("not_found", "Your profile is still being created. Reload in a moment.");
    return ok(profileToUser(data));
  }

  async current(): Promise<Result<User | null>> {
    const { data, error } = await this.db().auth.getUser();
    if (error || !data.user) return ok(null);
    return this.loadProfile(data.user.id);
  }

  async signIn(email: string, password: string, captchaToken?: string): Promise<Result<User>> {
    if (!isValidEmail(email)) return fail("invalid_email", "Enter a valid email address.");
    if (password.length < MIN_PASSWORD) return fail("invalid_password", `Password must be at least ${MIN_PASSWORD} characters.`);
    const { data, error } = await this.db().auth.signInWithPassword({
      email: normaliseEmail(email),
      password,
      ...(captchaToken ? { options: { captchaToken } } : {}),
    });
    if (error) {
      if (isCaptchaError(error)) return captchaFailed();
      if (error.code === "email_not_confirmed") {
        return fail("email_not_confirmed", "Confirm your email first. We sent you a link when you signed up.");
      }
      if (error.status === 400) return fail("invalid_credentials", "That email and password don't match.", ["Check them, or reset your password."]);
      return supabaseErrorToResult(error);
    }
    return this.loadProfile(data.user.id);
  }

  async signUp(email: string, password: string, name: string, captchaToken?: string, next: string = DEFAULT_NEXT): Promise<Result<User>> {
    if (!isValidEmail(email)) return fail("invalid_email", "Enter a valid email address.");
    if (password.length < MIN_PASSWORD) return fail("invalid_password", `Password must be at least ${MIN_PASSWORD} characters.`);
    if (!name.trim()) return fail("invalid_name", "Enter your name.");
    // The confirmation link is expected in this browser (login-CSRF defence, lib/auth/emailLink.ts).
    markEmailFlowStarted();
    const { data, error } = await this.db().auth.signUp({
      email: normaliseEmail(email),
      password,
      options: {
        data: { name: name.trim() },
        // Also the confirmation email's `{{ .RedirectTo }}`: the link returns to `next` (lib/email/authTemplates.ts).
        emailRedirectTo: authCallbackUrl(this.origin(), next),
        ...(captchaToken ? { captchaToken } : {}),
      },
    });
    if (error) {
      if (isCaptchaError(error)) return captchaFailed();
      if (error.code === "user_already_exists") return fail("exists", "An account with that email already exists", ["Log in instead."]);
      if (error.code === "weak_password") return fail("invalid_password", error.message);
      return supabaseErrorToResult(error);
    }
    // With confirmations on (the production setting) there is no session until the link is used.
    if (!data.session || !data.user) {
      return fail("verification_sent", `We sent a confirmation link to ${normaliseEmail(email)}. Open it to finish signing up.`);
    }
    return this.loadProfile(data.user.id);
  }

  async signInWith(provider: AuthProvider, next: string = DEFAULT_NEXT): Promise<Result<User>> {
    if (!this.features.providers.includes(provider)) return fail("unsupported", "That sign-in option is not available.");
    const { error } = await this.db().auth.signInWithOAuth({
      provider,
      options: { redirectTo: authCallbackUrl(this.origin(), next) },
    });
    if (error) return supabaseErrorToResult(error);
    // The browser is navigating to the provider; keep the button busy until it does.
    return new Promise<Result<User>>(() => {});
  }

  async continueAsGuest(): Promise<Result<User>> {
    return fail("unsupported", "Create an account to continue.");
  }

  async requestPasswordReset(email: string, captchaToken?: string): Promise<Result<void>> {
    if (!isValidEmail(email)) return fail("invalid_email", "Enter a valid email address.");
    markEmailFlowStarted();
    const { error } = await this.db().auth.resetPasswordForEmail(normaliseEmail(email), {
      redirectTo: `${this.origin()}/auth/callback?next=/reset-password`,
      ...(captchaToken ? { captchaToken } : {}),
    });
    if (error && isCaptchaError(error)) return captchaFailed();
    if (error && (error.status === 429 || !error.status || error.status >= 500)) return supabaseErrorToResult(error);
    // Same answer whether or not the address has an account.
    return ok(undefined);
  }

  async updatePassword(password: string): Promise<Result<void>> {
    if (password.length < MIN_PASSWORD) return fail("invalid_password", `Password must be at least ${MIN_PASSWORD} characters.`);
    const { error } = await this.db().auth.updateUser({ password });
    if (error) {
      if (error.code === "same_password") return fail("invalid_password", "Choose a password you haven't used here before.");
      if (error.code === "weak_password") return fail("invalid_password", error.message);
      if (error.status === 401 || error.code === "session_not_found") return fail("unauthorized", "This reset link has expired. Request a new one.");
      return supabaseErrorToResult(error);
    }
    return ok(undefined);
  }

  async signOut(): Promise<Result<void>> {
    const { error } = await this.db().auth.signOut();
    await clearLocalCaches();
    return error ? supabaseErrorToResult(error) : ok(undefined);
  }

  async updateProfile(patch: ProfilePatch): Promise<Result<User>> {
    const cur = await this.current();
    if (!cur.ok) return failFrom(cur.error);
    if (!cur.value) return fail("signed_out", "You are signed out.");
    const name = patch.name?.trim();
    if (patch.name !== undefined && !name) return fail("invalid_name", "Enter your name.");
    const update: Partial<ProfileRow> = {};
    if (name) update.name = name;
    if (patch.prefs) update.prefs = { ...cur.value.prefs, ...patch.prefs };
    if (patch.emailRenderReady !== undefined) update.email_render_ready = patch.emailRenderReady;
    if (patch.emailProductTips !== undefined) update.email_product_tips = patch.emailProductTips;
    const { data, error } = await this.db().from("profiles").update(update).eq("id", cur.value.id).select().single<ProfileRow>();
    if (error) return supabaseErrorToResult(error);
    return ok({ ...cur.value, ...profileToUser(data) });
  }

  async deleteAllData(): Promise<Result<void>> {
    const r = await apiFetch<void>("/api/account/delete", { method: "POST", body: "{}" });
    if (!r.ok) return r;
    await this.db().auth.signOut().catch(() => undefined);
    await clearLocalCaches();
    return ok(undefined);
  }
}

/** Model and thumbnail caches in this browser; the account data itself lives on the server. */
async function clearLocalCaches(): Promise<void> {
  try {
    await clearIdb();
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k?.startsWith(KEY_PREFIX)) keys.push(k);
    }
    keys.forEach((k) => localStorage.removeItem(k));
  } catch {
    // Caches are best-effort.
  }
}

/**
 * Supabase Auth verifies the Turnstile token itself when CAPTCHA protection is on (dashboard:
 * Authentication -> Attack Protection), so a direct API call without a solved challenge is refused.
 */
function isCaptchaError(error: { code?: string; message: string }): boolean {
  return error.code === "captcha_failed" || /captcha/i.test(error.message);
}

function captchaFailed<T = never>(): Result<T> {
  return fail("verification_failed", "Complete the security check and try again.");
}
