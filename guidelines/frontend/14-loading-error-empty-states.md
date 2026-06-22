---
model: sonnet
effort: high
---

# Loading, Error, and Empty States — App Router Conventions

Use when building any page, route, or interactive component that depends on async data. Defines the four states **every** data-bound component must explicitly handle (loading, error, empty, success), Next.js App Router's purpose-built files (`loading.tsx`, `error.tsx`, `not-found.tsx`), Suspense boundary placement, and the rule that an unhandled state is a **DoD-blocking** finding — a vibecoded page that shows a flicker, a flash of "undefined", or a blank screen because the success state was the only one designed is incomplete.

The success state is the one developers (and AIs) think about. The other three are where most production UX bugs live: blank screens, dancing layouts, "Error: undefined", an empty page that should have said "no datasets yet". Make all four states explicit at design time.

## The rule

> Every data-bound page/component handles **four states** explicitly:
>
> 1. **Loading** — visible feedback that something is happening.
> 2. **Error** — a useful message and (if possible) a retry.
> 3. **Empty** — "nothing yet" with a clear next action.
> 4. **Success** — the data.
>
> A component that renders `data.map(...)` without first checking `isLoading`, `error`, and `data.length === 0` is incomplete.
>
> Use the App Router's purpose-built files (`loading.tsx`, `error.tsx`, `not-found.tsx`) for route-level states; use Suspense boundaries for sub-route states.

## The four states — what each one is for

```tsx
function DatasetList() {
  const { data, isPending, error, refetch } = useDatasets();

  if (isPending) return <DatasetListSkeleton />;
  if (error) return <DatasetListError error={error} onRetry={refetch} />;
  if (data.items.length === 0) return <DatasetListEmpty />;

  return (
    <ul>
      {data.items.map((d) => (
        <DatasetRow key={d.id} dataset={d} />
      ))}
    </ul>
  );
}
```

The order matters: **loading first**, then error, then empty, then success. If you check `data.length` before `isPending`, you get a "no datasets" flash before the data loads.

### Loading — skeleton over spinner (most of the time)

Pick the loading affordance based on **how long** and **how much**:

| Wait | Affordance |
|---|---|
| < ~200ms | Nothing. Don't show anything; the eye won't see it before the data arrives. |
| 200ms – ~2s | **Skeleton** — gray placeholders shaped like the eventual content. Preserves layout; no flash; the page feels instant. |
| > 2s | Skeleton **plus** a "Still loading..." after a delay; offer a cancel if the action is cancellable. |
| Unbounded (uploads, jobs) | Progress indicator with real progress, not an indeterminate spinner. |

```tsx
function DatasetListSkeleton() {
  return (
    <ul aria-busy="true" aria-live="polite">
      {Array.from({ length: 5 }).map((_, i) => (
        <li key={i} className="animate-pulse">
          <div className="h-4 w-1/2 rounded bg-gray-200" />
          <div className="mt-2 h-3 w-1/3 rounded bg-gray-200" />
        </li>
      ))}
    </ul>
  );
}
```

`aria-busy="true"` and `aria-live="polite"` tell assistive tech that the region is loading and that updates will arrive.

### Error — message + retry, not a dump

```tsx
function DatasetListError({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return (
    <div role="alert" className="rounded border border-red-300 bg-red-50 p-4">
      <h2 className="font-semibold text-red-900">Couldn't load datasets</h2>
      <p className="mt-1 text-sm text-red-800">
        {messageFor(error)}
      </p>
      <button
        onClick={onRetry}
        className="mt-3 rounded bg-red-600 px-3 py-1.5 text-sm text-white"
      >
        Try again
      </button>
    </div>
  );
}

function messageFor(error: unknown): string {
  if (isApiError(error) && error.status === 403) return "You don't have access to this list.";
  if (isApiError(error) && error.status === 429) return "Too many requests. Try again in a moment.";
  if (isApiError(error) && error.status === 503) return "Datasets are temporarily unavailable.";
  return "Something went wrong on our side. Try again, and contact support if it persists.";
}
```

