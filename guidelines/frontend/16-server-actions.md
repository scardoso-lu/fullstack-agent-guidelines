# Server Actions — Auth, Validation, Revalidation, and Errors

Use when adding a mutation in a Next.js App Router project. Defines when to reach for a Server Action vs a Route Handler, the **non-negotiable inside-the-action checklist** (auth re-check, input validation, audit, no leaking server errors), the `revalidateTag` / `revalidatePath` semantics, the **return-errors-don't-throw** pattern for `useFormState`, and progressive enhancement.

Server Actions are public, callable POST endpoints with a friendly RPC syntax. Treat them as such — every concern that applies to a `POST` route applies to a Server Action: authentication, authorization, input validation, audit, error handling. The friendly syntax is a UX win; it is not a permission to skip the gate.

## The rule

> Every Server Action:
>
> 1. **Re-verifies the actor** inside the function body (cookie/session lookup) — never trusts a passed-in `userId`.
> 2. **Authorizes** the action via the project's permission check.
> 3. **Validates the input** with the same Zod schema the API would use — server-side, not just client-side.
> 4. **Calls into the same use-case layer** as the API. No duplicated business logic.
> 5. **Returns errors as data** (for `useFormState`) rather than throwing — except for genuine 500-class failures.
> 6. **Calls `revalidateTag`/`revalidatePath`** for any data the mutation invalidates.
> 7. **Never returns server internals** in the error payload.

## When to use a Server Action vs alternatives

