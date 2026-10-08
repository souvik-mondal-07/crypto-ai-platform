# Database Schema

MongoDB is schema-flexible, but this application still relies on
consistent document shapes. This document defines the intended
structure of every planned collection.

**Status.** As of Step 3, `coins` and `market_data` are actively
populated by the market-data sync service (see
`docs/market-data.md`) — these two are no longer architecture-only.
Every other collection below remains schema-only: no business logic,
data population, or queries against them exist yet. Example documents
for the still-unimplemented collections are illustrative schema
examples, not real data.

## Conventions used throughout

- **Timestamps** are always timezone-aware UTC (`datetime` with
  `tzinfo=timezone.utc`, stored as BSON `Date`). Never naive/local
  time. Field names ending in `_at` (e.g. `created_at`, `updated_at`)
  follow this rule.
- **Identifiers**: MongoDB `ObjectId` is used for `_id` on every
  collection. External provider identifiers (e.g. a CoinGecko coin
  ID) are stored as separate fields, never reused as `_id` — the
  system must support multiple providers per coin, and provider IDs
  can change or be re-issued.
- **References** between collections are stored as the referenced
  document's `ObjectId` (e.g. `user_id`, `coin_id`), following
  MongoDB's normalized-reference pattern rather than embedding, since
  these are high-write, independently-queried collections.
- Collection names are never hard-coded as string literals in
  application code — see `app/database/collections.py`
  (`CollectionName`).

---

## `users`

**Purpose:** Registered platform accounts. Schema only — no
registration/login/JWT is implemented until Step 4.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `name` | string | yes | |
| `email` | string | yes | Unique (see indexes) |
| `password_hash` | string | yes | Never store a plaintext password. Hashing algorithm chosen in Step 4. |
| `is_active` | boolean | yes | Default `true` |
| `role` | string | yes | e.g. `"user"`, `"admin"` |
| `created_at` | datetime (UTC) | yes | |
| `updated_at` | datetime (UTC) | yes | |

**Identifier strategy:** `_id` (ObjectId), referenced by other
collections as `user_id`.

**Relationships:** referenced by `watchlists`, `portfolios`, `alerts`,
`analysis_history`.

**Indexes:** unique index on `email` (a user's email is their login
identifier; must be unique).

