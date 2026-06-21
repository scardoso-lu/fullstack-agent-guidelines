---
model: sonnet
effort: extract
---

# Frontend Project Structure — Next.js 15 App Router

Use when deciding where a new file belongs in a Next.js 15 App Router project. Covers the directory tree, route groups, the [lang] segment, and placement rules for components, hooks, services, and context.

Understanding the folder structure prevents the most common AI mistake: dumping everything in one place. Every file has an exact home; put it anywhere else and the codebase becomes unmaintainable within weeks.

## Directory Tree

```
src/
├── actions/                  ← Server Actions ("use server") — mutations only
│   └── <feature>.ts
├── app/                      ← Next.js App Router — routing only, no business logic
│   ├── layout.tsx            ← Root layout: providers, fonts, global CSS
│   ├── globals.css
│   └── [lang]/               ← i18n dynamic segment (all routes under a language prefix)
│       ├── (auth)/           ← Route group: login, register, forgot-password (no auth required)
│       ├── (private)/        ← Route group: protected pages (redirect to login if no token)
│       │   └── admin/
│       │       ├── layout.tsx
│       │       ├── page.tsx
│       │       └── <feature>/
│       │           └── page.tsx
│       └── (public)/         ← Route group: landing, marketing pages
├── components/
│   ├── ui/                   ← Base UI wrappers using daisyUI classes — no business logic
│   ├── app/                  ← Feature-specific components tied to a domain
│   └── <feature>/            ← Components scoped to one section (landing, tree-view…)
├── lib/
│   ├── utils.ts              ← cn(), textNormalize(), clog/cwarn/cerror
│   ├── jwt.ts                ← isTokenExpired()
│   ├── cookies.ts            ← Cookie read/write helpers
│   └── navigation.ts         ← Locale-aware redirect helpers
├── locale/                   ← i18n translation files
├── middleware.ts             ← Edge middleware: locale detection, auth redirect
├── providers/
│   ├── user-provider.tsx     ← UserContext: current user + logout
│   └── theme-provider.tsx    ← Dark/light mode
└── services/
    ├── api.ts                ← Base fetch wrappers: authApi(), api(), TypedResponse<T>
    ├── dashboard.ts          ← Domain service: DashboardService.stats()
    ├── drugs.ts              ← Domain service: DrugService.paged(), .getById()
    └── <domain>.ts           ← One file per API domain
```

## File Placement Decision Guide

| You have... | It belongs in... |
|---|---|
| A page (URL-routable) | `app/[lang]/(group)/<route>/page.tsx` |
| A layout shared by several pages | `app/[lang]/(group)/layout.tsx` |
| A reusable UI primitive (Button, Card, Input) | `components/ui/` |
| A form or feature component tied to a domain | `components/app/` or `components/<feature>/` |
| API call logic (fetch + response type) | `services/<domain>.ts` |
| A server-side mutation (revalidate, DB write via Server Action) | `actions/<feature>.ts` |
| Auth state / current user | `providers/user-provider.tsx` |
| Utility function (classnames, format, validate) | `lib/utils.ts` |
| JWT helpers | `lib/jwt.ts` |
| Locale / redirect logic | `lib/navigation.ts` |
| Route protection / locale redirect | `middleware.ts` |

## Route Groups — `(auth)`, `(private)`, `(public)`

Parentheses in folder names create **route groups** — they affect layout inheritance but not the URL:

```
app/[lang]/(private)/admin/page.tsx   →   URL: /en/admin  (the (private) part is invisible)
app/[lang]/(auth)/login/page.tsx      →   URL: /en/login
```

This lets you apply different layouts to different sections without nesting the URLs:

```tsx
// app/[lang]/(private)/layout.tsx — only wraps private pages
export default function PrivateLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
```

## Naming Conventions

| Thing | Convention | Example |
|---|---|---|
| Page files | `page.tsx` | always `page.tsx` (Next.js convention) |
| Layout files | `layout.tsx` | always `layout.tsx` |
| Component files | `kebab-case.tsx` | `login-form.tsx`, `drug-card.tsx` |
| Service files | `kebab-case.ts` | `dashboard.ts`, `drugs.ts` |
| Service exports | `PascalCase` object | `export const DrugService = { ... }` |
| Context files | `kebab-case-provider.tsx` | `user-provider.tsx` |
| Utility files | `kebab-case.ts` | `utils.ts`, `jwt.ts` |
| Interfaces | `PascalCase` | `DrugDataItem`, `PaginationResponse<T>` |

## Anti-Pattern: Everything in `app/`

```
❌ WRONG — business logic, fetch calls, and UI all in the page file
app/
└── admin/
    └── page.tsx  ← 300 lines: fetch call, data transform, form, table, modal
```

```
✅ CORRECT — page is thin, each concern has a home
app/[lang]/(private)/admin/page.tsx  ← 20 lines: layout + data fetch only
services/dashboard.ts                ← API call
components/app/stats-card.tsx        ← UI component
components/app/action-grid.tsx       ← UI component
```

## Quick Checklist

- [ ] Every page is under `app/[lang]/(group)/<route>/page.tsx`
- [ ] All `fetch()` calls are in `services/`, never in components or pages
- [ ] `components/ui/` contains only generic, reusable primitives — no API calls
- [ ] `actions/` files have `"use server"` at the top and contain only mutations
- [ ] Providers wrap the root layout, not individual pages
- [ ] Utility functions live in `lib/`, not inlined in components
