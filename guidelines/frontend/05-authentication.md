---
model: opus
effort: high
---

# Authentication — JWT, Cookies, and Route Protection

Use when implementing login, protecting routes, or reading the current user. Covers JWT cookie setup, Edge middleware route guard, AuthProvider with useUser hook, and the /api/me pattern for HttpOnly cookies.

The app uses JWT access tokens stored in a cookie (`x-access-token`). Authentication flows through three layers: middleware (Edge, catches everything), `UserContext` (client-side user state), and individual pages/components (consume the context or redirect).

---

## How Tokens Flow

```
Login form → POST /auth/login → response sets "x-access-token" cookie
                ↓
Middleware reads cookie on every request → redirects to /login if missing or expired
                ↓
Server Components read cookies() for server-side API calls
Client Components read UserContext for user data
```

---

## Token Helpers (`src/lib/`)

```ts
// src/lib/jwt.ts
import { jwtDecode } from "jwt-decode";

type JwtPayload = {
  sub: string;
  exp: number;
  email?: string;
};

export function isTokenExpired(token: string): boolean {
  try {
    const { exp } = jwtDecode<JwtPayload>(token);
    return Date.now() / 1000 > exp;
  } catch {
    return true;   // malformed token = treat as expired
  }
}

export function decodeToken(token: string): JwtPayload | null {
  try {
    return jwtDecode<JwtPayload>(token);
  } catch {
    return null;
  }
}
```

```ts
// src/lib/cookies.ts
import Cookies from "js-cookie";

const TOKEN_KEY = "x-access-token";

export const cookieStore = {
  getToken: () => Cookies.get(TOKEN_KEY) ?? null,
  setToken: (token: string, expiresInDays = 1) =>
    Cookies.set(TOKEN_KEY, token, { expires: expiresInDays, sameSite: "Strict" }),
  removeToken: () => Cookies.remove(TOKEN_KEY),
};
```

---

## Middleware — Route Protection at the Edge

The middleware runs before any page renders. It checks the token and redirects unauthenticated requests:

```ts
// src/middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { isTokenExpired } from "@/lib/jwt";

const PUBLIC_PATHS = ["/login", "/register", "/forgot-password"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const lang = request.nextUrl.locale ?? "en";

  // Strip lang prefix for matching
  const pathWithoutLang = pathname.replace(/^\/(en|fr|es)/, "") || "/";

  const isPublic = PUBLIC_PATHS.some((p) => pathWithoutLang.startsWith(p));
  const token = request.cookies.get("x-access-token")?.value;

  if (!isPublic) {
    if (!token || isTokenExpired(token)) {
      const loginUrl = new URL(`/${lang}/login`, request.url);
      loginUrl.searchParams.set("from", pathname);   // remember where they were
      return NextResponse.redirect(loginUrl);
    }
  }

  // Redirect authenticated users away from auth pages
  if (isPublic && token && !isTokenExpired(token)) {
    return NextResponse.redirect(new URL(`/${lang}/admin`, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|api|favicon.ico|.*\\..*).*)"],  // exclude Next.js internals
};
```

**Key design decisions:**
- Middleware runs at the Edge — zero server boot time
- `from` param lets the login form redirect back after success
- Both "no token" and "expired token" redirect the same way — no information leak

---

## `UserContext` — Client-Side Auth State

```tsx
// src/providers/user-provider.tsx
"use client";

import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { decodeToken } from "@/lib/jwt";
import { cookieStore } from "@/lib/cookies";

type User = {
  sub: string;
  email: string;
};

type UserContextValue = {
  user: User | null;
  isLoading: boolean;
  logout: () => void;
};

const UserContext = createContext<UserContextValue | null>(null);

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = cookieStore.getToken();
    if (token) {
      const payload = decodeToken(token);
      if (payload) {
        setUser({ sub: payload.sub, email: payload.email ?? "" });
      }
    }
    setIsLoading(false);
  }, []);

  const logout = useCallback(() => {
    cookieStore.removeToken();
    setUser(null);
    window.location.href = "/en/login";
  }, []);

  return (
    <UserContext.Provider value={{ user, isLoading, logout }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used inside <UserProvider>");
  return ctx;
}
```

The `UserProvider` wraps the root layout — it's available everywhere without prop drilling:

```tsx
// src/app/layout.tsx
import { UserProvider } from "@/providers/user-provider";
import { QueryProvider } from "@/providers/query-provider";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>
        <QueryProvider>
          <UserProvider>
            {children}
          </UserProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
```

---

## Login Form

```tsx
// src/components/app/login-form.tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { z } from "zod";
import { AuthService } from "@/services/auth";
import { cookieStore } from "@/lib/cookies";
import { ApiError } from "@/services/api";

const LoginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});
type LoginData = z.infer<typeof LoginSchema>;

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("from") ?? "/en/admin";

  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } =
    useForm<LoginData>({ resolver: zodResolver(LoginSchema) });

  const onSubmit = async ({ email, password }: LoginData) => {
    try {
      const { access_token } = await AuthService.login(email, password);
      cookieStore.setToken(access_token);
      router.push(redirectTo);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("root", { message: "Invalid email or password" });
      } else {
        setError("root", { message: "Something went wrong. Try again." });
      }
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <input {...register("email")} type="email" placeholder="Email" />
      {errors.email && <p className="text-red-500 text-sm">{errors.email.message}</p>}

      <input {...register("password")} type="password" placeholder="Password" />

      {errors.root && <p className="text-red-500 text-sm">{errors.root.message}</p>}

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
```

---

## Using Auth State in Components

```tsx
// src/components/app/user-menu.tsx
"use client";

import { useUser } from "@/providers/user-provider";

export function UserMenu() {
  const { user, logout, isLoading } = useUser();

  if (isLoading) return null;
  if (!user) return null;

  return (
    <div>
      <span>{user.email}</span>
      <button onClick={logout}>Sign out</button>
    </div>
  );
}
```

---

## 401 Handling in Services

When an API call returns 401, the user's token has been revoked or expired mid-session. Intercept it at the `authApi` wrapper:

```ts
// src/services/api.ts
export async function authApi<T>(url: string, options: RequestInit = {}): Promise<TypedResponse<T>> {
  // ...
  if (!response.ok) {
    if (response.status === 401) {
      cookieStore.removeToken();
      window.location.href = "/en/login";  // hard redirect clears all client state
      throw new ApiError(401, "Session expired");
    }
    // other errors...
  }
  return response;
}
```

This is the global 401 handler — individual components never need to handle session expiry.

---

## Anti-Pattern: Storing Tokens in localStorage

```ts
// ❌ WRONG — localStorage is accessible to any JS on the page (XSS vulnerability)
localStorage.setItem("token", accessToken);

// ❌ WRONG — checking token in every component instead of using middleware
export default function AdminPage() {
  const token = localStorage.getItem("token");
  if (!token) return redirect("/login");
  // ...
}
```

Cookies with `SameSite: Strict` are inaccessible to cross-site scripts. Middleware handles redirect — pages don't need individual auth checks.

---

## Quick Checklist

- [ ] Tokens stored in cookies with `SameSite: "Strict"` — never `localStorage` or `sessionStorage`
- [ ] `isTokenExpired()` is called in middleware before every non-public request
- [ ] `middleware.ts` handles both "no token" and "expired token" cases identically
- [ ] `UserContext` is populated from the cookie on mount — not from an API call
- [ ] `logout()` removes the cookie and hard-redirects to clear all React state
- [ ] `authApi()` globally handles 401 with a redirect — components never check for 401 individually
- [ ] Login form stores token on success and reads `?from=` to redirect back
