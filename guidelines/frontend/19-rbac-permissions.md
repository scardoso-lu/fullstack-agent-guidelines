---
model: opus
effort: high
---

# RBAC Permissions — Frontend Route Guards, Permission Hooks, and UI Visibility

Use when building any UI that needs to show or hide features based on the user's role or permissions, or when protecting Next.js routes from unauthorised access. The frontend is never a security boundary — the API enforces access. The frontend reflects what the user is allowed to see, using permissions fetched live from the API. AI agents and vibecoding tools almost always get this wrong in several distinct ways.

## The Anti-Patterns (What AI Always Generates)

### Hardcoded role strings scattered across components

```tsx
// ❌ WRONG — magic strings duplicated across every component
if (user.role === "admin") { ... }
if (user.role === "superuser" || user.role === "admin") { ... }
```

One rename of a role slug breaks every component individually.

### Reading roles or permissions from env vars

```tsx
// ❌ WRONG — roles configured in env vars on the frontend
const ADMIN_ROLES = process.env.NEXT_PUBLIC_ADMIN_ROLES?.split(",") ?? ["admin"];

if (ADMIN_ROLES.includes(user.role)) {
  return <AdminPanel />;
}
```

Changing which roles see the admin panel requires a code change and a redeploy. This also exposes your role structure publicly via `NEXT_PUBLIC_*`.

### Using frontend checks as security gates

```tsx
// ❌ WRONG — frontend check treated as the access control decision
export default function AdminPage() {
  const { user } = useAuth();
  if (user.role !== "admin") return <Redirect to="/" />;   // client-side only
  return <AdminDashboard />;
}
```

Any user can open DevTools, patch the response, and see the page. The server must enforce; the frontend reflects.

### Checking only role slugs, not permissions

```tsx
// ❌ WRONG — tightly coupled to role names; breaks when roles are reorganised
const canDelete = user.role === "admin" || user.role === "editor";
```

If an admin adds a new "senior_editor" role in the admin UI and grants it `articles:delete`, this component won't pick it up until a developer manually adds `|| user.role === "senior_editor"` and redeploys.

### Storing permissions in localStorage or a client cookie

```tsx
// ❌ WRONG — stale, forgeable, and bypassed with DevTools
const permissions = JSON.parse(localStorage.getItem("permissions") ?? "[]");
```

### Using a `isAdmin` boolean from the JWT

```tsx
// ❌ WRONG — doesn't reflect runtime permission changes; doesn't scale
const { isAdmin } = useJwt();
```

## The Correct Pattern

### 1 — Fetch the Full Permission List from `/me`

The JWT carries only the user id and role slug (see `backend/26-rbac-permissions`). The frontend fetches the current user's full permission list from a `/me` endpoint on load. This means permission changes made via the admin UI take effect for the user on their next page load — without a redeploy.

**`lib/api/me.ts`**
```ts
export type CurrentUser = {
  id: number;
  email: string;
  role: { slug: string; name: string };
  permissions: string[];   // slugs: ["articles:read", "articles:write", ...]
};

export async function fetchMe(): Promise<CurrentUser> {
  const res = await fetch("/api/me", { cache: "no-store" });
  if (!res.ok) throw new Error("Unauthenticated");
  return res.json();
}
```

### 2 — Permission Context with a Single Hook

Centralise all permission logic in one place. Components never check `user.role` directly — they call `usePermission()`.

**`lib/auth/permission-context.tsx`**
```tsx
"use client";

import { createContext, useContext } from "react";
import type { CurrentUser } from "@/lib/api/me";

type PermissionContextValue = {
  user: CurrentUser | null;
  can: (slug: string) => boolean;
  hasRole: (roleSlug: string) => boolean;
};

const PermissionContext = createContext<PermissionContextValue>({
  user: null,
  can: () => false,
  hasRole: () => false,
});

export function PermissionProvider({
  user,
  children,
}: {
  user: CurrentUser | null;
  children: React.ReactNode;
}) {
  const can = (slug: string) =>
    user?.permissions.includes(slug) ?? false;

  const hasRole = (roleSlug: string) =>
    user?.role.slug === roleSlug;

  return (
    <PermissionContext.Provider value={{ user, can, hasRole }}>
      {children}
    </PermissionContext.Provider>
  );
}

export function usePermission() {
  return useContext(PermissionContext);
}
```

Load `CurrentUser` once in the root layout (Server Component) and pass it to the provider:

**`app/layout.tsx`**
```tsx
import { fetchMe } from "@/lib/api/me";
import { PermissionProvider } from "@/lib/auth/permission-context";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const user = await fetchMe().catch(() => null);
  return (
    <html>
      <body>
        <PermissionProvider user={user}>
          {children}
        </PermissionProvider>
      </body>
    </html>
  );
}
```

