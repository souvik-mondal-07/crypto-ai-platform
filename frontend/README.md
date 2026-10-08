# Crypto AI Platform — Frontend (Steps 1–6)

React + TypeScript + Vite application. Currently includes: an app
shell with backend health-check status (Step 1), a market-data test
page (Step 3), JWT-based authentication (Step 4), and a real
Dashboard + Markets experience backed by the actual backend APIs
(Step 5) — search, sort, filter, pagination, light/dark theme, and
authenticated navigation — plus a real Coin Details page with a
candlestick chart and timeframe selector (Step 6). Technical
indicators are Step 7.

## Setup

```bash
cd frontend
npm install
cp .env.example .env
```

## Run

```bash
npm run dev
```

Visit http://localhost:5173/. The homepage shows a System Status panel
(backend health check). Log in (after registering) to reach
`/dashboard` and `/markets`.

## Build, Lint & Test

```bash
npm run build
npm run lint
npm run test    # Vitest
```

## Structure

```
src/
├── main.tsx            # React entrypoint
├── App.tsx             # Router shell + ThemeProvider + auth initialization on startup
├── index.css           # Tailwind entrypoint
├── components/
│   ├── common/          # Loader, ErrorMessage, EmptyState, etc.
│   ├── layout/           # PageContainer, Header, AppShell (Step 5)
│   ├── auth/             # AuthLayout, LoginForm, RegisterForm (Step 4)
│   ├── market/           # CoinTable, MoverList, MarketOverviewCards, CoinLogo, Skeletons (Step 5)
│   └── coin-details/     # CandlestickChart, TimeframeSelector, CoinStats (Step 6)
├── pages/               # Home, NotFound, MarketTest, Login, Register, Dashboard,
│                          Markets, CoinDetails
├── services/
│   ├── api/              # Axios client (auth interceptor) + per-feature API services
│   └── websocket/        # Placeholder — not implemented, see its README (Step 5)
├── store/               # Zustand: systemStore, authStore (single source of truth for
│                          the authenticated user), marketStore (Step 5)
├── routes/              # React Router route definitions + ProtectedRoute
├── context/              # ThemeContext (light/dark — the one theme system; Step 5)
├── utils/               # authStorage.ts, formatters.ts, chartUtils.ts (Step 6)
├── types/                # Shared TypeScript types (coin, market, auth, apiError)
├── config/              # Centralized env + API config
├── hooks/                # useDebouncedValue, useCoins, useMarketData, useCoinDetails (Step 6)
├── tests/                # Vitest setup
└── data/                 # (empty — reserved for future static/mock data)
```

See [`../docs/authentication.md`](../docs/authentication.md) for the
auth flow and [`../docs/market-data.md`](../docs/market-data.md) for
the market-data API this frontend consumes.

## What Steps 5–6 do NOT do

No technical indicators (RSI/MACD/Bollinger/etc.), fundamental
analysis, news/sentiment, AI/ML, portfolio, watchlist, or alerts —
those are later steps. The candlestick chart is deliberately plain
price data; Step 7 ("Technical Analysis Engine") layers indicators
onto it.

## A known trade-off worth knowing

The Step 3 backend has no single endpoint that returns a paginated
list of coins *with* price/market-cap/volume already joined — only
`/coins` (identity only) and `/market/gainers`/`/market/losers`
(joined, but capped to a "top movers" list). To show price/24h-change
columns in the Markets/Dashboard coin table, the frontend fetches
`/coins/{id}/market` for each coin on the *current page only* (in
parallel, capped at 20 rows per page — see `DEFAULT_LIMIT` in
`store/marketStore.ts`) rather than inventing data or leaving those
columns blank. This is a deliberate, bounded trade-off, not a bulk
per-coin loop over the whole database — a future step should add a
proper bulk "coins + market data" backend endpoint to replace it.

## Password visibility fix (Phase 7)

**Symptom:** password dots were near-invisible in the Login, Register,
and Confirm Password fields.

**Root cause:** the auth forms used bare `<input>` elements whose
className set border/padding/focus styles but **no `text-*` or `bg-*`
class**. Tailwind's preflight doesn't give inputs a background, so
each field fell back to the browser default (white) while inheriting
`color` from `body` — which is `dark:text-slate-100` in dark mode.
Near-white text on a white field. It was never a password-specific
bug; password fields just made it most obvious, and the same defect
was present on the `/market-test` search input (also fixed).

**Fix:**
- New shared `components/common/FormFields.tsx` exporting `TextField`
  and `PasswordField`, which set background *and* text colour
  explicitly for both themes, so contrast never depends on inherited
  body colour. Both auth forms now use these instead of duplicating
  input markup.
- `PasswordField` adds a show/hide toggle (masking stays on by
  default, `aria-pressed` exposed to assistive tech). Masked dots and
  revealed text share the same colours.
- Autofill handled in `index.css` via `-webkit-text-fill-color` and an
  inset box-shadow — the only way to override the UA's autofill
  styling, which utility classes can't reach. Scoped to autofill
  states, no `!important`.
- Auth pages and the shared `Loader`/`ErrorMessage`/`EmptyState`
  components gained the dark-mode variants they were missing.

Covered by `components/common/FormFields.test.tsx`.

## Markets page (Phase 8)

The Markets table is driven by `GET /market/coins` via
`useMarketCoins` → `marketStore` → `market.api.ts`. Sorting,
filtering, pagination, and page size are **all server-side** — the
browser never holds more than the current page, and no column is
sorted client-side.

Search is a separate path (`/coins/search` via `useCoins`), debounced
350ms, because it queries coin identity rather than the joined market
view. Searching swaps the table for the search-results table.

The Step 5 N+1 noted below (one `/coins/{id}/market` request per row)
no longer applies to the Markets table — `/market/coins` returns the
joined rows in one request. The Dashboard table still uses the older
`useCoins` path.

## Coin Details data (Phase 9)

Coin Details' chart/page structure was built in Step 6 and reused
as-is. Phase 9 added display of fields the backend now supplies but
previously didn't capture: absolute 24h USD change (next to the
percentage), fully diluted valuation, 1-year performance, and ATH/ATL
dates. Every one of these is `N/A` when the backend returns `null` —
never computed client-side from other fields, which could disagree
with the provider's own figures.
