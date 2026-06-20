// Description: Auth context — UserContext provider, useUser hook, session state from /api/me
// ─────────────────────────────────────────────────────────────────────────────
// PATTERN: The JWT is HttpOnly — JS cannot decode it to read user fields.
// AuthProvider fetches /api/me (which reads the cookie server-side) on mount
// to populate the client-side user state. One provider at the root layout;
// every component reads it via useUser().
// ─────────────────────────────────────────────────────────────────────────────
// File location: src/context/auth-context.tsx
// ─────────────────────────────────────────────────────────────────────────────

"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

export type UserPayload = {
  id: number;
  email: string;
  role: "admin" | "viewer";
};

type AuthState =
  | { status: "loading" }
  | { status: "authenticated"; user: UserPayload }
  | { status: "unauthenticated" };

// ── Context ───────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthState>({ status: "loading" });

// ── Provider ──────────────────────────────────────────────────────────────────
// Wrap the root layout with <AuthProvider> — not individual pages.

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    // /api/me is a Next.js Route Handler that reads the HttpOnly cookie
    // server-side and returns the decoded user payload (or 401)
    fetch("/api/me", { credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error("unauthenticated");
        return r.json() as Promise<UserPayload>;
      })
      .then((user) => setState({ status: "authenticated", user }))
      .catch(() => setState({ status: "unauthenticated" }));
  }, []);

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useUser(): AuthState {
  return useContext(AuthContext);
}

// Convenience accessor — throws if called outside AuthProvider
export function useRequiredUser(): UserPayload {
  const state = useContext(AuthContext);
  if (state.status !== "authenticated") {
    throw new Error("useRequiredUser called outside an authenticated session");
  }
  return state.user;
}

// ── Example: consuming the context ───────────────────────────────────────────

export function UserMenu() {
  const auth = useUser();

  if (auth.status === "loading") return <span>Loading…</span>;
  if (auth.status === "unauthenticated") return null;

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm">{auth.user.email}</span>
      <span className="rounded bg-muted px-2 py-0.5 text-xs">{auth.user.role}</span>
    </div>
  );
}

// ── /api/me route handler (app/api/me/route.ts) ───────────────────────────────
// The server-side counterpart that reads the HttpOnly cookie and returns user info.
//
// import { cookies } from "next/headers";
// import { NextResponse } from "next/server";
//
// export async function GET() {
//   const cookieStore = await cookies();
//   const token = cookieStore.get("x-access-token")?.value;
//   if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
//
//   try {
//     const payload = JSON.parse(atob(token.split(".")[1])) as UserPayload;
//     // ponytail: no signature verification here — middleware already checked expiry;
//     //           add full jwt.verify() if this endpoint is exposed to untrusted callers
//     return NextResponse.json(payload);
//   } catch {
//     return NextResponse.json({ error: "Invalid token" }, { status: 401 });
//   }
// }

// ─────────────────────────────────────────────────────────────────────────────
// ANTI-PATTERNS:
//
// 1. Decoding the JWT in the client to get user fields:
//
//   const token = document.cookie.match(/x-access-token=([^;]+)/)?.[1];
//   const user = JSON.parse(atob(token.split(".")[1]));   // ← requires non-HttpOnly cookie
//   → HttpOnly cookies cannot be read by JS. Use /api/me to get user data.
//
// 2. Storing user state in localStorage:
//
//   localStorage.setItem("user", JSON.stringify(user));  // ← persists across sessions,
//                                                        //   accessible to XSS attacks
//   → Use React context (in-memory). Re-fetch from /api/me on page load.
//
// 3. One AuthProvider per page instead of at the root layout:
//
//   // app/(private)/admin/page.tsx
//   export default function Page() {
//     return <AuthProvider><AdminContent /></AuthProvider>;  // ← re-fetches on every nav
//   }
//   → Mount AuthProvider once in app/layout.tsx. State persists across client navigations.
// ─────────────────────────────────────────────────────────────────────────────
