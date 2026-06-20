// Description: Server Component — async data fetch, no client JS, server-side auth cookie
// ─────────────────────────────────────────────────────────────────────────────
// PATTERN: Server Components are async functions. They await service calls
// directly. The page arrives fully rendered — no loading spinner, no
// useEffect, no client-side fetch.
//
// Auth: cookies() from next/headers reads the HttpOnly cookie server-side
// and forwards it to the backend. The client never sees the token value.
// ─────────────────────────────────────────────────────────────────────────────
// File location: app/[lang]/(private)/admin/drugs/page.tsx
// NO "use client" directive — this runs on the server only.
// ─────────────────────────────────────────────────────────────────────────────

import { cookies } from "next/headers";
import { Suspense } from "react";
import type { DrugDataItem, PaginationResponse } from "@/services/drugs";
import { DrugTable } from "@/components/app/drug-table";
import { DrugSearchClient } from "@/components/app/drug-search-client";

// ── Server-side fetch helper ──────────────────────────────────────────────────
// Reads the HttpOnly cookie server-side and forwards it to the backend.
// Cannot use the client-side authApi here (it references window.location).

async function serverFetch<T>(path: string): Promise<T> {
  const cookieStore = await cookies();
  const token = cookieStore.get("x-access-token")?.value;

  const res = await fetch(`${process.env.API_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      // Forward cookie as Authorization — backend accepts either form
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    cache: "no-store",   // always fresh for authenticated data
  });

  if (!res.ok) throw new Error(`API ${res.status} for ${path}`);
  return res.json() as Promise<T>;
}

// ── Page (Server Component) ───────────────────────────────────────────────────

// searchParams is provided by Next.js — typed, server-side only
type PageProps = {
  params: { lang: string };
  searchParams: { page?: string; q?: string };
};

export default async function DrugsPage({ params, searchParams }: PageProps) {
  const page = Math.max(1, parseInt(searchParams.page ?? "1", 10));
  const query = searchParams.q ?? "";

  const drugs = await serverFetch<PaginationResponse<DrugDataItem>>(
    `/drugs?page=${page}&size=20${query ? `&q=${encodeURIComponent(query)}` : ""}`
  );

  return (
    <div className="flex flex-col gap-6 p-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Drugs</h1>
        {/* Client Component passed as child — valid Server→Client composition */}
        <DrugSearchClient initialQuery={query} />
      </header>

      {/* DrugTable is a Server Component — receives data as props, renders HTML */}
      <DrugTable data={drugs.data} />

      <Pagination current={page} total={drugs.total} size={20} />
    </div>
  );
}

// ── Stats card — another Server Component, receives pre-fetched data ──────────

type StatsCardProps = {
  label: string;
  value: number;
};

export function StatsCard({ label, value }: StatsCardProps) {
  // Pure render — no hooks, no async, no interactivity
  return (
    <div className="rounded-lg border p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-3xl font-bold">{value.toLocaleString()}</p>
    </div>
  );
}

// ── Pagination — Server Component with links (no JS needed) ──────────────────

type PaginationProps = {
  current: number;
  total: number;
  size: number;
};

function Pagination({ current, total, size }: PaginationProps) {
  const totalPages = Math.ceil(total / size);

  // Server Component navigation — plain <a> tags, no JS
  return (
    <nav className="flex gap-2">
      {current > 1 && (
        <a href={`?page=${current - 1}`} className="btn-outline">
          Previous
        </a>
      )}
      <span className="py-2 px-4 text-sm text-muted-foreground">
        Page {current} of {totalPages}
      </span>
      {current < totalPages && (
        <a href={`?page=${current + 1}`} className="btn-outline">
          Next
        </a>
      )}
    </nav>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ANTI-PATTERNS:
//
// 1. "use client" on a page just to fetch data:
//
//   "use client"
//   export default function DrugsPage() {
//     const [drugs, setDrugs] = useState([]);
//     useEffect(() => { DrugService.paged(1,20).then(r => setDrugs(r.data)); }, []);
//     if (!drugs.length) return <Spinner />;   // ← flash of empty state
//     ...
//   }
//   → Adds React state machinery to a page that only needs to display data.
//     Use a Server Component and await the service call directly.
//
// 2. Hardcoding auth token in server fetch:
//
//   headers: { Authorization: "Bearer hardcoded-token" }  ← exposes secret
//   → Always read the token from cookies() or environment variables.
//
// 3. Using client-side authApi in a Server Component:
//
//   const drugs = await authApi(...)   ← authApi references window.location (browser only)
//   → Use serverFetch() in Server Components; authApi() in Client Components.
// ─────────────────────────────────────────────────────────────────────────────
