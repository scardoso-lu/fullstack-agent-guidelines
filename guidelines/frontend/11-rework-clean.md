# Write Only What the Task Needs

> "The best code is the code you never wrote."

Applies to all code — new components, targeted fixes, and changes to existing code. Covers the decision ladder, ponytail: comment convention, and anti-patterns — deprecated props, v2 components, stale React Query keys, optional Zod fields.

AI agents over-build. Given a task, they install packages, create wrapper components, add compatibility layers, and preserve old implementations "for safety." The result is 5× more code than necessary, slower builds, and a component tree the user can no longer navigate.

This guideline addresses three failure modes that compound each other:

1. **Over-building new features** — writing a generic abstraction when a specific component or hook would do
2. **Over-touching existing code** — refactoring, cleaning, or "improving" code adjacent to the task when only a targeted change was asked for
3. **Backwards-compatibility accumulation during reworks** — keeping old code alongside new code when the user has explicitly narrowed the requirement

The task is narrow → the implementation must be equally narrow. This is the core principle.

---

## The Decision Ladder

Before writing any code, stop at the **first rung that holds**:

```
1. Does this need to exist?                  → Skip it (YAGNI)
2. Does the browser or Next.js do it natively? → Use that
3. Is it a native React feature?             → Use that
4. Is it already installed?                  → Use that
5. Can it be one component or one hook?      → Write that
6. Only then: the minimum that works
```

Apply this ladder **at every coding decision point** — not just at the start of a task. Each new component, each new hook, each new import triggers the same check.

### What the ladder prevents

| Requested task | Agent default | Correct answer |
|---|---|---|
| Email field validation | Install `validator.js`, write `EmailInput` with regex + MX-check wrapper | `z.string().email()` — Zod is already installed |
| Debounced search input | Write `useDebounce` hook, `DebouncedInput` component, config file | `useCallback` + `setTimeout` — 3 lines, no install |
| Auth token check | Install `jwt-decode`, write `TokenManager` class with cache, event emitter | `JSON.parse(atob(token.split(".")[1]))` — one line |
| Modal state | Install `zustand` or `jotai`, create `modalSlice` | `useState(false)` — already in React |

---

## Non-Negotiable Safeguards

Minimizing code **never** means cutting these:

- **Form validation** — every user-submitted field validated with Zod
- **Auth guards** — middleware or layout-level checks for protected routes
- **Error boundaries** — per route segment (`error.tsx`)
- **Accessibility attributes** — `aria-*`, `role`, keyboard nav, focus management
- **Loading and error states** — every React Query call has `isPending` and `isError` paths

The goal is code that is small because it is **necessary**, not artificially compressed.

---

## The `ponytail:` Comment Convention

When a deliberate simplification has a known limitation, mark it inline:

```tsx
// ponytail: linear filter — fine for <50 items; replace with server-side search if list grows
const filtered = drugs.filter((d) =>
  d.inn.toLowerCase().includes(query.toLowerCase())
);
```

This makes the trade-off visible and the upgrade path explicit, without adding premature complexity now.

---

## Over-Touching Existing Code

A bug fix fixes the bug. A prop rename renames the prop. A style tweak changes the style. The task scope is the change scope — nothing else.

Agents routinely do more than asked: rename surrounding variables "for clarity," extract hooks "while they're in there," reformat JSX, upgrade adjacent patterns. Every untasked touch is:

- A diff that obscures the real change
- A potential regression in working code
- Work the user did not ask for and cannot easily review

### Anti-pattern: Cleanup While Fixing

```tsx
// Task: fix the loading state not showing on the drug list
// ❌ WRONG — agent fixes the bug AND restructures the component
export function DrugList({ drugs, isLoading }: DrugListProps) {
  // Agent also: renamed drugList → drugs, extracted DrugListItem component,
  // added key prop comment, reformatted JSX, removed "unnecessary" fragment
  if (isLoading) return <Spinner />;  // bug fixed here
  return (
    <ul>
      {drugs.map((drug) => (
        <DrugListItem key={drug.id} drug={drug} />  // extracted by agent, not requested
      ))}
    </ul>
  );
}
```

