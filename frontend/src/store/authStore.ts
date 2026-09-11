import { create } from "zustand";
import { login, logout } from "../services/keycloak";

interface AuthState {
  initialised: boolean;
  authenticated: boolean;
  roles: string[];
  init: () => Promise<void>;
  signIn: () => Promise<void>;
  signOut: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  initialised: false,
  authenticated: false,
  roles: [],

  init: async () => {
    try {
      await login();
      set({ authenticated: true, initialised: true });
    } catch {
      set({ authenticated: false, initialised: true });
    }
  },

  signIn: async () => {
    await login();
    set({ authenticated: true, initialised: true });
  },

  signOut: () => {
    logout();
    set({ authenticated: false });
  },
}));