Rules:

- **`role="alert"`** so screen readers announce it.
- **Map status codes to human messages** — never render `JSON.stringify(error)`.
- **Offer a retry** when the operation is idempotent (a GET; most are). Don't offer retry on a payment that may have succeeded — show "check the transactions page" instead.
- **Never display the raw error in production.** It leaks server details. Log it; show a sanitized message.

### Empty — "nothing yet" with a next action

The single most-missed state. An empty list is *not* a bug; it's a UX moment:

```tsx
function DatasetListEmpty() {
  return (
    <div className="rounded border-2 border-dashed p-8 text-center">
      <Database className="mx-auto h-10 w-10 text-gray-400" aria-hidden="true" />
      <h2 className="mt-2 font-semibold">No datasets yet</h2>
      <p className="mt-1 text-sm text-gray-600">
        Datasets are the basic unit of organization. Create your first one to get started.
      </p>
      <Link
        href="/datasets/new"
        className="mt-3 inline-flex items-center rounded bg-blue-600 px-3 py-1.5 text-sm text-white"
      >
        Create dataset
      </Link>
    </div>
  );
}
```

A blank list with no message is a vibecoding tell. Every empty state tells the user **why** the list is empty (new account, all-filtered-out, "no archived items") and **what to do next** (create, change filter, switch view).

### Success — what AIs always do; not the hard part

The data render is the only state most AI-generated components handle. With the other three in place, this becomes the *short* branch.

## App Router's purpose-built files

Next.js gives you four colocated files per route segment. Use them.

```
app/
└── (app)/
    └── datasets/
        ├── layout.tsx
        ├── loading.tsx        ← shown while the page Server Component is fetching
        ├── error.tsx          ← caught render/data errors for this segment
        ├── not-found.tsx      ← shown when notFound() is called
        └── page.tsx           ← the route content
```

### `loading.tsx` — Suspense fallback for the segment

```tsx
// app/(app)/datasets/loading.tsx
export default function DatasetsLoading() {
  return (
    <main aria-busy="true" aria-live="polite">
      <DatasetListSkeleton />
    </main>
  );
}
```

`loading.tsx` is **automatically** the Suspense fallback for the segment's `page.tsx`. You don't wrap anything; Next.js wires it. While `page.tsx` (or any nested Server Component) suspends on data, `loading.tsx` renders.

### `error.tsx` — must be a Client Component

```tsx
// app/(app)/datasets/error.tsx
"use client";
import { useEffect } from "react";

export default function DatasetsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Report to your observability platform, including error.digest.
    console.error(error);
  }, [error]);

  return (
    <div role="alert" className="m-6 rounded border border-red-300 bg-red-50 p-4">
      <h2 className="font-semibold text-red-900">Something went wrong</h2>
      <p className="mt-1 text-sm text-red-800">
        We couldn't load this page. Our team has been notified.
      </p>
      <button onClick={reset} className="mt-3 rounded bg-red-600 px-3 py-1.5 text-sm text-white">
        Try again
      </button>
    </div>
  );
}
```

Things to get right:

- **`"use client"`** — `error.tsx` always runs on the client (it has to handle thrown errors at runtime).
- **`error.digest`** — Next.js's hashed error ID; ship it to your error tracker, **not to the user**. The full message is server-only.
- **`reset()`** — re-renders the segment. Wire it to a retry button.

### `not-found.tsx` — for `notFound()`

```tsx
// app/(app)/datasets/[id]/not-found.tsx
export default function DatasetNotFound() {
  return (
    <div className="m-6">
      <h2 className="text-lg font-semibold">Dataset not found</h2>
      <p className="mt-1 text-sm text-gray-600">
        It may have been deleted, or you may not have access.
      </p>
      <Link href="/datasets" className="mt-3 inline-block underline">
        Back to datasets
      </Link>
    </div>
  );
}
```

