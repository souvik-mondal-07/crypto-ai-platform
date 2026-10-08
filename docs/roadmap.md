# Roadmap

## Step 1 — Foundation (complete)

- Monorepo structure (frontend, backend, database, ml, scripts, docs)
- React + TypeScript + Vite frontend shell
- FastAPI backend with health check
- Frontend ↔ backend connectivity via Axios
- No auth, no external data, no ML, no database connection

## Step 2 — Database Architecture & MongoDB Integration (complete)

- Centralized async MongoDB client (PyMongo `AsyncMongoClient`),
  managed via FastAPI's lifespan (connect on startup, close on
  shutdown)
- Centralized collection-name registry (`CollectionName`)
- Indexing strategy for current + near-term query patterns
- Repository-pattern skeleton (`BaseRepository`) — no feature
  repositories yet
- Full schema documentation for all 17 planned collections
  (`docs/database-schema.md`)
- `GET /api/v1/health` reports real database connectivity
- No auth, no external APIs, no ML — schema/connection layer only

## Step 3 — Crypto Market Data Engine (complete)

- Provider architecture (`MarketDataProvider` interface) with
  CoinGecko (broad coin-universe source) and Binance (exchange-
  specific enrichment) implementations
- Coin normalization + synchronization (`MarketSyncService`):
  full-universe upsert, paginated market-data enrichment, Binance
  mapping — all via bulk MongoDB operations, no duplicates
- Coins collection schema evolved to a `providers` map
  (`providers.coingecko.id`, `providers.binance.symbol`)
