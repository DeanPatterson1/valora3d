import { create } from "zustand";
import { services, type AuthProvider, type ProfilePatch, type ServiceError } from "@/lib/services";
import type { Result } from "@/lib/services";
import type { User } from "@/lib/schema";

type AuthState = {
  user: User | null;
  /** True once `refresh` has resolved at least once. */
  loaded: boolean;
  error: ServiceError | null;
  refresh: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<boolean>;
  signUp: (email: string, password: string, name: string, turnstileToken?: string) => Promise<boolean>;
  signInWith: (provider: AuthProvider) => Promise<boolean>;
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

  return {
    user: null,
    loaded: false,
    error: null,
    refresh: async () => {
      const r = await services.auth.current();
      set(r.ok ? { user: r.value, loaded: true, error: null } : { loaded: true, error: r.error });
    },
    signIn: async (email, password) => apply(await services.auth.signIn(email, password)),
    signUp: async (email, password, name, token) => apply(await services.auth.signUp(email, password, name, token)),
    signInWith: async (provider) => apply(await services.auth.signInWith(provider)),
    guest: async () => apply(await services.auth.continueAsGuest()),
    signOut: async () => {
      const r = await services.auth.signOut();
      set(r.ok ? { user: null, error: null } : { error: r.error });
    },
    updateProfile: async (patch) => apply(await services.auth.updateProfile(patch)),
  };
});
