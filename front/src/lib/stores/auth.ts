import { writable } from "svelte/store";

export type AuthUser = {
  id: number;
  email: string;
};

export type AuthState = {
  token: string | null;
  user: AuthUser | null;
};

const stored =
  typeof localStorage !== "undefined"
    ? localStorage.getItem("auth")
    : null;

const initial: AuthState = stored
  ? JSON.parse(stored)
  : { token: null, user: null };

export const auth = writable<AuthState>(initial);

auth.subscribe((value) => {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem("auth", JSON.stringify(value));
});

export function setAuth(token: string, user: AuthUser) {
  auth.set({ token, user });
}

export function clearAuth() {
  auth.set({ token: null, user: null });
}

