# Accessibility — Semantic HTML, ARIA, Focus, and Keyboard

Use when building any UI component, when reviewing a vibecoded page, or when an existing screen has only ever been driven by a mouse. Defines the **semantic-HTML-first** rule (use `<button>`, `<a>`, `<label>`, `<nav>` — not `<div onclick>`), how ARIA *complements* (not replaces) semantic markup, the focus-management ruleset (visible focus, focus traps in modals, focus restore on close), and keyboard-navigation expectations. Aims at WCAG 2.2 AA — pragmatic, not ceremonial.

Accessibility is the most universally missed thing in vibecoded UIs. The fix is mostly cheap and mostly mechanical — but it has to be done **at the time the component is built**, not as a sweep at the end. By then the markup is wrong, the focus order is wrong, and the only "fix" is a rewrite.

## The rule

> 1. **Use the right HTML element** before reaching for `role` or `aria-*`. A `<button>` already announces, focuses, and triggers on `Enter`/`Space` for free.
> 2. **Every interactive element is reachable, operable, and announced** via keyboard and screen reader.
> 3. **Focus is visible** at all times for keyboard users; **focus is managed** during route changes, modals, and dynamic content.
> 4. **Form fields have labels** — not placeholders, not adjacent prose. Labels.
> 5. **Color is never the only signal.** Errors, statuses, and selection states use text or icons in addition to color.
> 6. **Contrast meets AA** — 4.5:1 for body text, 3:1 for large text and UI components.

## Semantic HTML first — ARIA is the patch, not the cloth

```tsx
// good — semantic, keyboard-operable, screen-reader-announced for free
<button onClick={onSave} disabled={isSaving}>
  {isSaving ? "Saving…" : "Save"}
</button>

// bad — re-implements every browser default poorly
<div onClick={onSave} className="cursor-pointer">Save</div>
```

The bad version is broken in five ways: no `Tab` reachability, no `Enter`/`Space` activation, no announcement as a button, no `disabled` semantics, no focus ring. Patching each with `role="button"` + `tabIndex={0}` + `onKeyDown` is more code, more bugs, and still wrong. **Use `<button>`.**

A short menu of "use the right element":

| Want to... | Use |
|---|---|
| Trigger an action | `<button>` (`type="button"` unless it submits) |
| Navigate to a URL | `<a href>` (or `<Link>`) |
| Group form fields | `<fieldset>` + `<legend>` |
| Label a field | `<label htmlFor>` or wrap the input |
| Mark a region | `<header>`, `<nav>`, `<main>`, `<aside>`, `<footer>`, `<section>` |
| List items | `<ul>` / `<ol>` + `<li>` (not `<div>` + `<div>`) |
| Headings | `<h1>` ... `<h6>` (one `<h1>` per page) |
| Tabular data | `<table>` + `<thead>`/`<tbody>`/`<th scope=>` |
| Show emphasis | `<strong>` / `<em>` (not bare CSS bolding) |

If you're typing `role="button"` you're almost certainly in the wrong neighborhood.

## ARIA — when you need it, use it correctly

ARIA is for cases the platform doesn't cover. The big ones:

```tsx
// Live region for dynamic announcements (toasts, status updates)
<div role="status" aria-live="polite">{statusMessage}</div>

// Critical alerts (form errors, blocking issues)
<div role="alert">{error}</div>

// Loading regions
<section aria-busy={isLoading} aria-live="polite">{children}</section>

// Custom widgets — combobox, listbox, tablist, etc.
// Use the established ARIA Authoring Practices patterns or a tested library.
```

ARIA rules of thumb:

- **First rule of ARIA: don't use ARIA.** Prefer a semantic element.
- **Don't double up.** `<button role="button">` is redundant; `<nav role="navigation">` is redundant.
- **Don't override semantics.** `<a role="button">` confuses everyone — use `<button>` if it's an action, `<a>` if it navigates.
- **`aria-label` for icon-only buttons.** `<button aria-label="Close"><X /></button>` — without it, the screen reader announces "button" with no purpose.
- **`aria-describedby` for help/error text** that describes a field.
- **`aria-hidden="true"` on decorative icons.** Icons inside a labeled button should be hidden from AT — the label is the content.

## Form fields — `<label>` is non-negotiable

```tsx
// good — explicit, accessible, clickable
<label htmlFor="email">Email</label>
<input id="email" type="email" name="email" autoComplete="email" required />

// also good — wrapping; no `htmlFor` needed
<label>
  Email
  <input type="email" name="email" autoComplete="email" required />
</label>

// bad — placeholder as label; vanishes on focus, low contrast, no AT label
<input placeholder="Email" type="email" />
```

