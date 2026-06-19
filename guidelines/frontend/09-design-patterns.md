# Design Patterns for Next.js

Design patterns for React/Next.js are different from backend OOP patterns. The primitives are components, hooks, and context — not classes and interfaces. These patterns solve recurring composition problems.

---

## Component Patterns

### Compound Components — Shared Implicit State

A compound component is a group of components that share state through context rather than prop drilling. The parent owns the state; children consume it implicitly.

**Use case:** `<Tabs>`, `<Accordion>`, `<Select>`, `<Dropdown>`

```tsx
// components/ui/tabs.tsx
import { createContext, useContext, useState } from "react";

type TabsContext = { active: string; setActive: (t: string) => void };
const Ctx = createContext<TabsContext | null>(null);
const useTabsCtx = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error("Must be inside <Tabs>");
  return c;
};

// Root — owns the state
export function Tabs({
  defaultTab,
  children,
}: {
  defaultTab: string;
  children: React.ReactNode;
}) {
  const [active, setActive] = useState(defaultTab);
  return <Ctx.Provider value={{ active, setActive }}>{children}</Ctx.Provider>;
}

// List of tab triggers
export function TabList({ children }: { children: React.ReactNode }) {
  return <div role="tablist" className="flex gap-2">{children}</div>;
}

// Individual trigger — reads context, no prop drilling
export function Tab({ value, children }: { value: string; children: React.ReactNode }) {
  const { active, setActive } = useTabsCtx();
  return (
    <button
      role="tab"
      aria-selected={active === value}
      onClick={() => setActive(value)}
      className={active === value ? "border-b-2 border-primary" : ""}
    >
      {children}
    </button>
  );
}

// Panel — renders only when its tab is active
export function TabPanel({ value, children }: { value: string; children: React.ReactNode }) {
  const { active } = useTabsCtx();
  if (active !== value) return null;
  return <div role="tabpanel">{children}</div>;
}

// Usage — consumer controls composition, not the library
<Tabs defaultTab="overview">
  <TabList>
    <Tab value="overview">Overview</Tab>
    <Tab value="details">Details</Tab>
  </TabList>
  <TabPanel value="overview"><DrugOverview /></TabPanel>
  <TabPanel value="details"><DrugDetails /></TabPanel>
</Tabs>
```

---

### Container / Presenter (Smart / Dumb)

The Container fetches data and manages state. The Presenter receives props and renders — it is pure and testable in isolation.

In Next.js App Router this maps cleanly to Server/Client boundary:

```tsx
// Container — Server Component (data, async, no JS shipped)
// app/[lang]/(private)/admin/drugs/page.tsx
export default async function DrugsPage() {
  const drugs = await DrugService.paged(1, 20);       // data lives here
  return <DrugListView drugs={drugs.data} total={drugs.total} />;
}

// Presenter — pure render, easily tested
// components/app/drug-list-view.tsx
type DrugListViewProps = {
  drugs: DrugDataItem[];
  total: number;
};

export function DrugListView({ drugs, total }: DrugListViewProps) {
  return (
    <section>
      <p className="text-sm text-muted-foreground">{total} drugs found</p>
      {drugs.map((d) => (
        <DrugCard key={d.id} drug={d} />
      ))}
    </section>
  );
}
// Presenter is easy to test: render(<DrugListView drugs={[mock]} total={1} />)
```

---

### Provider Pattern — Global State Without Prop Drilling

Wrap the tree with a context provider; any descendant can read the value without receiving it as a prop. Already shown in `UserProvider` — the key point is providers belong at the root layout, not ad-hoc around individual pages.

```tsx
// src/app/layout.tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>
        <QueryProvider>       {/* React Query */}
          <UserProvider>      {/* Auth state */}
            <ThemeProvider>   {/* Dark/light mode */}
              {children}
            </ThemeProvider>
          </UserProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
```

**Anti-pattern:** wrapping each page individually creates multiple provider instances and breaks cache sharing.

---

## Hook Patterns

### Custom Hook — Extract Reusable Logic

A custom hook moves non-rendering logic out of components. The component calls a hook; the hook encapsulates the complexity.

```tsx
// hooks/use-drug-search.ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { useQueryState } from "nuqs";
import { DrugService } from "@/services/drugs";

export function useDrugSearch() {
  const [query, setQuery] = useQueryState("q", { defaultValue: "" });
  const [page, setPage] = useQueryState("page", { defaultValue: "1" });

  const { data, isLoading, isError } = useQuery({
    queryKey: ["drugs", "search", query, page],
    queryFn: () => DrugService.paged(parseInt(page, 10), 20, query),
    enabled: true,
    placeholderData: (prev) => prev,
  });

  return {
    query, setQuery,
    page: parseInt(page, 10), setPage: (p: number) => setPage(String(p)),
    data, isLoading, isError,
  };
}

// Component is now trivially simple
export function DrugSearchPage() {
  const { query, setQuery, data, isLoading } = useDrugSearch();

  return (
    <div>
      <input value={query} onChange={(e) => setQuery(e.target.value)} />
      {isLoading ? <Spinner /> : <DrugTable drugs={data?.data ?? []} />}
    </div>
  );
}
```

