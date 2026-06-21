---
model: sonnet
effort: high
---

# Performance — `next/image`, `next/font`, Dynamic Imports, Bundle Hygiene

Use when adding an image, importing a font, importing a heavy library, or reviewing a route whose bundle has grown. Defines the **`next/image` + `next/font` defaults**, when to `dynamic()` an import (and when not to), how to read the Next.js build output to spot bundle bloat, and the four Core-Web-Vitals levers that matter: **LCP, CLS, INP, TTFB**.

Performance issues in vibecoded code rarely come from clever algorithms — they come from forgetting that images are huge, fonts shift layout, and `import` pulls everything by default. Apply the cheap fixes; the page becomes fast.

## The four levers

| Metric | What it measures | Common cause | First lever to pull |
|---|---|---|---|
| **LCP** (Largest Contentful Paint) | When the biggest above-the-fold thing finishes painting | A huge hero image, a slow API call gating render | `next/image` with `priority`, server-render the data |
| **CLS** (Cumulative Layout Shift) | How much the layout jumps after first paint | Images without dimensions, fonts swapping in, late-injected ads/banners | Set `width`/`height`, `next/font`, reserve space for dynamic regions |
| **INP** (Interaction to Next Paint) | Slowest interaction → paint round-trip | Huge JS bundle, synchronous main-thread work, large client components | Code-split, push to Server Components, defer non-critical hydration |
| **TTFB** (Time to First Byte) | Server → first byte to browser | Heavy Server Component work, no edge caching | Move work to the client when not critical, cache server fetches |

These are the **only four levers** that consistently move user-perceived perf on a modern site. Lighthouse and Web Vitals score everything against them.

## Images — `next/image`, always

```tsx
// good — automatic sizing, lazy load, responsive srcset, format negotiation
import Image from "next/image";

<Image
  src="/hero.jpg"
  alt="A team collaborating around a whiteboard"
  width={1200}
  height={630}
  priority                     // tells Next to preload it (LCP candidate)
  sizes="(max-width: 768px) 100vw, 1200px"
  className="rounded"
/>

// bad — original-size download, blocks LCP, no responsive variants
<img src="/hero.jpg" alt="…" />
```

What `next/image` does for you:

- **Resizes on the fly** — serves an appropriately-sized variant for the viewport (per the `sizes` prop).
- **Modern formats** — WebP / AVIF when the browser supports them.
- **Lazy loads** off-screen images by default (set `priority` only on the LCP image).
- **Reserves layout space** via `width`/`height` — kills CLS from images.

### Required attributes

| Attribute | Why |
|---|---|
| `alt` | Accessibility (per `frontend/15-accessibility`). Empty string for purely decorative images. |
| `width` + `height` (or `fill`) | Layout reservation — CLS prevention. |
| `priority` | On the LCP image only. **Not** on every image; preloading everything defeats the lazy-load benefit. |
| `sizes` | Tells the browser which variant to download at each viewport. Critical for the responsive `srcset` to work — without it the largest variant is used. |

### When NOT to use `next/image`

- Tiny inline icons → use an SVG component instead. `next/image` overhead isn't worth it for 24×24 pixels.
- Logos that need to be CSS-styled (`fill`, `stroke`) → SVG.
- Decorative backgrounds → CSS `background-image` with explicit dimensions.

### Remote images — configure `images.remotePatterns`

```ts
// next.config.ts
const config = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "cdn.example.com", pathname: "/uploads/**" },
    ],
  },
};
```

`next/image` refuses unknown remote hosts on purpose — open-ended remote image proxies are a security/billing risk.

## Fonts — `next/font`, never `<link>`-loaded webfonts

```tsx
// good — self-hosted, preloaded, no FOIT/FOUT, no layout shift
import { Inter } from "next/font/google";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans">{children}</body>
    </html>
  );
}

// bad — external request, layout shift on swap, blocks render
<link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet" />
```

Why `next/font`:

- **Self-hosted at build time** — no `fonts.googleapis.com` request on first render. Faster TTFB; works offline; no GDPR issue.
- **Automatic font-display: swap.** Text appears immediately in a fallback, swaps to the web font when ready. No FOIT (invisible text).
- **`size-adjust` and `ascent-override`** computed automatically to match the fallback's metrics — **no layout shift** when the web font swaps in. This alone eliminates a major CLS source.
- **Preloaded** in the right `<link rel="preload">` form on the routes that use it.

### Local fonts

```tsx
import localFont from "next/font/local";

const brandSans = localFont({
  src: [
    { path: "./fonts/BrandSans-Regular.woff2", weight: "400", style: "normal" },
    { path: "./fonts/BrandSans-Bold.woff2", weight: "700", style: "normal" },
  ],
  display: "swap",
  variable: "--font-brand",
});
```