| Use case | Use this |
|---|---|
| Mutate server state from a `<form>` (works without JS) | **Server Action** |
| Mutate server state from a complex client interaction (optimistic update, mid-form retry, polling) | **Route Handler** (`app/api/.../route.ts`) called from a small in-repo client hook (`fetch` + `AbortController`) |
| Submit programmatically with custom client logic | Same — Route Handler + in-repo client hook |
| Open a new resource via REST contract for external clients | **Route Handler** (Server Actions aren't a documented public API) |
| Pure server data fetch on render | Direct `await` in a Server Component (not an action) |

Server Actions shine for **form submits**. They struggle for **rich client-side flows** with optimistic state, retries, or background polling — for those, expose a Route Handler and drive it from a small client hook (`fetch` + `AbortController` + debounce as needed, per `frontend/03-data-fetching`).

## File layout — actions live with the feature

```
app/
└── (app)/
    └── datasets/
        ├── _actions.ts        ← server actions for this route (private to the route)
        ├── _components/
        ├── new/
        │   ├── _actions.ts
        │   └── page.tsx
        └── page.tsx
```

Or grouped per feature module (`features/datasets/server-actions.ts`). The `_` prefix keeps the file from being routable.

**One action per file** when an action is non-trivial. Multiple tiny related actions can share a file when they're cohesive (`create-dataset`, `update-dataset`, `archive-dataset` in one `dataset-actions.ts`).

> The `getActorFromCookie()` helper used below is the Server-Action equivalent of the client-side `useUser()` hook covered in `frontend/05-authentication`. It reads the httpOnly cookie via `next/headers`' `cookies()`, validates the token via `isTokenExpired()` from `src/lib/jwt`, and returns the decoded actor (or `null`). Build it once in `src/lib/auth/actor.ts` so every Server Action and route handler shares the same auth check.

## The skeleton — every Server Action follows it

```ts
// app/(app)/datasets/_actions.ts
"use server";

import { revalidateTag } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";
import { getActorFromCookie } from "@/lib/auth/actor";
import { datasetService } from "@/features/datasets/service";

// 1. Schema — server-validated even if the client validated too
const CreateDatasetSchema = z.object({
  name: z.string().min(1).max(120),
  description: z.string().max(2000).optional(),
});

export type CreateDatasetState =
  | { status: "idle" }
  | { status: "ok"; datasetId: string }
  | {
      status: "error";
      formError?: string;
      fieldErrors?: Partial<Record<keyof z.infer<typeof CreateDatasetSchema>, string>>;
    };

export async function createDataset(
  _prev: CreateDatasetState,
  formData: FormData,
): Promise<CreateDatasetState> {
  // 2. Re-verify the actor — never trust a passed-in id
  const actor = await getActorFromCookie();
  if (!actor) {
    return { status: "error", formError: "You must be signed in." };
  }

  // 3. Authorize via the project's permission check
  if (!actor.permissions.has("dataset.create")) {
    return { status: "error", formError: "You don't have permission to create datasets." };
  }

  // 4. Validate input — return errors as data, don't throw
  const parsed = CreateDatasetSchema.safeParse({
    name: formData.get("name"),
    description: formData.get("description"),
  });
  if (!parsed.success) {
    const fieldErrors: Record<string, string> = {};
    for (const issue of parsed.error.issues) {
      fieldErrors[issue.path[0] as string] = issue.message;
    }
    return { status: "error", fieldErrors };
  }

  // 5. Call into the same service the API uses — business logic lives there
  try {
    const dataset = await datasetService.create({
      actor,
      input: parsed.data,
    });

    // 6. Invalidate the caches this mutation affects
    revalidateTag("datasets");
    revalidateTag(`dataset:${dataset.id}`);

    // 7. Redirect (Server Action's natural finisher) OR return success state for useFormState
    redirect(`/datasets/${dataset.id}`);
  } catch (error) {
    // Domain errors → user-safe message; never the raw error.
    return { status: "error", formError: messageFor(error) };
  }
}
```

Every numbered step above is doing real work. Drop any one of them and the action is broken in a specific way:

- Skip **(2)** → unauthenticated user can mutate via direct POST.
- Skip **(3)** → permission bypass.
- Skip **(4)** → client validation alone; trivially bypassed.
- Skip **(5)** → business logic forks between the API and the action.
- Skip **(6)** → cached pages show stale data after the mutation.
- Skip **(7)** error mapping → the user sees a stack trace or a useless "Internal error".

## Return errors as data; throw only on genuine failures

```ts
// good — validation / domain errors return as state
if (!parsed.success) return { status: "error", fieldErrors };
if (await datasetService.nameTaken(parsed.data.name)) {
  return { status: "error", fieldErrors: { name: "Already taken." } };
}

// good — genuine 500-class failures throw → Next.js routes to error.tsx
try {
  await datasetService.create({...});
} catch (e) {
  if (isExpectedDomainError(e)) {
    return { status: "error", formError: messageFor(e) };
  }
  throw e;          // genuine bug — let error.tsx handle it
}
```

The split:

- **Expected / user-facing problems** (validation, permission denied, duplicate, not-found) → return state. The form re-renders with the errors; `error.tsx` doesn't trigger.
- **Unexpected / programmer errors** (the DB is down, a third-party API exploded, the code threw a `TypeError`) → throw. `error.tsx` catches it; the user sees a friendly "something went wrong" page; the error tracker gets the digest.

Mixing these is the most common Server-Action mistake — every error thrown means the user sees the segment's `error.tsx`, which is the wrong UX for "the name is too long."

## Wire it up — `useFormState` / `useActionState`

```tsx
// app/(app)/datasets/new/_components/create-dataset-form.tsx
"use client";

import { useActionState } from "react";
import { createDataset, type CreateDatasetState } from "../_actions";

const initial: CreateDatasetState = { status: "idle" };

export function CreateDatasetForm() {
  const [state, formAction, isPending] = useActionState(createDataset, initial);

  return (
    <form action={formAction}>
      {state.status === "error" && state.formError && (
        <p role="alert" className="text-sm text-red-700">{state.formError}</p>
      )}

      <fieldset disabled={isPending}>
        <label htmlFor="name">Name</label>
        <input
          id="name"
          name="name"
          type="text"
          required
          maxLength={120}
          aria-invalid={state.status === "error" && !!state.fieldErrors?.name}
          aria-describedby={state.fieldErrors?.name ? "name-error" : undefined}
        />
        {state.status === "error" && state.fieldErrors?.name && (
          <p id="name-error" role="alert" className="text-sm text-red-700">
            {state.fieldErrors.name}
          </p>
        )}

        <label htmlFor="description">Description (optional)</label>
        <textarea id="description" name="description" maxLength={2000} />

        <button type="submit">{isPending ? "Creating…" : "Create dataset"}</button>
      </fieldset>
    </form>
  );
}
```

What this gets right:

- **`useActionState`** wires the action; `state` reflects the latest return, `isPending` lets the UI disable the form during the submit.
- **`<fieldset disabled={isPending}>`** — single attribute disables every nested input and the submit button.
- **`aria-invalid` + `aria-describedby`** announce errors to screen readers (per `frontend/15-accessibility`).
- **No JS required to submit** — the form works with `action={formAction}`; the page just doesn't get the optimistic disable. Progressive enhancement for free.

## Progressive enhancement — design for the no-JS case

A Server Action attached to a `<form action={...}>` works **without JavaScript** — submit, server renders the next page, you're done. That's the headline feature. Don't break it:

- **`required`, `maxLength`, `type=`** for browser-side validation that works without JS.
- **Don't rely on a Client Component wrapper** for the form to function. Wrappers should *enhance* (disable on pending, optimistic UI) — the form should still work if the wrapper never hydrates.
- **Redirect-on-success** instead of "update this state to show a success banner" — works the same in both worlds.

If JS is required for the form to function, you've lost the progressive-enhancement win — expose a Route Handler and drive it from a small in-repo client hook (`fetch` + `AbortController`), and own the complexity explicitly.

## Revalidation — `revalidateTag` vs `revalidatePath`

Next.js's cache is **opt-in tagged**; revalidation invalidates entries.

```ts
// fetching — tag the cache so we can invalidate it later
const datasets = await fetch(`${API}/datasets`, {
  next: { tags: ["datasets"] },
});

// individual resource — tag with the id
const dataset = await fetch(`${API}/datasets/${id}`, {
  next: { tags: ["datasets", `dataset:${id}`] },
});
```

```ts
// inside the action — invalidate what the mutation touched
revalidateTag("datasets");                  // list views
revalidateTag(`dataset:${dataset.id}`);     // the resource itself
```

| Function | When to use |
|---|---|
| `revalidateTag("...")` | When the data is identified by a tag. **Default**. Targets exactly what was mutated; cheap. |
| `revalidatePath("/datasets")` | When you don't tag-cache but want to revalidate all data on a route. Heavier. |
| `revalidatePath("/datasets", "layout")` | Revalidate the whole layout subtree. Use sparingly. |

**Prefer tag-based revalidation.** It's surgical; path-based is the blunt instrument when tags weren't set up.

### Don't forget to invalidate

The single most common bug after a Server Action ships: the mutation works, the database has the new row, **but the list page shows the old data** because the fetch was cached and nothing told the cache to update. Always pair the mutation with the right `revalidateTag` calls.

## Don't trust client-supplied IDs blindly

```ts
// bad — trusts the form to send the actor id
export async function archiveDataset(formData: FormData) {
  "use server";
  const actorId = formData.get("actorId");    // 🛑 client controls this
  const datasetId = formData.get("datasetId");
  await datasetService.archive({ actorId, datasetId });
}

// good — actor comes from the session, not the form
export async function archiveDataset(formData: FormData) {
  "use server";
  const actor = await getActorFromCookie();
  if (!actor) return { status: "error", formError: "Not signed in." };
  const datasetId = z.string().uuid().parse(formData.get("datasetId"));
  if (!actor.permissions.has("dataset.archive")) {
    return { status: "error", formError: "Not allowed." };
  }
  await datasetService.archive({ actor, datasetId });
  revalidateTag("datasets");
  revalidateTag(`dataset:${datasetId}`);
  return { status: "ok" };
}
```

Form data is **user input**. Anything that affects authorization (actor, role, tenant) comes from the session, never from a hidden field.

## Audit on write applies

If the project has an audit-on-write rule (see `backend/19-audit-on-write`), it applies to Server Actions too — because they call into the same use-case layer that audits. The pattern keeps audit emission centralized in the use-case; the action just supplies the actor and the inputs.

A Server Action that talks to the DB directly (bypassing the use-case) is a defect — it likely skips audit, skips permissions, and duplicates logic. Always route through the service / use-case.

## Cookies, headers, and `redirect()`

```ts
import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";

export async function setTheme(theme: "light" | "dark") {
  "use server";
  (await cookies()).set("theme", theme, { path: "/", maxAge: 60 * 60 * 24 * 365 });
  redirect("/settings");
}
```

- `cookies()` and `headers()` are async in modern App Router.
- `redirect()` throws — it must be the **last** statement; code after it doesn't run, including `return`.
- `revalidatePath` before `redirect` so the destination renders fresh data.

## Error mapping — user-safe messages

```ts
function messageFor(error: unknown): string {
  if (error instanceof PermissionDeniedError) return "You don't have permission to do that.";
  if (error instanceof NotFoundError) return "That item no longer exists.";
  if (error instanceof RateLimitError) return "Too many requests. Try again in a moment.";
  if (error instanceof ValidationError) return error.message;     // already user-safe
  return "Something went wrong. Try again, and contact support if it persists.";
}
```

Never `return { formError: String(error) }`. The Error message may contain server paths, query fragments, or PII.

## Testing

- **Unit-test the underlying use-case / service** — it's where the business logic lives. The Server Action is a thin adapter.
- **E2E with Playwright** — submit the form, assert the result page renders, assert the empty/error states (per `frontend/14-loading-error-empty-states` and `qa/02-e2e-per-feature`).
- **A specific test for the unauthenticated case** — open the action's URL via direct POST while signed out; assert the server responds with the unauthenticated error, not 500. (Server Actions are reachable via direct POST; verify they refuse.)

## Quick checklist

- [ ] `"use server"` is at the top of every Server Action file or function.
- [ ] Actor is **re-verified inside the action** from the cookie/session — never trusted from form data.
- [ ] Permission check inside the action.
- [ ] Input validated server-side with Zod (or equivalent); same schema as the API where possible.
- [ ] Business logic is in the service / use-case, **not inline in the action**.
- [ ] Errors are **returned as state** for expected problems; **thrown** only for genuine bugs.
- [ ] User-facing error messages are mapped from domain errors — never raw exception text.
- [ ] `revalidateTag` (preferred) or `revalidatePath` called for every cache the mutation affects.
- [ ] Form works without JavaScript (progressive enhancement); client wrapper only enhances.
- [ ] Audit event emitted by the underlying use-case in the same transaction.
- [ ] Playwright E2E covers the form submission, success, and validation-error paths.