- `CoinRepository`, `MarketDataRepository` (first concrete
  repositories on Step 2's pattern)
- API: `/coins` (paginated), `/coins/search`, `/coins/{id}`,
  `/coins/{id}/market`, `/market/overview|gainers|losers|global|trending`
- Dev-only manual sync trigger (`/dev/sync/market`), off by default
- Consistent `{"error": {"code","message"}}` error shape across the API
- Frontend: typed API services (`coins.api.ts`, `market.api.ts`) and a
  development test page (`/market-test`) proving real backend data
  reaches the frontend — no hard-coded/sample coin data anywhere
- No auth, no AI/ML, no technical indicators, no news/sentiment, no
  trading — market-data infrastructure only

## Step 4 — Authentication & User Management (complete)

- Register, login, logout (client-side state clear), current user
  (`/auth/me`)
- Argon2 password hashing (`app/core/security.py`); passwords never
  stored/logged/returned in plaintext
- JWT access tokens (minimal claims: `sub`/`iat`/`exp`), configurable
  via environment variables
- `get_current_user` — single reusable FastAPI auth dependency
- `UserRepository`, `AuthService` — no auth logic in route files
- Email normalization (trim + lowercase) + unique index enforcement
  (not just an application-level check)
- Frontend: `authStore` (Zustand), centralized token storage
  (`utils/authStorage.ts`), Axios request/response interceptors
  (auto-attach Bearer token, clear session on 401), `ProtectedRoute`,
  `/login`, `/register`, minimal `/dashboard` placeholder
- Single source of truth for the authenticated user: `/auth/me` —
  no hard-coded/sample/demo user anywhere in the frontend
- No OTP, no email verification, no forgot-password/reset, no social
  login — explicitly out of scope for V1 (see `docs/authentication.md`)
- Step 3's market/coin endpoints remain unauthenticated and unchanged

## Step 5 — Full Frontend Market & Dashboard Integration (complete)

- Real Dashboard: market overview cards (total market cap, 24h
  volume, active cryptocurrencies, market trend), top gainers/losers,
  a paginated/sortable coin table — all from the real backend, no
  fake/sample data
- Real Markets page: search (debounced, backend-driven), All/Gainers/
  Losers filter, sortable coin table, pagination
- `marketStore` (Zustand) + `useCoins`/`useMarketData` hooks — clean
  component-facing interfaces over the Step 3 market API
- Authenticated header: actual registered user's name (never "Demo
  User"), logout, theme toggle, nav, header search
- `ProtectedRoute` extended to `/markets` and `/coins/:coinId`
  (`/dashboard` already protected since Step 4)
- Minimal `/coins/:coinId` placeholder page (Step 6 builds the real
  coin details + charts)
- Light/dark theme (`ThemeContext`, Tailwind `class` dark mode) —
  the first theme system in this project; nothing duplicates it
- `services/websocket/` placeholder — documented, not implemented
- Loading/error/empty states throughout; consistent retry affordances
- No technical indicators, fundamental analysis, news/sentiment, ML,
  portfolio, watchlist, or alerts — explicitly out of scope for this step
- Step 3's coin/market APIs and Step 4's auth were not modified

## Step 6 — Coin Details + Candlestick Charts (complete)

- Backend: `GET /api/v1/coins/{id}/history` serving real CoinGecko
  OHLC candles through the existing Step 3 provider architecture
  (client → mapper → provider → service → route); new
  `Timeframe` enum as the single source of truth for supported ranges
- Candle validation that drops inconsistent/malformed provider rows
  rather than "correcting" them; volume left null (provider sends none)
- Frontend: real `/coins/:coinId` page — breadcrumb, coin header,
  current price, market stats, price performance, ATH/ATL, last-updated
- `CandlestickChart` via TradingView Lightweight Charts, with
  responsive resize, theme reaction, and proper unmount cleanup
- `TimeframeSelector` (1D/7D/30D/90D/1Y), switching refetches history
  only — not the whole page; stale requests aborted
- Independent loading for coin/market vs. chart; distinct not-found,
  error-with-retry, and empty-chart states
- No technical indicators, AI/ML, or predictions — Step 7 onward
- `historical_prices` collection still unpopulated; candles are read
  live from the provider (documented in `docs/market-data.md`)

## Phase 7 — Market Data Engine hardening + password visibility fix (complete)

- **Password visibility fix:** shared `TextField`/`PasswordField`
  components with explicit background *and* text colours per theme,
  plus an autofill contrast fix in `index.css`. Root cause and details
  in the frontend README.
- 24h high/low added through the full provider → DB → API → UI chain
- `GET /market/top/market-cap` and `GET /market/top/volume` (whitelisted
  ranking fields)
- Binance 24h tickers normalized into `ExchangeTicker` and exposed at
  `GET /market/exchange/binance/tickers`, kept distinct from the
  cross-market `MarketData`
- The rest of the Market Data Engine spec was already satisfied by
  Step 3 and was not rebuilt

## Phase 8 — Markets & Coin Search (complete)

- New `GET /market/coins`: coins joined with market data, server-side
  sorting (market cap / price / 24h change / volume), filtering
  (all / gainers / losers), and pagination — replaces the Step 5 N+1
  per-row market fetch on the Markets table
- Coin search hardened: regex-escaped input (was ReDoS-prone) and
  provider-coin-ID matching added
- New indexes on `market_data.price_usd` and `volume_24h_usd`
- Markets page rebuilt: market statistics, gainers/losers, full table
  (rank, logo, name, symbol, price, 24h %, 24h high/low, market cap,
  volume, circulating supply), page-size selector, debounced backend
  search, clickable rows → coin details
- All states covered: initial/search/pagination loading, error+retry,
  empty search, empty market
- No fake data anywhere; nothing in Phases 1–7 modified

## Phase 9 — Coin Details & Charts hardening (complete)

- Coin Details' core (candlestick chart, timeframe selector, price,
  market stats, ATH/ATL, price performance, all loading/error/
  not-found states) was already built in Step 6 and was not rebuilt
- Closed real data gaps: absolute 24h USD change, 1-year performance,
  fully diluted valuation, and ATH/ATL dates — all now flow provider →
  normalized model → `market_data` → API schema → UI, `N/A` when absent
- Verified navigation from Markets/Search/Gainers/Losers all resolve
  to the backend's own coin ID (already correct since Phase 8)
- Verified the Phase 7 password-visibility fix is untouched
- 1H/4H timeframes remain unavailable — CoinGecko's OHLC endpoint has
  no sub-daily range parameter (documented in Step 6 and reconfirmed)

## Step 10 — Technical analysis (complete)

- `GET /api/v1/coins/{coin_id}/technical-analysis` — RSI, MACD,
  SMA/EMA (20/50/200), Bollinger Bands, ATR, volume trend
  (Binance historical volume vs. current 24h USD volume),
  support/resistance levels, and a descriptive trend classification
  (bullish/bearish/neutral) — never a BUY/HOLD/SELL signal
- Indicator math implemented as small, dependency-free pure-Python
  functions (`app/services/indicators.py`) — deliberately no
  pandas/numpy/`ta` dependency (see `backend/requirements.txt`)
- Real historical candles only: CoinGecko OHLC for price-based
  indicators, Binance klines for volume, with a documented minimum
  candle count before analysis is computed at all