Same benefits as the Google integration, with the files in your repo.

### Subset, weight, variable

- **`subsets: ["latin"]`** — don't download the full Cyrillic/Greek/Vietnamese set if you don't render those scripts.
- **Specify only the weights you use.** Each weight is a separate file.
- **Prefer variable fonts** if your design uses multiple weights — one file covers `400`–`700` (or whatever the design needs).

## Dynamic imports — split what you don't need on first render

```tsx
// good — heavy editor only loaded when the route renders the page that uses it
import dynamic from "next/dynamic";

const Editor = dynamic(() => import("./MonacoEditor"), {
  ssr: false,                                  // editor needs window; skip SSR
  loading: () => <EditorSkeleton />,           // shown while the chunk loads
});

export default function DatasetEditPage() {
  return (
    <div>
      <h1>Edit dataset</h1>
      <Editor /> {/* 800 KB chunk; not in the initial bundle */}
    </div>
  );
}
```

When `dynamic()` makes sense:

- **A heavy library used on one route** — Monaco, charts (Recharts/Chart.js), maps (Leaflet), markdown previewers, video players.
- **A modal that's rarely opened** — load on first open, not on every page render.
- **Client-only widgets** that don't render on the server anyway.

When `dynamic()` is **wrong**:

- Above-the-fold content — splitting it adds a loading flash without bandwidth savings.
- Small components — the network round-trip dwarfs the bytes saved.
- Components used in multiple routes — they'll be in shared chunks anyway.

### Don't over-split

Splitting *everything* makes the network the bottleneck (lots of tiny requests). Trust the Next.js / webpack default bundling for small things; reach for `dynamic()` when a single chunk dominates a route's footprint.

## Server Components first — push computation off the client

```tsx
// good — page is a Server Component; the heavy markdown renderer runs on the server
import { renderMarkdown } from "@/lib/markdown";

export default async function DocPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = await docService.find(slug);
  const html = await renderMarkdown(doc.body);            // runs server-side
  return <article dangerouslySetInnerHTML={{ __html: html }} />;
}

// bad — page is a Client Component; renderMarkdown ships to the browser
"use client";
import { renderMarkdown } from "@/lib/markdown";

export default function DocPage({ doc }) {
  return <article dangerouslySetInnerHTML={{ __html: renderMarkdown(doc.body) }} />;
}
```

Anything that runs on the server **does not ship JS to the client**. The single highest-leverage perf decision in App Router is: **default to Server Components**, drop to `"use client"` only at the leaves that genuinely need interactivity (per `frontend/02-server-vs-client`).

A page that's mostly read-only content should be 100% Server Components with maybe one client island for a button or a search box. AI-generated code defaults to `"use client"` on everything; that's the single biggest source of unnecessary bundle bloat.

## Reading the build output — know your bundles

```
$ pnpm build
...
Route (app)                              Size     First Load JS
┌ ○ /                                    1.2 kB        92 kB
├ ○ /datasets                            5.4 kB       104 kB
├ ● /datasets/[id]                       18.7 kB      232 kB   ← big
└ ○ /datasets/[id]/edit                  240 kB       510 kB   ← huge
```

What to look at:

- **First Load JS** is what users actually download for that page. Anything > ~250 kB on a route is worth investigating; > ~500 kB is a problem.
- **Routes with a big delta** vs siblings indicate a route-specific heavy import — that's your dynamic-import candidate.
- **Shared chunks** at the bottom of the output — those load on every route. A single bad import here taxes the entire app.

Tools:

- **`@next/bundle-analyzer`** — visual treemap of what's in each chunk. The single best way to find "why is moment.js in here".
- **`pnpm why <package>`** — finds why a transitive dep ended up in your tree.
- **`source-map-explorer`** — drill into a specific chunk if you've shipped source maps.

## Common bundle bloat — and the fix

| Symptom | Cause | Fix |
|---|---|---|
| `moment` in the bundle | Imported by a transitive dep | Replace caller, or use `dayjs`/`date-fns`. moment is unmaintained. |
| `lodash` (full) | `import _ from "lodash"` | `import debounce from "lodash/debounce"` (named per-function); or `lodash-es` + tree-shaking; better, use native `Array.prototype` / small helpers. |
| Huge icon library | `import { Icon } from "react-icons"` pulls everything | Use `lucide-react` (per-icon imports) or per-package imports (`react-icons/fi/FiX`). |
| Charting library on every page | `import { LineChart } from "recharts"` in shared layout | `dynamic()` import on the chart-using route only. |
| Markdown renderer in client bundle | `"use client"` page renders Markdown client-side | Move rendering to a Server Component (see above). |
| Full firebase / aws-sdk | One module imports the umbrella | Use the modular per-service import (`firebase/firestore`, `@aws-sdk/client-s3`). |