```tsx
// app/(app)/datasets/[id]/page.tsx
import { notFound } from "next/navigation";

export default async function DatasetPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const dataset = await datasetService.findById(id);
  if (!dataset) notFound();
  return <DatasetView dataset={dataset} />;
}
```

`notFound()` throws an internal error that Next.js routes to `not-found.tsx`. Don't render "No dataset with id X" yourself; throw `notFound()` and let the dedicated file handle presentation.

### Tenant isolation note (security)

Per `backend/13-owasp-top10` (A01 Broken Access Control) and your project's security ADRs, a cross-tenant resource read is **not-found**, not 403. The use-case returns `None` for "exists but not yours"; the page calls `notFound()`. Same outcome, no information leak about resource existence.

## Suspense boundaries — granularity matters

`loading.tsx` is the boundary for the **whole segment**. If you want **independently-loading** sub-regions inside the same page (a sidebar + main content that fetch separately), wrap them in their own `<Suspense>`:

```tsx
// app/(app)/datasets/page.tsx — Server Component
import { Suspense } from "react";

export default async function DatasetsPage() {
  return (
    <main>
      <aside>
        <Suspense fallback={<DatasetFiltersSkeleton />}>
          <DatasetFilters />
        </Suspense>
      </aside>
      <section>
        <Suspense fallback={<DatasetListSkeleton />}>
          <DatasetList />
        </Suspense>
      </section>
    </main>
  );
}
```

Each `<Suspense>` boundary lets its child's data fetch independently — the filters appear when ready, the list appears when ready, neither blocks the other. **Use Suspense to stream UI**; don't await everything at the top of the page and show one big skeleton.

### Suspense vs `loading.tsx`

| Question | Answer |
|---|---|
| Whole page is loading? | `loading.tsx` — implicit Suspense at the segment boundary. |
| Sub-regions independent? | Explicit `<Suspense>` per region inside `page.tsx`. |
| Need shared loading? | Wrap them in **one** `<Suspense>`. |

## Client Components — manage state with the same shape

The four-state pattern applies inside Client Components too — Suspense is for Server Components, but the logical shape is identical:

```tsx
"use client";
function DatasetCreateForm() {
  const { mutate, isPending, error, isSuccess } = useCreateDataset();

  if (isSuccess) return <DatasetCreated />;
  if (isPending) return <DatasetCreatePending />;

  return (
    <form onSubmit={(e) => { e.preventDefault(); mutate(form); }}>
      {error && <FormError error={error} />}
      <fieldset disabled={isPending}>
        {/* fields */}
        <button type="submit">{isPending ? "Creating…" : "Create"}</button>
      </fieldset>
    </form>
  );
}
```

`<fieldset disabled={isPending}>` is the easiest way to lock the form during a write — covers inputs, selects, and the submit button in one attribute. Don't roll your own per-input `disabled` prop.

## The "I'll add it later" trap

Loading/error/empty states **always** get added later if they aren't there on day one — and "later" is usually production. The cost of adding all four when the component is being built is small; the cost of adding them after a bug report is large (you have to re-derive what each looks like with a screenshot in hand).

Build the four states **together** — sometimes literally side-by-side in Storybook or a `_demo` route — before the success state ships.

## Quick checklist

- [ ] Every data-bound component handles **loading, error, empty, success** explicitly.
- [ ] Loading uses a **skeleton** shaped like the content (not just a spinner), unless < 200ms.
- [ ] Error messages map status codes to **human messages** with a retry where it's safe.
- [ ] Empty states tell the user **why** it's empty and **what to do next**.
- [ ] Route-level: `loading.tsx`, `error.tsx`, `not-found.tsx` exist where relevant.
- [ ] `error.tsx` is `"use client"`; never displays the raw error message in production.
- [ ] Suspense boundaries wrap **independent** sub-regions inside a page.
- [ ] `notFound()` is called instead of rendering "not found" markup directly.
- [ ] A Playwright E2E opens the page with empty data and asserts the empty state renders without errors (per `qa/02-e2e-per-feature`).
