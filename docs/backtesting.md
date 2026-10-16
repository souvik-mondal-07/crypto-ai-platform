# Phase 17 — Backtesting & Model Accuracy

Historical evaluation and simulation only. Nothing in this phase places, simulates-as-a-product, or prepares real
orders. Evaluation code lives in `ml/evaluation/` (standard library only, deterministic) and is wrapped by the backend
(`backend/app/services/evaluation_service.py`, `backtest_service.py`) and the `/backtesting` page.

Versions: methodology `1.0.0` (`METHODOLOGY_VERSION`) and engine `1.0.0` (`BACKTEST_ENGINE_VERSION`) in
`ml/evaluation/constants.py`. Both are stored with every result; change a rule => bump the version.

```
stored predictions + stored decisions        real exchange candles (Binance klines, read-only)
              \                                  /
               outcome matching (ml/evaluation/matching.py, decision_eval.py)
                              |
                    prediction_results  (existing collection, idempotent)
                              |
              accuracy metrics (metrics.py)  ->  /backtesting/accuracy, /decisions
 
 stored decisions + real candles -> backtest engine (backtest.py) -> backtest_runs -> /backtesting/runs
```

Prediction evaluation and strategy backtesting are separate: the first asks "was the forecast right?", the second
"what would acting on the decisions have returned after costs?".

## 1. Prediction → outcome matching

* `reference_time` is the CLOSE time of the last completed candle the forecast started from; `current_price` is that
  candle's close (Phase 13). `target_time = reference_time + horizon`.
* A prediction is **matured** only when `now >= target_time`. Unmatured predictions are never stored as results and never
  counted.
* Actual price = close of the candle whose close time is nearest `target_time`, accepted only within a **half candle
  interval** (`MATCH_TOLERANCE_FRACTION = 0.5`): 30 min for 1h candles (1h/4h/24h horizons), 2h for 4h (7d), 12h for 1d (30d).
  The candle must already be closed at evaluation time.
* `actual_return = actual_price / reference_price − 1` using the RECORDED reference price.
* Timestamps are normalised to UTC (naive = UTC; ISO strings, `Z`, offsets, epoch s/ms accepted; unparseable → invalid).

| Outcome status | Meaning | Stored? |
|---|---|---|
| `matched` | actual price found | yes |
| `not_matured` | horizon not elapsed | no |
| `missing_reference_price` | no valid recorded reference price | yes (permanent) |
| `missing_future_price` | later data exists but nothing near the target (gap), or no Binance mapping | yes (permanent) |
| `stale_market_data` | data ends before the target | no — retried |
| `unsupported_horizon` / `invalid_record` | unknown horizon; missing time/return/direction; inconsistent `target_time` | yes (permanent) |
| provider failure / empty download | indistinguishable from an outage | no — retried next refresh |

Candles with non-finite/non-positive prices or inconsistent high/low are dropped (never repaired); duplicate candles
collapse (last wins); incomplete candles (close after `now`) are excluded. Duplicate predictions (same
coin/horizon/model/version/reference time) are collapsed at metric time, keeping the latest generated one.

## 2. Accuracy metrics (computed only from matched outcomes)

`r` = actual return, `p` = predicted return, `n` = matched sample.

| Metric | Definition |
|---|---|
| Directional accuracy | hits / directional calls. Hit: predicted `up` & r>0, or `down` & r<0. Predictions the model labelled `flat` make no call and are excluded (counted separately). An up/down call with r exactly 0 is a miss. |
| MAE | mean(\|p − r\|), in return units (shown as percentage points) |
| RMSE | sqrt(mean((p − r)²)) |
| Mean error (bias) | mean(p − r); positive = over-prediction |
| Zero baseline MAE | mean(\|r\|) = MAE of always predicting 0; `mae_vs_zero_baseline` < 1 means the model beat it |
| Range coverage | share of outcomes inside the stored range (inclusive); return range preferred, else price range; compared with the nominal coverage the range was built for |
| Sample size / period | `n`; earliest to latest target time |

Not computed on purpose: **MAPE** (undefined/unstable when returns are ≈0) and **R²** (not meaningful for near-zero-mean,
heavy-tailed return forecasts). Fewer than **30** matched outcomes (`MIN_SAMPLE_SIZE`) ⇒ `status: insufficient_data` and
every metric is `null`; zero matched ⇒ `no_data`. Nothing is ever defaulted to 0. Metrics are broken down by overall,
horizon, model+version and coin (top 50). Results are cached for 60 s keyed by the stored-results fingerprint.

## 3. Decision evaluation