Required reading on every form:

- **Every `<input>`, `<textarea>`, `<select>` has a `<label>`** — explicit or wrapping.
- **`autoComplete`** with the right token (`email`, `current-password`, `new-password`, `name`, `street-address`, `tel`, `one-time-code` for OTP, …) lets browsers + password managers help users.
- **`type=`** matters — `email`, `tel`, `url`, `number`, `search` give appropriate keyboards on mobile.
- **`required`** for required fields — and pair with `aria-describedby` pointing at any visible "required" cue.
- **Error messages** wired with `aria-describedby` and `role="alert"` so screen readers announce them when they appear.

```tsx
<label htmlFor="password">Password</label>
<input
  id="password"
  type="password"
  autoComplete="new-password"
  required
  aria-invalid={!!errors.password}
  aria-describedby={errors.password ? "password-error" : "password-hint"}
/>
<p id="password-hint" className="text-sm text-gray-600">
  At least 12 characters.
</p>
{errors.password && (
  <p id="password-error" role="alert" className="text-sm text-red-700">
    {errors.password}
  </p>
)}
```

## Headings — one `<h1>`, descend in order

```tsx
// good — single h1, descending without skipping
<main>
  <h1>Datasets</h1>
  <section>
    <h2>Recent</h2>
    <h3>This week</h3>
    <h3>Earlier</h3>
  </section>
  <section>
    <h2>Archived</h2>
  </section>
</main>

// bad — h1 inside a card, h4 after h2, decorative bolding instead of headings
<div className="font-bold text-2xl">Datasets</div>
<h1>Recent</h1>
<h4>This week</h4>
```

Screen-reader users navigate by heading; broken hierarchy makes the page un-skimmable. Don't pick a heading by visual size — pick by structural role, then style.

## Focus — visible, managed, restored

Three rules.

### 1. Focus is always visible

```css
/* a single global rule, not removed per component */
:focus-visible {
  outline: 2px solid var(--ring-color, #2563eb);
  outline-offset: 2px;
}
```

Never write `outline: none` without a replacement. The `:focus-visible` pseudo applies only to keyboard focus, so the ring shows for keyboard users without flashing on every mouse click. Tailwind's `focus-visible:ring-2` is the same idea.

### 2. Focus moves to the right place on dynamic UI

- **Route change** — focus moves to the new page's `<h1>` (or `<main>` if `<h1>` is decorative). Without this, keyboard users have to `Tab` from the top of the page after every navigation.
- **Modal opens** — focus moves to the first focusable element inside the modal (often the close button or the first input). Focus is trapped inside the modal until it closes.
- **Modal closes** — focus returns to the element that opened it.
- **Async content arrives** — if the content replaces the current focus target, move focus to the new target's heading; otherwise leave focus where it is.

```tsx
// route change — move focus to <h1>
useEffect(() => {
  document.querySelector("h1")?.focus();
}, [pathname]);

// give <h1> a focus target
<h1 tabIndex={-1}>Datasets</h1>
```

