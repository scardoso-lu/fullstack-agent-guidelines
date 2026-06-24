---
model: opus
effort: high
---

# OWASP Top 10 2025 — Next.js and Web Application Edition

Use when implementing auth, rendering user-provided content, or configuring security headers. Maps all ten OWASP Top 10 2025 risks to Next.js patterns — middleware access control, CSP, XSS via DOMPurify, and NEXT_PUBLIC_ rules.

The same OWASP Top 10 2025 that governs your FastAPI backend applies to the frontend — but the attack surfaces and fixes are different. A secure backend is not enough if the frontend leaks tokens, renders arbitrary HTML, or ships secrets in the client bundle.

Each entry maps the 2025 risk to a concrete Next.js pattern.

---

## A01:2025 — Broken Access Control

The frontend must never trust client-side state alone. Middleware is the only reliable gate.

**Vulnerable — client-side role check:**
```tsx
// ❌ WRONG — user can manipulate localStorage or React state
"use client";

export default function AdminPage() {
  const { user } = useUser();
  if (user?.role !== "admin") return <div>Forbidden</div>;  // still loaded the page
  return <AdminDashboard />;
}
```

**Vulnerable — decoding without signature verification:**
```ts
// ❌ WRONG — decodeToken does not verify the JWT signature
// A user can forge a cookie with role: "admin" and a future exp
const payload = token ? decodeToken(token) : null;
if (payload?.role !== "admin") return redirect("/login");
```

**Fixed — Auth.js middleware verifies the session before any page is served:**
```ts
// src/middleware.ts
export { auth as middleware } from "@/auth";

export const config = {
  matcher: ["/((?!_next|api/auth|favicon.ico|.*\\..*).*)"],
};
```

For custom redirect behaviour (e.g. role-scoped sections):

```ts
// src/middleware.ts — extended variant with role check
import { auth } from "@/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  if (!req.auth) {
    const loginUrl = new URL("/api/auth/signin", req.url);
    loginUrl.searchParams.set("callbackUrl", req.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  // Role-scoped gate: verify the session's role claim for admin routes
  if (req.nextUrl.pathname.startsWith("/admin") && req.auth.user?.role !== "admin") {
    return NextResponse.redirect(new URL("/403", req.url));
  }
  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!_next|api/auth|favicon.ico|.*\\..*).*)"],
};
```

Auth.js verifies the session cookie cryptographically on every request and runs in Edge Runtime. The browser never holds a raw JWT — it only holds the encrypted Auth.js session cookie. Never render privileged content and hide it with CSS or a conditional — gate it at the network edge.

For the full RBAC pattern — permission-based visibility, `<PermissionGate>`, and `usePermission()` hook — see `frontend/19-rbac-permissions`.

---

## A02:2025 — Security Misconfiguration

**Vulnerable:**
```ts
// next.config.js
const nextConfig = {
  // No security headers at all
  // CORS wide open via API routes
  // .env.local committed to git
};
```

**Fixed — security headers via `next.config.js`:**
```ts
// next.config.ts
import type { NextConfig } from "next";

const securityHeaders = [
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",   // tighten in production by removing unsafe-inline
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https:",
      "connect-src 'self' https://api.yourapp.com",
      "frame-ancestors 'none'",
    ].join("; "),
  },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
];

const nextConfig: NextConfig = {
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
  // Never expose internal errors to users
  productionBrowserSourceMaps: false,
};

export default nextConfig;
```

**`.env.local — never commit this file`**
```bash
NEXT_PUBLIC_API_URL=https://api.yourapp.com   # safe: intentionally client-visible
JWT_SECRET=...                                 # NEVER add NEXT_PUBLIC_ prefix to secrets
DATABASE_URL=...                               # server-only
```

`NEXT_PUBLIC_` prefix embeds a value in the client bundle — visible to anyone who opens DevTools. Never use it for secrets.

---

## A03:2025 — Software Supply Chain Failures

