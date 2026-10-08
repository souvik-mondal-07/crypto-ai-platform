# API Reference

Base URL (development): `http://127.0.0.1:8000`

## GET /

Basic API information.

**Response 200**

```json
{
  "message": "Crypto AI Platform API",
  "version": "1.0.0"
}
```

## GET /api/v1/health

Liveness + database connectivity check, used by the frontend's System
Status panel.

**Response 200 — database connected**

```json
{
  "status": "ok",
  "service": "crypto-ai-platform-backend",
  "database": "connected"
}
```

**Response 200 — database unreachable**

`status` and `database` degrade together; the endpoint still returns
HTTP 200 (the API process itself is up), but never falsely reports
`"connected"`:

```json
{
  "status": "degraded",
  "service": "crypto-ai-platform-backend",
  "database": "disconnected"
}
```

## Future endpoints (not implemented in Step 1)

These are planned for later steps and documented here only for
context — none of them existed at Step 1. As of Phase 11,
`GET /api/v1/coins`, `GET /api/v1/coins/{id}`,
`GET /api/v1/coins/{id}/history`, `GET /api/v1/coins/{id}/market`,
`GET /api/v1/coins/search`, `GET /api/v1/coins/{id}/technical-analysis`,
and `GET /api/v1/coins/{id}/fundamentals`
are implemented — see backend/app/api/v1/coins.py. The rest below are
still not implemented:

- `POST /api/v1/auth/register`, `/login`, `/logout` — implemented separately, see docs/authentication.md
- `GET /api/v1/coins/{id}/prediction`
- `GET /api/v1/news`
- `GET /api/v1/watchlist`, `POST /api/v1/watchlist`
- `GET /api/v1/portfolio`, `POST /api/v1/portfolio`
- `GET /api/v1/alerts`, `POST /api/v1/alerts`
- `GET /api/v1/predictions/history`

### GET /api/v1/coins/{id}/technical-analysis (Phase 10)

RSI, MACD, SMA/EMA moving averages, Bollinger Bands, ATR, volume,
support/resistance, and a descriptive trend label ("bullish" /
"bearish" / "neutral" — never a BUY/HOLD/SELL decision), computed from
real historical OHLC candles. See
backend/app/schemas/technical_analysis.py for the exact response shape
and backend/app/services/technical_analysis_service.py /
backend/app/services/indicators.py for how each value is computed.

Query params: `timeframe` (one of `1D`/`7D`/`30D`/`90D`/`1Y`, default
`30D`), `force_refresh` (bool, default `false` — bypasses the ~5
minute server-side cache).

