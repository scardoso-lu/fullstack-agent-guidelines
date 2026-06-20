# State Management — React Query, Context, URL State, and Local State

Use when choosing where to store a piece of state. Covers the four buckets — React Query (server state), Context (global UI), URL params via nuqs (shareable state), useState (local) — and the rule for when each applies.

State in a Next.js App Router app falls into four buckets. Choosing the wrong one causes cache invalidation bugs, unnecessary re-renders, or state that gets lost on navigation. Match the bucket to the kind of state.

---

## The Four Buckets

| State type | Lives in | Tool |
|---|---|---|
| Server data (users, drugs, catalogs) | React Query cache | `useQuery` / `useMutation` |
| Global UI state (current user, theme) | React Context | `useContext` + Provider |
| URL-synchronized state (filters, tab, page) | URL search params | `nuqs` `useQueryState` |
| Ephemeral UI state (open/closed, hover) | Component local | `useState` |

**Default rule:** push state as high (URL > Context > component) as it needs to be for sharing — and no higher. A dialog's open/closed state belongs in `useState`. A search filter that appears in the URL belongs in `nuqs`.

---

## React Query — Server State

React Query is the cache for all remote data. It handles loading, error, and stale states automatically. Never duplicate server state in `useState`.

```tsx
// ✅ Correct — React Query owns the server data
"use client";

import { useQuery } from "@tanstack/react-query";
import { DrugService } from "@/services/drugs";
import { useQueryState } from "nuqs";

export function DrugList() {
  const [page, setPage] = useQueryState("page", { defaultValue: "1" });
  const [search] = useQueryState("q", { defaultValue: "" });

  const { data, isLoading, isError } = useQuery({
    queryKey: ["drugs", "paged", page, search],
    queryFn: () => DrugService.paged(parseInt(page), 20, search),
  });

  return (
    <div>
      {isLoading && <p>Loading…</p>}
      {isError && <p>Failed to load.</p>}
      {data?.data.map((drug) => <DrugRow key={drug.id} drug={drug} />)}
      <Pagination current={parseInt(page)} total={data?.total ?? 0} onChange={setPage} />
    </div>
  );
}
```

```tsx
// ❌ Wrong — duplicating server state in useState
"use client";

export function DrugList() {
  const [drugs, setDrugs] = useState([]);

  useEffect(() => {
    DrugService.paged(1, 20).then((r) => setDrugs(r.data));  // no cache, no dedup, no error state
  }, []);
}
```

---

## React Context — Global Client State

Use Context only for state that is:
1. Needed by many components at different nesting levels
2. Not server data (that belongs in React Query)
3. Not derivable from the URL

Current user and theme are the canonical examples. Avoid putting derived or fetched data in Context — it becomes a second cache that diverges from React Query.

```tsx
// src/providers/user-provider.tsx
"use client";

import { createContext, useContext, useState, useEffect } from "react";
import { decodeToken } from "@/lib/jwt";
import { cookieStore } from "@/lib/cookies";

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
  drugs: [],            // server data — belongs in React Query
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

The URL becomes `/en/admin/drugs?q=paracetamol&page=2` — shareable, bookmarkable, survives hard refresh.

**When NOT to use nuqs:**
- Ephemeral UI state (modal open/closed, hover) — `useState`
- Auth state — `UserContext`
- Multi-step wizard state shared between steps but not in the URL — `useState` in a parent or React Query with a `draft` mutation

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
Is this data fetched from the server?
  → YES → React Query (useQuery / useMutation)

Is this state needed by many unrelated components?
  → YES → Context (useContext + Provider) — only for truly global state (user, theme)

Should the state appear in the URL / survive page refresh / be shareable?
  → YES → nuqs (useQueryState)

Is it only used within one component or a small tree?
  → YES → useState
```

---

## Combining All Four

A realistic page uses all four types simultaneously:

```tsx
// app/[lang]/(private)/admin/drugs/page.tsx (Server Component)
export default async function DrugsPage() {
  const initialDrugs = await DrugService.paged(1, 20);  // server state for initial render
  return <DrugListClient initialData={initialDrugs} />;
}

// components/app/drug-list-client.tsx
"use client";
export function DrugListClient({ initialData }: { initialData: PaginationResponse<DrugDataItem> }) {
  const { user } = useUser();                         // Context — current user
  const [search, setSearch] = useQueryState("q");     // nuqs — URL state
  const [modalOpen, setModalOpen] = useState(false);  // useState — ephemeral UI

  const { data } = useQuery({                         // React Query — server state with cache
    queryKey: ["drugs", "paged", search],
    queryFn: () => DrugService.paged(1, 20, search ?? ""),
    initialData,                                      // avoid first-load spinner
  });
  // ...
}
```

`initialData` in `useQuery` hydrates the cache from the server — the page renders with data instantly, and React Query takes over for subsequent interactions.

---

## Quick Checklist

- [ ] Server data (from the API) is in React Query — never duplicated in `useState`
- [ ] Context is used only for truly global client state (user, theme) — not for data that comes from the server
- [ ] URL-related state (filters, page, active tab) uses `nuqs` `useQueryState`
- [ ] Ephemeral UI state (open/closed, hover, animation) stays in `useState`
- [ ] `initialData` is passed to `useQuery` from Server Components to avoid loading flashes
- [ ] `queryClient.invalidateQueries` is called after mutations to keep the cache consistent
- [ ] Context providers are at the root layout level — not wrapping individual pages
