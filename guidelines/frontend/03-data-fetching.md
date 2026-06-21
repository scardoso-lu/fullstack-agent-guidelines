# Data Fetching — Services, Server Components, and Server Actions

Use when fetching or mutating data in a page or component. Covers the service layer (only services call fetch()), Server Component direct-await for reads, Server Actions for writes with tag-based revalidation, and the (rare) case where a Client Component genuinely needs to fetch (debounced search, polling).

Every data fetch in the app goes through one of two paths: a **Server Component** fetching directly via a service function, or — only when the data is genuinely client-driven — a **Client Component** with `fetch` + `AbortController`. Raw `fetch()` calls in components are never acceptable — they bypass error handling, type safety, and the shared auth layer.

---

## The Service Layer (`src/services/`)

All API calls live in `src/services/`. A service file exports a plain object with static async methods — no classes, no instantiation. The core building blocks live in `src/services/api.ts`.

### `api.ts` — Base Fetch Wrappers

```ts
// src/services/api.ts

export type TypedResponse<T> = Response & {
  json(): Promise<T>;
};

export type PaginationResponse<TData> = {
  data: TData[];
  total: number;
  page: number;
  size: number;
};

// Authenticated fetch — reads token from cookie, throws on 4xx/5xx
export async function authApi<T>(
  url: string,
  options: RequestInit = {}
): Promise<TypedResponse<T>> {
  const token = Cookies.get("x-access-token");

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  }) as TypedResponse<T>;

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new ApiError(response.status, (error as { detail?: string }).detail ?? "Request failed");
  }

  return response;
}

// Unauthenticated fetch — for public endpoints (login, register)
export async function api<T>(
  url: string,
  options: RequestInit = {}
): Promise<TypedResponse<T>> {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  }) as TypedResponse<T>;

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new ApiError(response.status, (error as { detail?: string }).detail ?? "Request failed");
  }

  return response;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}
```

### Domain Service File

```ts
// src/services/dashboard.ts
import { authApi, TypedResponse } from "./api";

type DashboardStats = {
  total_catalogs: { total: number };
  total_mappings: { total: number };
};

export const DashboardService = {
  async stats(cookies?: RequestCookies): Promise<DashboardStats> {
    // Server component path: pass cookies explicitly; browser path: cookies read automatically
    const url = `${process.env.NEXT_PUBLIC_API_URL}/dashboard/stats`;
    const res = await authApi<DashboardStats>(url);
    return res.json();
  },
};
```

```ts
// src/services/drugs.ts
import { authApi, PaginationResponse, TypedResponse } from "./api";

export type DrugDataItem = {
  id: number;
  inn: string;
  atc_code: string;
  form: string;
};

export const DrugService = {
  async paged(page: number, size: number): Promise<PaginationResponse<DrugDataItem>> {
    const url = `${process.env.NEXT_PUBLIC_API_URL}/drugs?page=${page}&size=${size}`;
    const res = await authApi<PaginationResponse<DrugDataItem>>(url);
    return res.json();
  },

  async getById(id: number): Promise<DrugDataItem> {
    const res = await authApi<DrugDataItem>(`${process.env.NEXT_PUBLIC_API_URL}/drugs/${id}`);
    return res.json();
  },

  async searchSuggestions(query: string): Promise<DrugDataItem[]> {
    const res = await authApi<DrugDataItem[]>(
      `${process.env.NEXT_PUBLIC_API_URL}/drugs/search?q=${encodeURIComponent(query)}`
    );
    return res.json();
  },
};
```

**Rules:**
- One service file per API domain (`dashboard.ts`, `drugs.ts`, `catalogs.ts`)
- Export a `PascalCase` object — `DrugService`, `DashboardService`
- Return typed data, never raw `Response`
- Never import a service directly in a page — pages call services, components receive props

---

## Server Component Fetching

For initial page data, fetch directly in the Server Component. No `useEffect`, no loading spinner:

```tsx
// app/[lang]/(private)/admin/drugs/page.tsx
import { DrugService } from "@/services/drugs";
import { DrugTable } from "@/components/app/drug-table";

export default async function DrugsPage() {
  const drugs = await DrugService.paged(1, 20);  // runs on server, zero client JS

  return (
    <div>
      <h1>Drugs</h1>
      <DrugTable initialData={drugs} />
    </div>
  );
}
```

The response arrives fully rendered — no loading state, no flash of empty content, good SEO and LCP.

---

## Mutations — Server Actions, not client fetch

Writes go through **Server Actions** (per `frontend/16-server-actions`). The Server Action lives next to the feature, re-verifies the actor server-side, validates the input with Zod, calls into the same service the API does, then `revalidateTag()` / `revalidatePath()` so any cached reads on the next render are fresh.

