---
model: sonnet
effort: high
---

# Component Testing — Vitest + Testing Library

Use when writing tests for a React component, a hook, or a small piece of UI logic that doesn't need a browser. Defines the **three-layer test pyramid** (unit logic in Vitest, component rendering in Vitest + Testing Library + jsdom, full flows in Playwright), what each layer is *for*, the Testing Library query priority (`getByRole` over `getByTestId`), the `user-event` rule (never fire raw DOM events), and the mocking boundary (mock the network and time; don't mock React).

E2E gets a lot of attention (per `qa/02-e2e-per-feature`) — for good reason; it catches the bug nothing else does. But running every test through a real browser is slow, brittle, and overkill for "does this hook return the right value when the URL changes?". Component tests are the **fast middle layer** between unit logic and E2E.

## The rule

> Three layers, each with a clear job:
>
> | Layer | Runs in | What it tests | Speed |
> |---|---|---|---|
> | **Unit** | Vitest, no DOM | Pure functions, schema parsers, formatters, reducer/state logic. | < 10ms / test |
> | **Component** | Vitest + Testing Library + jsdom | A component or hook rendering with realistic interactions. | ~30–200ms / test |
> | **E2E** | Playwright + real browser | A user flow across pages, with real navigation. | seconds / test |
>
> A bug should be caught at the **lowest** layer that can catch it. Don't write an E2E for what a component test can prove; don't write a component test for what a unit test can prove.

## What goes in each layer

### Unit — no React, no DOM

- Pure utilities: `formatCurrency`, `parseQueryString`, `sanitizeUsername`.
- Zod schemas: assert valid inputs parse, invalid inputs produce expected errors.
- Pure state reducers / state machines.
- Data transforms used inside hooks.

If a function takes data in and returns data out — unit test it. If it touches the DOM or React state, push it down to component tests.

### Component — React, jsdom

- Component rendering with props variants.
- User interactions (`user-event`).
- Hooks tested with `renderHook`.
- Form validation flows that don't need real HTTP.
- Client-side fetch hooks (debounced search, polling) tested against a mocked fetch via MSW.

### E2E — full browser

- Multi-page flows.
- Anything that depends on real navigation, real auth cookies, real CSS layout.
- "Does the page render at all for this new variant" (`qa/02-e2e-per-feature`).

A common mistake: testing form validation at the E2E layer because "it's user-facing". Component tests do this faster, more thoroughly, and run on every save without Playwright spinning up.

## Vitest setup — what to install

```jsonc
// package.json — devDependencies
{
  "vitest": "^2.x",
  "@vitest/coverage-v8": "^2.x",
  "@testing-library/react": "^16.x",
  "@testing-library/user-event": "^14.x",
  "@testing-library/jest-dom": "^6.x",
  "jsdom": "^25.x",
  "msw": "^2.x"             // for fetch mocking; optional but recommended
}
```

```ts
// vitest.config.ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./test/setup.ts"],
    globals: true,
    css: false,
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      exclude: ["**/*.config.*", "**/*.d.ts", ".next/**", "e2e/**"],
    },
  },
});
```

```ts
// test/setup.ts
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});
```

- **`environment: "jsdom"`** is fine; `happy-dom` is faster but has more quirks. Pick `jsdom` unless your suite is large enough to feel the difference.
- **`globals: true`** lets you write `describe`/`it` without imports — match the team's preference.
- **`@testing-library/jest-dom`** adds `.toBeVisible()`, `.toHaveValue()`, etc. — install it.

## Query priority — `getByRole` first, `getByTestId` last

