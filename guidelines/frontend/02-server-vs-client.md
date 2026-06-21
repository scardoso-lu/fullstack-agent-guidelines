# Server vs Client Components

Use when deciding whether a component needs "use client". Covers the default-Server-Component model, when each type is appropriate, and the Server→Client composition pattern for interactive sub-components.

The biggest mental shift in Next.js 15 App Router is the default: **every component is a Server Component** unless you opt into the client. This is the opposite of the old Pages Router. Getting this wrong is the single most common vibecoding mistake — AI defaults to `"use client"` everywhere, defeating the entire performance model.

## The Mental Model

```
Server Component                    Client Component
─────────────────────────────────   ────────────────────────────────
Runs on server only                 Runs on server (SSR) + browser
Can be async — await data directly  Cannot be async
No bundle size impact               Adds JS to the browser bundle
Can read cookies, headers, env      Cannot read server-only APIs
Cannot use useState, useEffect      Must use for interactivity
Cannot use browser APIs             Can use window, document, etc.
Cannot handle events (onClick)      Handles all user events
```

## Default — Server Component

No directive needed. Fetch data directly, no loading states, no useEffect:

```tsx
// app/[lang]/(private)/admin/page.tsx
// This is a Server Component — async, direct data access, zero client JS

import { cookies } from "next/headers";
import { DashboardService } from "@/services/dashboard";
import { StatsCard } from "@/components/app/stats-card";

export default async function AdminPage() {
  const serverCookies = await cookies();                    // server-only API
  const stats = await DashboardService.stats(serverCookies); // direct service call

  return (
    <section className="grid gap-4 md:grid-cols-3">
      <StatsCard label="Catalogs" value={stats.total_catalogs.total ?? 0} />
      <StatsCard label="Mappings" value={stats.total_mappings.total ?? 0} />
    </section>
  );
}
```

No `useEffect`, no `useState`, no loading spinner. The page arrives fully rendered.

## When to Add `"use client"`

Add it to the lowest possible node in the tree — only the component that actually needs it:

| Need | Directive |
|---|---|
| `useState` / `useReducer` | `"use client"` |
| `useEffect` | `"use client"` |
| Event handlers (`onClick`, `onChange`) | `"use client"` |
| Browser APIs (`window`, `localStorage`) | `"use client"` |
| Third-party client hooks (React Hook Form, swiper, etc.) | `"use client"` |
| Animation (Framer Motion) | `"use client"` |
| Context consumers | `"use client"` |

```tsx
// components/app/login-form.tsx
"use client";   // ← needed: uses useForm, useState, router, onClick

import { useForm } from "react-hook-form";
import { useRouter } from "next/navigation";

export function LoginForm() {
  const { register, handleSubmit } = useForm();
  const router = useRouter();
  // ...
}
```

## The Boundary Rule

You can render a Server Component **inside** a Client Component by passing it as `children`. You **cannot** import a Server Component into a Client Component directly:

```tsx
// ✅ CORRECT — server component passed as children prop
// app/[lang]/(private)/admin/layout.tsx  (Server Component)
import { Sidebar } from "@/components/app/sidebar";  // Client Component
import { UserGreeting } from "@/components/app/user-greeting";  // Server Component

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex">
      <Sidebar>
        <UserGreeting />  {/* Server Component passed as children into a Client Component */}
      </Sidebar>
      <main>{children}</main>
    </div>
  );
}
```

```tsx
// ❌ WRONG — importing Server Component inside Client Component
"use client";

import { UserGreeting } from "@/components/app/user-greeting";  // Server Component
// This breaks — Server Component cannot run in client context
```

## Data Fetching: Server vs Client

The default is **Server Components for reads, Server Actions for writes**. Reach for client-side fetching only when the data genuinely depends on client-only state (after-mount interaction, polling, debounced input).

| Scenario | Use |
|---|---|
| Initial page data, SEO matters | Server Component + `await service.call()` |
| Data driven by user interaction *after* page load (search-as-you-type, filters) | Client Component + `fetch` inside a `useEffect`/`useTransition` with an `AbortController` |
| Polling / live updates | Client Component + interval + `fetch`, or Server Component refresh via `router.refresh()` after a Server Action |
| Mutations (create, update, delete) | **Server Action** (per `frontend/16-server-actions`) |
| Fire-and-forget server mutation with cache revalidation | Server Action + `revalidateTag` / `revalidatePath` |

For everything except "interactive client-driven flow," prefer Server Components — they ship rendered HTML, no client bundle, no loading flicker.

```tsx
// Server Component — data fetched before HTML is sent
export default async function CatalogPage() {
  const catalogs = await CatalogService.list();   // no loading state needed
  return <CatalogTable data={catalogs} />;
}
```

```tsx
// Client Component — only when the fetch genuinely needs client state (debounced query)
"use client";
import { useEffect, useState } from "react";
import { DrugService } from "@/services/drugs";

export function LiveDrugSearch({ initialQuery }: { initialQuery: string }) {
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<Drug[]>([]);

  useEffect(() => {
    const ctrl = new AbortController();
    DrugService.searchSuggestions(query, { signal: ctrl.signal })
      .then(setResults)
      .catch((e) => { if (e.name !== "AbortError") throw e; });
    return () => ctrl.abort();
  }, [query]);

  return /* ... */;
}
```

If a project repeatedly needs polling, optimistic updates, or stale-while-revalidate semantics across many features, that's the point to introduce a small in-repo hook (or a vetted library, after running it through `frontend/08-supply-chain`). Don't add a library on the first occurrence.

## Anti-Pattern: Client Everywhere

```tsx
// ❌ WRONG — AI generates this by default
"use client";  // ← unnecessary — no interactivity here

import { useEffect, useState } from "react";
import { DashboardService } from "@/services/dashboard";

export default function AdminPage() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    DashboardService.stats().then(setStats);  // client-side fetch, flash of empty state
  }, []);

  if (!stats) return <div>Loading...</div>;
  return <StatsCard value={stats.total} />;
}
```

The server component version above sends fully-rendered HTML — no loading flash, no client JS bundle, better SEO, faster LCP.

## Quick Checklist

- [ ] No `"use client"` on page files unless the entire page is interactive
- [ ] `"use client"` is placed at the lowest component that needs it
- [ ] `async/await` data fetching only in Server Components — never in `useEffect` for initial data
- [ ] Server Components pass data to Client Components via props
- [ ] Client-side `fetch` (when truly needed) uses `AbortController` and runs only on user-driven interaction — never for the initial page data
- [ ] No `useState(null)` + `useEffect(fetch)` pattern where a Server Component would work
- [ ] Mutations go through a Server Action, not a hand-rolled client fetch + cache-bust