**Example (illustrative only):**
```json
{
  "_id": "ObjectId('...')",
  "name": "Example User",
  "email": "example@example.com",
  "password_hash": "<never populated in Step 2>",
  "is_active": true,
  "role": "user",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

---

## `coins`

**Purpose:** Master reference list of cryptocurrencies. As of Step 3,
this collection is actively synchronized from CoinGecko (the platform's
broad-listing source — see `docs/market-data.md`), with an optional
Binance trading-pair mapping attached where a match is found.

> **Schema note:** this collection's shape changed from Step 2's
> original design. Step 2 assumed one `(provider, provider_coin_id)`
> pair per coin document; Step 3 replaced that with a `providers` map
> so a single canonical coin can hold mappings for multiple providers
> at once (CoinGecko *and* Binance). Since Step 2 never wrote any real
> data, this was a clean, non-breaking change — see
> `app/database/indexes.py` for the safe index migration.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `name` | string | yes | e.g. `"Bitcoin"` |
| `symbol` | string | yes | e.g. `"BTC"` — NOT unique (see below) |
| `slug` | string | no | URL-friendly identifier (CoinGecko's own `id`, e.g. `"bitcoin"`, doubles as this) |
| `logo_url` | string | no | |
| `market_cap_rank` | int | no | Only populated once a coin appears in a `/coins/markets` page |
| `is_active` | boolean | yes | Default `true`; set `false` by the full-universe sync's mark-and-sweep step |
| `providers.coingecko.id` | string | yes | CoinGecko's internal ID — the uniqueness anchor |
| `providers.coingecko.available` | boolean | yes | |
| `providers.binance.symbol` | string | no | e.g. `"BTCUSDT"` — only present once matched |
| `providers.binance.available` | boolean | no | |
| `created_at` | datetime (UTC) | yes | |
| `updated_at` | datetime (UTC) | yes | |

**Identifier strategy:** `_id` (ObjectId) is the internal identifier
used by every other collection (`coin_id` references point here — not
at any provider's ID). `providers.coingecko.id` is the uniqueness
anchor since CoinGecko is the broad-universe source of truth; a coin
without a CoinGecko mapping doesn't currently exist in this system.

**Relationships:** referenced by `market_data`, `historical_prices`,
`technical_analysis`, `fundamental_analysis`, `news`, `predictions`,
`decisions`, `watchlists`, `portfolio_transactions`, `alerts`,
`analysis_history`.

**Indexes:**
- **Unique, sparse** index on `providers.coingecko.id` — the actual
  uniqueness guarantee, not `symbol`. Token symbols collide across
  unrelated projects (multiple coins have shared a ticker
  historically), so a unique index on `symbol` alone would be
  incorrect and would eventually reject legitimate distinct coins.
- Non-unique index on `providers.binance.symbol` (a delisted/relisted
  symbol, or a rare provider inconsistency, shouldn't hard-fail a sync).
- Non-unique indexes on `symbol`, `name`, `slug` (search/lookup).
- Non-unique indexes on `market_cap_rank`, `is_active` (listing/filtering).

**Example (illustrative only):**
```json
{
  "_id": "ObjectId('...')",
  "name": "Bitcoin",
  "symbol": "BTC",
  "slug": "bitcoin",
  "logo_url": "https://example.com/btc.png",
  "market_cap_rank": 1,
  "is_active": true,
  "providers": {
    "coingecko": { "id": "bitcoin", "available": true },
    "binance": { "symbol": "BTCUSDT", "available": true }
  },
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

---

## `market_data`

**Purpose:** Current market snapshot per coin (price, market cap,
volume, etc.) — deliberately separate from `historical_prices` so
this collection stays small and fast to query, rather than growing
unbounded with every historical point.

> **Implementation note (Step 3):** unlike Step 2's original sketch
> (a new timestamped document per refresh), the implemented design
> stores **one upserted document per coin** — each sync overwrites
> that coin's snapshot rather than appending a new one. This matches
> Step 3's actual requirement ("store current market data"; historical
> tracking is `historical_prices`, a later step) and keeps the
> collection's size proportional to the number of coins, not the
> number of sync runs.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `coin_id` | ObjectId | yes | References `coins._id` — **unique** (one snapshot per coin) |
| `price_usd` | double | no | Null if the provider didn't supply it |
| `market_cap_usd` | double | no | |
| `volume_24h_usd` | double | no | |
| `percent_change_1h` | double | no | |
| `percent_change_24h` | double | no | |
| `percent_change_7d` | double | no | |
| `percent_change_30d` | double | no | |
| `circulating_supply` | double | no | |
| `total_supply` | double | no | |
| `max_supply` | double | no | |
| `ath_usd` | double | no | |
| `atl_usd` | double | no | |
| `ath_change_percentage` | double | no | |
| `atl_change_percentage` | double | no | |
| `last_updated` | datetime (UTC) | no | The provider's own reported timestamp for this data |
| `data_source` | string | yes | e.g. `"coingecko"` |
| `updated_at` | datetime (UTC) | yes | When *this application* last wrote the snapshot; used to compute `is_stale` at read time |

**Identifier strategy:** `_id` (ObjectId); `coin_id` is unique — each
sync upserts the existing document for that coin rather than
inserting a new one.

**Relationships:** `coin_id` → `coins._id`.

**Indexes:**
- **Unique** index on `coin_id`.
- Index on `updated_at` (staleness checks, future cleanup jobs).
- Index on `percent_change_24h` (gainers/losers queries).
- Index on `market_cap_usd` (overview/ranking queries).

**Example (illustrative only):**
```json
{
  "_id": "ObjectId('...')",
  "coin_id": "ObjectId('...')",
  "price_usd": 65000.12,
  "market_cap_usd": 1280000000000,
  "volume_24h_usd": 32000000000,
  "percent_change_1h": 0.12,
  "percent_change_24h": 1.85,
  "percent_change_7d": -2.3,
  "percent_change_30d": 10.1,
  "circulating_supply": 19700000,
  "ath_usd": 73000,
  "atl_usd": 67.81,
  "last_updated": "2026-01-01T00:00:00Z",
  "data_source": "coingecko",
  "updated_at": "2026-01-01T00:05:00Z"
}
```

---

## `historical_prices`

