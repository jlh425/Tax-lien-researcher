import { create } from "zustand";

const TOKEN_KEY = "aloha_token";

interface AuthState {
  token: string | null;
  userId: string | null;
  tier: string | null;
  setAuth: (token: string, userId: string, tier: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem(TOKEN_KEY),
  userId: null,
  tier: null,

  setAuth: (token, userId, tier) => {
    localStorage.setItem(TOKEN_KEY, token);
    set({ token, userId, tier });
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    set({ token: null, userId: null, tier: null });
  },
}));
