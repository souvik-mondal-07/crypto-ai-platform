# Development Guide

## Prerequisites

- Node.js 18+ and npm
- Python 3.10+
- MongoDB (installed locally — no Docker)

## MongoDB local setup

Install MongoDB Community Edition for your OS following the official
docs, then start it as you normally would for your platform (e.g. via
your OS's service manager, or by running `mongod` directly pointed at
a data directory).

**Verify it's running:**

```bash
mongosh --eval "db.runCommand({ ping: 1 })"
```

A successful response (`{ ok: 1 }`) means MongoDB is reachable at the
default `mongodb://localhost:27017`.

**Default connection:** the backend defaults to
`MONGODB_URI=mongodb://localhost:27017` and
`MONGODB_DATABASE=crypto_ai_platform` (see `backend/.env.example`).
The database itself doesn't need to be created ahead of time — MongoDB
creates it (and each collection) lazily on first write.

**Changing the URI or database name:** edit `backend/.env`:

```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=crypto_ai_platform
```

If your MongoDB instance requires authentication, embed the
credentials directly in the URI
(`mongodb://<user>:<password>@localhost:27017`) — never as separate
plain-text fields, and never commit a real URI to `.env.example`.

**If MongoDB isn't running:** the backend still starts (so you can
work on the frontend independently), but logs a clear
`MongoDB connection failed` message and `GET /api/v1/health` reports
`"database": "disconnected"` / `"status": "degraded"` instead of
silently claiming to be connected.

## Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Verify:
- http://127.0.0.1:8000/
- http://127.0.0.1:8000/api/v1/health — check `"database": "connected"`
  if MongoDB is running
- http://127.0.0.1:8000/docs (interactive Swagger UI)

Run tests:

```bash
pytest                    # everything, including integration tests
pytest -m "not integration"   # unit tests only — no MongoDB required
pytest -m integration         # only tests that require a running MongoDB
```

Integration tests (`tests/test_database.py`,
`tests/test_market_data_integration.py`) skip themselves automatically
(rather than failing) if MongoDB isn't reachable at the configured
`MONGODB_URI`. All external HTTP calls (CoinGecko/Binance) in the
test suite are mocked with `respx` — tests never hit the real
provider APIs.

## Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Visit http://localhost:5173/ — the homepage's System Status panel
should show both Frontend and Backend as Online once the backend is
running. Follow the "View market data test page" link (or go to
http://localhost:5173/market-test) to see real synchronized coin data
once you've run a sync (see below).

## Manually testing authentication locally (Step 4)

1. Start the backend and frontend as above (MongoDB running).
2. Visit http://localhost:5173/register and create a real account —
   pick any name/email/password you like for local testing.
3. You'll be redirected to `/login` (V1 does not auto-login after
   registration — see `docs/authentication.md`). Log in with the same
   credentials.
4. You should land on `/dashboard` and see the *exact* name/email you
   registered with — never "Demo User" or any other placeholder.
5. Refresh the browser. The same name should still be there (this
   exercises `authStore.initializeAuth()` calling `/auth/me`).
6. Click Logout. You should be sent to `/login`, and the previous
   name must not remain visible anywhere.
7. Log in again with the same account and confirm the name is correct
   again.
8. Try visiting `/dashboard` directly while logged out — you should be
   redirected to `/login`, not shown the page.

## Manually testing the market dashboard locally (Step 5)

Requires a market-data sync to have been run (see the section below)
— otherwise the empty states are what you'll see, which is correct
behavior, not a bug.

1. Log in (see above), landing on `/dashboard`.
2. Confirm the market overview cards, top gainers, top losers, and
   coin table show real numbers matching what you synced — not
   placeholders.
3. Click a coin row — you should land on `/coins/<id>` showing that
   coin's actual name/symbol/price.
4. Go to `/markets`. Type a real coin name/symbol into the search box
   and confirm the network tab shows a request to
   `/api/v1/coins/search?q=...` (not a locally-filtered list) after
   you stop typing (the 350ms debounce).
5. Switch the All / Gainers / Losers filter and confirm each shows
   different, real data.
6. Click a column header (Rank/Coin) to sort; confirm the arrow
   indicator and order change, and that this triggers a new
   `/api/v1/coins?sort_by=...` request rather than re-sorting
   client-side.
