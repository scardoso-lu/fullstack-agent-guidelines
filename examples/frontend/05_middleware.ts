// Description: Edge middleware — JWT auth guard for all protected routes
// ─────────────────────────────────────────────────────────────────────────────
// PATTERN: One middleware.ts at the project root guards routes under (private).
// Runs on the Edge runtime before the page renders — no unauthorized HTML
// ever reaches the browser. Reads the HttpOnly cookie directly from the request.
// ─────────────────────────────────────────────────────────────────────────────
// File location: middleware.ts (project root, next to package.json)
// ─────────────────────────────────────────────────────────────────────────────

import { NextResponse, type NextRequest } from "next/server";

// Routes that do NOT require authentication
const PUBLIC_PATHS = ["/login", "/register", "/api/auth", "/_next", "/favicon"];

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some((p) => pathname.startsWith(p));
}

// Decode JWT payload and check expiry — Edge-safe (no Node.js crypto needed)
function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return typeof payload.exp !== "number" || Date.now() >= payload.exp * 1000;
  } catch {
    return true;   // malformed token → treat as expired
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isPublic(pathname)) return NextResponse.next();

  // Read HttpOnly cookie — only accessible server-side; JS cannot read this value
  const token = request.cookies.get("x-access-token")?.value;

  if (!token || isTokenExpired(token)) {
    const loginUrl = new URL("/en/login", request.url);
    // Preserve the original path so login can redirect back after success
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

// matcher excludes static files — middleware only runs on page/API routes
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

// ─────────────────────────────────────────────────────────────────────────────
// ANTI-PATTERNS:
//
// 1. Guarding inside the page component with useEffect:
//
//   "use client"
//   export default function AdminPage() {
//     const router = useRouter();
//     useEffect(() => {
//       if (!isLoggedIn()) router.push("/login");  // ← renders first, THEN redirects
//     }, []);
//   }
//   → The unauthorized user sees a flash of the protected page before redirect.
//     Middleware runs BEFORE rendering — the page is never sent.
//
// 2. Checking auth in every layout separately:
//
//   // app/(private)/layout.tsx
//   export default async function Layout() {
//     const user = await getUser();
//     if (!user) redirect("/login");   // ← duplicated in every protected layout
//   }
//   → One middleware guards all routes centrally. Layouts stay clean.
//
// 3. Using Node.js JWT libraries in middleware:
//
//   import jwt from "jsonwebtoken";   // ← Node.js only — crashes on Edge runtime
//   jwt.verify(token, secret);
//   → Middleware runs on Edge. Use the manual atob() decode for expiry checks.
//     Move full signature verification to an API route or Server Action.
// ─────────────────────────────────────────────────────────────────────────────
