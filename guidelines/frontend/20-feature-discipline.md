---
model: sonnet
effort: high
---

# New Feature Discipline

> "The best code is the code you never wrote."

Applies when building new features, adding new routes, or writing net-new components or hooks. Covers the decision ladder, the `ponytail:` comment convention, and non-negotiable safeguards. For changes to *existing* code — reworks, refactors, bug fixes — see `frontend/11-rework-clean`.

AI agents over-build. Given a task, they install packages, create wrapper components, add compatibility layers, and preserve old implementations "for safety." The result is 5× more code than necessary, slower builds, and a component tree the user can no longer navigate.

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
| Email field validation | Install `validator.js`, write `EmailInput` with regex + MX-check wrapper | `z.string().email()` — Zod is already installed (see `frontend/04-forms-validation`) |
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
- **Loading and error states** — every data-bound component handles the four states (`frontend/14-loading-error-empty-states`)

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

## Rules Summary

- **No abstractions that weren't explicitly requested**
- **No new dependency if the browser, Next.js, React, or an installed package already does it**
- **No boilerplate nobody asked for**
- **Deletion over addition**
- **Boring over clever**
- **Minimize file count** — the correct number of files is the minimum that keeps concerns separated

---

## Quick Checklist

- [ ] Decision ladder walked before writing anything: does this need to exist? browser native? React native? installed? one component?
- [ ] `ponytail:` comment added for any deliberate simplification with a known upgrade path
- [ ] No new package installed when an existing one already covers it
- [ ] No wrapper component or custom hook added without a second concrete consumer
- [ ] Validation, auth guards, error boundaries, accessibility, and loading states are intact — minimizing never touches these