**Purpose:** OHLCV candle data for charting/backtesting. Designed to
scale — no document grows unbounded with appended candles.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `coin_id` | ObjectId | yes | References `coins._id` |
| `provider` | string | yes | |
| `timeframe` | string | yes | e.g. `"1h"`, `"4h"`, `"1d"` |
| `timestamp` | datetime (UTC) | yes | Candle open time |
| `open` | double | yes | |
| `high` | double | yes | |
| `low` | double | yes | |
| `close` | double | yes | |
| `volume` | double | yes | |

**Design decision — one document per candle, not one growing document
per coin.** An earlier alternative (a single document per coin holding
an array of all candles) was deliberately rejected: MongoDB documents
have a 16MB size ceiling, and an ever-appending array also causes
repeated document moves/rewrites as it outgrows its allocated space.
One document per candle keeps writes cheap and append-only, and lets
the compound index below serve range queries efficiently.

**MongoDB time-series collections:** considered, and likely the right
choice once real historical ingestion begins (a `timeseries`
collection with `timeField: "timestamp"`, `metaField: "coin_id"`,
`granularity` matched to the ingestion cadence would reduce storage
and improve range-scan performance over the plain-collection approach
above). **Not adopted in Step 2** — there's no data being ingested
yet, so introducing a time-series collection now would be
over-engineering ahead of actual need. This is flagged here so the
decision gets revisited in the step that implements historical price
ingestion, rather than defaulting silently to a plain collection.

**Identifier strategy:** `_id` (ObjectId) per candle document.

**Relationships:** `coin_id` → `coins._id`.

**Indexes:** compound index on `(coin_id, timeframe, timestamp desc)`
— supports "give me the last N daily candles for coin X" efficiently.

**Example (illustrative only):**
```json
{
  "_id": "ObjectId('...')",
  "coin_id": "ObjectId('...')",
  "provider": "binance",
  "timeframe": "1d",
  "timestamp": "2026-01-01T00:00:00Z",
  "open": 64500.0,
  "high": 65200.0,
  "low": 64100.0,
  "close": 65000.12,
  "volume": 18234.5
}
```

---

## `technical_analysis`

**Purpose:** Computed technical indicators per coin/timeframe. No
calculation logic exists yet — this is storage shape only.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `coin_id` | ObjectId | yes | References `coins._id` |
| `timeframe` | string | yes | |
| `timestamp` | datetime (UTC) | yes | |
| `rsi` | double | no | |
| `macd` | object | no | `{ macd, signal, histogram }` |
| `sma` | object | no | e.g. `{ "20": ..., "50": ..., "200": ... }` |
| `ema` | object | no | same shape as `sma` |
| `bollinger_bands` | object | no | `{ upper, middle, lower }` |
| `atr` | double | no | |
| `volume` | double | no | |
| `support_levels` | array\<double\> | no | |
| `resistance_levels` | array\<double\> | no | |
| `trend` | string | no | e.g. `"bullish"`, `"bearish"`, `"neutral"` |

**Identifier strategy:** `_id` (ObjectId), one document per
coin/timeframe/timestamp snapshot.

**Relationships:** `coin_id` → `coins._id`.

**Indexes:** none created in Step 2 — no query pattern exists yet
since no indicator is calculated. A compound index on
`(coin_id, timeframe, timestamp desc)` (mirroring `historical_prices`)
is the expected future index once this collection is written to.

---

## `fundamental_analysis`

**Purpose:** Per-coin fundamental analysis (Phase 11): the
provider-fetched project/ecosystem profile (cached) plus the latest
calculation snapshot. Market values are **not** stored here — they are
read from `market_data` so there is a single source of truth. See
docs/fundamental-analysis.md.