```tsx
// ✅ CORRECT — one change, nothing else touched
export function DrugList({ drugList, loading }: DrugListProps) {
  if (loading) return <Spinner />;  // was missing — added
  return (
    <ul>
      {drugList.map((drug) => (
        <li key={drug.id}>{drug.inn}</li>
      ))}
    </ul>
  );
}
```

### Rule

Change exactly what the task describes. Leave everything else exactly as it was — including formatting, naming, and structure you personally dislike. If you notice a separate problem, flag it in your reply; do not fix it silently.

---

## Backwards-Compatibility Accumulation — The Rework Problem

When a user reworks a component or hook, they are narrowing the requirement. The agent must narrow the code too — **not preserve the old breadth alongside the new implementation**.

The correct rule: **when you rework something, delete the old thing in the same commit. Update every usage site. Merge nothing that leaves both paths alive.**

### Anti-pattern: Legacy Prop Left on a Component

```tsx
// ❌ WRONG — old props kept "for backwards compatibility with existing callers"
type DrugCardProps = {
  drug: DrugDataItem;
  // @deprecated — use drug.inn directly
  drugName?: string;
  // @deprecated — use drug.atc_code directly
  atcCode?: string;
};

export function DrugCard({ drug, drugName, atcCode }: DrugCardProps) {
  const name = drugName ?? drug.inn;       // compatibility fallback
  const code = atcCode ?? drug.atc_code;  // compatibility fallback
  return <div>{name} — {code}</div>;
}
```

```tsx
// ✅ CORRECT — rework replaces; all callers updated in the same PR
type DrugCardProps = { drug: DrugDataItem };

export function DrugCard({ drug }: DrugCardProps) {
  return <div>{drug.inn} — {drug.atc_code}</div>;
}
// All callers updated: <DrugCard drug={drug} /> — no drugName or atcCode props
```

### Anti-pattern: v2 Component Next to v1

```tsx
// ❌ WRONG — both components exist; callers pick one; the old one never gets removed
export function LoginForm() { /* old version with manual useState */ }
export function LoginFormV2() { /* new version with react-hook-form */ }
```

```tsx
// ✅ CORRECT — one component; all usages updated; LoginFormV2 was only the name while building
export function LoginForm() { /* react-hook-form — the only version */ }
// LoginFormV2 file deleted.
```

### Anti-pattern: Conditional Flag to Switch Behaviour

```tsx
// ❌ WRONG — "temporary" flag that controls which implementation runs
type DrugListProps = {
  drugs: DrugDataItem[];
  useNewPagination?: boolean;   // "temporary" — will never be removed
};

export function DrugList({ drugs, useNewPagination = false }: DrugListProps) {
  if (useNewPagination) {
    return <NewPaginatedDrugList drugs={drugs} />;
  }
  return <OldScrollingDrugList drugs={drugs} />;  // old path kept for "safety"
}
```

```tsx
// ✅ CORRECT — one implementation; old component deleted
export function DrugList({ drugs }: { drugs: DrugDataItem[] }) {
  return <NewPaginatedDrugList drugs={drugs} />;
}
// OldScrollingDrugList deleted. useNewPagination prop deleted.
```

### Anti-pattern: Compatibility Wrapper That Becomes Permanent

```tsx
// ❌ WRONG — wrapper added "during migration" that was never removed
// TODO: remove once all callers use <DrugCard drug={...} /> directly
function LegacyDrugCardWrapper({ id, name, atc }: { id: number; name: string; atc: string }) {
  return <DrugCard drug={{ id, inn: name, atc_code: atc, form: "", strength: "" }} />;
}
```

```tsx
// ✅ CORRECT — callers updated to pass a DrugDataItem; wrapper deleted
// (nothing — the wrapper never needed to exist if callers were updated in the same PR)
```

### Anti-pattern: Dead Query Keys and Stale React Query State

```tsx
// ❌ WRONG — old query key kept alongside new one after renaming
const { data } = useQuery({
  queryKey: ["drug-list", page],        // old key — still in cache, still invalidated
  // queryKey: ["drugs", "paged", page], // new key — agent added both "just in case"
  queryFn: () => DrugService.paged(page, 20),
});

// And in the mutation:
queryClient.invalidateQueries({ queryKey: ["drug-list"] });   // old
queryClient.invalidateQueries({ queryKey: ["drugs"] });        // new — both invalidated
```