Testing Library has a [documented query priority](https://testing-library.com/docs/queries/about/#priority). It's the same as for Playwright (see `frontend/13-e2e-playwright`):

1. **`getByRole(name)`** — semantic; doubles as accessibility verification.
2. **`getByLabelText(name)`** — for form fields.
3. **`getByPlaceholderText`** — only when no label is feasible.
4. **`getByText`** — for assertions on visible content.
5. **`getByDisplayValue`** — for form fields with a current value.
6. **`getByAltText`** — for images.
7. **`getByTitle`** — rare.
8. **`getByTestId`** — escape hatch. Only when none of the above can target the element uniquely.

```tsx
// good — semantic, breaks only when the user-visible label changes
expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
expect(screen.getByLabelText("Email")).toHaveValue("user@example.com");

// bad — fragile, no a11y signal
expect(screen.getByTestId("save-button")).toBeEnabled();
```

If you find yourself reaching for `data-testid` constantly, the component's markup is probably missing accessible labels — fix the labels (per `frontend/15-accessibility`) and the queries get cleaner for free.

## `user-event`, never `fireEvent`

```tsx
// good — simulates the full user interaction (focus, click, key events)
import userEvent from "@testing-library/user-event";

test("submits the form", async () => {
  const user = userEvent.setup();
  render(<CreateDatasetForm />);

  await user.type(screen.getByLabelText("Name"), "Sales 2026");
  await user.click(screen.getByRole("button", { name: "Create" }));

  expect(await screen.findByText("Dataset created")).toBeVisible();
});

// bad — fires a synthetic click only; misses real-user event sequence
import { fireEvent } from "@testing-library/react";
fireEvent.click(screen.getByRole("button", { name: "Create" }));
```

`fireEvent` dispatches a single DOM event. `userEvent` simulates the **full user-input sequence** — focus, keydown, keypress, input, keyup, change — which is what your component actually receives in production. Use `fireEvent` only when you specifically need a synthetic event (rare; e.g. testing custom event handlers).

`userEvent.setup()` returns a session; reuse it across the test.

## Mock the network with MSW

```ts
// test/msw/handlers.ts
import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/datasets", () =>
    HttpResponse.json({
      items: [{ id: "1", name: "Sales 2026" }],
      next_cursor: null,
      page_size: 20,
    }),
  ),
  http.post("/api/datasets", async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({ id: "2", name: body.name }, { status: 201 });
  }),
];
```

```ts
// test/setup.ts (extension)
import { setupServer } from "msw/node";
import { handlers } from "./msw/handlers";

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

Why MSW:

- **Intercepts at the network boundary** — your fetch code runs unchanged; only the response is faked.
- **`onUnhandledRequest: "error"`** — any unmocked request fails the test loudly. No silent fallbacks to "real" calls.
- **Same handlers reusable in Storybook / dev** — one fake, many consumers.

A common temptation is to `vi.mock("./service")` and stub the service function. That works for small components, but it couples tests to the service module shape. MSW couples to the **HTTP contract** instead — which is the boundary that actually shouldn't change without the API agreeing.

## Testing hooks — `renderHook`

```tsx
import { renderHook, waitFor, act } from "@testing-library/react";
import { useDebouncedSearch } from "./use-debounced-search";

test("useDebouncedSearch fetches after the debounce window and exposes results", async () => {
  // MSW handler (configured in test/setup.ts) returns the canned response for /api/drugs?q=asp
  const fetcher = async (q: string, { signal }: { signal: AbortSignal }) => {
    const r = await fetch(`/api/drugs?q=${q}`, { signal });
    return r.json();
  };

  const { result } = renderHook(() => useDebouncedSearch(fetcher, "", 250));

  act(() => result.current.setQuery("asp"));
  expect(result.current.state).toBe("loading");

  await waitFor(() => expect(result.current.state).toBe("idle"));
  expect(result.current.results).toEqual([{ id: 1, inn: "aspirin" }]);
});
```

Things to get right:

- **No provider wrapper needed** — the hook owns its own state via `useState` + `useEffect` + `AbortController`. No global client cache to set up or tear down between tests.
- **`act(...)` for synchronous state updates** that originate from outside React (`setQuery` here).
- **`await waitFor(...)`** for the async settling — never `await new Promise(r => setTimeout(r, 100))`.
- **MSW intercepts the network**, so the hook's `fetch` runs unchanged and tests are isolated from real HTTP.

## Async — `findBy*`, not sleep

```tsx
// good — findBy* polls until found or times out (default 1000ms)
const banner = await screen.findByText("Dataset created");
expect(banner).toBeVisible();

// also good — waitFor for non-element assertions
await waitFor(() => {
  expect(mockOnSuccess).toHaveBeenCalledTimes(1);
});

// bad — sleeps for an arbitrary time; flaky on slow machines
await new Promise((r) => setTimeout(r, 200));
expect(screen.getByText("Dataset created")).toBeVisible();
```

`findBy*` is `waitFor` + `getBy*`. Use it whenever the element you're asserting on appears asynchronously.

## Test the behavior, not the implementation

```tsx
// good — what the user sees
test("disables submit while the action is pending", async () => {
  const user = userEvent.setup();
  render(<CreateDatasetForm />);

  await user.type(screen.getByLabelText("Name"), "x");
  await user.click(screen.getByRole("button", { name: "Create" }));

  expect(screen.getByRole("button", { name: /creat/i })).toBeDisabled();
});

// bad — internals
test("sets state to loading", () => {
  const { result } = renderHook(() => useDebouncedSearch(fetcher));
  act(() => result.current.setQuery("asp"));
  expect(result.current.state).toBe("loading");   // tests the hook's internal state machine, not user-visible behavior
});
```

The good test will pass as long as the user-visible behavior holds — even if you refactor the underlying hook (state-machine shape, debounce mechanism, fetch wrapper). The bad test breaks every time you change the hook's internals.

## Time and randomness — control them

```tsx
import { vi } from "vitest";

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true, shouldAdvanceTimeDelta: 20 });
});
afterEach(() => {
  vi.useRealTimers();
});