## Defer non-critical work

```tsx
// good — defer non-critical analytics to after page load
"use client";
import { useEffect } from "react";

export function AnalyticsLoader() {
  useEffect(() => {
    const idle = (window as any).requestIdleCallback ?? ((cb: () => void) => setTimeout(cb, 1));
    idle(() => {
      // import dynamically so the analytics SDK doesn't block hydration
      import("@/lib/analytics").then((m) => m.init());
    });
  }, []);
  return null;
}
```

Anything that doesn't gate user interaction can wait — analytics, feature-flag prefetches, marketing pixels, background sync. Push them to `requestIdleCallback` or `setTimeout(0)` so they don't compete with hydration.

For third-party scripts, prefer Next.js's `<Script>` with `strategy="lazyOnload"` or `"afterInteractive"`:

```tsx
import Script from "next/script";

<Script src="https://example.com/analytics.js" strategy="afterInteractive" />;
```

## CSS — keep it lean

- **Tailwind purges** unused classes at build time — there's no easy way to ship CSS you don't use, but **inline styles** with arbitrary values (`style={{ color: someDynamicColor }}`) bypass the purger when they're truly dynamic.
- **Critical CSS** is automatically inlined by Next.js for the initial route. You don't need to do this by hand.
- **Avoid CSS-in-JS that requires a runtime** (styled-components, emotion) on a page where it matters for performance. The runtime is JS the browser has to download and execute. Tailwind / CSS Modules / vanilla-extract compile to plain CSS — preferred.

## Caching — server-side fetches

```ts
// good — cached per-request, revalidated on tag bust
const datasets = await fetch(`${API}/datasets`, {
  next: { tags: ["datasets"], revalidate: 60 },
});

// also good — never cache user-specific data
const me = await fetch(`${API}/me`, {
  cache: "no-store",
  headers: { cookie: (await cookies()).toString() },
});
```

- **`next: { tags: [...] }`** lets a Server Action invalidate this exact fetch (per `frontend/16-server-actions`).
- **`revalidate: <seconds>`** caches for N seconds across all users — only for genuinely public, identical-for-everyone data.
- **`cache: "no-store"`** for anything user-specific (auth-dependent, tenant-specific, time-sensitive).

Defaulting all fetches to "cached forever" is a bug; defaulting all to "no cache" wastes the perf win. Be explicit per fetch.

## Measuring — don't optimize blind

Install Web Vitals reporting once; let it run forever:

```ts
// app/web-vitals.ts (Client Component)
"use client";
import { useReportWebVitals } from "next/web-vitals";

export function WebVitals() {
  useReportWebVitals((metric) => {
    // send to your analytics; or console.log in dev
    if (process.env.NODE_ENV !== "production") {
      console.log(metric);
    } else {
      navigator.sendBeacon("/api/vitals", JSON.stringify(metric));
    }
  });
  return null;
}
```

Real-user metrics (RUM) > Lighthouse > local Chrome. Lighthouse is a useful proxy; the real distribution is what users actually see. Track p75 LCP / INP / CLS over time and set a budget — a perf regression that ships and reverts in two weeks is far better than one nobody noticed for two months.

## Anti-patterns

- **`<img>` instead of `next/image`.** Loses every optimization Next.js does for free.
- **`<link>` to Google Fonts.** External request, FOUT, CLS. Use `next/font`.
- **`"use client"` on the page root.** Ships the entire tree to the browser. Default to Server Components.
- **`dynamic()` on small components.** Network round-trip dwarfs savings.
- **`priority` on every image.** Defeats the lazy-load default; preloads the wrong things.
- **No `sizes` on responsive images.** Browser picks the biggest variant.
- **Importing a date library when `Intl.DateTimeFormat` suffices.** The browser already does this.
- **`useEffect` to fetch initial page data.** Use a Server Component (per `frontend/03-data-fetching`). `useEffect` + `fetch` is only acceptable for genuinely client-driven flows (debounced search, polling) — and even then with `AbortController` and a debounce.

## Quick checklist

- [ ] Every image uses `next/image` (or is a small inline SVG).
- [ ] LCP image has `priority`; non-LCP images don't.
- [ ] Every responsive image has a `sizes` prop.
- [ ] All web fonts via `next/font` with subset + explicit weights + `display: "swap"`.
- [ ] Heavy route-specific libraries are `dynamic()` imported with a loading state.
- [ ] Pages default to Server Components; `"use client"` lives at interactive leaves only.
- [ ] `pnpm build` output reviewed before merging; no route's First Load JS regressed.
- [ ] No `moment`, no full `lodash`, no full icon library in the production bundle.
- [ ] Server fetches set `next: { tags }` or `cache: "no-store"` explicitly.
- [ ] Web Vitals reporting is wired; p75 LCP / INP / CLS tracked.
