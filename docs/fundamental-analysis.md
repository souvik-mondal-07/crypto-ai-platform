# Fundamental Analysis (Phase 11)

Descriptive, real-data fundamentals for one coin: market position,
supply, valuation extremes, project information, development/ecosystem
information, derived metrics, a transparent rule-based score, and a
factual summary.

It is deliberately **separate from** technical analysis, ML prediction,
the risk engine, the BUY/HOLD/SELL decision, news/sentiment and Gemini
— those are later phases. Nothing here is a recommendation, and nothing
here predicts price.

## Architecture

```
CoinGecko  /coins/{id}                 (project profile — via the provider abstraction)
MongoDB    market_data                 (market figures — already synchronized, Phases 3/7)
        │
        ▼
FundamentalDataService                 app/services/fundamental_data_service.py
   cache policy + provider failure fallbacks for the *profile*
        │
        ▼
FundamentalAnalysisService             app/services/fundamental_analysis_service.py
   orchestration; shapes the response
        │            ▲
        │            └── fundamental_calculations.py   (pure functions, no I/O)
        ▼
FundamentalAnalysisRepository          app/repositories/fundamental_analysis_repository.py
        │
        ▼
GET /api/v1/coins/{coin_id}/fundamentals     app/api/v1/coins.py (no logic in the route)
        │
        ▼
fundamentals.api.ts → useFundamentals → FundamentalAnalysisSection (Coin Details)
```

Market figures are **not** re-fetched or copied. They are read live from
`market_data`, so there is one source of truth. Only the slow-changing
project profile is fetched per coin, and cached.

## Data sources and what is (and isn't) used

| Data | Source | Notes |
|---|---|---|
| Market cap, FDV, volume, supply, price, ATH/ATL, % changes | `market_data` collection (CoinGecko; price may come from Binance for mapped coins) | `market_data_source` in the response says which |
| Market-cap rank | `coins.market_cap_rank` | |
| Description, links, categories, platform, contract addresses, genesis date, hashing algorithm, block time | CoinGecko `GET /coins/{id}` | requested with `market_data=false&tickers=false` |
| Repositories, stars/forks/commits/PR activity | CoinGecko `developer_data` | provider-reported only |
| Reddit/Telegram reach, community links | CoinGecko `community_data` / `links` | reach figures, **not** sentiment |
| `max_supply_infinite` | CoinGecko | explicit flag only |

Deliberately **not** used: `sentiment_votes_*` and `watchlist_portfolio_users`
(sentiment is a later phase). No scraping, no hard-coded values.

If the provider doesn't supply something, the field is `null` and the UI
shows "Not available". Nothing is estimated.

## Provider-reported vs. calculated

The response keeps these in separate objects:

- Provider-reported: `market`, `supply`, `valuation`, `project_info`, `ecosystem`
- Calculated by this platform: `calculated_metrics` (each metric carries its
  `formula`, and an `unavailable_reason` whenever its value is `null`),
  `score`, `summary`

The UI labels each card "Provider-reported" or "Calculated".

Unit convention: `*_ratio` is a fraction (0.045); `*_percent` is on a
0–100 scale.

## Calculated metrics

All are `null` (with a reason) unless every input is present **and** the
formula is mathematically valid.

| Metric | Formula | Unavailable when |
|---|---|---|
| `volume_to_market_cap` | 24h volume ÷ market cap | volume missing; market cap missing or 0 |
| `market_cap_to_fdv` | market cap ÷ FDV | either missing/0; ratio > 1.01 (data inconsistent) |
| `circulating_to_max_supply_percent` | circulating ÷ max supply × 100 | circulating missing; max supply missing; circulating > max (inconsistent) |
| `remaining_to_max_supply_percent` | 100 − the above | same as above |
| `remaining_supply_to_max` | max supply − circulating | same as above |
| `circulating_to_total_supply_percent` | circulating ÷ total supply × 100 | circulating or total missing; circulating > total (inconsistent) |
| `distance_from_ath_percent` | (price ÷ ATH − 1) × 100 | price or ATH missing |
| `distance_from_atl_percent` | (price ÷ ATL − 1) × 100 | price missing; ATL missing or 0 |

Inconsistent provider data (e.g. circulating supply above max supply) is
reported as unavailable with a warning — it is **not** clamped or
"fixed".

`distance_from_ath_percent` uses the latest stored price, whereas the
provider-reported `valuation.ath_change_percentage` is as of the
provider's last sync. They are shown separately and labelled, and can
differ slightly.

### Supply type

| `supply_type` | Meaning |
|---|---|
| `capped` | a positive maximum supply is reported |
| `unlimited` | the provider **explicitly** flags infinite supply |
| `not_reported` | no maximum supply and no flag |

A `null` maximum supply alone is ambiguous (unlimited *or* unknown), so
it is never promoted to "unlimited" on assumption.

## Fundamental score (method v1.0)

A transparent, rule-based 0–100 **structural descriptor**. It is not a
BUY/HOLD/SELL signal and does not predict price. It deliberately
**excludes price action** (distance from ATH, recent performance).

Six components with fixed weights (sum 100). Each yields a 0–100
sub-score from fixed bands:

| Component (weight) | Input | Bands → sub-score |
|---|---|---|
| Market size (25) | market cap | ≥ $10B: 100 · ≥ $1B: 80 · ≥ $100M: 60 · ≥ $10M: 40 · ≥ $1M: 20 · else 10 |
| Trading liquidity (20) | volume ÷ market cap | < 0.5%: 20 · < 2%: 50 · < 10%: 100 · < 30%: 80 · ≥ 30%: 50 |
| Supply in circulation (20) | circulating ÷ max supply; if no max supply is reported, market cap ÷ FDV | ≥ 90%: 100 · ≥ 75%: 85 · ≥ 50%: 65 · ≥ 25%: 40 · else 20 |
| Development activity (15) | commits in last 4 weeks (provider-reported) | ≥ 100: 100 · ≥ 30: 75 · ≥ 10: 50 · ≥ 1: 25 · 0: 0 |
| Project maturity (10) | years since provider-reported genesis date | ≥ 5: 100 · ≥ 2: 75 · ≥ 1: 50 · ≥ 0.5: 25 · else 10 |
| Project information (10) | share of 6 items present: description, website, whitepaper, block explorer, code repository, categories | present ÷ 6 × 100 |

**Score = Σ(weight × sub-score) ÷ Σ(weight)** over the components that
have real data. A missing input never counts as zero; it lowers
**coverage** instead (`coverage_percent` = available weight).

**Not enough data:** if available weight is below 50 *or* fewer than 3
components are available, no score is produced — `status` is
`"not_enough_data"`, `score` is `null`, and the UI shows "Not enough
data".

Development data counts as available only if a GitHub repository is
linked **and** the provider reports at least one non-zero activity
figure. CoinGecko returns all-zero developer blocks for repositories it
doesn't track; scoring that as "0 commits" would present a data gap as
measured inactivity.

Every response includes each component's weight, sub-score, points,
input description and rule, so any score can be reproduced by hand. The
thresholds are heuristics chosen for explainability; they are constants
in `fundamental_calculations.py` (`SCORE_METHOD_VERSION` is bumped when
they change).

## Summary

Short factual sentences generated from fixed templates (market position,
volume relation, supply, distance from ATH/ATL, categories/platform/
genesis date, development). A statement is omitted — never guessed — if
its inputs are missing; in particular a missing market snapshot or
project profile never produces "supply cap unknown" or "no repository
linked". No recommendations, no predictions.

## Freshness

| Field | Meaning |
|---|---|
| `timestamps.fetched_at` | when project/ecosystem data was last fetched from the provider (`null` if never) |
| `timestamps.calculated_at` | when the metrics/score in this response were calculated |
| `timestamps.updated_at` | when the stored record was last written |
| `timestamps.market_data_updated_at` | timestamp of the market snapshot used |
| `freshness.market_data_is_stale` | market snapshot older than the existing staleness threshold |
| `freshness.project_data_is_stale` | stored profile older than its TTL (only when a refresh couldn't happen) |
| `freshness.project_refresh_failed` | a provider refresh was attempted and failed |

Market-derived metrics and the score are **recalculated on every
request** from the current `market_data`; only the provider profile is
cached (`FUNDAMENTALS_PROFILE_TTL_SECONDS`, default 6h). `force_refresh`
re-fetches the profile but is limited to once per
`FUNDAMENTALS_MIN_REFRESH_INTERVAL_SECONDS` (default 60s) per coin.

## API

`GET /api/v1/coins/{coin_id}/fundamentals?force_refresh=false`

| Situation | Result |
|---|---|
| Everything available | `200`, `is_partial: false` |
| Some sections unavailable | `200`, `is_partial: true`, `unavailable_sections`, `warnings` |
| Provider fails, stored profile exists | `200`, stored profile with `project_refresh_failed`/stale flags |
| Provider fails, market data exists | `200`, partial (no project info) |
| Provider has no profile (404) and market data exists | `200`, partial |
| Invalid id | `400 INVALID_COIN_ID` |
| Unknown coin | `404 COIN_NOT_FOUND` |
| No market data **and** no profile | `404 FUNDAMENTALS_NOT_AVAILABLE` |
| No market data, no stored profile, provider failing | provider error (`503`/`504`/`429`) |
| MongoDB failure on read | `503 DATABASE_UNAVAILABLE` |
| MongoDB failure on write | logged; the computed result is still returned |

## Storage — `fundamental_analysis`

One document per coin (unique `coin_id`). It stores only what
`market_data` doesn't already hold:

- profile (written on provider fetch): `project_info`, `ecosystem`,
  `tokenomics.max_supply_infinite`, `fetched_at`
- calculation snapshot (written per request): `calculated`
  (metrics, score, summary), `fundamental_score`,
  `development_activity_score`, `score_status`, `score_method_version`,
  `market_data_updated_at`, `calculated_at`, `timestamp`
- `coin_id`, `symbol`, `source`, `created_at`, `updated_at`

The two write paths `$set` disjoint fields, so a profile refresh never
overwrites the last calculation, and vice versa. The stored
`fundamental_score` is there for the later decision phase to read; this
phase does not turn it into a BUY/HOLD/SELL.