One document per coin (upserted).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `coin_id` | ObjectId | yes | References `coins._id`; **unique** |
| `symbol` | string | yes | |
| `source` | string | yes | Profile provider, `"coingecko"` |
| `project_info` | object | no | `{ description, homepage_urls, whitepaper_url, blockchain_explorer_urls, categories, asset_platform_id, contract_addresses, hashing_algorithm, block_time_in_minutes, genesis_date }` — provider-reported |
| `ecosystem` | object | no | `{ development: {repositories, forks, stars, subscribers, total_issues, closed_issues, pull_requests_merged, pull_request_contributors, commit_count_4_weeks, code_additions_4_weeks, code_deletions_4_weeks}, community: {official_forum_urls, announcement_urls, chat_urls, twitter_screen_name, subreddit_url, telegram_channel_identifier, reddit_subscribers, telegram_channel_user_count} }` — provider-reported |
| `tokenomics` | object | no | `{ max_supply_infinite }` — the provider's explicit flag only (nullable) |
| `calculated` | object | no | `{ supply_type, metrics, score, summary }` — platform-calculated snapshot |
| `development_activity_score` | double | no | Development component sub-score (0–100); null if not scoreable |
| `fundamental_score` | double | no | 0–100; null when `score_status` is `not_enough_data`. **Not** a BUY/HOLD/SELL |
| `score_status` | string | no | `"scored"` or `"not_enough_data"` |
| `score_method_version` | string | no | Version of the scoring rules |
| `market_data_source` | string | no | Source of the market snapshot used |
| `market_data_updated_at` | datetime (UTC) | no | Timestamp of the market snapshot used |
| `fetched_at` | datetime (UTC) | no | When the profile was last fetched from the provider |
| `calculated_at` | datetime (UTC) | no | When `calculated` was last computed |
| `timestamp` | datetime (UTC) | no | Equals `calculated_at` (kept from the original Step 2 schema) |
| `created_at`, `updated_at` | datetime (UTC) | yes | |

**Identifier strategy:** `_id` (ObjectId); one document per `coin_id`.

**Relationships:** `coin_id` → `coins._id`.

**Indexes:** unique `coin_id` (`uniq_fundamentalanalysis_coinid`) — the
only query pattern is lookup by coin, and it guarantees upserts cannot
create duplicates. Replaces the Step 2 "expected future index"
`(coin_id, timestamp desc)`: Phase 11 keeps one current document per
coin rather than a history.

**Write paths:** profile refresh `$set`s the profile fields and
`fetched_at`; each analysis `$set`s `calculated`, the scores and
`calculated_at`. They touch disjoint fields and never overwrite each
other.

---|---|---|---|
| `_id` | ObjectId | yes | |
| `coin_id` | ObjectId | yes | References `coins._id` |
| `project_info` | object | no | e.g. `{ description, website, whitepaper_url, launch_date }` |
| `tokenomics` | object | no | e.g. `{ total_supply, circulating_supply, inflation_model }` |
| `ecosystem` | object | no | e.g. `{ github_url, active_developers }` |
| `development_activity_score` | double | no | |
| `fundamental_score` | double | no | Composite score, calculation TBD |
| `source` | string | no | Where this data was sourced from |
| `timestamp` | datetime (UTC) | yes | |

**Identifier strategy:** `_id` (ObjectId).

**Relationships:** `coin_id` → `coins._id`.

**Indexes:** none created in Step 2 (no query pattern yet). Expected
future index: `(coin_id, timestamp desc)`.

---

## `news`

**Purpose:** Aggregated news articles, optionally tagged with relevant
coins. No provider integration yet.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `title` | string | yes | |
| `description` | string | no | |
| `url` | string | yes | |
| `image_url` | string | no | |
| `source` | string | yes | Publisher name |
| `provider` | string | yes | Which aggregation API this came from |
| `coins` | array\<ObjectId\> | no | References into `coins._id` |
| `published_at` | datetime (UTC) | yes | |
| `created_at` | datetime (UTC) | yes | When we ingested it |

**Identifier strategy:** `_id` (ObjectId).

**Relationships:** `coins` → array of `coins._id`.

**Indexes:** compound index on `(coins, published_at desc)` — supports
"latest news for coin X".

---

## `sentiment`

**Purpose:** Sentiment score attached to a news article (and/or coin).
No FinBERT/model integration yet.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `news_id` | ObjectId | no | References `news._id`, if derived from an article |
| `coin_id` | ObjectId | no | References `coins._id` |
| `label` | string | yes | e.g. `"positive"`, `"negative"`, `"neutral"` |
| `score` | double | yes | Model confidence/magnitude |
| `model` | string | yes | e.g. `"finbert-v1"` |
| `created_at` | datetime (UTC) | yes | |

**Identifier strategy:** `_id` (ObjectId).

**Relationships:** `news_id` → `news._id`; `coin_id` → `coins._id`.

**Indexes:** none created in Step 2. Expected future index on
`coin_id` once sentiment aggregation queries exist.

---

## `predictions`

