# Crypto AI Platform

An AI-powered cryptocurrency market analysis and decision-support
platform.

> **PHASE 11 COMPLETED** — this repository contains the project
> foundation (Step 1), a MongoDB database architecture layer
> (Step 2), a crypto market-data engine (Step 3), JWT-based
> authentication (Step 4), a full frontend market/dashboard
> integration (Step 5), a real Coin Details page with candlestick
> charts backed by live provider OHLC data (Step 6), market-data
> engine hardening (Phase 7), markets/coin-search improvements
> (Phase 8), Coin Details hardening (Phase 9), and a technical
> analysis engine — RSI/MACD/SMA/EMA/Bollinger Bands/ATR/volume/
> support-resistance/trend (Step 10), and a fundamental analysis
> system — market/supply/valuation/project/development data,
> calculated metrics and a transparent rule-based score (Phase 11,
> see `docs/fundamental-analysis.md`). No news/sentiment, AI/ML
> prediction, or trading features are implemented yet. See `docs/roadmap.md` for what's planned next
> (Step 11: News & Sentiment).

## 1. Project Overview

The platform will eventually provide market data, coin search and
details, technical/fundamental analysis, news, sentiment analysis,
ML-based price/direction prediction, risk analysis, BUY/HOLD/SELL
decision support with Gemini-generated explanations, watchlists,
portfolios, alerts, prediction history, and backtesting. Market data,
coin search/details, authentication, technical analysis, and
fundamental analysis now exist (Steps 1–10 and Phase 11, see
`docs/roadmap.md`); news/
sentiment, ML prediction, risk scoring, decision support, and
personalization features (watchlists/portfolios/alerts) do not exist
yet.

## 2. Architecture

See [`docs/architecture.md`](docs/architecture.md) for diagrams and
layering, [`docs/database-schema.md`](docs/database-schema.md) for the
full MongoDB schema, [`docs/market-data.md`](docs/market-data.md) for
the provider/sync architecture, and
[`docs/authentication.md`](docs/authentication.md) for the auth flow.
In short: a React/Vite frontend talks to a FastAPI backend over a
versioned REST API (`/api/v1`); the backend maintains a MongoDB
connection, synchronizes coin/market data from CoinGecko (+ Binance
enrichment), and issues JWTs for authenticated sessions.

## 3. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS, React Router, Zustand, Axios, Lucide React, TradingView Lightweight Charts |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| Database | MongoDB via PyMongo's async API (`AsyncMongoClient`) |
| Market data | CoinGecko (broad universe) + Binance (exchange-specific), via `httpx` |
| Auth | Argon2 password hashing (`argon2-cffi`), JWT (`python-jose`) |
| Cache (future) | Redis |
| Background tasks (future) | Celery |
| AI/ML (future) | Pandas, NumPy, TA-Lib/`ta`, XGBoost, LightGBM, PyTorch (LSTM/GRU), FinBERT, Google Gemini 3.1 Flash-Lite |

Only the dependencies actually needed for Steps 1–4 are installed
today (see `frontend/package.json` and `backend/requirements.txt`).

## 4. Directory Structure

```
crypto-ai-platform/
├── frontend/       # React + TypeScript + Vite app
├── backend/        # FastAPI app (database, repositories, providers, services, core/auth)
├── database/       # MongoDB schema/migration docs
├── ml/             # ML pipeline scaffold (empty — no models yet)
├── scripts/        # Dev utility scripts
├── docs/           # Architecture, dev guide, API reference, schema, market data, auth, roadmap
├── tests/          # Reserved for cross-cutting/integration tests
├── .gitignore
├── README.md
└── .env.example
```

## 5. Prerequisites

- Node.js 18+ and npm
- Python 3.10+
- MongoDB installed locally (no Docker) — see
  [`docs/development.md`](docs/development.md) for setup