Errors: `400 INVALID_COIN_ID`, `404 COIN_NOT_FOUND`,
`404`/`503 TECHNICAL_ANALYSIS_NOT_AVAILABLE` (no provider mapping, or
the provider doesn't support historical OHLC),
`422 INSUFFICIENT_HISTORICAL_DATA` (fewer than 20 candles available
for the requested timeframe), plus the standard provider-failure
errors (`503`/`504`/`429`) shared with `/history`.

### GET /api/v1/coins/{id}/fundamentals (Phase 11)

Real-data fundamental analysis: provider-reported market, supply,
valuation, project and development/ecosystem information; clearly
separated **calculated** metrics (each with its formula and, when
`null`, the reason); a transparent rule-based fundamental score; and a
factual summary. Never a BUY/HOLD/SELL decision. Full details, the
score methodology and the error matrix are in
[fundamental-analysis.md](fundamental-analysis.md); the exact response
shape is backend/app/schemas/fundamentals.py.

Query params: `force_refresh` (bool, default `false` — re-fetches the
provider project profile; limited to once per
`FUNDAMENTALS_MIN_REFRESH_INTERVAL_SECONDS` per coin).

Unavailable data is `null` (and listed in `unavailable_sections`), never
estimated. Timestamps: `fetched_at`, `calculated_at`, `updated_at`,
`market_data_updated_at`, plus `freshness` flags.

Errors: `400 INVALID_COIN_ID`, `404 COIN_NOT_FOUND`,
`404 FUNDAMENTALS_NOT_AVAILABLE` (no market data and no project profile),
`503 DATABASE_UNAVAILABLE`, plus the standard provider-failure errors
(`503`/`504`/`429`) when nothing else can be served.


## News & sentiment (Phase 12)

| Endpoint | Notes |
|---|---|
| `GET /api/v1/news` | Global feed, newest first. Params: `page`, `limit` (≤50), `coin_id`, `search`, `source`, `sentiment`, `date_from`, `date_to`. Response includes `status` (last sync / sentiment-model state). |
| `GET /api/v1/news/sources` | Distinct publisher names (values accepted by `source`). |
| `GET /api/v1/news/{news_id}` | One article; 404 `NEWS_NOT_FOUND`. |
| `GET /api/v1/coins/{coin_id}/news` | Coin-scoped feed (same filters except `coin_id`); 400 `INVALID_COIN_ID`, 404 `COIN_NOT_FOUND`. |
| `GET /api/v1/coins/{coin_id}/sentiment?timeframe=24h\|7d` | Aggregated sentiment; `status: "insufficient_data"` when too few analyzed articles. |
| `POST /api/v1/dev/sync/news` | Dev-only manual ingest + analysis (needs `ENABLE_DEV_SYNC_ENDPOINT=true`). |

See `docs/news-sentiment.md`.

## Predictions (Phase 13)

Model estimates only — never market facts, never advice. Values come from trained
models and are `null`/unavailable rather than invented. Like the other analysis
endpoints these are not individually token-gated (the frontend routes are protected).

### GET /api/v1/predictions/{coin_id}

Without `horizon`: every horizon (`1h`, `4h`, `24h`, `7d`, `30d`) that has a valid
prediction, plus why the others do not.

```json
{
  "coin_id": "…", "symbol": "BTC",
  "predictions": [ { "horizon": "24h", "kind": "model_prediction", "current_price": 100000,
    "predicted_return": 0.024, "predicted_return_range": {"lower": 0.012, "upper": 0.04},
    "predicted_price_range": {"lower": 101200, "upper": 104000}, "range_nominal_coverage": 0.8,
    "direction": "up", "confidence": 0.71, "confidence_status": "calibrated", "confidence_note": null,
    "model": "xgboost", "model_version": "v1", "feature_version": "v1",
    "evaluation": {"test_mae": 0.011, "baseline_mae": 0.013, "test_directional_accuracy": 0.57, "test_samples": 412, "interval_coverage_test": 0.78},
    "reference_time": "…", "target_time": "…", "generated_at": "…", "expires_at": "…", "is_stale": false, "disclaimer": "…" } ],
  "unavailable": [ { "horizon": "7d", "status": "model_unavailable", "reason": "…" } ]
}
```
(The numbers above only illustrate the shape.)

### GET /api/v1/predictions/{coin_id}?horizon=24h[&model=xgboost|lightgbm|lstm|ridge|ensemble]

One prediction. A stored prediction is reused until `expires_at`
(`ML_PREDICTION_TTL_SECONDS`), then regenerated from real recent candles.

| Status | Code | Meaning |
|---|---|---|
| 400 | `INVALID_COIN_ID` / `INVALID_HORIZON` | malformed id / unsupported horizon |
| 404 | `COIN_NOT_FOUND` | unknown coin |
| 404 | `PREDICTION_MODEL_UNAVAILABLE` | no validated model for that coin/horizon (or requested model type) |
| 422 | `INSUFFICIENT_HISTORICAL_DATA` | no exchange pair, too little/stale/gappy history |
| 422 | (validation) | unknown `model` value |
| 503 | `PREDICTION_ENGINE_UNAVAILABLE` | ML libraries not installed on the server |
| 429/503/504 | provider errors | exchange rate-limit / outage (existing handlers) |

### GET /api/v1/predictions/{coin_id}/latest[?horizon=24h]

The most recent **stored** prediction. Never generates one. `is_stale: true` when it
has expired; `404 PREDICTION_NOT_FOUND` when none exists yet.

## Risk & Decision (Phase 14)

Deterministic, rule-based BUY / HOLD / SELL decision support with a risk score and level, confidence,
signals and factors. No LLM, no training, no trading. Full methodology: [risk-decision-engine.md](risk-decision-engine.md).

- `GET /api/v1/decisions/{coin_id}` — fresh stored decision, else a new calculation (`force_refresh=true` recalculates)
- `GET /api/v1/decisions/{coin_id}/latest` — latest stored decision; never calculates; `is_stale` flags expiry
- `GET /api/v1/decisions/{coin_id}/risk` — risk score, level, components and risk factors

`decision` is `null` with `status` of `INSUFFICIENT_DATA` / `STALE_DATA` / `PREDICTION_UNAVAILABLE` /
`ANALYSIS_UNAVAILABLE` when the available data cannot support one. The exact shape is
backend/app/schemas/decisions.py (mirrored in frontend/src/types/decisions.ts).


## AI Analysis (Phase 15)

`GET /ai-analysis/{coin_id}` returns the stored Gemini explanation (404 `AI_ANALYSIS_NOT_FOUND` if none; never calls Gemini).
`POST /ai-analysis/{coin_id}/generate[?force_refresh=true]` returns a fresh stored explanation or generates one (login required).
The response wraps the explanation with the official Phase 14 `decision_snapshot`, `data_availability`, model/prompt
versions and cache flags. Full details: [ai-analysis.md](ai-analysis.md).
