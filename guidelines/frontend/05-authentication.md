---
model: opus
effort: high
---

# Authentication — OIDC Authorization Code Flow with OBO

Use when implementing login, protecting routes, or making authenticated calls from Next.js (BFF) to FastAPI. Covers the full OIDC Authorization Code Flow, the On-Behalf-Of (OBO) token exchange, Edge middleware route guard, and FastAPI JWT validation.

The app uses Next.js as a Backend-for-Frontend (BFF). The browser never sees access tokens — Next.js holds them server-side in an encrypted session and exchanges them for API-scoped tokens via the OBO flow before calling FastAPI. FastAPI validates every incoming JWT against the identity provider's public keys.

---

## Architectural Flow

```
Browser → Next.js BFF
  User logs in via OIDC redirect (Entra / Google / Okta / any OIDC IdP)
  BFF stores tokens in encrypted, HttpOnly session cookie
  Browser only ever holds this opaque session cookie — never a raw JWT

Next.js BFF → Identity Provider (OBO exchange)
  BFF takes the user's access token from the session
  Calls /token with grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer
  IdP returns a new token scoped specifically for the FastAPI app

Next.js BFF → FastAPI
  Attaches the OBO token as Authorization: Bearer <token>
  FastAPI receives a cryptographically signed, audience-scoped JWT

FastAPI → Validation
  Fetches IdP's JWKS endpoint to verify the signature
  Checks aud claim matches the FastAPI app registration
  Zero Trust: even if the BFF is bypassed, callers need a valid signed JWT
```

---

## Identity Provider Setup

Two App Registrations are required (shown here for Microsoft Entra; adjust for other IdPs):

| Registration | Purpose | Key settings |
|---|---|---|
| `nextjs-bff` | Client | Redirect URI: `https://app.example.com/api/auth/callback/azure-ad` |
| `fastapi-api` | Resource | Expose an API scope, e.g. `api://<fastapi-client-id>/access_as_user` |

Grant `nextjs-bff` the `access_as_user` delegated permission on `fastapi-api` and admin-consent it.

---

## Next.js — OIDC Login (Auth.js / next-auth)

```ts
// src/auth.ts  — shared auth config consumed by the route handler and middleware
import NextAuth from "next-auth";
import AzureAD from "next-auth/providers/azure-ad";

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    AzureAD({
      clientId: process.env.AZURE_AD_CLIENT_ID!,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
      tenantId: process.env.AZURE_AD_TENANT_ID!,
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      // Persist the IdP access token so OBO can use it later
      if (account?.access_token) {
        token.idpAccessToken = account.access_token;
      }
      return token;
    },
    async session({ session, token }) {
      // Expose only what the server components need; never expose raw tokens to the client
      session.userId = token.sub as string;
      return session;
    },
  },
});

// src/app/api/auth/[...nextauth]/route.ts
export { handlers as GET, handlers as POST } from "@/auth";
```

For Google or other OIDC providers, swap `AzureAD(...)` for the relevant Auth.js provider and update the OBO logic below — the rest of the flow is identical.

---

## Next.js — OBO Token Acquisition

```ts
// src/lib/obo.ts
import { ConfidentialClientApplication } from "@azure/msal-node";
import { auth } from "@/auth";

const msalClient = new ConfidentialClientApplication({
  auth: {
    clientId: process.env.AZURE_AD_CLIENT_ID!,
    clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
    authority: `https://login.microsoftonline.com/${process.env.AZURE_AD_TENANT_ID}`,
  },
  cache: { cachePlugin: undefined }, // swap in a Redis cache plugin for production
});

export async function getApiToken(): Promise<string> {
  const session = await auth();
  const idpToken = (session as any)?.idpAccessToken as string | undefined;
  if (!idpToken) throw new Error("No IdP token in session");

  const result = await msalClient.acquireTokenOnBehalfOf({
    oboAssertion: idpToken,
    scopes: [`api://${process.env.AZURE_AD_FASTAPI_CLIENT_ID}/access_as_user`],
  });

  if (!result?.accessToken) throw new Error("OBO token acquisition failed");
  return result.accessToken;
}
```

Cache the resulting token (e.g. keyed by `session.userId + scope`) to avoid hitting the IdP on every request. MSAL's in-memory cache handles this by default; swap in a Redis cache plugin for multi-instance deployments.

---

## Next.js — BFF Proxy Route

Server Actions or Route Handlers should call FastAPI through a thin proxy that injects the OBO token:

```ts
// src/lib/api-client.ts
import { getApiToken } from "@/lib/obo";

