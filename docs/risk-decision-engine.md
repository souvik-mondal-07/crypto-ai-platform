# Risk & Decision Engine (Phase 14)

A deterministic, rule-based, explainable decision-support engine. It combines the outputs of the
existing modules — market data, technical analysis, fundamental analysis, news sentiment and the
Phase 13 ML prediction — into a **risk score**, a **BUY / HOLD / SELL decision**, a **confidence**,
and rule-generated **positive / negative factors**.

* No Gemini / LLM (that is Phase 15), no randomness, no clock inside the engine, no model training.
* No trading, paper trading, orders, wallets, alerts, watchlists or backtesting.
* Decision support only — never a guarantee, never an order.

```
Market ─┐
Technical ─┤                       ┌─> risk_service.calculate_risk ──> Risk Score (0-100) + level
Fundamental ┼─> DecisionInputs ──┤
Sentiment ─┤   (availability)     └─> decision_engine.evaluate ────> Decision Score ─> BUY/HOLD/SELL
ML prediction ┘                                                        + confidence + factors
```

Code map

| File | Role |
|---|---|
| `backend/app/config/risk_config.py` | **Every** weight, curve, threshold and version (`DECISION_ENGINE_VERSION`, `RISK_CONFIG_VERSION`) |
| `backend/app/services/decision_inputs.py` | Availability-aware inputs + builders from the existing module responses |
| `backend/app/services/risk_service.py` | Pure risk engine |
| `backend/app/services/decision_engine.py` | Pure decision engine (signals, risk adjustment, overrides, confidence) |
| `backend/app/services/scoring.py` | Piecewise-linear curves, weighted averages, level mapping |
| `backend/app/services/decision_service.py` | Orchestration: loads inputs, caches, stores, builds the API response |
| `backend/app/repositories/decision_repository.py` | Storage in the existing `decisions` collection |
| `backend/app/schemas/decisions.py`, `backend/app/api/v1/decisions.py` | API |

## Data availability

Each input carries a state — `available`, `missing`, `stale`, `insufficient_data`, `unavailable` — and
a reason. Only `available` inputs are scored. A missing input is **never** treated as 0, neutral,
low risk or high confidence: its weight is removed and the remaining weights are re-normalised, and
the lost coverage lowers the confidence.

## Risk score (0-100, higher = riskier)

| Component | Default weight | Sub-factors (re-normalised over those available) |
|---|---|---|
| Volatility | 25% | ATR % of price, Bollinger-band width %, 24h high-low range % |
| Liquidity | 15% | 24h volume, market cap, volume / market cap (too thin *and* abnormally high turnover are risky) |
| Technical | 20% | RSI (extremes), MACD, trend, Bollinger %B position, support/resistance position |
| Fundamental | 15% | fundamental score, market rank, market cap / FDV, circulating / max supply (capped only), ATH drawdown, data completeness |
| Sentiment | 10% | average score, negative-news share, trend, news volume (thin coverage = riskier) |
| Prediction | 15% | predicted direction, predicted-return range width, calibrated model confidence |

Each sub-factor maps its input to 0-100 through a piecewise-linear curve in `risk_config.py`.
A component with no available sub-factor is excluded. A score is produced only if usable (present and fresh) market data exists, at least
`min_coverage` (50%) of the weight is backed by data, **and** volatility or liquidity evidence exists.
Without usable market data the risk score and level are `null`.

| Score | Level |
|---|---|
| 0-20 | `VERY_LOW` |
| 21-40 | `LOW` |
| 41-60 | `MODERATE` |
| 61-80 | `HIGH` |
| 81-100 | `VERY_HIGH` |

The level is classified from the score **as displayed** (rounded to a whole number) so the number and
the label never disagree. The backend is the source of truth; the frontend only renders it.

## Decision score (-100 bearish … +100 bullish)

Four module scores, each a weighted average of its own components:

| Module | Default weight | Components |
|---|---|---|
| Technical | 35% | trend, MACD, RSI (extremes counted as stretched), price vs SMA/EMA, Bollinger position, support/resistance |
| Fundamental | 20% | fundamental score, market rank, market cap / FDV |
| Sentiment | 15% | average score, positive-minus-negative share, trend — weight scaled by `min(1, articles / 10)` |
| ML prediction | 30% | predicted return curve × confidence factor × range factor |

