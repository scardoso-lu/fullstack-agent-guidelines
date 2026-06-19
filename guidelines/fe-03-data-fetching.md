# Data Fetching — Services, React Query, and Server Components

Every data fetch in the app goes through one of two paths: a **Server Component** fetching directly via a service function, or a **Client Component** fetching through React Query. Raw `fetch()` calls in components are never acceptable — they bypass error handling, type safety, and the shared auth layer.

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

## React Query — Client-Side Fetching

Use React Query when:
- The data changes based on user interaction (search, filters)
- The data needs polling or background refresh
- You need optimistic updates after mutations

### `QueryProvider` Setup

```tsx
// src/providers/query-provider.tsx
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: { staleTime: 60_000, retry: 1 },
    },
  }));

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
```

### `useQuery` — Read

```tsx
// components/app/drug-search.tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { DrugService } from "@/services/drugs";

export function DrugSearch({ initialQuery }: { initialQuery: string }) {
  const [query, setQuery] = useState(initialQuery);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["drugs", "search", query],
    queryFn: () => DrugService.searchSuggestions(query),
    enabled: query.length > 2,   // don't fire on short queries
    staleTime: 30_000,
  });

  return (
    <div>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search drugs..."
      />
      {isLoading && <p>Searching...</p>}
      {isError && <p>Failed to load results.</p>}
      {data?.map((drug) => (
        <div key={drug.id}>{drug.inn}</div>
      ))}
    </div>
  );
}
```

### `useMutation` — Write

```tsx
// components/app/drug-delete-button.tsx
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DrugService } from "@/services/drugs";

export function DrugDeleteButton({ drugId }: { drugId: number }) {
  const queryClient = useQueryClient();

  const { mutate, isPending } = useMutation({
    mutationFn: (id: number) => DrugService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["drugs"] });  // refetch list
    },
  });

  return (
    <button onClick={() => mutate(drugId)} disabled={isPending}>
      {isPending ? "Deleting…" : "Delete"}
    </button>
  );
}
```

**`queryKey` convention:**
```ts
["drugs"]                          // all drug queries
["drugs", "search", query]         // specific search query
["drugs", "detail", id]            // single item
["drugs", "paged", page, size]     // paginated list
```

Invalidating `["drugs"]` clears all drug-related cache entries.

---

## Anti-Pattern: Raw Fetch in useEffect

```tsx
// ❌ WRONG — never fetch in useEffect
"use client";

export function DrugList() {
  const [drugs, setDrugs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/drugs")                 // no error handling, no caching
      .then((r) => r.json())
      .then(setDrugs)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading...</div>;
  return drugs.map((d) => <div key={d.id}>{d.inn}</div>);
}
```

Problems: no error state, no deduplication, no cache, no loading UX beyond a spinner, doesn't cancel on unmount. Use React Query or a Server Component instead.

---

## Quick Checklist

- [ ] All `fetch()` calls are in `services/<domain>.ts`, never inside components or pages
- [ ] `authApi()` is used for authenticated requests; `api()` for public (login, register)
- [ ] Return type annotations are present on every service method (`Promise<DrugDataItem[]>`)
- [ ] Server Components fetch data directly via services — no `useEffect`, no loading state
- [ ] React Query is used for interactive, user-driven, or polling data — not raw `fetch` in `useEffect`
- [ ] `queryKey` arrays follow the `[entity, operation, params]` hierarchy
- [ ] Mutations call `queryClient.invalidateQueries` on success to keep the UI consistent