const FASTAPI_BASE = process.env.FASTAPI_BASE_URL!;

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getApiToken();

  const response = await fetch(`${FASTAPI_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
      Authorization: `Bearer ${token}`,   // OBO token — scoped to FastAPI
    },
  });

  if (!response.ok) {
    throw new Error(`FastAPI error: ${response.status}`);
  }

  return response.json() as Promise<T>;
}
```

Usage in a Server Action:

```ts
// src/app/actions/items.ts
"use server";
import { apiFetch } from "@/lib/api-client";

export async function getItems() {
  return apiFetch<Item[]>("/items");
}
```

---

## Middleware — Route Protection at the Edge

```ts
// src/middleware.ts
export { auth as middleware } from "@/auth";

export const config = {
  matcher: ["/((?!_next|api/auth|favicon.ico|.*\\..*).*)"],
};
```

Auth.js handles the redirect to the IdP login page automatically when the session is missing. To customise the redirect (e.g. preserve the original URL):

```ts
// src/middleware.ts — custom redirect
import { auth } from "@/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  if (!req.auth) {
    const loginUrl = new URL("/api/auth/signin", req.url);
    loginUrl.searchParams.set("callbackUrl", req.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!_next|api/auth|favicon.ico|.*\\..*).*)"],
};
```

---

## FastAPI — JWT Validation

```python
# api/auth.py
import os
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

TENANT_ID = os.environ["AZURE_AD_TENANT_ID"]
AUDIENCE  = os.environ["AZURE_AD_FASTAPI_CLIENT_ID"]  # the fastapi-api app registration client id
JWKS_URL  = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"

bearer_scheme = HTTPBearer()


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(JWKS_URL, cache_jwk_set=True, lifespan=3600)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> dict[str, Any]:
    token = credentials.credentials
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=AUDIENCE,
            issuer=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        )
        return payload
    except jwt.exceptions.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


# Usage in a route
from fastapi import FastAPI

app = FastAPI()

@app.get("/items")
def list_items(user: Annotated[dict, Depends(get_current_user)]):
    owner_id = user["oid"]   # object ID — stable cross-token identifier
    return fetch_items(owner_id)
```

Useful claims available after validation:

| Claim | Meaning |
|---|---|
| `oid` | Object ID — stable user identifier across tokens |
| `preferred_username` | UPN / email |
| `groups` | Group membership (requires Entra config) |
| `scp` | Delegated scopes granted |

---

## Client-Side Auth State

Because the session cookie is HttpOnly, client components cannot decode it. Fetch user data from a Next.js route handler that reads the server-side session:

```ts
// src/app/api/me/route.ts
import { auth } from "@/auth";
import { NextResponse } from "next/server";

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return NextResponse.json({
    id: session.userId,
    name: session.user.name,
    email: session.user.email,
    image: session.user.image,
  });
}
```

```tsx
// src/providers/user-provider.tsx
"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";

type User = { id: string; name: string; email: string; image?: string };
type AuthState =
  | { status: "loading" }
  | { status: "authenticated"; user: User }
  | { status: "unauthenticated" };

const AuthContext = createContext<AuthState>({ status: "loading" });

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    fetch("/api/me", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((user: User) => setState({ status: "authenticated", user }))
      .catch(() => setState({ status: "unauthenticated" }));
  }, []);

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

export function useUser(): AuthState {
  return useContext(AuthContext);
}

export function useRequiredUser(): User {
  const state = useContext(AuthContext);
  if (state.status !== "authenticated") {
    throw new Error("useRequiredUser called outside an authenticated session");
  }
  return state.user;
}
```

---

## Provider-Agnostic Design

This architecture is not specific to Entra ID. Any OIDC-compliant provider works because the BFF only needs the provider's well-known discovery URL:

| Provider | Discovery URL |
|---|---|
| Microsoft Entra | `https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration` |
| Google | `https://accounts.google.com/.well-known/openid-configuration` |
| Okta | `https://{domain}/.well-known/openid-configuration` |
| Auth0 | `https://{domain}/.well-known/openid-configuration` |

To switch providers, change the Auth.js provider config — the middleware, client code, and FastAPI validation logic are unaffected.

**Multi-provider note:** If you support multiple IdPs simultaneously (e.g. "Login with Google" AND "Login with Microsoft"), add a user-mapping layer (a `users` table keyed by email or a stable `sub`+`iss` pair) so accounts from different providers can be linked.

**OBO with non-Entra providers:** Google does not support the OBO flow. For Google-issued tokens, issue a short-lived service-to-service token (e.g. a signed JWT from your BFF) or use a shared API key over a private network. The FastAPI validation logic stays the same; only the token source changes.

---

## Anti-Patterns

```ts
// ❌ Shared secret header — trivially bypassable if the BFF is compromised or circumvented
headers["X-Internal-User-Id"] = userId;

// ❌ Forwarding the user's IdP token to FastAPI instead of an OBO token
//    The token's aud will be the BFF app, not FastAPI — validation will fail
headers["Authorization"] = `Bearer ${session.idpAccessToken}`;

// ❌ Storing tokens in localStorage — readable by any JS, XSS-vulnerable
localStorage.setItem("access_token", token);

// ❌ Skipping JWT validation in FastAPI because "the network is private"
//    Zero Trust means every service validates — even inside a VPC
@app.get("/items")
def list_items(user_id: str = Header(...)):   # trusts a plain header
    ...
```

---

## Quick Checklist

- [ ] **Two App Registrations**: one for the Next.js BFF (Client), one for the FastAPI API (Resource)
- [ ] **API permission**: BFF app has delegated `access_as_user` permission on the API app, admin-consented
- [ ] **Auth.js configured**: OIDC provider set up, `idpAccessToken` persisted in the JWT callback
- [ ] **OBO implemented**: `getApiToken()` exchanges the IdP token for an API-scoped token before every FastAPI call
- [ ] **Token cache**: OBO results cached (in-memory or Redis) — not re-fetched on every request
- [ ] **Middleware guards all routes**: unauthenticated requests redirect to the IdP sign-in page
- [ ] **FastAPI validates JWTs**: signature verified against JWKS, `aud` and `iss` claims checked
- [ ] **No raw tokens on the client**: browser only receives the encrypted session cookie and opaque user fields from `/api/me`
- [ ] **No shared secret headers**: FastAPI rejects any request without a valid signed Bearer token