## 6. Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env
```

## 7. Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## 8. Environment Variables

- Frontend: `VITE_API_BASE_URL` (see `frontend/.env.example`) — never
  a provider secret or JWT secret; those are backend-only.
- Backend: `APP_NAME`, `APP_ENV`, `API_V1_PREFIX`, `BACKEND_HOST`,
  `BACKEND_PORT`, `FRONTEND_URL`, `MONGODB_URI`, `MONGODB_DATABASE`,
  `COINGECKO_API_BASE_URL`, `BINANCE_API_BASE_URL`,
  `COINGECKO_API_KEY` (optional), `ENABLE_DEV_SYNC_ENDPOINT`,
  `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`
  (see `backend/.env.example`)

No API keys are required through Step 4 (`COINGECKO_API_KEY` is
optional). **`JWT_SECRET_KEY` must be replaced with a real random
secret in any non-local environment** — see
[`docs/authentication.md`](docs/authentication.md). Real secrets
should never be committed — `.env` is gitignored in both `frontend/`
and `backend/`.

## 9. Running the Frontend

```bash
cd frontend
npm run dev
```

Visit http://localhost:5173/. The homepage links to `/market-test`
(Step 3's market-data verification page) and `/login` / `/register`
(Step 4). Once logged in: `/dashboard` and `/markets` (Step 5) show
real backend market data with search, sort, filter, and a light/dark
theme toggle in the header.

## 10. Running the Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Visit http://127.0.0.1:8000/ and http://127.0.0.1:8000/docs. The
backend connects to MongoDB (and initializes indexes) on startup, and
closes the connection cleanly on shutdown.

## 11. Health Endpoint

`GET /api/v1/health` reports database connectivity honestly:

```json
{ "status": "ok", "service": "crypto-ai-platform-backend", "database": "connected" }
```

## 12. Market Data API (Step 3)

```
GET /api/v1/coins?page=1&limit=100
GET /api/v1/coins/search?q=bitcoin
GET /api/v1/coins/{id}
GET /api/v1/coins/{id}/market
GET /api/v1/coins/{id}/history?timeframe=7D
GET /api/v1/market/coins?sort_by=market_cap&filter=all
GET /api/v1/market/overview
GET /api/v1/market/gainers
GET /api/v1/market/losers
GET /api/v1/market/global
GET /api/v1/market/trending
```

See [`docs/market-data.md`](docs/market-data.md) for full details.
Coin/market data is empty until a sync is triggered — see
[`docs/development.md`](docs/development.md).

## 13. Authentication API (Step 4)

```
POST /api/v1/auth/register   { name, email, password, confirm_password }
POST /api/v1/auth/login      { email, password } → { user, token }
GET  /api/v1/auth/me         (Authorization: Bearer <token>) → actual user
POST /api/v1/auth/logout     → client discards its token (see docs/authentication.md)
```

Argon2-hashed passwords, JWT access tokens, and a single reusable
`get_current_user` dependency protecting authenticated routes. Step
3's coin/market endpoints remain unauthenticated and unaffected. See
[`docs/authentication.md`](docs/authentication.md) for the full flow,
error codes, and V1 limitations (no OTP, no email verification, no
password reset, no social login — not started, not scaffolded).

## 14. Frontend Pages (Step 5)

| Route | Auth required | Notes |
|---|---|---|
| `/` | No | Landing page |
| `/login`, `/register` | No | Auth pages (Step 4) |
| `/market-test` | No | Step 3's development verification page |
| `/dashboard` | Yes | Market overview, gainers/losers, paginated coin table |
| `/markets` | Yes | Market stats, gainers/losers, full sortable/filterable/paginated coin table, backend search |
| `/coins/:coinId` | Yes | Coin details: price (with 24h $ and %), stats incl. FDV, ATH/ATL with dates, 1h–1y performance, candlestick chart with timeframe selector |

All market data on `/dashboard` and `/markets` comes from the Step 3
API — there is no hard-coded coin list anywhere in the frontend. If
the backend has no synced data yet, the UI shows an empty state
("No cryptocurrencies found.") rather than fabricating one.

## 14b. ML Prediction Engine (Phase 13)

Models are **trained explicitly** and only *loaded* by the API (nothing trains at
start-up or on page load):

```bash
pip install -r backend/requirements.txt          # numpy, pandas, scikit-learn, xgboost, lightgbm, torch
python -m ml.pipelines.training_pipeline --coin bitcoin --horizons 24h --models xgboost lightgbm --ensemble
curl http://127.0.0.1:8000/api/v1/predictions/<coin_id>
```

Until a model has been trained **and** has beaten the baselines on held-out data, the
API reports `model_unavailable` and the Coin Details page says "Prediction
unavailable" — it never shows a placeholder forecast. Details: `ml/README.md`,
`ml/artifacts/README.md`, `docs/api.md`.

## 14d. Gemini AI Analysis (Phase 15)

Gemini (`gemini-3.1-flash-lite`) explains the platform's existing analysis in plain language; it never changes the
Phase 14 BUY / HOLD / SELL and never predicts prices. Set `GEMINI_API_KEY` in `backend/.env` (server-side only);
without it the app works normally and the AI section reports "temporarily unavailable".

```bash
curl http://127.0.0.1:8000/api/v1/ai-analysis/<coin_id>                      # stored explanation
curl -X POST -H "Authorization: Bearer <token>" http://127.0.0.1:8000/api/v1/ai-analysis/<coin_id>/generate
```

Details: [`docs/ai-analysis.md`](docs/ai-analysis.md).

## 14c. Risk & Decision Engine (Phase 14)

A deterministic, rule-based decision-support engine (no Gemini/LLM, no randomness, no trading) that combines
market, technical, fundamental, sentiment and ML-prediction outputs into a risk score (0-100), a
risk level, a BUY / HOLD / SELL decision, a confidence and rule-generated factors:

```bash
curl http://127.0.0.1:8000/api/v1/decisions/<coin_id>
```

When the data cannot support an honest decision the API returns `decision: null` with a `status`
(`INSUFFICIENT_DATA`, `STALE_DATA`, ...) — it never forces one. A missing ML prediction (e.g. no trained model)
is handled explicitly: the decision is made from the remaining signals and says so. Weights, thresholds and
versions are in `backend/app/config/risk_config.py`; the methodology is in
[`docs/risk-decision-engine.md`](docs/risk-decision-engine.md). The Coin Details page has a "Risk & Decision" section.

## 15. Current Project Phase

**Phase 9 — Coin Details & Charts.** See
[`docs/roadmap.md`](docs/roadmap.md).

## 16. Future Roadmap

See [`docs/roadmap.md`](docs/roadmap.md) for Steps 7–11
(technical/fundamental analysis, news/sentiment, prediction engine,
personalization features, and hardening).