For modals, use a tested primitive (`Radix UI`, `react-aria`, shadcn's `Dialog`) — they get focus trap + restore right; hand-rolling them is where bugs live.

### 3. Skip link for keyboard users

The first focusable element on every page is a "Skip to main content" link, visually hidden until focused:

```tsx
// app/layout.tsx
<a
  href="#main"
  className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:ring"
>
  Skip to main content
</a>
{/* nav, header, sidebar ... */}
<main id="main">{children}</main>
```

This is the single biggest quality-of-life win for keyboard users on a site with a long top nav.

## Keyboard — every action reachable

Every interactive element must be operable from the keyboard:

| Element | Keys |
|---|---|
| `<button>` | `Tab` to focus; `Enter` or `Space` to activate |
| `<a>` | `Tab` to focus; `Enter` to follow |
| `<input type="checkbox">` | `Space` to toggle |
| Radio group | `Tab` enters group; `↑/↓` (or `←/→`) moves within |
| Menus / popovers | `Tab` to opener; `Enter`/`Space` opens; `↑/↓` navigates; `Esc` closes; **`Tab` does not move out** while open |
| Modals | `Esc` closes; `Tab` cycles within the modal only |
| Tabs | `Tab` to the active tab; `←/→` switches tabs; `Tab` again moves to the panel |

If you ship a custom widget, follow the [ARIA Authoring Practices Guide](https://www.w3.org/WAI/ARIA/apg/) for that pattern — it gives the exact key bindings and roles. Reaching for a tested library (Radix, react-aria) for combobox, listbox, datepicker, etc. is almost always the right answer.

## Color and contrast

- **AA contrast** — 4.5:1 for body text, 3:1 for large text (≥ 18pt or 14pt bold) and for UI components / graphics that convey information.
- **Never color-only signals.** A red border on an invalid field needs a text error too; a green "online" dot needs a label.
- **Hover and focus rings** must also meet 3:1 against their background.

Use a tool (`@axe-core/playwright`, Lighthouse, Chrome DevTools' contrast checker) — eyeballing it is not enough.

## Images, icons, media

- **Every meaningful `<img>` has `alt`.** Empty `alt=""` for purely decorative images.
- **`next/image`** — the `alt` prop is required at the type level; use it. (See `frontend/18-performance` for the rest.)
- **SVG icons** — wrap in a button with `aria-label`; mark the SVG `aria-hidden="true"` if the button is labeled.
- **Video** — captions / transcript. If users are uploading video for others to watch, captions are not optional.

```tsx
// good — labeled button, hidden decorative icon
<button aria-label="Delete" onClick={onDelete}>
  <TrashIcon aria-hidden="true" />
</button>

// bad — icon visible but unannounced
<button onClick={onDelete}><TrashIcon /></button>
```

## Motion — respect `prefers-reduced-motion`

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

Or per-component (Tailwind `motion-safe:` / `motion-reduce:` variants). Vestibular disorders are real; flying-card animations cause nausea for a non-trivial slice of users.

## Internationalization touches that affect a11y

- **`<html lang="...">`** is set correctly (per route if you support multiple).
- **Direction** — `dir="rtl"` for right-to-left languages; CSS uses `start`/`end` instead of `left`/`right`.
- **Don't bake plurals or grammatical gender into strings**; use a real i18n primitive.

## Testing — automated catches ~30%; the rest is manual

```ts
// frontend/e2e/a11y.spec.ts
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("datasets page has no a11y violations", async ({ page }) => {
  await page.goto("/datasets");
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
```

`axe` (via `@axe-core/playwright` or `vitest-axe`) catches color contrast, missing labels, missing alt text, broken aria — **about 30% of real a11y issues**. The rest you find by:

1. **Navigate every page with the keyboard alone.** No mouse. Can you reach everything? Can you operate it? Is focus visible?
2. **Turn on a screen reader.** VoiceOver (Mac), NVDA (Windows), TalkBack (Android). Listen to a flow. Do labels make sense? Do error messages announce?
3. **Test at 200% zoom.** Layouts must reflow, not produce horizontal scroll.

A per-feature E2E that runs `axe` is a healthy baseline (one per critical flow), but it does not replace the manual passes.

## Common vibecoding tells

- **`<div onClick={...}>` clickable cards.** Wrap with `<Link>` or `<button>`, or add `role="button" tabIndex={0}` and key handlers (and then ask whether it should be a real button/link).
- **Placeholder as label.** Disappears on focus, fails contrast, fails AT.
- **Color-only validation.** Red border, no message — colorblind users see nothing.
- **`outline: none` on focus.** Disables the keyboard-user feedback loop. Don't.
- **`tabIndex={1}`+**. Don't set positive `tabIndex` — it breaks natural tab order. Only `0` (focusable) or `-1` (programmatically focusable, not in tab order).
- **Modal without focus trap.** Tab escapes out of the modal into the page underneath. Use a tested primitive.
- **Heading hierarchy by visual size.** Pick by structure; style independently.

## Quick checklist

- [ ] Every interactive element is a `<button>`, `<a>`, `<input>`, or has a tested ARIA pattern — no naked `<div onClick>`.
- [ ] Every form field has a real `<label>` (not just a placeholder).
- [ ] Headings descend in order; one `<h1>` per page.
- [ ] Focus ring is visible (`:focus-visible`); never `outline: none` without a replacement.
- [ ] Modals trap focus and restore it on close; route changes move focus to the new heading.
- [ ] "Skip to main content" link is the first focusable element.
- [ ] Color is never the only signal of an error or status.
- [ ] Body text meets 4.5:1; UI elements meet 3:1.
- [ ] `prefers-reduced-motion` is honored.
- [ ] At least one E2E per critical flow runs `axe` and asserts no violations.
- [ ] Keyboard-only navigation of the slice was attempted before merging.