**Purpose:** Model-generated forecasts (Phase 13). Insert-only: each generated
prediction is kept (the later user-facing prediction history reads from here), and a
stored prediction is reused until `expires_at`. Every document is a **model estimate**,
never a market fact.

> **Schema evolution (Phase 13).** The Step 2 design (`model_name`, `predicted_direction`,
> `predicted_price_low/high`, required `confidence`) was reserved but never written to —
> no model existed. Phase 13 settled the real shape below: ranges are nested, the model
> is stored as `model` + `model_version`, and `confidence` may be `null` (with
> `confidence_status: "unavailable"`) when it cannot be calibrated defensibly. No
> migration is needed because the collection was empty; the same collection is used —
> no duplicate collection was created.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `coin_id` | ObjectId | yes | References `coins._id` |
| `symbol` | string | no | Copied from the coin at generation time |
| `horizon` | string | yes | One of `1h`, `4h`, `24h`, `7d`, `30d` |
| `current_price` | double | yes | Close of the last *completed* candle the forecast starts from (an input fact) |
| `prediction` | object | yes | `{ predicted_return, kind: "model_prediction" }`; return is fractional (0.024 = +2.4%) |
| `range` | object | no | `{ return_lower, return_upper, price_lower, price_upper, nominal_coverage }` — empty when the model could not calibrate an interval |
| `direction` | string | yes | `"up"`, `"down"` or `"flat"` (flat = move smaller than typical model error) |
| `confidence` | double \| null | no | 0–1 calibrated probability the *direction* is correct; `null` when unavailable |
| `confidence_status` | string | yes | `"calibrated"` or `"unavailable"` |
| `confidence_note` | string \| null | no | Why confidence is unavailable / withheld |
| `model` | string | yes | `xgboost`, `lightgbm`, `lstm`, `ridge` or `ensemble` |
| `model_version` | string | yes | e.g. `v3` |
| `feature_version` | string | yes | Feature-engineering version the model was trained on |
| `evaluation` | object | no | Held-out test evidence: `test_mae`, `baseline_mae`, `test_directional_accuracy`, `test_samples`, `interval_coverage_test` |
| `trained_at` | string | no | Training timestamp of the model used |
| `reference_time` / `target_time` | datetime (UTC) | yes | Close time of the source candle / that plus the horizon |
| `generated_at` | datetime (UTC) | yes | |
| `expires_at` | datetime (UTC) | yes | After this the prediction is stale and regenerated on the next request |
| `status` | string | yes | `"active"` |
| `created_at` | datetime (UTC) | yes | Equal to `generated_at`; kept for the Step 2 index |

**Identifier strategy:** `_id` (ObjectId).

**Relationships:** `coin_id` → `coins._id`; referenced by
`prediction_results.prediction_id` (future).

**Indexes:** `(coin_id, horizon, created_at desc)` (Step 2) and
`(coin_id, horizon, generated_at desc)` — "latest prediction for coin X at horizon H" —
plus `(generated_at desc)`. `expires_at` is deliberately **not** a TTL index.

**Model metrics:** the training CLI mirrors each model's registry record
(metrics, version, status) into the existing `model_metrics` collection on a
best-effort basis; the file registry under `ml/artifacts/` is the source of truth.

---

## `decisions`

**Purpose:** The platform's BUY/HOLD/SELL output (Phase 14 Risk & Decision Engine), combining
technical/fundamental/sentiment/prediction signals with a risk score. Insert-only history — every
calculated decision is kept; freshness is decided from `expires_at`. See
[risk-decision-engine.md](risk-decision-engine.md).

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `coin_id` | ObjectId | yes | References `coins._id` |
| `symbol` | string | no | |
| `decision` | string \| null | yes | `"BUY"`, `"HOLD"`, `"SELL"`, or `null` when `status` is not `"VALID"` |
| `status` | string | yes | `VALID`, `INSUFFICIENT_DATA`, `STALE_DATA`, `PREDICTION_UNAVAILABLE`, `ANALYSIS_UNAVAILABLE` |
| `decision_score` | double \| null | no | Risk-adjusted, -100..+100 |
| `confidence` | double \| null | no | 0–100 (not 0–1); `null` with `confidence_status: "unavailable"` |
| `confidence_status` | string | yes | `computed` / `unavailable` |
| `risk_score` | double \| null | no | 0–100 |
| `risk_level` | string \| null | no | `VERY_LOW`, `LOW`, `MODERATE`, `HIGH`, `VERY_HIGH` |
| `positive_factors` / `negative_factors` | array\<string\> | yes | Rule-generated sentences |
| `technical_signal` / `fundamental_signal` / `sentiment_signal` / `prediction_signal` | string | yes | e.g. `BULLISH`, `STRONG`, `POSITIVE`, `UNAVAILABLE` |
| `data_quality` | object | yes | Per-module availability state and reason |
| `generated_at` / `expires_at` / `created_at` | datetime (UTC) | yes | `expires_at` is NOT a TTL index |
| `engine_version` / `risk_config_version` | string | yes | For future backtesting / comparison |
| `response` | object | yes | The complete API response, so a cached read rebuilds exactly what was calculated |

