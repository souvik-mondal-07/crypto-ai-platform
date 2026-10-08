# Market Data Engine (Step 3)

This document describes the crypto market-data infrastructure: the
provider architecture, coin normalization/synchronization, and the
API endpoints built on top of it.

## Provider architecture

```
API Route → Service → Provider Interface → Provider Client → Mapper → Normalized object → Repository → MongoDB
```

Every provider implements the common `MarketDataProvider` interface
(`app/providers/base.py`). Each provider is split into three files:

- **`client.py`** — raw HTTP calls only (via the shared
  `request_json()` helper in `app/providers/http.py`, built on
  `httpx`). No normalization, no business logic.
- **`mapper.py`** — pure functions that convert raw provider JSON into
  provider-agnostic dataclasses (`app/providers/normalized.py`). No
  HTTP, no MongoDB.
- **`provider.py`** — implements `MarketDataProvider` by combining the
  client and mapper.

Nothing outside `app/providers/<name>/` knows what a raw CoinGecko or
Binance response looks like.

## CoinGecko — the broad-universe source

CoinGecko is used as the platform's primary source for the coin
*universe* (which coins exist) because it covers a very large set of
cryptocurrencies without requiring scraping or a paid license:

- `GET /coins/list` — the **entire** coin universe (id, symbol, name),
  in one unpaginated call. This is what the platform's coin list is
  built from — not a hard-coded top-10/50/100.
- `GET /coins/markets` — paginated, ranked by market cap, with live
  price/market-cap/volume/rank/logo data. Bounded per sync run (see
  "Sync bounds" below) — this is the *enrichment* pass, not the
  universe source.
- `GET /global` — aggregate market statistics.
- `GET /search/trending` — CoinGecko's trending-coins list.

All of these are CoinGecko's public REST API — no scraping, no
violation of terms of service.

## Binance — exchange-specific data, not a universe source

Binance only lists the trading pairs it actually supports. It is used
for a narrower purpose: enriching a coin record with
"is this tradable on Binance, and under what symbol" via
`GET /api/v3/exchangeInfo` (filtered to USDT-quoted pairs).

**Binance's listing is explicitly NOT treated as equivalent to
CoinGecko's.** `BinanceProvider.list_coins()` /
`get_market_data()` intentionally raise `ProviderError` rather than
silently returning a partial/misleading result — Binance's actual
capability is `list_trading_pairs()`. The matching between a Binance
base asset and a CoinGecko coin is done by symbol, which is
best-effort (symbols aren't globally unique — see
`docs/database-schema.md`), so an occasional wrong match is possible
and acceptable for this enrichment step; it never affects whether a
coin is considered part of the platform's universe.

**"All coins available from CoinGecko" and "all Binance-tradable
assets" are two different sets.** Nothing in this codebase claims
otherwise.

## CoinMarketCap

The original product vision references a coin universe "comparable to
CoinMarketCap." **This step does not integrate CoinMarketCap in any
way** — no scraping, no HTML parsing of their site, no unofficial data
reuse. The provider abstraction (`MarketDataProvider`) is designed so
a `CoinMarketCapProvider` could be added later *if* the project
obtains a licensed/official API key, without changing the sync
service, repositories, or API layer. For Step 3, **CoinGecko is the
sole broad-listing source**, and every response that returns coin data
reports `"data_source": "coingecko"` so this is never ambiguous to a
client of the API.

## Coin identity model

A coin's canonical identity is an internal MongoDB `_id` — never a
provider's ID, and never its ticker symbol (symbols collide across
unrelated coins). Provider-specific identifiers live in a `providers`
map:

```json
{
  "_id": "ObjectId(...)",
  "name": "Bitcoin",
  "symbol": "BTC",
  "slug": "bitcoin",
  "logo_url": "https://...",
  "market_cap_rank": 1,
  "is_active": true,
  "providers": {
    "coingecko": { "id": "bitcoin", "available": true },
    "binance": { "symbol": "BTCUSDT", "available": true }
  },
  "created_at": "...",
  "updated_at": "..."
}
```

`providers.coingecko.id` is the uniqueness anchor (unique index — see
`docs/database-schema.md`). This is a schema evolution from Step 2's
flat `(provider, provider_coin_id)` design, made necessary by the
requirement that one canonical coin can map to multiple providers at
once. Since Step 2 never wrote any real data, this was a clean,
non-breaking change (the outdated index is dropped safely on startup;
see `app/database/indexes.py`).