Decisions carry no horizon or reference price, so the reference is the close of the last candle COMPLETE at
`generated_at` (must be ≤1.5 intervals old), and the forward return is measured at `generated_at + H` for
H ∈ {24h, 7d, 30d}. Not-yet-matured decisions are not counted; decisions without a BUY/HOLD/SELL value are excluded.

* **BUY** — *directionally aligned* when the forward return > 0.
* **SELL** — *directionally aligned* when the forward return < 0 (a SELL followed by a rise is reported as such).
* **HOLD** — no directional claim. Reported by mean/median forward return and the share of outcomes inside a **neutral
  band** (±2% at 24h, ±5% at 7d, ±10% at 30d — explicit assumptions, not success criteria).
* Per (decision, horizon) cells need ≥ 20 samples (`MIN_DECISION_SAMPLE_SIZE`) or show `insufficient_data`.

## 4. Backtest engine (strategy `phase14_decisions`)

Long-only replay of the STORED Phase 14 decisions — no new strategy:

* BUY while flat → open; SELL while long → close the whole position; HOLD, repeated BUY, SELL while flat → no action.
* A decision generated at `t` is executed at the OPEN of the first bar whose open time is ≥ `t` ("next-bar open").
  Only decisions with `start ≤ generated_at ≤ bar open` are visible at a bar, so later decisions/prices never influence
  earlier ones. Equity is marked at each bar's close; a missing bar carries the last known close forward.
* **Costs** (always shown in the report): fee = `fee_rate × notional` per side (default 0.10%); slippage adverse to the
  trade (buys at `open × (1+s)`, sells at `open × (1−s)`, default 0.05%). Zero is accepted only when configured explicitly
  (the UI warns).
* **Sizing**: `fixed_fraction` of current equity or `fixed_amount`; capped by `max_allocation_pct` of equity and by cash
  (fee included). No leverage, no shorting, no pyramiding.
* Open positions are closed at the final bar's close (with costs) unless disabled.
* **Benchmark**: equal-weight buy-and-hold of the same coins, same fee and slippage, entered at each coin's first bar.

Statistics (`backtest_metrics.py`): total return = final/initial − 1; annualised return only for periods ≥ 30 days;
max drawdown = largest peak-to-trough fall of the equity curve (starting capital is the first peak), shown as a loss;
win rate = winning closed round trips / closed round trips (net of fees and slippage); average win/loss = mean net
return of winning/losing trades; Sharpe only with ≥ 30 return observations and non-zero volatility (risk-free 0%,
√(bars per year) annualisation). Otherwise `null` with an explanatory note.
Runs with no stored decisions in the period are flagged `insufficient_data` (a benchmark is still shown). Results are
simulations on history, **not forecasts or guarantees**.

Limits: ≤10 coins, 1–365 days, ≤5,000 bars per coin (1h ≈ 208 days), capital ≤ 1e9, 2 concurrent runs per user.
Runs execute as background tasks (`asyncio.create_task`, as the schedulers do); runs left `queued/running` by a previous
process are marked failed at startup.

## 5. Data-leakage controls

* Engine: next-bar-open execution, point-in-time decision visibility, as-of candle filtering (`PriceSeries(as_of=…)`),
  chronological iteration — tested by `test_execution_never_precedes_the_decision`,
  `test_future_price_never_changes_an_earlier_decision_or_trade`, `test_future_decision_cannot_influence_earlier_bars`,
  `test_decisions_before_the_window_or_after_it_are_ignored`, `test_series_as_of_blocks_unfinished_candles`,
  `test_future_candles_beyond_now_are_ignored`, `test_reference_price_falls_back_to_point_in_time_candle_close_never_later`.
* Matching/maturity: a prediction is only evaluated after its horizon; candles closing after `now` are invisible.
* Pre-existing Phase 13 controls (unchanged, tested in `ml/tests`): features at `t` do not change when future candles
  change; scaler/preprocessor statistics come from training rows only; chronological split with embargo; historical
  news/fundamental features that would leak present-day data are OFF.

## 6. Known limitations

* Accuracy needs REAL matured predictions: the platform only has them after predictions have been generated and their
  horizons (1h … 30d) have elapsed. Until ≥ 30 are matched, the UI shows
  "Insufficient historical predictions to calculate reliable accuracy metrics."
* Decisions are only stored when generated (or cached) — there is no historical decision backfill (it would require
  point-in-time news/sentiment/fundamentals that are not stored). Backtests over periods without stored decisions are
  reported as `insufficient_data`.
* Decisions do not store the price they were generated at; the point-in-time candle close is used instead.
* Outcome prices come from Binance klines only; coins without a Binance mapping cannot be evaluated.
* Outcome matching runs on demand (`POST /backtesting/accuracy/refresh`, button "Update outcomes"), not on a schedule.