Prediction details: confidence `p` maps to `(p-0.5)/(0.75-0.5)` clamped to [0,1]; when confidence is
*not calibrated* the prediction counts at **50% strength** (documented in `prediction_uncalibrated_factor`)
and says so; a predicted-return range that crosses zero halves the strength again.

`raw score = weighted average of usable module scores`. **Risk adjustment:** a *positive* raw score is
multiplied by `1 - dampening(risk)` (0% up to risk 40, 15% at 60, 35% at 80, 55% at 100). Negative scores are
never dampened — high risk must not make a SELL harder.

Thresholds: **BUY ≥ +25**, **SELL ≤ −25**, otherwise HOLD.

## Override rules (applied in order; each that fires is returned in `overrides`)

1. `risk_buy_gate` — at `HIGH` a BUY needs a score ≥ +35, at `VERY_HIGH` ≥ +55, otherwise HOLD.
2. `signal_conflict` — BUY/SELL while the modules clearly disagree (conflict share ≥ 25%) and |score| < 45 → HOLD.
3. `low_confidence` — BUY/SELL with confidence below 40 (or unavailable) → HOLD.
4. `risk_sell_escalation` — a HOLD with score ≤ −20 (`HIGH`) / ≤ −15 (`VERY_HIGH`) and confidence ≥ 40 → SELL
   (only if none of 1-3 fired).

## Confidence (0-100, or `null`)

Weighted average of: cross-module agreement (40%), agreement inside each module (15%), data coverage (20%),
sentiment reliability (10%) and calibrated ML confidence (15%) — only the ingredients that exist. Then
−10 when modules conflict and −5 / −12 for a bullish reading at `HIGH` / `VERY_HIGH` risk. With fewer than
two usable modules there is nothing to agree with, so `confidence = null`, `confidence_status = "unavailable"`.

## Status

`VALID`, `INSUFFICIENT_DATA`, `STALE_DATA`, `PREDICTION_UNAVAILABLE`, `ANALYSIS_UNAVAILABLE`. When the
status is not `VALID`, `decision` is `null` — no decision is forced. A decision needs usable market data and
at least 2 of the 4 modules. **The ML prediction is optional** (`prediction_required = False`): when
it is unavailable (engine not installed, no validated model, too little history, expired) the decision is made
from the remaining modules, `data_quality.prediction.available = false`, a warning says so, and confidence drops.
Set `prediction_required = True` to return `PREDICTION_UNAVAILABLE` instead.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/decisions/{coin_id}` | Fresh stored decision, else a new calculation. `?force_refresh=true` recalculates. |
| `GET /api/v1/decisions/{coin_id}/latest` | Latest stored decision; never calculates; `is_stale` flags expiry (`404 DECISION_NOT_FOUND` if none). |
| `GET /api/v1/decisions/{coin_id}/risk` | Risk score, level, components, risk-only factors. |

Errors use the standard `{"error": {"code", "message"}}` shape: `400 INVALID_COIN_ID`, `404 COIN_NOT_FOUND`,
`404 DECISION_NOT_FOUND`, `503 DATABASE_UNAVAILABLE`. Missing analysis data is **not** an error — it is a
`200` with `decision: null` and an explanatory `status`.

## Storage and freshness

Existing `decisions` collection (no new collection), insert-only history. Top-level queryable fields:
`coin_id, symbol, decision, status, decision_score, confidence, confidence_status, risk_score, risk_level,
positive_factors, negative_factors, technical_signal, fundamental_signal, sentiment_signal, prediction_signal,
data_quality, generated_at, expires_at, engine_version, risk_config_version`; the full response is kept under
`response`. Indexes: `idx_decisions_coin_generatedat`, `idx_decisions_engineversion_generatedat`
(`expires_at` is deliberately not a TTL index). Valid decisions live 5 minutes, non-valid ones 1 minute
(so a transient failure is retried soon). Concurrent requests for a coin cost one calculation.

Technical snapshots older than 30 minutes, predictions older than 4 hours and stale market data are excluded.
The prediction step is bounded by `DECISION_PREDICTION_TIMEOUT_SECONDS` (default 8); on timeout the latest
stored prediction is used, otherwise it is marked unavailable. **Nothing is trained** by this service.

## Changing the engine

Edit `risk_config.py`, bump `DECISION_ENGINE_VERSION` / `RISK_CONFIG_VERSION`, and update the tests that pin
behaviour. Stored decisions record both versions so results stay comparable (future backtesting).