- Cached snapshot per coin/timeframe (`technical_analysis` collection)
  with a short TTL, `force_refresh` query param to bypass it
- Coin search hardened further: relevance-ranked, regex-escaped
  aggregation pipeline (exact ID → exact name/symbol → starts-with →
  contains), generic for any coin — nothing hard-coded
- Fundamental analysis, ML prediction, risk scoring, and BUY/HOLD/SELL
  decision support are explicitly **not** part of this step — see
  Step 12
- **Real-time refresh upgrade** (still within Step 10's scope — not a
  new step): background asyncio scheduler replacing the old
  4-page/one-shot market sync, near-real-time Binance prices for
  mapped coins, rotating CoinGecko pagination so the full ranked
  universe is eventually covered, and frontend auto-refresh on
  Dashboard/Markets/Coin Details. See `docs/market-data.md`.

## Phase 11 — Fundamental analysis (complete)

- `GET /api/v1/coins/{coin_id}/fundamentals` — provider-reported market,
  supply, valuation, project and development/ecosystem data; calculated
  metrics (volume/market cap, circulating/max supply, market cap/FDV,
  distance from ATH/ATL, supply remaining) each with formula and
  unavailable-reason; a transparent rule-based fundamental score
  (`not_enough_data` when real data is insufficient); a factual summary
- Reuses the provider abstraction (new optional `get_coin_profile`,
  CoinGecko `/coins/{id}`), the existing `market_data` collection, the
  repository layer and the error handling; only the slow-changing
  project profile is cached, market-derived metrics are recalculated
  per request
- `fundamental_analysis` collection now holds one upserted document per
  coin (unique `coin_id`); see `docs/database-schema.md`
- Frontend: Fundamental Analysis section on Coin Details (own
  loading/error/empty/partial states, light + dark mode); API errors now
  carry the HTTP status and backend error code (`ApiError`, still an
  `Error`)
- Methodology and error matrix: `docs/fundamental-analysis.md`
- Explicitly **not** part of this phase: news, sentiment, ML
  prediction, risk engine, BUY/HOLD/SELL, Gemini, portfolio/watchlist/
  alerts, backtesting
- The planned items below keep their earlier "Step" labels; they have
  not been renumbered to the Phase numbering.

## Step 11 — News & sentiment (planned)

- News aggregation
- Sentiment analysis (FinBERT)

## Step 12 — Prediction engine (planned)

- ML models (XGBoost, LightGBM, LSTM/GRU) for price/direction prediction
- Risk analysis
- BUY / HOLD / SELL decision support
- Gemini 3.1 Flash-Lite natural-language explanations

## Step 13 — Personalization (planned)

- Watchlist, portfolio, alerts (now that authentication exists)
- Prediction history & accuracy tracking, backtesting

## Step 14 — Hardening (planned)

- Caching (Redis), background jobs (Celery)
- Production CORS/security review
- Token revocation / refresh-token support
- OTP / email verification / password reset (see
  `docs/authentication.md`'s "Future OTP compatibility")
- Real-time market data via WebSocket (`frontend/src/services/websocket/`)
- Observability & logging improvements


## Phase 13 — ML Prediction Engine (done)

Explicitly trained, chronologically validated XGBoost / LightGBM / LSTM-GRU models (plus a ridge baseline and an optional ensemble) producing calibrated range-based return forecasts; `GET /api/v1/predictions/...`; Model Prediction section on Coin Details. See `ml/README.md`. BUY/HOLD/SELL, risk scoring and Gemini explanations remain Phases 14–15.

## Phase 14 — Risk & Decision Engine (complete)

- Deterministic, rule-based risk score (0-100, 5 levels) and BUY/HOLD/SELL decision with confidence,
  signals, rule-generated factors and explicit data-availability handling
- `decisions` collection (existing) + `/api/v1/decisions/...` endpoints + "Risk & Decision" section on Coin Details
- Explicitly NOT included: Gemini / AI explanations (Phase 15), watchlists, portfolio, alerts, backtesting, trading


## Phase 15 — Gemini AI Analysis (implemented)

- `gemini-3.1-flash-lite` explains the existing market/technical/fundamental/news/sentiment/prediction/risk/decision data
- `ai_analysis` collection + `GET /api/v1/ai-analysis/{coin_id}` and `POST /api/v1/ai-analysis/{coin_id}/generate`
- "AI Analysis" section on Coin Details; Gemini is optional and never changes the Phase 14 decision
- See [ai-analysis.md](ai-analysis.md)