test("debounced search fires once after 300ms", async () => {
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  render(<Search />);

  await user.type(screen.getByLabelText("Search"), "a");
  await user.type(screen.getByLabelText("Search"), "b");
  await user.type(screen.getByLabelText("Search"), "c");

  vi.advanceTimersByTime(300);

  expect(mockOnSearch).toHaveBeenCalledTimes(1);
  expect(mockOnSearch).toHaveBeenCalledWith("abc");
});
```

For randomness (UUIDs, `Math.random`), inject the generator as a dependency, or use a stable seed in tests. A test that's flaky because of `Math.random()` is your bug.

## Snapshots — use sparingly

Inline snapshots (`expect(thing).toMatchInlineSnapshot()`) are useful for **stable, deterministic data shapes** — a parsed schema's error output, a normalized DTO. They're **not** useful for component DOM — DOM snapshots become noisy, get blindly updated when they break, and stop catching regressions.

Prefer explicit assertions (`getByRole`, `getByText`, attribute checks) for components.

## React Strict Mode — keep it on

Wrap the test render tree (or your providers) with `React.StrictMode`. It double-invokes effects in development; tests catch the same class of bugs (effect cleanup, ref handling) that production would expose during fast Suspense unmount/remount cycles.

## Coverage — number is a side effect, not the goal

A high coverage number is **necessary but not sufficient**. The goal is: **the bugs that would actually ship are caught**. A test that runs `myFunc()` and asserts nothing has coverage; it has no value.

Track coverage. Set a floor (commonly 80%) so untested new code is visible at the gate (`agile/02-definition-of-done`). Don't optimize for the number — optimize for the failure modes that matter (boundary conditions, error paths, empty/loading states from `frontend/14`).

## Anti-patterns

- **`vi.mock("react")`** or mocking other library internals. You're now testing your mocks, not your code.
- **`querySelector(".btn-save")`** — coupled to CSS classes; use `getByRole`.
- **`screen.getByTestId` everywhere** — the markup is missing accessible labels; fix that first.
- **Awaiting `setTimeout` for "let React settle".** Use `findBy*` or `waitFor`.
- **Asserting on rendered HTML strings** (`container.innerHTML`). Brittle; opaque failure messages.
- **Component tests that spin up Playwright** — wrong layer. Use jsdom; reach for Playwright when the test genuinely needs a browser.

## Quick checklist

- [ ] Tests live next to the code they test (`MyComponent.test.tsx` beside `MyComponent.tsx`).
- [ ] Queries follow the priority — `getByRole` first, `getByTestId` last.
- [ ] Interactions use `userEvent`, not `fireEvent`.
- [ ] Network is faked via **MSW**; `onUnhandledRequest: "error"`.
- [ ] Hooks tested with `renderHook` + a fresh wrapper per test.
- [ ] Async waits use `findBy*` / `waitFor`, not sleeps.
- [ ] Tests assert on **what the user sees**, not on internal hook state.
- [ ] Time and randomness are controlled (fake timers, injected generators).
- [ ] No DOM snapshots; inline snapshots only for stable data shapes.
- [ ] The test pyramid is respected — unit logic isn't tested through component rendering; user flows aren't tested through component rendering.
