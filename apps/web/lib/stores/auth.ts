import { create } from "zustand";
import type { AuthProvider, ProfilePatch, Result, ServiceError } from "@/lib/services";
import { loadServices } from "@/lib/services/backend";
import type { User } from "@/lib/schema";

type AuthState = {
  user: User | null;
  /** True once `refresh` has resolved at least once. */
  loaded: boolean;
  error: ServiceError | null;
  refresh: () => Promise<void>;
  signIn: (email: string, password: string, captchaToken?: string) => Promise<boolean>;
  signUp: (email: string, password: string, name: string, captchaToken?: string, next?: string) => Promise<boolean>;
  signInWith: (provider: AuthProvider, next?: string) => Promise<boolean>;
  guest: () => Promise<boolean>;
  signOut: () => Promise<void>;
  updateProfile: (patch: ProfilePatch) => Promise<boolean>;
};

export const useAuthStore = create<AuthState>((set) => {
  /** Applies a sign-in result to the store; returns whether it succeeded. */
  const apply = (r: Result<User>): boolean => {
    if (!r.ok) {
      set({ error: r.error });
      return false;
    }
    set({ user: r.value, loaded: true, error: null });
    return true;
  };

  // Every action is async, so the implementations (supabase-js, zod) load on first use instead of
  // shipping with every page that merely shows a sign-in form or a plan card.
  const auth = () => loadServices().then((s) => s.auth);

  return {
    user: null,
    loaded: false,
    error: null,
    refresh: async () => {
      const r = await (await auth()).current();
      set(r.ok ? { user: r.value, loaded: true, error: null } : { loaded: true, error: r.error });
    },
    signIn: async (email, password, token) => apply(await (await auth()).signIn(email, password, token)),
    signUp: async (email, password, name, token, next) => apply(await (await auth()).signUp(email, password, name, token, next)),
    signInWith: async (provider, next) => apply(await (await auth()).signInWith(provider, next)),
    guest: async () => apply(await (await auth()).continueAsGuest()),
    signOut: async () => {
      const r = await (await auth()).signOut();
      set(r.ok ? { user: null, error: null } : { error: r.error });
    },
    updateProfile: async (patch) => apply(await (await auth()).updateProfile(patch)),
  };
});
