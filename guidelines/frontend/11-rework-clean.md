---
model: sonnet
effort: high
---

# Rework & Refactor Clean

> "The best code is the code you never wrote."

Applies when changing *existing* code — bug fixes, targeted edits, and reworks that narrow a requirement. Covers over-touching, backwards-compatibility accumulation, and the rework workflow. For net-new code — new components, new routes — see `frontend/20-feature-discipline` (decision ladder, `ponytail:` convention).

AI agents over-touch. Given a bug fix, they rename props "for clarity," extract hooks "while they're in there," and preserve deprecated props "for safety." The result is a diff that obscures the real change, regressions in working components, and a codebase accumulating dead code paths.

This guideline addresses two failure modes:

1. **Over-touching existing code** — refactoring, cleaning, or "improving" code adjacent to the task when only a targeted change was asked for
2. **Backwards-compatibility accumulation during reworks** — keeping old code alongside new code when the user has explicitly narrowed the requirement

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

### Anti-pattern: Dead Cache Tags After Renaming

```ts
// ❌ WRONG — old cache tag kept alongside the new one after renaming
// in the Server Component:
const drugs = await fetch(`${API}/drugs`, {
  next: { tags: ["drug-list", "drugs"] },   // old + new — agent added both "just in case"
});

// in the Server Action:
revalidateTag("drug-list");                  // old
revalidateTag("drugs");                      // new — both invalidated, both kept alive
```

```ts
// ✅ CORRECT — one tag, consistently used everywhere after renaming
const drugs = await fetch(`${API}/drugs`, { next: { tags: ["drugs"] } });

// ...and in the Server Action:
revalidateTag("drugs");
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

- **Touch only what the task requires** — do not rename, reformat, or refactor adjacent code
- **When a requirement is narrowed, the component is narrowed** — not kept broad "for compatibility"
- **Deletion over addition**
- **No TODO: remove old component** — remove it now, or don't merge
- **No `useNewVersion?: boolean` flags** — pick one implementation and delete the other
- **No commented-out JSX** — git history is the reference

---

## Quick Checklist

- [ ] Only code required by the task was changed — no adjacent renames, reformats, or refactors
- [ ] Reworked component replaces the old one in the same commit — no parallel versions
- [ ] Deprecated props removed; all call sites updated before merging
- [ ] No `useNewVersion?: boolean` flags — pick one implementation and delete the other
- [ ] No "TODO: remove legacy component" comments — remove it now or don't merge
- [ ] No commented-out JSX — git history is the reference
- [ ] Service methods removed when their endpoint is removed — no `@deprecated` methods left alive
- [ ] Cache tags (`next: { tags: [...] }` + `revalidateTag(...)`) renamed everywhere at once — grep confirms zero old occurrences
- [ ] Zod schema field removed when the form field is removed — not kept as `optional()`
- [ ] Component narrowed by the user → component props narrowed in code, not expanded with "also accept old shape"
- [ ] Validation, auth guards, error boundaries, accessibility, and loading states are intact — minimizing never touches these
