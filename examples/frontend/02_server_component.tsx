// Description: Server Component — async data fetch, no client JS, no loading state
// ─────────────────────────────────────────────────────────────────────────────
// PATTERN: Server Components are async functions. They await service calls
// directly. The page arrives fully rendered — no loading spinner, no
// useEffect, no client-side fetch.
// ─────────────────────────────────────────────────────────────────────────────
// File location: app/[lang]/(private)/admin/drugs/page.tsx
// NO "use client" directive — this runs on the server only.
// ─────────────────────────────────────────────────────────────────────────────

import { Suspense } from "react";
import { DrugService, type DrugDataItem, type PaginationResponse } from "@/services/drugs";
import { DrugTable } from "@/components/app/drug-table";   // can be Server or Client Component
import { DrugSearchClient } from "@/components/app/drug-search-client";  // Client Component

// ── Page (Server Component) ───────────────────────────────────────────────────

// searchParams is provided by Next.js — typed, server-side only
type PageProps = {
  params: { lang: string };
  searchParams: { page?: string; q?: string };
};

export default async function DrugsPage({ params, searchParams }: PageProps) {
  const page = parseInt(searchParams.page ?? "1", 10);
  const query = searchParams.q ?? "";

  // Direct service call — runs on server, not in the browser bundle
  const drugs = await DrugService.paged(page, 20, query);

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

// ── Pagination — Server Component with a link (no JS needed) ─────────────────

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
// ANTI-PATTERN — never convert a page to "use client" just to fetch:
//
//   "use client"
//   export default function DrugsPage() {
//     const [drugs, setDrugs] = useState([]);
//     useEffect(() => { DrugService.paged(1,20).then(r => setDrugs(r.data)); }, []);
//     if (!drugs.length) return <Spinner />;
//     ...
//   }
//
// This adds the entire React state machinery to a page that only needs
// to display data. Use a Server Component and await the service call.
// ─────────────────────────────────────────────────────────────────────────────