---

### Observer via React Query

React Query implements the Observer pattern. Multiple components subscribe to the same `queryKey` — when the cache updates, all subscribers re-render. No manual pub/sub needed.

```tsx
// Both components observe the same cache key
function DrugBadge({ id }: { id: number }) {
  const { data } = useQuery({ queryKey: ["drugs", "detail", id], queryFn: () => DrugService.getById(id) });
  return <span>{data?.inn}</span>;
}

function DrugHeader({ id }: { id: number }) {
  const { data } = useQuery({ queryKey: ["drugs", "detail", id], queryFn: () => DrugService.getById(id) });
  return <h1>{data?.atc_code}</h1>;
}
// Only ONE network request is made — both share the cached result
```

---

## Server Action Pattern — Command on the Server

Server Actions are the Command pattern applied to Next.js. They encapsulate a server-side mutation, can be called from any Client Component, and trigger cache revalidation.

```ts
// src/actions/drug.ts
"use server";

import { revalidatePath } from "next/cache";
import { DrugService } from "@/services/drugs";

export async function deleteDrugAction(drugId: number): Promise<void> {
  await DrugService.delete(drugId);
  revalidatePath("/en/admin/drugs");  // invalidate Next.js cache for this path
}
```

```tsx
// components/app/drug-delete-button.tsx
"use client";

import { deleteDrugAction } from "@/actions/drug";
import { useTransition } from "react";

export function DrugDeleteButton({ id }: { id: number }) {
  const [isPending, startTransition] = useTransition();

  return (
    <button
      disabled={isPending}
      onClick={() => startTransition(() => deleteDrugAction(id))}
    >
      {isPending ? "Deleting…" : "Delete"}
    </button>
  );
}
```

Server Actions are the preferred pattern for mutations that only need to invalidate the Next.js cache. Use React Query `useMutation` when you need optimistic updates or React Query cache invalidation.

---

## Adapter Pattern — Isolate Third-Party APIs

When a third-party library changes its API, you should change one file — not twenty components.

```ts
// lib/analytics.ts — your stable interface
type TrackEvent = (event: string, props?: Record<string, unknown>) => void;

// Adapter wraps the third-party SDK
export const analytics: { track: TrackEvent } = {
  track(event, props) {
    // Swap Mixpanel for PostHog here — no component changes
    if (typeof window === "undefined") return;
    window.posthog?.capture(event, props);
  },
};

// Usage — components depend on your interface, not PostHog
import { analytics } from "@/lib/analytics";
analytics.track("drug_viewed", { drug_id: drug.id });
```

---

## Strategy Pattern — Swappable Form Validation Rules

Validation strategy objects keep Zod schemas composable:

```ts
// Reusable validation building blocks — Strategy objects
const strategies = {
  email: z.string().email("Invalid email"),
  strongPassword: z
    .string()
    .min(8, "Min 8 characters")
    .regex(/[A-Z]/, "Must contain uppercase")
    .regex(/[0-9]/, "Must contain number"),
  atcCode: z.string().regex(/^[A-Z]\d{2}[A-Z]{2}\d{2}$/, "Invalid ATC code"),
};

// Compose schemas from strategies — no duplication
const RegisterSchema = z.object({
  email: strategies.email,
  password: strategies.strongPassword,
});

const ChangePasswordSchema = z
  .object({
    new_password: strategies.strongPassword,
    confirm: z.string(),
  })
  .refine((d) => d.new_password === d.confirm, {
    message: "Passwords must match",
    path: ["confirm"],
  });
```

---

## Anti-Patterns

### God Component
```tsx
// ❌ 300 lines: fetch, state, form, table, modal all in one component
export default function AdminPage() {
  const [drugs, setDrugs] = useState([]);
  const [formOpen, setFormOpen] = useState(false);
  const [formData, setFormData] = useState({ inn: "", atc: "" });
  useEffect(() => { fetch("/api/drugs").then(r => r.json()).then(setDrugs) }, []);
  // ... 250 more lines
}
```

Split into: Server Component for data → Container passes props → Presenter renders → Separate form component.

### Prop Drilling
```tsx
// ❌ Passing user through 5 levels of components
<Layout user={user}>
  <Sidebar user={user}>
    <Nav user={user}>
      <UserAvatar user={user} />
    </Nav>
  </Sidebar>
</Layout>

// ✅ Context — UserAvatar calls useUser() directly
```

---

## Quick Checklist

- [ ] Shared state between sibling components uses Compound Component (context) — not prop lifting + drilling
- [ ] Server Components act as Containers — they fetch and pass props to Presenters
- [ ] Presenters (Client Components) receive props only — no data fetching
- [ ] Non-rendering logic (queries, URL state) extracted into custom hooks
- [ ] Third-party SDKs wrapped behind an Adapter in `lib/` — components never import SDKs directly
- [ ] Reusable validation rules defined as Strategy objects — composed into form schemas
- [ ] Server Actions used for fire-and-forget mutations that only need path revalidation
