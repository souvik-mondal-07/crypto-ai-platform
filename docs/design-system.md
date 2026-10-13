# Design system

A restrained, data-first fintech look: deep-navy layered surfaces in dark mode, a neutral light mode, one cyan/blue
accent, and green/red used **only** for gains/losses.

## Tokens (`frontend/tailwind.config.js`)

* **Surfaces (dark):** `slate-950` page → `slate-900` cards → `slate-800` raised/borders → `slate-700` strong borders.
  The existing UI is written against Tailwind's `slate` scale, so re-tinting its dark end to navy re-skins every screen
  consistently. The light end (50–400) is unchanged.
* **Accent:** Tailwind `sky` (primary buttons, focus rings, active nav/tabs).
* **Semantic:** `gain` / `loss` aliases; the `ChangeBadge` and price colour helpers are the only red/green in the app.
* **Type:** Inter (system fallback), tabular numerals on every table and metric (`font-variant-numeric: tabular-nums`).
* **Radius / shadow:** `rounded-card`, `shadow-card`, `shadow-pop` (menus, toasts, dialogs).

## Shared classes (`frontend/src/index.css`, `@layer components`)

`card`, `card-pad`, `card-interactive` · `page-title`, `page-subtitle`, `section-title`, `label-caps`, `metric-value`, `muted` ·
`btn`, `btn-primary`, `btn-secondary`, `btn-ghost`, `btn-danger`, `btn-icon` · `input` ·
`segmented`, `segmented-item`, `segmented-item-active` (ranges, timeframes, asset pickers) ·
`table-wrap`, `table-head`, `table-row` · `badge`, `badge-neutral|info|success|warning|danger`.

One consistent `:focus-visible` outline is defined globally; `prefers-reduced-motion` disables animation and smooth scroll.

## Components (`frontend/src/components/ui`)

`PageHeader` · `Skeleton` / `TableSkeleton` / `MetricSkeleton` · `ConfirmDialog` (accessible alert dialog: labelled,
focus on Cancel, Tab trap, Escape cancels, focus restored) · `ToastViewport` + `store/toastStore` (polite live region;
used for watchlist, portfolio, alert, history and settings outcomes) · `DataKindBadge`
(Observed data / Model estimate / Risk assessment / AI-generated — with a plain-language caveat).

## Layout rules

* Header (`components/layout/Header.tsx`): flex only, no absolute positioning. ≥1024px one row (nav is icon-only at
  1024px, labelled from 1280px; search flexes with `min-w-0`; username truncates). <1024px: menu button + full-width
  search row; the menu panel lists every link plus Profile / Settings / Logout.
* Tables scroll **inside** their own container (`table-wrap`), never the page; the Coin column stays sticky.
* Charts: shorter on phones (`useChartHeight`), USD axis formatting, SMA legend when the overlay is on.
* Coin Details: identity + price card with Watchlist / Add to Portfolio / Set price alert, then sections, each tagged by
  data kind. Predictions are never presented as guarantees.


## Dashboard redesign ("crypto terminal" look)

* **Accent tokens:** `brand-400/500/600`, `brand-violet`, `brand-cyan` (electric blue → violet → cyan). Gains/losses stay emerald/red.
  `shadow-glow` / `shadow-glow-violet`, `animate-glow` / `animate-float` / `animate-fade-in`, and a `3xl` (1800px) screen were added to `tailwind.config.js`.
* **Shared classes:** `ai-surface` (hero / AI panels), `glass`, `hover-lift`, `btn-gradient`. In dark mode `.card` is a navy gradient with a thin blue border.
* **Shell:** `AppShell` = fixed `Sidebar` (lg+; a drawer below) + sticky `Header` + content. The Header holds only search (flexes, `min-w-0`),
  the alerts bell, the theme toggle and the account menu (Profile / Settings / Logout), so its controls cannot collide at any width.
  Navigation lives only in the Sidebar. Only real routes are linked (no standalone Technical/Fundamental/ML/Risk/AI pages exist).
* **Dashboard grid:** one column below `xl`; from `xl` the AI Market Insights column sits beside the left column; chart and heatmap sit side by
  side from 1400px; the five statistic cards are 3+2 until 1800px, then one row. Lower panels: Top Movers · Portfolio · Watchlist, then Latest News · Quick Actions.
* **Honesty rules:** no sparklines or volume bars (the market responses the frontend consumes carry no sparkline series, and candles have no volume);
  "ALL" history range is disabled; "Market Open" is a fixed label because crypto trades 24/7; the membership label is the user's real role.
* **Tests:** assert figures inside the element they belong to (`within(screen.getByRole("region", { name: "Total Market Cap" }))`);
  the stat cards, banner, chart, AI panel, Top Movers, Latest News and Quick Actions are all labelled regions.
