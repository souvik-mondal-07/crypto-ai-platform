# Architecture

## Overview

Crypto AI Platform is a monorepo with an independently-runnable React
frontend and FastAPI backend, communicating over a versioned REST API.
This document describes the current (Steps 1–6) architecture
and the planned future architecture.

## Current (Steps 1–6)

```
┌──────────┐  HTTP (Axios, Bearer token)  ┌───────────┐  Service → Provider  ┌───────────────────┐
│ Frontend │─────────────────────────────▶│  Backend  │─────────────────────▶│ CoinGecko/Binance │
│ React    │◀───────────────────────────── │  FastAPI  │◀───────────────────── │ (public REST APIs)│
└──────────┘                              └─────┬─────┘                      └───────────────────┘
                                                 │ PyMongo (async)
                                                 ▼
                                           ┌──────────┐
                                           │ MongoDB  │
                                           └──────────┘
```

- **Authentication (Step 4):** JWT-based, stateless. `app/core/security.py`
  (Argon2 hashing + JWT create/decode) and `app/core/dependencies.py`
  (`get_current_user`) are the only modules that touch passwords or
  tokens. `/auth/register`, `/auth/login`, `/auth/me`, `/auth/logout`
  are the only auth routes; Step 3's coin/market routes remain
  unauthenticated and unchanged. See `docs/authentication.md`.
- **Frontend market/dashboard integration (Step 5):** `marketStore`
  (Zustand) + `useCoins`/`useMarketData` hooks are the only things
  that call `services/api/{coins,market}.api.ts` — components never
  call Axios directly. `Header`/`AppShell` wrap the authenticated app
  pages (`/dashboard`, `/markets`, `/coins/:coinId`), all gated by the
  same `ProtectedRoute` introduced in Step 4. No frontend change in
  this step touched a Step 3/4 backend route.
- **Coin details + historical OHLC (Step 6):** one new backend route
  (`GET /coins/{id}/history`) built entirely on the existing Step 3
  provider chain — `CoinGeckoClient.get_coin_ohlc` → `map_ohlc` →
  `CoinGeckoProvider.get_historical_ohlc` → `MarketService` → route.
  Supported timeframes live in `app/providers/timeframes.py`. On the
  frontend, `useCoinDetails` + `CandlestickChart` (TradingView
  Lightweight Charts) render it; see `docs/market-data.md` for why
  volume is null and why 1H/4H aren't offered.
- **MongoDB is connected** via a single application-level async
  client (`app/database/client.py`), created and pinged once in
  FastAPI's `lifespan`, closed cleanly on shutdown. No client is ever
  created per-request.
- `GET /api/v1/health` reports real database connectivity
  (`"connected"`/`"disconnected"`) rather than only backend liveness.
- Collection names are centralized (`app/database/collections.py`);
  no collection name is a hard-coded string literal outside that file.
- Indexes are created once at startup (`app/database/indexes.py`),
  not per-request. See `docs/database-schema.md` for the full schema
  and indexing rationale.
- The repository pattern (`app/repositories/base.py`) established in
  Step 2 now has its first concrete implementations:
  `CoinRepository`, `MarketDataRepository`.
- **Market data providers (Step 3):** `app/providers/` implements
  CoinGecko (broad coin-universe source) and Binance (exchange-
  specific enrichment) behind a common `MarketDataProvider` interface.
  `MarketSyncService` orchestrates fetch → normalize → upsert; see
  `docs/market-data.md` for the full provider architecture.
- Still no AI/ML, no Gemini, no news/sentiment, no caching (Redis), no
  background workers (Celery), no OTP/email-verification/password-reset.
- CORS is restricted to the configured frontend origin.
- If MongoDB or a market-data provider is unreachable, the backend
  **still starts/responds** — it logs/reports the degraded state
  honestly rather than silently claiming success (see
  `app/core/exceptions.py` for the consistent error-response shape).

## Planned future architecture

```
┌───────────┐   ┌───────────┐   ┌────────────────┐
│ Frontend  │──▶│ Backend   │──▶│ MongoDB         │ (users, portfolios,
│ (React)   │   │ (FastAPI) │   │                 │  watchlists, alerts,
└───────────┘   └─────┬─────┘   └────────────────┘  prediction history)
                      │
                      ├──▶ Redis (caching, rate limiting)
                      ├──▶ Celery workers (scheduled data refresh,
                      │                     model inference jobs)
                      ├──▶ External market data APIs (Binance/CoinGecko)
                      ├──▶ News / sentiment sources + FinBERT
                      ├──▶ ML pipeline (XGBoost/LightGBM/LSTM/GRU) for
                      │    price & direction prediction
                      └──▶ Google Gemini 3.1 Flash-Lite for natural
                           language explanations of AI decisions
```

## Backend layering

`app/api` (routes) → `app/services` (business logic) →
`app/repositories` (data access, `BaseRepository`) → `app/database`
(connection/client/index management) → `app/models` (persisted
schema, once introduced) / `app/schemas` (API contracts). For
market data specifically: `app/services` also calls
`app/providers/<name>` (client → mapper → provider), never a raw
`httpx` call from a route or repository. For authentication:
`app/api/v1/auth.py` → `app/services/auth_service.py` →
`app/repositories/user_repository.py`, with password/JWT operations
factored out into `app/core/security.py` and the reusable
`get_current_user` dependency in `app/core/dependencies.py` — no
route decodes a JWT or hashes a password itself.

This separation is in place from Step 1 so future features slot into
existing layers rather than requiring a rewrite. Routes never query
MongoDB directly (the health endpoint goes through `app/database`'s
`ping_database()`) and never call a provider directly (coin/market
routes go through `CoinService`/`MarketService`, which call
`CoinRepository`/`MarketDataRepository` and, for live data,
`CoinGeckoProvider`).

## Frontend layering

`pages` (screens) → `components` (UI) → `store` (Zustand state) →
`services/api` (Axios calls) → `config` (centralized env/config).