**Indexes:** `idx_decisions_coin_generatedat` `(coin_id, generated_at desc)` and
`idx_decisions_engineversion_generatedat` `(engine_version, generated_at desc)`.

---

## `prediction_results`

**Purpose:** Post-hoc evaluation of a prediction against what actually
happened — the basis for future backtesting and accuracy tracking.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `prediction_id` | ObjectId | yes | References `predictions._id` |
| `actual_price` | double | yes | |
| `actual_direction` | string | yes | |
| `horizon` | string | yes | Copied from the source prediction for convenient querying |
| `error` | double | no | e.g. absolute or percentage error |
| `direction_correct` | boolean | yes | |
| `evaluated_at` | datetime (UTC) | yes | |

**Identifier strategy:** `_id` (ObjectId).

**Relationships:** `prediction_id` → `predictions._id`.

**Indexes:** none created in Step 2. Expected future index on
`prediction_id` (one-to-one/one-to-few lookups) and possibly
`evaluated_at` for accuracy-over-time reporting.

---

## `watchlists`

**Purpose:** Coins a user is tracking. No watchlist functionality
implemented yet.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `user_id` | ObjectId | yes | References `users._id` |
| `coin_id` | ObjectId | yes | References `coins._id` |
| `created_at` | datetime (UTC) | yes | |

**Identifier strategy:** `_id` (ObjectId); one document per
user/coin pair.

**Relationships:** `user_id` → `users._id`; `coin_id` → `coins._id`.

