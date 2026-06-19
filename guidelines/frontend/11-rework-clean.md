# Rework Clean — The Ponytail Principle

When an AI agent reworks a component, hook, or service, it defaults to preserving the old implementation alongside the new one. The reasoning sounds safe: "keep the old one while the new one is proven." In practice it creates debt that never gets paid — dead props, compatibility wrappers, v2 components next to v1 components, and conditional render paths that outlive the migration indefinitely.

**The user narrows the concept → the agent widens the implementation. This is backwards.**

The [Ponytail principle](https://github.com/DietrichGebert/ponytail): the best code is code you never wrote. When you rework something, cut the old thing completely in the same change. A narrow, correct implementation that solves the actual problem beats a generalized one that tries to preserve all past behaviour.

---

## The Decision Ladder — Before Writing Anything

Before adding any new code, walk down this ladder:

1. **Does this need to exist?** — If the feature was removed or narrowed, delete code, don't replace it with a disabled stub.
2. **Does the browser or Next.js already do it natively?** — Use that; don't wrap it.
3. **Is there an existing installed dependency that solves it?** — Use that.
4. **Can it be one component or one hook?** — Write one. Not one per "variant".
5. **Only then:** implement the minimum that solves the current requirement.

Non-negotiable even when minimizing: form validation, auth guards, error boundaries, accessibility attributes.

---

## Anti-Patterns: What Accumulates

### Legacy Prop Left on a Component

```tsx
// ❌ WRONG — old prop kept "for backwards compatibility with existing callers"
type DrugCardProps = {
  drug: DrugDataItem;
  // @deprecated — use drug.inn directly
  drugName?: string;         // kept because "some callers still pass it"
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
// Old callers updated: <DrugCard drug={drug} /> — no drugName or atcCode props
```

### v2 Component Next to v1

```tsx
// ❌ WRONG — both components exist; callers pick one; the old one never gets removed
export function LoginForm() { /* old version with manual useState */ }
export function LoginFormV2() { /* new version with react-hook-form */ }
```

```tsx
// ✅ CORRECT — one component; all usages updated; LoginFormV2 was only the name while building it
export function LoginForm() { /* react-hook-form — the only version */ }
// LoginFormV2 file deleted.
```

### Conditional Flag to Switch Behaviour

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

### Compatibility Wrapper That Becomes Permanent

```tsx
// ❌ WRONG — wrapper added "during migration" that was never removed
// TODO: remove this once all callers use <DrugCard drug={...} /> directly
function LegacyDrugCardWrapper({ id, name, atc }: { id: number; name: string; atc: string }) {
  return <DrugCard drug={{ id, inn: name, atc_code: atc, form: "", strength: "" }} />;
}
```

```tsx
// ✅ CORRECT — callers updated to pass a DrugDataItem; wrapper deleted
// (nothing — the wrapper never needed to exist if callers were updated in the same PR)
```

### Dead Query Keys and Stale React Query State

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

### Commented-Out JSX

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

---

## The Correct Rework Workflow

```
1. Understand the NEW requirement exactly — what it does, what it no longer does.
2. Implement the narrow new version.
3. Update EVERY usage site (components, pages, hooks) to the new version.
4. DELETE the old component/hook/type, its CSS, its test, its story.
5. Run build + tests. Fix any breakage. Commit everything together.
```

Steps 3–4 are what AI agents skip. They implement step 2 and stop, leaving the old version "for existing callers to use." The callers never migrate — both paths rot in parallel.

---

## Applied to Services

When an API endpoint changes shape:

```ts
// ❌ WRONG — service keeps old method signature "for callers that haven't migrated"
export const DrugService = {
  // @deprecated — use paged(page, size, query)
  list: () => authApi<DrugDataItem[]>(`${BASE}/drugs`),          // old: returns flat array
  paged: (page: number, size: number, query?: string) =>         // new: returns pagination
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
// DrugService.list() — deleted. All callers updated. Zero occurrences in codebase.
```

---

## Applied to Zod Schemas

When a form field is removed:

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

## What NOT to Cut

The principle is about **dead paths**, not about correctness:

- Zod validation on every form field → always keep
- Auth guards in middleware → always keep
- Error boundaries → always keep
- Accessibility attributes (`aria-*`, `role`) → always keep
- Loading and error states in React Query → always keep

Removing a deprecated prop is not the same as removing a guard.

---

## Quick Checklist

- [ ] Reworked components replace the old one in the same commit — no parallel versions
- [ ] Deprecated props removed; all call sites updated before merging
- [ ] No `useNewVersion?: boolean` flags — pick one implementation and delete the other
- [ ] No "TODO: remove legacy component" comments — remove it now or don't merge
- [ ] No commented-out JSX — git history is the reference
- [ ] Service methods removed when their endpoint is removed — no `@deprecated` methods left alive
- [ ] React Query `queryKey` renamed everywhere at once — grep confirms zero old occurrences
- [ ] Zod schema field removed when the form field is removed — not kept as `optional()`
- [ ] Component narrowed by the user → component props narrowed in code, not expanded with "also accept old shape"
