# State Management — Where Server, Global UI, URL, and Local State Live

Use when choosing where to store a piece of state in a Next.js App Router app. Covers the four buckets — **server state stays on the server** (Server Components + Server Actions, *not* a client cache), Context (global client UI), URL params via `nuqs` (shareable state), `useState` (local) — and the rule for when each applies.

State in a Next.js App Router app falls into four buckets. Choosing the wrong one causes cache invalidation bugs, unnecessary re-renders, or state that gets lost on navigation. Match the bucket to the kind of state.

---

## The Four Buckets

| State type | Lives in | Tool |
|---|---|---|
| Server data (users, drugs, catalogs) | The server | Server Components for reads · Server Actions for writes · `next/cache` tags for revalidation |
| Global client UI state (current user, theme) | React Context | `useContext` + Provider |
| URL-synchronized state (filters, tab, page) | URL search params | `nuqs` `useQueryState` |
| Ephemeral UI state (open/closed, hover) | Component local | `useState` |

**Default rule:** push state as high (server > URL > Context > component) as it needs to be for sharing — and no higher. A dialog's open/closed state belongs in `useState`. A search filter that appears in the URL belongs in `nuqs`. Anything that came from the API belongs **on the server**, not in a client cache.

---

## Server State — keep it on the server

The App Router's headline feature is that server data doesn't need a client-side cache. **Reads happen in Server Components; writes happen in Server Actions; cache invalidation is tag-based and runs on the server.** That triangle covers ~90% of what a client cache would do — without shipping the cache, the hydration glue, or its supply-chain surface, to every visitor.

```tsx
// app/[lang]/(private)/admin/drugs/page.tsx — Server Component
import { DrugService } from "@/services/drugs";

export default async function DrugsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; page?: string }>;
}) {
  const { q = "", page = "1" } = await searchParams;
  const result = await DrugService.paged(Number(page), 20, q);   // server-side fetch (taggable)
  return <DrugTable rows={result.data} total={result.total} page={Number(page)} />;
}
```

Tag the `fetch` so a Server Action can invalidate it:

```ts
// inside DrugService.paged
const res = await fetch(`${API}/drugs?...`, { next: { tags: ["drugs"] } });
```

```ts
// app/(app)/drugs/_actions.ts
"use server";
import { revalidateTag } from "next/cache";

export async function deleteDrugAction(formData: FormData) {
  await DrugService.delete(Number(formData.get("id")));
  revalidateTag("drugs");        // next render of DrugsPage serves fresh data
}
```

See `frontend/03-data-fetching` for the full service-layer + cache-tag pattern and `frontend/16-server-actions` for the non-negotiable inside-the-action checklist.

### When you genuinely need a client read (debounced search, polling)

Some flows truly do not work as a Server Component — debounced search-as-you-type, infinite scroll, a panel that polls. Use a small Client Component with `useEffect` + `AbortController` + a debounce; keep the pattern local to the component. See the `DrugSearch` example in `frontend/03-data-fetching`.

If a project finds itself rewriting that pattern across many features, extract a tiny in-repo hook (`useDebouncedFetch`). Don't add a library on the first occurrence — and if you eventually do, any candidate passes through `frontend/08-supply-chain` first.

### Anti-pattern — caching server state in `useState`

```tsx
// ❌ Wrong — manual cache in client memory, ships rendering and stale-data bugs
"use client";

export function DrugList() {
  const [drugs, setDrugs] = useState<Drug[]>([]);

  useEffect(() => {
    DrugService.paged(1, 20).then((r) => setDrugs(r.data));
  }, []);

  return drugs.map((d) => <DrugRow key={d.id} drug={d} />);
}
```

Problems: flash of empty content, no error/loading discipline (`frontend/14-loading-error-empty-states`), no abort on unmount, no revalidation after mutations, worse LCP. The Server Component version above sends rendered HTML in the first byte.

---

## React Context — Global Client UI State

Use Context only for state that is:

1. Needed by many components at different nesting levels.
2. **Not server data** (that lives on the server).
3. Not derivable from the URL.

Current user and theme are the canonical examples.

```tsx
// src/providers/user-provider.tsx
"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { cookieStore } from "@/lib/cookies";
import { decodeToken } from "@/lib/jwt";

type User = { sub: string; email: string };
const UserContext = createContext<{ user: User | null; logout: () => void } | null>(null);

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const token = cookieStore.getToken();
    if (token) {
      const payload = decodeToken(token);
      if (payload) setUser({ sub: payload.sub, email: payload.email ?? "" });
    }
  }, []);

  const logout = () => {
    cookieStore.removeToken();
    setUser(null);
    window.location.href = "/en/login";
  };

  return <UserContext.Provider value={{ user, logout }}>{children}</UserContext.Provider>;
}

export const useUser = () => {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be inside <UserProvider>");
  return ctx;
};
```

**Context anti-pattern — using Context as a general-purpose store:**