## Synchronization

`MarketSyncService.sync()` (`app/services/market_sync_service.py`)
runs three steps, each independently resilient to failure:

1. **Full-universe upsert.** Fetches `/coins/list` (all coins, one
   call), upserts every coin by `providers.coingecko.id` (bulk
   `UpdateOne` operations, never one write per coin), and then
   deactivates (`is_active: false`) any previously-active coin *not*
   seen in this fetch. This deactivation step is safe specifically
   because `/coins/list` is a genuinely complete universe fetch, not
   a page — see the `deactivate_stale()` docstring in
   `app/repositories/coin_repository.py`.
2. **Market data pages.** Fetches up to `max_market_pages` pages
   (default 4 × 250 = 1,000 coins) of `/coins/markets`, upserting both
   coin enrichment fields (rank, logo) and the `market_data` snapshot.
   Bounded deliberately — see "Sync bounds" below.
3. **Binance mapping.** Fetches Binance's USDT trading pairs and
   attaches a `providers.binance` mapping wherever a symbol match is
   found. Never deactivates a coin — Binance not listing something is
   not evidence it doesn't exist.

A failure in any step is recorded in `SyncResult.errors` and does not
abort the other steps or crash the process. **Duplicate prevention**:
every upsert is keyed by `providers.coingecko.id` (coins) or `coin_id`
(market data) — running `sync()` repeatedly updates existing
documents rather than inserting new ones (see
`tests/test_market_sync_service.py::test_sync_does_not_create_duplicate_coins_on_repeat_id`
and the equivalent MongoDB-backed integration test).

### Sync bounds

