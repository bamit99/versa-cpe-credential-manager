import { create } from "zustand";
import { login, logout, getRoles } from "../services/keycloak";

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
      set({ authenticated: true, initialised: true, roles: getRoles() });
    } catch {
      set({ authenticated: false, initialised: true });
    }
  },

  signIn: async () => {
    await login();
    set({ authenticated: true, initialised: true, roles: getRoles() });
  },

  signOut: () => {
    logout();
    set({ authenticated: false });
  },
}));