See the dedicated `08-supply-chain.md` guideline for full detail. Summary:

- Pin exact versions in `package.json` — `"react": "19.0.0"`, not `"^19.0.0"`
- Commit `package-lock.json` or `pnpm-lock.yaml` — never delete or `.gitignore` it
- Run `npm audit` / `pnpm audit` in CI — break the build on high-severity findings
- Review `npm install <pkg>` before running it — check weekly downloads and last publish date

---

## A04:2025 — Cryptographic Failures

**Vulnerable:**
```ts
// ❌ WRONG — token stored where XSS can steal it
localStorage.setItem("token", accessToken);
sessionStorage.setItem("token", accessToken);

// ❌ WRONG — raw JWT stored in a readable cookie
import Cookies from "js-cookie";
Cookies.set("x-access-token", rawJwt, { sameSite: "Strict" });
// JS can read js-cookie values — the token is visible to any script on the page
```

**Fixed:**
```ts
// ✅ Auth.js sets an encrypted, HttpOnly, Secure session cookie automatically.
// The browser never sees a raw JWT. JS cannot read the cookie at all.
// No manual cookie management is needed — Auth.js handles it.

// ✅ Fetch user data server-side via /api/me — never decode a client-visible token
fetch("/api/me", { credentials: "include" })
  .then(r => r.json())
  .then(user => setUser(user));
```

Sensitive data should never appear in URLs (`/reset?token=abc123` leaks to server logs, Referer headers, and browser history). Always use POST body or request headers.

---

## A05:2025 — Injection (XSS)

Cross-Site Scripting is the injection attack on the frontend. React prevents most XSS by default — JSX escapes all values. The danger points are explicit escapes.

**Vulnerable:**
```tsx
// ❌ WRONG — executes arbitrary HTML/JS from user content or API response
<div dangerouslySetInnerHTML={{ __html: userBio }} />
<div dangerouslySetInnerHTML={{ __html: apiResponse.description }} />

// ❌ WRONG — constructing URLs from user input without validation
<a href={user.website}>Profile</a>   // user.website could be "javascript:alert(1)"
```

**Fixed:**
```tsx
import DOMPurify from "dompurify";

// Sanitize before rendering rich HTML
const clean = DOMPurify.sanitize(userBio, { ALLOWED_TAGS: ["b", "i", "em", "strong"] });
<div dangerouslySetInnerHTML={{ __html: clean }} />

// Validate URL protocol before rendering
function SafeLink({ href, children }: { href: string; children: React.ReactNode }) {
  const safe = href.startsWith("https://") || href.startsWith("http://");
  if (!safe) return <span>{children}</span>;   // strip dangerous URLs
  return <a href={href} rel="noopener noreferrer">{children}</a>;
}
```

Never use `eval()`, `new Function()`, or `innerHTML` on untrusted data.

---

## A06:2025 — Insecure Design

Insecure design at the frontend level includes:

- Relying on `disabled` attribute or hidden fields to prevent actions (server must enforce)
- Trusting URL parameters for authorization (`?isAdmin=true`)
- Storing sensitive data in URL query strings (logs, Referer header)

```tsx
// ❌ WRONG — disabled button is the only protection
<button disabled={!user.isAdmin} onClick={deleteAllData}>Delete All</button>

// ✅ Server Action rejects unauthorized calls regardless of client state
"use server";
async function deleteAllData() {
  const user = await getCurrentUser();           // verify on server
  if (!user || user.role !== "admin") {
    throw new Error("Unauthorized");
  }
  // ...
}
```

---

## A07:2025 — Authentication Failures

```ts
// ❌ WRONG — manually decoding a client-visible JWT to check expiry
import { isTokenExpired } from "@/lib/jwt";
const token = Cookies.get("x-access-token");
if (token && !isTokenExpired(token)) setUser(decodeToken(token));
// A forged cookie with a future exp passes this check — no signature verification

// ✅ Auth.js manages session expiry and cryptographic validity automatically.
// The middleware rejects invalid or expired sessions before any page serves.
// Client code reads user data from /api/me — never decodes a raw token.
```

