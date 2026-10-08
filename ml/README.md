# ML Prediction Engine (Phase 13)

Probabilistic, range-based return forecasts built from **real** exchange candles,
the Phase 10 technical indicators and Phase 12 news sentiment. It never claims an
exact future price, never uses random or hard-coded values, and answers
`insufficient_data` / `model_unavailable` instead of guessing.

```
ml/
├── config/       horizons, hyper-parameters, ML_* settings, FEATURE_VERSION
├── data/         loaders (Binance klines) · preprocessing · validation · dataset_builder
├── features/     market · technical (reuses backend/app/services/indicators.py) · sentiment · fundamental
├── models/       base_model · xgboost · lightgbm · lstm (LSTM/GRU, PyTorch) · ridge baseline · model_registry
├── training/     trainer · validation (chronological split, walk-forward) · evaluation · model_selection
├── prediction/   predictor · confidence (intervals/calibration) · ensemble
├── pipelines/    training_pipeline (CLI) · prediction_pipeline
├── artifacts/    trained models (git-ignored) — see artifacts/README.md
└── tests/        pytest suite (run with the backend suite: `cd backend && python -m pytest`)
```

## Data and features

* **Source:** Binance spot klines (the only provider here with volume and
  sub-daily depth). Coins without a Binance pair have no real OHLCV history →
  `insufficient_data`.
* **Cleaning:** sort chronologically, drop invalid/duplicate rows, report (never
  fill) gaps, drop the still-open last candle.
* **Features** (all causal — row *t* uses only candles ≤ *t*): returns, log returns,
  volatility, candle shape, volume z-scores; RSI, MACD (+signal/histogram), SMA/EMA
  ratios, Bollinger distance/width/position, ATR, volume/OBV/VWAP ratios, rolling
  support/resistance distance, trend class; news sentiment (score, % positive/neutral/negative,
  trend, volume) using only articles published at or before the candle close.
* **Fundamentals:** implemented (`features/fundamental_features.py`) but **off** for
  training. Phase 11 fundamentals come from the *current* `market_data` snapshot; there
  is no stored history, so attaching them to past rows would leak the present into
  the past. They switch on only when point-in-time history exists.
* **Targets:** `target = close[t+steps] / close[t] − 1`, only where the future candle
  is exactly one horizon later in wall-clock time. A realised future volatility target is also derivable.

| horizon | candle | steps ahead |
|---------|--------|-------------|
| 1h | 1h | 1 |
| 4h | 1h | 4 |
| 24h | 1h | 24 |
| 7d | 4h | 42 |
| 30d | 1d | 30 |

## Leakage controls

Chronological train / validation / test split with an **embargo** of `steps` rows
between segments; scaler/imputer statistics fitted on the training rows only;
validation used only for early stopping and calibration; test segment touched only
for evaluation and the activation gate; sentiment point-in-time; open candle
dropped. `ml/tests/test_features_and_targets.py` proves truncation-invariance (changing
future candles never changes an earlier feature row).

## Models

`BasePredictionModel` (`fit / predict / evaluate / save / load / feature_importance`) with
`XGBoostModel`, `LightGBMModel`, `LSTMModel` (LSTM or GRU, configurable sequence
length / hidden size / layers / dropout / batch / epochs / learning rate), and a
`RidgeBaselineModel` linear benchmark. `EnsembleModel` combines only models that exist,
passed the gate and have finite validation MAE; weights are configured or
inverse-validation-MAE — never invented. Switch with `ML_DEFAULT_MODEL`.

## Evaluation, ranges and confidence

MAE, RMSE, R², directional accuracy, plus the baselines they must beat (zero-return MAE,
majority-direction accuracy). MAPE is not computed on returns (undefined across zero);
an implied-*price* MAPE is. **Range:** split-conformal residual quantiles on validation
data (nominal 80%); real test-set coverage is stored. **Confidence:** isotonic calibration
of "direction was correct" against |predicted return| on validation data — the probability
the *direction* is right, not that a price is reached. It is `null` /
`confidence_status: "unavailable"` when validation data is too small or the calibration
error on the test set is too large.

## Commands

```bash
python -m ml.pipelines.training_pipeline --help        # train (explicit, manual)
python -m ml.pipelines.prediction_pipeline --help      # one-off live prediction from a trained model
cd backend && python -m pytest                          # backend + ML tests
```

Not in this phase: BUY/HOLD/SELL, risk scoring, Gemini explanations, backtesting
dashboards, user prediction history.