`DEFAULT_MAX_MARKET_PAGES = 4` (with `per_page = 250`, ~1,000 coins
get live price/rank data per **manual dev-sync call**). This remains
a sane default for a single one-off manual trigger — CoinGecko's
public/demo tier is rate-limited, and looping through every page on
every manual click is both slow and likely to trip a 429. The
dev-sync endpoint's `max_pages` query parameter can go up to 100 for
a one-off full-universe backfill/validation run (see "Triggering a
sync" below).

**Day-to-day freshness is no longer this endpoint's job** — see "Step
11: real-time background refresh" below for what actually keeps
`market_data` current without a manual call or a backend restart.

### Triggering a sync

Step 3 does not implement a scheduler. Synchronization is triggered
manually via a **development-only** endpoint:

```
POST /api/v1/dev/sync/market
```

This endpoint only exists (the route isn't registered at all) when
`ENABLE_DEV_SYNC_ENDPOINT=true` is set — off by default. **This is not
authentication** — Step 3 explicitly does not implement auth — it's a
guard against accidentally exposing an unbounded, unauthenticated
"trigger provider requests" endpoint. Do not enable this flag in any
publicly reachable deployment. See `app/api/v1/dev_sync.py`.

`MarketSyncService.sync()` itself has no dependency on how it's
triggered — a future Celery periodic task or CLI script can call it
directly without any changes to this file.

## Pagination

```
GET /api/v1/coins?page=1&limit=100
```

Returns:

```json
{ "items": [...], "page": 1, "limit": 100, "total": 10432, "pages": 105 }
```

`total`/`pages` are computed from the actual synchronized MongoDB
collection at request time — never a fabricated number. `limit` is
clamped server-side to a maximum of 250 (`app/utils/pagination.py`)
regardless of what a client requests.

## Search

```
GET /api/v1/coins/search?q=bitcoin
```

Case-insensitive (MongoDB regex with the `i` option) across
`name`/`symbol`/`slug`, run against the normalized `coins` collection
— **never** a live provider call per keystroke. The frontend debounces
input by 350ms before calling this endpoint (see
`frontend/src/hooks/useDebouncedValue.ts`).

## Sorting & filtering

`GET /api/v1/coins` accepts `sort_by` (one of `name`, `symbol`,
`market_cap_rank`, `updated_at` — enforced by a server-side whitelist,
`SORTABLE_FIELDS` in `app/repositories/coin_repository.py`),
`sort_direction` (`asc`/`desc`), `active_only`, and `provider`
(`coingecko`/`binance`). Any other value for `sort_by`/`provider`
returns `400 INVALID_SORT_FIELD` / `400 INVALID_PROVIDER` — a raw
client-supplied string is never passed into a MongoDB sort/filter
spec.

## Market data endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/coins/{id}/market` | Current snapshot for one coin |
| `GET /api/v1/coins/{id}/history` | Historical OHLC candles (Step 6) |
| `GET /api/v1/market/overview` | Active coin count + top gainers/losers, for a future dashboard |
| `GET /api/v1/market/gainers` | Top 24h gainers from synced data |
| `GET /api/v1/market/losers` | Top 24h losers from synced data |
| `GET /api/v1/market/global` | Live global stats from CoinGecko's `/global` |
| `GET /api/v1/market/trending` | Trending coins, or `"available": false` if unsupported |

`market_data` stores **one upserted snapshot per coin** (unique index
on `coin_id`), not a growing time series — see `docs/database-schema.md`
for why this is architecturally distinct from the future
`historical_prices` collection.

### Data freshness

Every `MarketData` response includes `last_updated` (the provider's
own reported timestamp, if any), `data_source`, and `is_stale`
(computed at read time — a snapshot older than 6 hours is flagged
stale; see `STALE_AFTER` in `app/schemas/converters.py`). "Stale" data
is still returned (rather than hidden) — it's labeled, not hidden or
presented as live.

## Missing provider fields

Every mapper reads fields with `.get()` and no fabricated default — a
field CoinGecko doesn't return becomes `null` in the API response,
never a made-up number. See
`tests/test_coingecko_mapper.py::test_map_coin_market_missing_fields_become_none_not_fake_values`.

## Error handling

All provider failures are translated into a small hierarchy
(`app/providers/errors.py`) and given a consistent HTTP response by
handlers registered in `app/core/exceptions.py` — **every** API error,
regardless of cause, has the shape:

```json
{ "error": { "code": "PROVIDER_UNAVAILABLE", "message": "..." } }
```

No raw traceback or internal exception message is ever returned to a
client (unhandled exceptions are logged server-side and reported as a
generic `500 INTERNAL_ERROR`).

| Situation | HTTP status | Error code |
|---|---|---|
| Provider rate limit (429) | 429 | `PROVIDER_RATE_LIMITED` |
| Provider timeout | 504 | `PROVIDER_TIMEOUT` |
| Provider unreachable / 5xx | 503 | `PROVIDER_UNAVAILABLE` |
| Provider returned malformed data | 502 | `PROVIDER_BAD_RESPONSE` |
| Invalid pagination/sort/search input | 400 | `INVALID_*` |
| Coin/market data not found | 404 | `COIN_NOT_FOUND` / `MARKET_DATA_NOT_AVAILABLE` |
| Anything unexpected | 500 | `INTERNAL_ERROR` |

### Retry & rate-limit behavior

`app/providers/http.py`'s shared request helper:
- Retries up to twice on timeouts and 5xx responses only, with a short
  linear backoff.
- **Never retries a 429** — it's raised immediately as
  `ProviderRateLimitError` so the caller can decide what to do (the
  dev sync endpoint simply reports it in `SyncResult.errors`) rather
  than hammering an already-throttled provider.
- Never retries other 4xx responses (a bad request won't fix itself on
  retry).

## Environment variables

Added in Step 3 (see `backend/.env.example`):

```
COINGECKO_API_BASE_URL=https://api.coingecko.com/api/v3
BINANCE_API_BASE_URL=https://api.binance.com
COINGECKO_API_KEY=            # optional — raises CoinGecko's own rate limit
ENABLE_DEV_SYNC_ENDPOINT=false
```

No API key is required to run Step 3 — both base endpoints used here
are public. `COINGECKO_API_KEY` is backend-only and never exposed to
the frontend; the frontend only ever knows `VITE_API_BASE_URL`
(pointing at this backend, never at a provider directly).

## Caching

No Redis in Step 3. `market_data`'s one-document-per-coin upsert
pattern already gives a "current snapshot" read path without needing
an additional cache layer yet. The service layer (`MarketService`,
`MarketSyncService`) doesn't hold any provider-specific state, so
introducing Redis later (e.g. to cache `/market/global` for a few
minutes) won't require restructuring this code.

## Testing

- **Mapper unit tests** (`tests/test_coingecko_mapper.py`,
  `tests/test_binance_mapper.py`) — fixture JSON in, normalized
  dataclasses out. No HTTP, no MongoDB.
- **Provider HTTP tests** (`tests/test_provider_http.py`) — success,
  empty response, malformed JSON, timeout, 429 (asserts exactly one
  request — no retry loop), 500 (asserts bounded retries), 404,
  connection failure. All mocked with `respx`; no live network calls.
- **Service unit tests** (`tests/test_coin_service.py`,
  `tests/test_market_sync_service.py`) — fake repository/provider
  doubles, no MongoDB required. Covers input validation, duplicate
  prevention, pagination stop conditions, and provider-failure
  resilience.
- **API tests** (`tests/test_coins_api.py`) — `TestClient` with the
  service layer mocked, verifying request validation and the
  consistent error-response shape.
- **Integration tests** (`tests/test_market_data_integration.py`) —
  real MongoDB required; skip automatically (not fail) if unreachable.
  Verify upsert-not-duplicate behavior, gainers sorting, and
  case-insensitive search against real documents (which are cleaned up
  after each test).

Run `pytest -m "not integration"` for a MongoDB-free run, or `pytest`
for everything.

## Historical OHLC data (Step 6)

```
GET /api/v1/coins/{coin_id}/history?timeframe=7D
```

Returns candles for charting:

```json
{
  "coin_id": "<internal ObjectId>",
  "timeframe": "7D",
  "granularity": "4h",
  "candles": [
    { "timestamp": "2026-01-01T00:00:00Z", "open": 100.0, "high": 110.0,
      "low": 95.0, "close": 105.0, "volume": null }
  ],
  "data_source": "coingecko"
}
```

### Supported timeframes — and why not 1H/4H

`1D`, `7D`, `30D`, `90D`, `1Y` (see
`app/providers/timeframes.py`, the single source of truth). Anything
else returns a `422` listing the accepted values rather than being
silently coerced.

Sub-daily *ranges* (1H, 4H) are deliberately **not** offered.
CoinGecko's `/coins/{id}/ohlc` takes a `days` parameter and chooses
candle granularity itself — there is no way to request "the last
hour." Offering a 1H button that actually returned a day of data, or
synthesizing intraday candles, would both be lying about the data's
provenance. Note that `1D` already returns ~30-minute candles, which
covers the short-timeframe use case with real provider data.

Provider granularity per timeframe:

| Timeframe | `days` | Candle granularity |
|---|---|---|
| `1D` | 1 | ~30 minutes |
| `7D` | 7 | ~4 hours |
| `30D` | 30 | ~4 hours |
| `90D` | 90 | ~4 days |
| `1Y` | 365 | ~4 days |

The response echoes `granularity` so the frontend can label the chart
honestly instead of guessing.

### Volume is always null

CoinGecko's OHLC endpoint returns `[timestamp, open, high, low, close]`
— **no volume component**. `volume` is therefore always `null` in
these responses. It is never backfilled from the 24h-volume field in
`market_data` (a single rolling total, not per-candle volume), because
that would attach a number to each candle that the provider never
reported for that interval.

### Validation, not correction

`map_ohlc` (`app/providers/coingecko/mapper.py`) **drops** rows that
are malformed (wrong shape, non-numeric) or internally inconsistent
(`high < max(open, close)`, or `low > min(open, close)`). It never
clamps or adjusts values to make them consistent — silently reshaping
provider numbers would mean charting data the provider never sent.
Candles are returned sorted chronologically.

### Read live, not from `historical_prices`

This endpoint fetches from the provider on each request. The
`historical_prices` collection remains schema-only (see
`docs/database-schema.md`) — no ingestion job populates it yet, so
reading from it would return nothing. Persisting candles is a
separate concern from rendering a chart, and belongs to whichever
step actually builds that ingestion (at which point this service
method is the one place that would change).

## Phase 7 additions

Phase 7's Market Data Engine requirements were largely already
satisfied by the Step 3 build documented above (provider abstraction,
CoinGecko + Binance providers, normalization, coin synchronization
with bulk upserts, search/pagination/sorting, error and rate-limit
handling, environment-driven configuration). Rather than rebuild that,
Phase 7 closed the three genuine gaps against its spec:

### 1. 24h high / low

`high_24h_usd` and `low_24h_usd` now flow the full chain — CoinGecko's
`high_24h`/`low_24h` fields → `NormalizedMarketData` → the
`market_data` collection → the `MarketData` API schema → the Coin
Details page. Absent values stay `null`, as with every other optional
field.

### 2. Ranking endpoints

```
GET /api/v1/market/top/market-cap?limit=20
GET /api/v1/market/top/volume?limit=20
```

Both read synced `market_data` and sort descending on the
corresponding field. The ranking key is resolved through a whitelist
(`RANKABLE_FIELDS` in `app/services/market_service.py`) before it
reaches MongoDB — a client string is never used as a sort field
directly, matching the rule already applied to coin sorting.

### 3. Binance exchange tickers (normalized)

```
GET /api/v1/market/exchange/binance/tickers?limit=50
```

Binance's `/api/v3/ticker/24hr` is now normalized into
`NormalizedExchangeTicker` / `ExchangeTicker` rather than returned as
raw provider dicts (the previous `get_ticker_map` is gone).

This is deliberately a **separate model and a separate endpoint** from
`MarketData`. A Binance pair price is one venue's price for one
trading pair; `market_data` holds the CoinGecko-sourced cross-market
aggregate. Merging them would present an exchange price as a coin's
global price, so the response is explicitly labelled with its
`exchange`. Binance's numeric fields arrive as strings and are parsed
to floats — an unparseable value becomes `null`, never `0.0`, since a
zero price is indistinguishable from a real one. Base/quote assets are
filled from `/exchangeInfo` rather than by string-splitting the
combined symbol, which is ambiguous.

## Phase 8: the joined Markets endpoint

```
GET /api/v1/market/coins?page=1&limit=25&sort_by=market_cap&sort_direction=desc&filter=all
```

Returns each coin joined with its current market snapshot:

```json
{
  "items": [
    { "coin_id": "...", "name": "...", "symbol": "...", "logo_url": null,
      "market_cap_rank": 1, "price_usd": 0.0, "percent_change_24h": 0.0,
      "high_24h_usd": 0.0, "low_24h_usd": 0.0, "market_cap_usd": 0.0,
      "volume_24h_usd": 0.0, "circulating_supply": 0.0, "last_updated": "..." }
  ],
  "page": 1, "limit": 25, "total": 0, "pages": 0,
  "sort_by": "market_cap", "sort_direction": "desc", "data_source": "coingecko"
}
```

### Why this endpoint exists

Two problems it solves at once:

1. **Sorting by market fields.** `/coins` sorts the `coins` collection,
   which holds identity only — it cannot sort by price, 24h change,
   market cap, or volume, because those live in `market_data`. This
   endpoint runs the aggregation *from the market_data side* so the
   `$sort` happens on the collection that owns the field and can use
   an index, rather than sorting in memory after a `$lookup`.
2. **The Step 5 N+1.** The Markets/Dashboard table previously fetched
   `/coins/{id}/market` once per visible row. This replaces that with
   one request per page. (Dashboard still uses the older path; only
   the Markets table was migrated in Phase 8.)

### Validation

`sort_by` resolves through `MARKET_SORT_FIELDS` and `filter` through
`MARKET_FILTERS` (`app/services/market_service.py`) before anything
reaches MongoDB — a client string is never used as a sort key or
filter directly. `limit` is capped at 100 by the route and again by
`clamp_pagination`.

`gainers`/`losers` are expressed as bounds on `percent_change_24h`
rather than as separate code paths, so they compose normally with
sorting and pagination.

Rows whose coin was deactivated between syncs are dropped by the
pipeline (`$match: {coin: {$ne: []}}`) rather than emitted with a
missing name.

### Search hardening

`CoinRepository.search` now regex-escapes the query before building
the `$regex` filter. Previously a user typing an unbalanced `(` would
hand MongoDB an invalid — or ReDoS-prone — pattern. Search also now
matches `providers.coingecko.id` explicitly, in addition to name,
symbol, and slug.

## Phase 9 additions to MarketData

Coin Details (Step 6) already covered the core of Phase 9's spec —
candlestick chart, timeframe selector, current price, market stats,
ATH/ATL, price performance, all loading/error/not-found states. Phase
9 closed the remaining gaps against CoinGecko fields that were
available but not yet captured:

| Field | Meaning |
|---|---|
| `price_change_24h_usd` | Absolute USD change over 24h — distinct from `percent_change_24h` |
| `percent_change_1y` | 1-year performance (now requested via `price_change_percentage=...,1y`) |
| `fully_diluted_valuation_usd` | FDV, when the provider supplies it |
| `ath_date` / `atl_date` | When the provider recorded the all-time high/low |

All four flow through the same chain as every other market field:
provider → `NormalizedMarketData` → `market_data` upsert → `MarketData`
API schema → `market_data_doc_to_schema` → the frontend. Absent for a
given coin, they render `N/A` (or the whole card is simply not
emphasized) — never computed or guessed locally. In particular,
`price_change_24h_usd` is the provider's own figure, not
`price_usd × percent_change_24h` recomputed client-side, which could
disagree with the provider depending on rounding and snapshot timing.

Timeframes for the historical chart are unchanged from Step 6 (`1D`,
`7D`, `30D`, `90D`, `1Y`) — Phase 9's spec re-listed 1H/4H, but the
underlying limitation documented in Step 6 still holds: CoinGecko's
`/coins/{id}/ohlc` picks candle granularity from a `days` parameter
and has no way to request a sub-daily range.

## Real-time refresh upgrade: automatic background refresh

Everything above described a **manually-triggered, one-shot** sync.
This upgrade adds a background process that keeps `market_data` fresh on
its own — this is the fix for coins showing "last updated: 7 days
ago" because nothing had re-synced them since Step 3's original
4-page, one-off sync.

### Architecture

```
                 ┌─────────────────────────────────────────┐
                 │   MarketRefreshScheduler (asyncio task)  │
                 │   started/stopped from main.py lifespan  │
                 └───────────────┬───────────────────────────┘
                                 │ every MARKET_REFRESH_INTERVAL_SECONDS
                                 ▼
        ┌────────────────────────────────────────────────────┐
        │ 1. Binance 24hr ticker (ONE bulk call) → live price/ │
        │    24h fields for every Binance-mapped coin          │
        │ 2. CoinGecko /coins/markets: HOT pages (top N by     │
        │    market cap, every cycle) + a rotating COLD window │
        │    (the rest of the ranked universe, a few pages     │
        │    further each cycle)                               │
        └────────────────────────────────────────────────────┘
                                 │ every MARKET_REFRESH_UNIVERSE_INTERVAL_SECONDS
                                 ▼
        ┌────────────────────────────────────────────────────┐
        │ 3. Full /coins/list resync + Binance mapping refresh │
        │    (new/delisted coins, new trading pairs)           │
        └────────────────────────────────────────────────────┘
```

No Celery, Redis, or Docker — this is a single `asyncio.create_task`
loop (`app/services/market_refresh_scheduler.py`), guarded by an
`asyncio.Lock` so a second cycle can never start while one is still
running.

### Two update paths, two freshness levels

- **Binance-mapped coins**: near-real-time. One bulk `/api/v3/
  ticker/24hr` call refreshes price, 24h change, 24h high/low, and
  24h volume for every coin with a `providers.binance.symbol` — cost
  is O(1) HTTP request regardless of how many coins are mapped.
  `MarketDataRepository.bulk_upsert_binance_prices` writes only those
  fields (tagged `data_source: "binance"`); it never touches
  market_cap_usd, supply, or ATH/ATL, since Binance's ticker doesn't
  carry them, and never overwrites a field with `null` just because
  a given tick's ticker happened not to include it.
- **Everything else**: refreshed via the CoinGecko hot/cold rotation
  above. Hot pages (`MARKET_REFRESH_HOT_PAGES`, default top 2 pages =
  top 500 by market cap) are re-fetched on literally every cycle,
  because those are exactly the coins the Dashboard overview,
  gainers/losers, and Markets' default sort read. The remaining page
  budget (`MARKET_REFRESH_MAX_PAGES - MARKET_REFRESH_HOT_PAGES`)
  rotates through the rest of the ranked universe a few pages at a
  time, wrapping back to the start once it reaches an empty page.

**Honest limitation**: CoinGecko's public/demo tier cannot support
refreshing the entire ~21k-coin universe every cycle — only a bounded
slice per cycle. A coin ranked, say, #8,000 will be refreshed on a
rotation measured in **cycles**, not seconds — with the default
settings (`MARKET_REFRESH_MAX_PAGES=8`, `HOT_PAGES=2`,
`INTERVAL_SECONDS=60`), the cold window advances 6 pages (1,500
coins) every 60s, so a full sweep of a ~10,000-coin ranked universe
takes on the order of tens of minutes, not seconds. This is fixable
only by a paid CoinGecko tier (more requests/minute) or accepting a
longer sweep — not by any code change here. Binance-mapped coins are
unaffected by this limit, since they're refreshed via the one bulk
ticker call every single cycle.

### Configuration

All of these are read once at process start (`app/config/settings.py`)
— see `.env.example` for the checked-in defaults:

| Variable | Default | Meaning |
|---|---|---|
| `MARKET_REFRESH_ENABLED` | `true` | Master on/off switch for the whole background loop |
| `MARKET_REFRESH_INTERVAL_SECONDS` | `60` | Seconds between cycles |
| `MARKET_REFRESH_MAX_PAGES` | `8` | Total CoinGecko pages fetched per cycle (hot + cold) |
| `MARKET_REFRESH_HOT_PAGES` | `2` | Of those, how many are the same top-ranked pages every cycle |
| `MARKET_REFRESH_PER_PAGE` | `250` | Coins per CoinGecko page (max the API allows) |
| `MARKET_REFRESH_REQUEST_DELAY_SECONDS` | `1.5` | Delay between successive CoinGecko page requests within one cycle |
| `MARKET_REFRESH_INCLUDE_BINANCE` | `true` | Whether the Binance fast-price step runs each cycle |
| `MARKET_REFRESH_UNIVERSE_INTERVAL_SECONDS` | `21600` (6h) | How often the full coin-list + Binance-mapping resync runs |

Disabling `MARKET_REFRESH_ENABLED` does not disable the manual
dev-sync endpoint — they're independent.

### Status/observability

```
GET /api/v1/market/refresh-status
```

Returns whether a cycle is currently running, when the last one
finished, its per-source counts (Binance coins updated, CoinGecko
pages completed, whether the cold rotation has wrapped), and the last
error string, if any. This is an in-memory, process-local, best-effort
view for debugging "why is this coin still stale" — not a persisted
audit log, and not shared across multiple backend workers if the app
is ever run with more than one.

### Frontend auto-refresh

The Dashboard, Markets table, and Coin Details page each silently
re-fetch on an interval (`VITE_MARKET_REFRESH_INTERVAL_MS`, default
20s) via a shared `usePolling` hook
(`frontend/src/hooks/usePolling.ts`):

- Pauses while the browser tab is hidden (`document.visibilityState`)
  and fires one immediate refresh when it becomes visible again,
  rather than polling a backgrounded tab or leaving it stale for up
  to a full interval after the person returns.
- "Silent" means: no loading-skeleton flicker (the loading flag is
  never set to `true` for a background tick) and no error banner for
  one missed tick — the last good data simply stays on screen until
  the next successful refresh. A silent call's failure is not
  swallowed by accident: it's a deliberate choice (see
  `marketStore.ts`) not to let a transient network blip in the
  background replace good data with an error state.
- The Markets table refreshes the *current* page/sort/filter in
  place — it never resets pagination, sort, filter, or search state.
- Coin Details refreshes only the market snapshot (price, 24h change,
  `is_stale`) on this interval — coin identity and OHLCV history are
  not re-fetched on every tick, since they don't change on this
  cadence.

### What still requires a manual/dev step

- A **first-time** backfill of the full ~21k-coin universe's market
  data (rather than waiting for the cold rotation to reach every
  coin) is still done via the dev-sync endpoint with a large
  `max_pages` value — see "Triggering a sync" above.
- The background scheduler assumes a single backend process. Running
  multiple worker processes would currently run one independent
  scheduler (and one independent rate-limit budget) per worker — this
  is not coordinated across processes, since that would require the
  external infrastructure (Redis, a distributed lock) this step
  deliberately avoids.