**Indexes:** index on `user_id` (list a user's watchlist). A future
compound-unique index on `(user_id, coin_id)` should be added once
this collection is actually written to, to prevent duplicate entries
— not created yet since no write path exists to test it against.

---

## `portfolios`

**Purpose:** A named portfolio belonging to a user. No portfolio
functionality implemented yet.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `user_id` | ObjectId | yes | References `users._id` |
| `name` | string | yes | |
| `base_currency` | string | yes | e.g. `"USD"` |
| `created_at` | datetime (UTC) | yes | |
| `updated_at` | datetime (UTC) | yes | |

**Identifier strategy:** `_id` (ObjectId).

**Relationships:** `user_id` → `users._id`; referenced by
`portfolio_transactions.portfolio_id`.

**Indexes:** none created in Step 2. Expected future index on
`user_id`.

---

## `portfolio_transactions`

**Purpose:** Buy/sell/transfer records within a portfolio. No
portfolio functionality implemented yet.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `user_id` | ObjectId | yes | References `users._id` |
| `portfolio_id` | ObjectId | yes | References `portfolios._id` |
| `coin_id` | ObjectId | yes | References `coins._id` |
| `transaction_type` | string | yes | e.g. `"buy"`, `"sell"` |
| `quantity` | double | yes | |
| `price` | double | yes | Price per unit at transaction time |
| `fee` | double | no | |
| `timestamp` | datetime (UTC) | yes | |

**Identifier strategy:** `_id` (ObjectId).

**Relationships:** `user_id` → `users._id`; `portfolio_id` →
`portfolios._id`; `coin_id` → `coins._id`.

**Indexes:** none created in Step 2. Expected future compound index on
`(portfolio_id, timestamp desc)`.

---

## `alerts`

**Purpose:** User-configured triggers (price, % change, AI decision
change, volatility). No alert functionality implemented yet.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `user_id` | ObjectId | yes | References `users._id` |
| `coin_id` | ObjectId | yes | References `coins._id` |
| `alert_type` | string | yes | `"price"`, `"percentage_change"`, `"ai_decision"`, `"volatility"` |
| `condition` | string | yes | e.g. `"above"`, `"below"`, `"crosses"` |
| `target` | double | no | Threshold value, meaning depends on `alert_type` |
| `enabled` | boolean | yes | Default `true` |
| `created_at` | datetime (UTC) | yes | |
| `updated_at` | datetime (UTC) | yes | |
| `triggered_at` | datetime (UTC) | no | Null until first triggered |

**Identifier strategy:** `_id` (ObjectId).

**Relationships:** `user_id` → `users._id`; `coin_id` → `coins._id`.

**Indexes:** index on `user_id` (list a user's alerts).

---

## `analysis_history`

**Purpose:** Record of past analyses a user has viewed/run, avoiding
duplicate storage of the underlying analysis by referencing it.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `user_id` | ObjectId | yes | References `users._id` |
| `coin_id` | ObjectId | yes | References `coins._id` |
| `analysis_type` | string | yes | e.g. `"technical"`, `"fundamental"`, `"full"` |
| `decision_id` | ObjectId | no | References `decisions._id` — the underlying analysis is NOT duplicated here, only referenced |
| `summary` | string | no | Short human-readable note, not a full copy of the analysis |
| `timestamp` | datetime (UTC) | yes | |

**Identifier strategy:** `_id` (ObjectId).

**Relationships:** `user_id` → `users._id`; `coin_id` → `coins._id`;
`decision_id` → `decisions._id`.

**Indexes:** index on `user_id` (list a user's analysis history).

---

## `model_metrics`

**Purpose:** Training/evaluation metrics for each ML model version, to
support model comparison and regression detection over time. No
models are trained yet.

| Field | Type | Required | Notes |
|---|---|---|---|
| `_id` | ObjectId | yes | |
| `model_name` | string | yes | |
| `model_version` | string | yes | |
| `dataset_version` | string | yes | |
| `training_timestamp` | datetime (UTC) | yes | |
| `validation_metrics` | object | no | e.g. `{ mae, rmse, directional_accuracy }` |
| `test_metrics` | object | no | Same shape as `validation_metrics` |
| `precision` | double | no | |
| `recall` | double | no | |
| `f1` | double | no | |
| `sharpe_ratio` | double | no | Where applicable (trading-strategy-style models) |
| `max_drawdown` | double | no | Where applicable |

**Identifier strategy:** `_id` (ObjectId).

**Relationships:** none (standalone metrics log).

**Indexes:** compound index on `(model_name, training_timestamp desc)`
— supports "metrics history for model X, newest first".

---

## Fields deliberately left un-indexed

Per the indexing strategy, not every field mentioned in a query is
indexed. Notably:

- `technical_analysis`, `fundamental_analysis`, `sentiment`,
  `portfolios`, `portfolio_transactions` have no indexes
  yet, beyond what MongoDB creates automatically on `_id`. These
  collections have no write path or query pattern through Step 3 —
  indexing them now would be a guess at access patterns that haven't
  been implemented, incurring real storage and write-amplification
  cost for no current benefit. Each has a documented "expected future
  index" above, to be created in the step that actually implements
  reads against it.
- `coins.market_cap_rank` and `coins.is_active` **are** indexed as of
  Step 3 (`idx_coins_marketcaprank`, `idx_coins_isactive`) — coin
  listing/pagination now actively sorts and filters on these fields,
  which is exactly the "supports a concrete query pattern" bar the
  rest of this document holds indexes to.

## Unique constraints — summary and reasoning

| Collection | Field(s) | Why |
|---|---|---|
| `users` | `email` | The login identifier; two accounts must never share one. |
| `coins` | `providers.coingecko.id` | The true external-source identity, now that a coin holds a `providers` map rather than one flat provider field. `symbol` alone is explicitly **not** unique — token tickers collide across unrelated projects, so enforcing uniqueness there would eventually reject a legitimate coin. |
| `market_data` | `coin_id` | One upserted current-snapshot document per coin (see the `market_data` section above) — not a growing time series. |

No other collection has a unique constraint yet — every other
`user_id`/`coin_id` pairing (watchlists, alerts, etc.) is expected to
allow duplicates to be prevented at the service layer once that logic
exists, rather than guessing at the exact uniqueness rule (e.g.
watchlists likely want `(user_id, coin_id)` unique, but that repository
doesn't exist yet to validate the assumption against).