```tsx
// ✅ CORRECT — one key, consistently used everywhere after renaming
const { data } = useQuery({
  queryKey: ["drugs", "paged", page],
  queryFn: () => DrugService.paged(page, 20),
});
// "drug-list" references fully removed — grep confirms zero occurrences
```

### Anti-pattern: Commented-Out JSX

```tsx
// ❌ WRONG
export function DrugForm() {
  return (
    <form>
      {/* Old fields — kept for reference
      <input name="legacy_name" />
      <input name="legacy_code" />
      */}
      <input name="inn" />
      <input name="atc_code" />
    </form>
  );
}
```

Delete it. Git history is the reference.

### Anti-pattern: Deprecated Service Method Left Alive

```ts
// ❌ WRONG — old method kept "for callers that haven't migrated"
export const DrugService = {
  // @deprecated — use paged(page, size, query)
  list: () => authApi<DrugDataItem[]>(`${BASE}/drugs`),
  paged: (page: number, size: number, query?: string) =>
    authApi<PaginationResponse<DrugDataItem>>(`${BASE}/drugs?page=${page}&size=${size}`),
};
```

```ts
// ✅ CORRECT — old method removed; every caller updated to use paged()
export const DrugService = {
  paged: (page: number, size: number, query?: string) =>
    authApi<PaginationResponse<DrugDataItem>>(`${BASE}/drugs?page=${page}&size=${size}`)
      .then((r) => r.json()),
};
// DrugService.list() deleted. All callers updated. Zero occurrences in codebase.
```

### Anti-pattern: Optional Zod Field After Form Field Removed

```ts
// ❌ WRONG — old field kept as optional "so existing form data isn't rejected"
const DrugSchema = z.object({
  inn: z.string().min(2),
  atc_code: z.string(),
  legacy_sku: z.string().optional(),   // field removed from the form — kept "for safety"
});
```

```ts
// ✅ CORRECT — field removed from schema; DB migration removes the column too
const DrugSchema = z.object({
  inn: z.string().min(2),
  atc_code: z.string(),
});
// legacy_sku removed from schema, from the API payload, and from the DB column.
```

---

## The Rework Workflow

```
1. Understand the NEW requirement exactly — what it does, what it no longer does.
2. Implement the narrow new version.
3. Update EVERY usage site (components, pages, hooks, services).
4. DELETE the old component/hook/type, its CSS module, its test, its story.
5. Run build + tests. Fix any breakage. Commit everything together.
```

Steps 3–4 are what agents skip. They implement step 2 and stop, leaving the old version "for existing callers to use." The callers never migrate — both paths rot in parallel.

---

## Rules Summary

Adapted from the Lazy Senior Developer principle:

- **No abstractions that weren't explicitly requested**
- **No new dependency if the browser, Next.js, React, or an installed package already does it**
- **No boilerplate nobody asked for**
- **Deletion over addition**
- **Boring over clever**
- **Minimize file count** — the correct number of files is the minimum that keeps concerns separated
- **Touch only what the task requires** — do not rename, reformat, or refactor adjacent code
- **When a requirement is narrowed, the component is narrowed** — not kept broad "for compatibility"
- **No TODO: remove old component** — remove it now, or don't merge

---

## Quick Checklist

- [ ] Decision ladder walked before writing anything: does this need to exist? browser native? React native? installed? one component?
- [ ] `ponytail:` comment added for any deliberate simplification with a known upgrade path
- [ ] Only code required by the task was changed — no adjacent renames, reformats, or refactors
- [ ] Reworked component replaces the old one in the same commit — no parallel versions
- [ ] Deprecated props removed; all call sites updated before merging
- [ ] No `useNewVersion?: boolean` flags — pick one implementation and delete the other
- [ ] No "TODO: remove legacy component" comments — remove it now or don't merge
- [ ] No commented-out JSX — git history is the reference
- [ ] Service methods removed when their endpoint is removed — no `@deprecated` methods left alive
- [ ] React Query `queryKey` renamed everywhere at once — grep confirms zero old occurrences
- [ ] Zod schema field removed when the form field is removed — not kept as `optional()`
- [ ] Component narrowed by the user → component props narrowed in code, not expanded with "also accept old shape"
- [ ] Validation, auth guards, error boundaries, accessibility, and loading states are intact — minimizing never touches these