7. Toggle the theme button in the header; confirm the whole page
   (including cards/tables) switches between light and dark, and that
   the choice persists across a refresh.
8. Resize the browser to a mobile width; confirm the header collapses
   sensibly and the coin table scrolls horizontally rather than
   breaking the page layout.
9. Turn off the backend and refresh `/dashboard` — confirm you see
   "Unable to load..." messages with a Retry button, not a blank page
   or a crash.

## Syncing market data locally (Step 3)

The coin/market-data list is empty until you trigger a sync — there is
no seed data. To trigger one locally:

1. In `backend/.env`, set `ENABLE_DEV_SYNC_ENDPOINT=true` (development
   only — see `app/api/v1/dev_sync.py`; never enable this in a
   publicly reachable deployment).
2. Restart the backend.
3. `curl -X POST http://127.0.0.1:8000/api/v1/dev/sync/market`

This fetches CoinGecko's full coin list, several pages of ranked
market data, and (best-effort) Binance trading-pair mappings — see
`docs/market-data.md` for exactly what each step does and why it's
bounded the way it is. A sync takes anywhere from a few seconds to
around a minute depending on `max_pages`/`per_page` and CoinGecko's
current response time.

Build & lint:

```bash
npm run build
npm run lint
npm run test    # Vitest — auth store, ProtectedRoute, LoginForm, Axios interceptor (Step 4)
```

## Environment variables

See root `.env.example`, `frontend/.env.example`, and
`backend/.env.example`. No API keys are required for Step 1 — do not
add real credentials to any `.env.example` file, and never commit a
real `.env` file.

## Adding a new backend feature (future steps)

1. Define the Pydantic schema in `app/schemas/`.
2. Add/confirm the collection name in
   `app/database/collections.py` (`CollectionName`) — never a raw
   string literal elsewhere.
3. Add a repository in `app/repositories/` subclassing
   `BaseRepository`, with `collection_name = CollectionName.X`.
4. If the feature needs an external data source, add a provider under
   `app/providers/<name>/` (client + mapper + provider implementing
   `MarketDataProvider` or a similarly small interface) — never call
   an external HTTP API from a service or route directly.
5. Implement business logic in `app/services/`, calling the
   repository (and provider, if any) — never MongoDB or an external
   API directly.
6. Expose it via a router in `app/api/v1/`, registered in
   `app/api/v1/__init__.py`. Routes call services, never repositories,
   providers, or MongoDB directly.
6. If the collection needs a new index, add it to
   `app/database/indexes.py` and document it (with the query pattern
   it supports) in `docs/database-schema.md`.

## Adding a new frontend feature (future steps)

1. Add types to `src/types/`.
2. Add an API service in `src/services/api/`.
3. Add a Zustand store in `src/store/` if shared state is needed.
4. Build the page in `src/pages/` and components in `src/components/`.
5. Register the route in `src/routes/AppRoutes.tsx`.

## Manually testing Coin Details (Step 6)

Requires a market-data sync (see below) so coins exist to click into.

1. From `/dashboard` or `/markets`, click any coin row/card — you
   should land on `/coins/<internal-id>` (the platform's own ObjectId,
   not a symbol or provider ID).
2. Confirm the header shows that coin's real name, symbol, rank, and
   current price — matching what the same coin showed in the table.
3. Confirm market stats (market cap, volume, supply) and ATH/ATL
   render real values, with `N/A` wherever the backend returned null.
4. Confirm the candlestick chart loads with `7D` selected by default,
   and that the label under "Price Chart" states the candle
   granularity (e.g. "4h candles").
5. Switch timeframes (1D / 30D / 90D / 1Y). Each should show a chart
   loading state, then new candles — and the network tab should show
   only a new `/history` request, not a re-fetch of the coin itself.
6. Drag to pan and scroll to zoom the chart; confirm the crosshair
   follows the cursor.
7. Toggle the theme while on this page — the chart's text/grid/border
   colors should update without the chart being recreated or losing
   its zoom.
8. Resize to mobile width — the chart should resize with the
   container, and the stat cards should reflow without horizontal
   page scrolling.
9. Visit `/coins/not-a-real-id` directly — you should see
   "Cryptocurrency not found." with a Back to Markets link, not a
   crash.
10. Stop the backend and reload — you should get an error state with a
    Retry button rather than a blank or broken chart.