```tsx
// ❌ Wrong — putting everything in one context
const AppContext = createContext({
  user: null,
  drugs: [],            // server data — render on the server, don't cache in client memory
  selectedDrug: null,   // URL state — belongs in nuqs
  sidebarOpen: false,   // local state — belongs in useState
  theme: "light",       // fine in context
});
```

Every `AppContext` update re-renders every consumer. Split by domain.

---

## URL State with `nuqs`

State that should survive a page refresh, be shareable via URL, or sync with browser back/forward belongs in URL search params. `nuqs` provides typed, React-integrated access to `?key=value` params.

```tsx
// src/components/app/drug-filters.tsx
"use client";

import { useQueryState, parseAsInteger } from "nuqs";

export function DrugFilters() {
  const [search, setSearch] = useQueryState("q", { defaultValue: "" });
  const [page, setPage] = useQueryState("page", parseAsInteger.withDefault(1));
  const [atcCode, setAtcCode] = useQueryState("atc");

  return (
    <div className="flex gap-2">
      <input
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setPage(1);   // reset page when search changes
        }}
        placeholder="Search by INN…"
      />
      <select value={atcCode ?? ""} onChange={(e) => setAtcCode(e.target.value || null)}>
        <option value="">All ATC codes</option>
        {/* options */}
      </select>
    </div>
  );
}
```

The URL becomes `/en/admin/drugs?q=paracetamol&page=2` — shareable, bookmarkable, survives hard refresh. The parent Server Component picks the params up from `searchParams` and refetches — no client-side cache needed.

**When NOT to use nuqs:**

- Ephemeral UI state (modal open/closed, hover) — `useState`
- Auth state — `UserContext`
- Multi-step wizard state shared between steps but not in the URL — `useState` in a parent

---

## Local State with `useState`

Anything that is component-scoped, ephemeral, and not needed outside the component:

```tsx
"use client";

export function DrugCard({ drug }: { drug: DrugDataItem }) {
  const [expanded, setExpanded] = useState(false);   // open/closed toggle — purely local

  return (
    <div>
      <button onClick={() => setExpanded((v) => !v)}>{drug.inn}</button>
      {expanded && <DrugDetail drug={drug} />}
    </div>
  );
}
```

```tsx
"use client";

import { useState } from "react";

export function DeleteConfirmModal({ onConfirm }: { onConfirm: () => void }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button onClick={() => setOpen(true)}>Delete</button>
      {open && (
        <Modal onClose={() => setOpen(false)}>
          <p>Are you sure?</p>
          <button onClick={() => { onConfirm(); setOpen(false); }}>Confirm</button>
        </Modal>
      )}
    </>
  );
}
```

---

## Decision Tree

```
Is this data fetched from the API?
  → YES → server. Render in a Server Component, mutate via a Server Action,
                  revalidate by tag. NEVER cache the API result in client state.

Is this state needed by many unrelated components?
  → YES → Context (useContext + Provider) — only for truly global state (user, theme)

Should the state appear in the URL / survive page refresh / be shareable?
  → YES → nuqs (useQueryState) — and let the Server Component pick up searchParams

Is it only used within one component or a small tree?
  → YES → useState
```

---

## Combining All Four

A realistic page uses all four types simultaneously — but server state never leaves the server-rendered surface:

```tsx
// app/[lang]/(private)/admin/drugs/page.tsx — Server Component
export default async function DrugsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; page?: string }>;
}) {
  const { q = "", page = "1" } = await searchParams;
  const result = await DrugService.paged(Number(page), 20, q);   // server state, lives on the server
  return <DrugListClient initialRows={result.data} total={result.total} />;
}

// components/app/drug-list-client.tsx
"use client";
export function DrugListClient({
  initialRows,
  total,
}: { initialRows: DrugDataItem[]; total: number }) {
  const { user } = useUser();                         // Context — current user
  const [search, setSearch] = useQueryState("q");     // nuqs — URL state (drives the Server Component refetch)
  const [modalOpen, setModalOpen] = useState(false);  // useState — ephemeral UI
  // initialRows are server-rendered; updates happen by changing the URL,
  // which re-renders the page on the server with fresh data.
  // ...
}
```

The client component receives the initial rows as props; changing the URL re-renders the page on the server with fresh data. No client-side cache to synchronize.

---

## Quick Checklist

- [ ] Server data lives on the server — rendered in Server Components, mutated via Server Actions, revalidated by tag. **Never duplicated in `useState` or a client cache.**
- [ ] Server fetches set `next: { tags: [...] }`; matching Server Actions call `revalidateTag(...)` after a mutation.
- [ ] Context is used only for truly global client UI state (user, theme).
- [ ] URL-related state (filters, page, active tab) uses `nuqs` `useQueryState` — and the page-level Server Component reads from `searchParams` to refetch.
- [ ] Ephemeral UI state (open/closed, hover, animation) stays in `useState`.
- [ ] Client-side fetch (when truly needed for debounce/polling) uses `AbortController` + a debounce; never for initial page data.
- [ ] Context providers are at the root layout level — not wrapping individual pages.