```ts
// app/(app)/drugs/_actions.ts
"use server";

import { revalidateTag } from "next/cache";
import { z } from "zod";

import { getActorFromCookie } from "@/lib/auth/actor";
import { DrugService } from "@/services/drugs";

const DeleteDrug = z.object({ id: z.coerce.number().int().positive() });

export async function deleteDrugAction(_prev: unknown, formData: FormData) {
  const actor = await getActorFromCookie();
  if (!actor) return { ok: false, error: "not signed in" } as const;

  const parsed = DeleteDrug.safeParse({ id: formData.get("id") });
  if (!parsed.success) return { ok: false, error: "invalid id" } as const;

  await DrugService.delete(parsed.data.id);
  revalidateTag("drugs");
  return { ok: true } as const;
}
```

```tsx
// components/app/drug-delete-button.tsx
"use client";

import { useActionState } from "react";
import { deleteDrugAction } from "@/app/(app)/drugs/_actions";

export function DrugDeleteButton({ drugId }: { drugId: number }) {
  const [state, formAction, isPending] = useActionState(deleteDrugAction, null);
  return (
    <form action={formAction}>
      <input type="hidden" name="id" value={drugId} />
      <button type="submit" disabled={isPending}>
        {isPending ? "Deleting…" : "Delete"}
      </button>
      {state?.error && <p role="alert">{state.error}</p>}
    </form>
  );
}
```

Pair the action with **tag-based revalidation** on the matching server fetches:

```ts
// in a Server Component
const drugs = await fetch(`${API}/drugs`, { next: { tags: ["drugs"] } });
```

After the action runs, `revalidateTag("drugs")` invalidates that fetch's cache; the next render serves fresh data. See `frontend/16-server-actions` for the non-negotiable inside-the-action checklist.

---

## Client-side reads — only when the data is genuinely client-driven

Reach for client-side `fetch` when the request depends on **post-mount** state (debounced typing, infinite scroll, a setting toggled at runtime) and even then keep it small and explicit:

```tsx
// components/app/drug-search.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { DrugService } from "@/services/drugs";

export function DrugSearch({ initialQuery }: { initialQuery: string }) {
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<Drug[]>([]);
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const ctrlRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (query.length < 3) { setResults([]); setState("idle"); return; }

    ctrlRef.current?.abort();
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;

    setState("loading");
    const timer = setTimeout(async () => {
      try {
        const data = await DrugService.searchSuggestions(query, { signal: ctrl.signal });
        if (!ctrl.signal.aborted) { setResults(data); setState("idle"); }
      } catch (err) {
        if ((err as Error).name !== "AbortError") setState("error");
      }
    }, 250);   // debounce

    return () => { clearTimeout(timer); ctrl.abort(); };
  }, [query]);

  return /* ... */;
}
```

Three things this gets right and nothing else:

1. **`AbortController`** — every in-flight fetch is aborted before the next one starts, and on unmount. No race conditions, no `setState` after unmount.
2. **A debounce** for typing-driven queries — typing "asp" should not fire three requests.
3. **Loading / error states are first-class** (per `frontend/14-loading-error-empty-states`), not an afterthought.

That's enough for the vast majority of client-driven cases. If a project finds itself rewriting this pattern across many features, extract a tiny in-repo hook (`useDebouncedFetch`) — don't add a library on the first occurrence. Any candidate library passes through `frontend/08-supply-chain` first.

---

## Anti-Pattern: Raw Fetch in useEffect for initial page data

```tsx
// ❌ WRONG — never fetch initial page data in useEffect
"use client";

export function DrugList() {
  const [drugs, setDrugs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/drugs")                 // no error handling, no abort, no cache
      .then((r) => r.json())
      .then(setDrugs)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading...</div>;
  return drugs.map((d) => <div key={d.id}>{d.inn}</div>);
}
```

Problems: no error state, no abort on unmount, flash of empty content, larger client bundle, worse LCP. Use a **Server Component** with `await service.list()` — that's what App Router exists for.

---

## Quick Checklist

- [ ] All `fetch()` calls are in `services/<domain>.ts`, never inside components or pages
- [ ] `authApi()` is used for authenticated requests; `api()` for public (login, register)
- [ ] Return type annotations are present on every service method (`Promise<DrugDataItem[]>`)
- [ ] Server Components fetch data directly via services — no `useEffect`, no loading state
- [ ] Mutations go through a **Server Action**, not a client-side fetch + cache-bust
- [ ] Server-side `fetch` calls tag their cache (`next: { tags: ["..."] }`) so Server Actions can revalidate them
- [ ] Client-side fetch (when truly needed) uses `AbortController` and a debounce; never for initial page data