### 3 — Components Check Permissions, Not Roles

```tsx
// ❌ WRONG — checks role slug directly; breaks when roles are reorganised
const canDelete = user.role === "admin";

// ✅ CORRECT — checks the permission slug from the live DB-loaded list
const { can } = usePermission();
const canDelete = can("articles:delete");

return (
  <>
    <ArticleBody article={article} />
    {canDelete && <DeleteButton articleId={article.id} />}
  </>
);
```

When an admin creates a new "senior_editor" role via the admin UI and grants it `articles:delete`, all senior editors see the Delete button on their next page load — no code change.

### 4 — Route Protection in Next.js Middleware (Server-Side)

Middleware runs on the server before the page renders. It is the correct place to redirect unauthenticated or unauthorised users — not a client-side component.

**`middleware.ts`**
```ts
import { NextRequest, NextResponse } from "next/server";
import { verifyToken } from "@/lib/auth/jwt";

const PROTECTED = /^\/(dashboard|admin|settings)(\/|$)/;
const ADMIN_ONLY = /^\/admin(\/|$)/;

export async function middleware(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value;

  if (PROTECTED.test(request.nextUrl.pathname)) {
    if (!token) {
      return NextResponse.redirect(new URL("/login", request.url));
    }

    const payload = await verifyToken(token).catch(() => null);
    if (!payload) {
      return NextResponse.redirect(new URL("/login", request.url));
    }

    // Admin routes: check role slug from JWT for a quick gate.
    // The API will enforce permissions on every data request regardless.
    if (ADMIN_ONLY.test(request.nextUrl.pathname) && payload.role !== "admin") {
      return NextResponse.redirect(new URL("/403", request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/(dashboard|admin|settings)/:path*"],
};
```

The middleware uses the JWT `role` slug for the fast route-level gate. The API enforces permissions on every data request — these are complementary layers, not alternatives.

### 5 — `<PermissionGate>` Component for Conditional Rendering

Extract the visibility pattern into a single reusable component so permission checks are never scattered inline as ternaries across the codebase.

**`components/permission-gate.tsx`**
```tsx
"use client";

import { usePermission } from "@/lib/auth/permission-context";

type Props = {
  permission?: string;
  role?: string;
  fallback?: React.ReactNode;
  children: React.ReactNode;
};

export function PermissionGate({ permission, role, fallback = null, children }: Props) {
  const { can, hasRole } = usePermission();

  const allowed =
    (permission ? can(permission) : true) &&
    (role ? hasRole(role) : true);

  return allowed ? <>{children}</> : <>{fallback}</>;
}
```

Usage:

```tsx
// ✅ clean, declarative, no magic strings in JSX
<PermissionGate permission="articles:delete">
  <DeleteButton articleId={article.id} />
</PermissionGate>

<PermissionGate permission="settings:write" fallback={<ReadOnlySettings />}>
  <SettingsForm />
</PermissionGate>
```

### 6 — The Frontend Is UI, Not Security

The `can()` check and `<PermissionGate>` control what the user *sees*. They do not control what the user *can do* — that is the API's job.

```
User removes PermissionGate in DevTools → sees the button
User clicks the button → API call is made
API checks require_permission("articles:delete") → 403 Forbidden
Nothing changes in the database
```

Never write code that assumes a hidden button is a protected action.

## Decision Guide

| You want to… | Correct approach |
|---|---|
| Hide a button from users without a permission | `<PermissionGate permission="x:y">` or `can("x:y")` |
| Redirect unauthenticated users | Next.js middleware |
| Redirect users to 403 for an off-limits section | Next.js middleware (role slug from JWT) |
| Know which permissions the current user has | `usePermission()` → `can("x:y")` |
| React to a permission change made in the admin UI | Re-fetch `/me` (happens on next page load; or invalidate with `revalidatePath`) |
| Protect data from unauthorised reads/writes | API — `require_permission()` on the route (frontend cannot do this) |

## Quick Checklist

- [ ] No `process.env.NEXT_PUBLIC_*` variable holds role names or permission strings
- [ ] No `user.role === "admin"` checks scattered across components — use `can()` or `<PermissionGate>`
- [ ] No permission or role data stored in `localStorage` or client-set cookies
- [ ] Permissions come from `/me` API response, not from the JWT payload directly
- [ ] A single `usePermission()` hook is the only place components read auth state
- [ ] Route protection is in `middleware.ts`, not in client components with redirects
- [ ] `<PermissionGate>` wraps conditional UI — no inline ternaries checking role strings
- [ ] The frontend never treats its own permission checks as security enforcement
- [ ] See `backend/26-rbac-permissions` for the API-side enforcement pattern
