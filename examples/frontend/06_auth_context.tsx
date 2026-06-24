// Description: Auth context — UserProvider, useUser hook, session state from /api/me
// ─────────────────────────────────────────────────────────────────────────────
// PATTERN: The session cookie is HttpOnly and encrypted by Auth.js — JS cannot
// read it directly. UserProvider fetches /api/me (a Next.js Route Handler that
// reads the server-side session) on mount to populate client-side user state.
// One provider at the root layout; every component reads it via useUser().
// ─────────────────────────────────────────────────────────────────────────────
// File location: src/providers/user-provider.tsx
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

export type User = {
  id: string;           // stable identifier (oid from Entra, sub from other IdPs)
  name: string;
  email: string;
  image?: string;
};

type AuthState =
  | { status: "loading" }
  | { status: "authenticated"; user: User }
  | { status: "unauthenticated" };

// ── Context ───────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthState>({ status: "loading" });

// ── Provider ──────────────────────────────────────────────────────────────────
// Wrap the root layout with <UserProvider> — not individual pages.

export function UserProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    // /api/me is a Next.js Route Handler that calls auth() server-side and
    // returns the public user fields — never raw tokens.
    fetch("/api/me", { credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error("unauthenticated");
        return r.json() as Promise<User>;
      })
      .then((user) => setState({ status: "authenticated", user }))
      .catch(() => setState({ status: "unauthenticated" }));
  }, []);

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useUser(): AuthState {
  return useContext(AuthContext);
}

// Throws when called outside an authenticated session — use in protected pages.
export function useRequiredUser(): User {
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
      {auth.user.image && (
        <img src={auth.user.image} alt="" className="h-6 w-6 rounded-full" />
      )}
      <span className="text-sm">{auth.user.name}</span>
    </div>
  );
}

// ── /api/me route handler (src/app/api/me/route.ts) ──────────────────────────
// Reads the server-side Auth.js session and returns safe user fields.
// The session cookie and any access tokens never leave the server.
//
// import { auth } from "@/auth";
// import { NextResponse } from "next/server";
//
// export async function GET() {
//   const session = await auth();
//   if (!session?.user) {
//     return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
//   }
//   return NextResponse.json({
//     id: session.userId,        // populated in the session callback in auth.ts
//     name: session.user.name,
//     email: session.user.email,
//     image: session.user.image,
//   });
// }

// ─────────────────────────────────────────────────────────────────────────────
// ANTI-PATTERNS:
//
// 1. Forwarding the raw IdP access token to FastAPI:
//
//   headers["Authorization"] = `Bearer ${session.idpAccessToken}`;
//   → The token's `aud` is the BFF app, not FastAPI — validation fails.
//   → Use the OBO flow (see src/lib/obo.ts) to get an API-scoped token.
//
// 2. Trusting a plain header for user identity in FastAPI:
//
//   @app.get("/items")
//   def list_items(user_id: str = Header(...)):  # ← anyone can forge this
//       ...
//   → FastAPI must validate a signed Bearer JWT on every request.
//
// 3. Storing the session state in localStorage:
//
//   localStorage.setItem("user", JSON.stringify(user));  // ← XSS-readable
//   → Keep state in React context (in-memory). Re-fetch from /api/me on load.
//
// 4. Mounting UserProvider per-page instead of at the root layout:
//
//   // app/(private)/admin/page.tsx
//   export default function Page() {
//     return <UserProvider><AdminContent /></UserProvider>;  // ← re-fetches on every nav
//   }
//   → Mount once in app/layout.tsx so state persists across client navigations.
// ─────────────────────────────────────────────────────────────────────────────