```ts
// ✅ Middleware delegates session verification to Auth.js
export { auth as middleware } from "@/auth";

export const config = {
  matcher: ["/((?!_next|api/auth|favicon.ico|.*\\..*).*)"],
};
```

Implement logout via Auth.js's `signOut()` which clears the session cookie server-side, then performs a redirect to purge all client state. Never clear auth state with only a client-side cookie removal — the server session must also be invalidated.

---

## A08:2025 — Software and Data Integrity Failures

```html
<!-- ❌ WRONG — CDN resource without integrity check; can be tampered -->
<script src="https://cdn.example.com/library.js"></script>

<!-- ✅ Subresource Integrity (SRI) — browser verifies hash before executing -->
<script
  src="https://cdn.example.com/library.js"
  integrity="sha384-abc123..."
  crossorigin="anonymous"
></script>
```

For packages managed by npm/pnpm, the lockfile serves as the integrity check — it contains SHA hashes for every package. Never delete or bypass it.

---

## A09:2025 — Security Logging and Alerting Failures

```ts
// ❌ WRONG — silent failure; attackers know attempts aren't logged
async function login(email: string, password: string) {
  try {
    return await AuthService.login(email, password);
  } catch {
    // swallowed — nothing in logs
  }
}
```

```ts
// ✅ Log auth failures to your monitoring backend
import { logger } from "@/lib/logger";

async function login(email: string, password: string) {
  try {
    return await AuthService.login(email, password);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      logger.warn("login_failed", { email });   // never log the password
    }
    throw err;
  }
}
```

Ship errors to a service (Sentry, Datadog) from the global `error.tsx` boundary.

---

## A10:2025 — Mishandling of Exceptional Conditions

```tsx
// ❌ WRONG — unhandled crash exposes internals to the user
export default function DrugPage({ drug }: { drug: DrugDataItem | null }) {
  return <div>{drug.inn}</div>;  // TypeError if drug is null — leaks stack trace in dev, white screen in prod
}
```

```tsx
// ✅ Error boundary catches render errors — never expose stack traces
// src/app/[lang]/(private)/admin/error.tsx  (Next.js segment error boundary)
"use client";

export default function ErrorPage({ error, reset }: { error: Error; reset: () => void }) {
  // Log to monitoring — don't display error.message to users
  useEffect(() => {
    logger.error("render_error", { message: error.message });
  }, [error]);

  return (
    <div>
      <h2>Something went wrong.</h2>
      <button onClick={reset}>Try again</button>
    </div>
  );
}
```

Every route segment should have an `error.tsx` boundary. The root `app/error.tsx` is the last resort.

---

## Quick Checklist

- [ ] Route protection is in `middleware.ts` via Auth.js `auth()` — session cryptographically verified before every non-public request
- [ ] No raw JWTs on the client — browser holds only the encrypted Auth.js session cookie; user data comes from `/api/me`
- [ ] Role-based UI visibility uses `<PermissionGate>` and `usePermission()` from `frontend/19-rbac-permissions` — never inline `user.role === "admin"` checks
- [ ] Security headers set in `next.config.ts` (CSP, X-Frame-Options, HSTS, CORS)
- [ ] `NEXT_PUBLIC_` prefix only on values intentionally visible to users — never on secrets, tenant IDs, or client IDs
- [ ] `dangerouslySetInnerHTML` used only with `DOMPurify.sanitize()` — never on raw API data
- [ ] URLs from user input validated to `https://` or `http://` before rendering
- [ ] Logout uses Auth.js `signOut()` — server-side session invalidation, not just a client-side cookie clear
- [ ] Error boundaries on every route segment — stack traces never shown to users
- [ ] Auth failures logged to monitoring (never logging passwords or tokens)
- [ ] Lockfile committed — `npm audit` runs in CI
