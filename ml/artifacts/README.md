# ML artifacts

Trained models live here. **Nothing in this directory is committed to Git** except
this file and `.gitkeep` (see the root `.gitignore`: `ml/artifacts/*`).

## Where models are stored

The location is `ML_ARTIFACT_DIR` (default `ml/artifacts`, resolved relative to the
repository root; set it to another directory/volume if you prefer). Layout:

```
<ML_ARTIFACT_DIR>/<coin_id>/<horizon>/<model_type>/<version>/
    model.json | model.txt | weights.pt | ridge.json | ensemble.json   the model
    model_meta.json     model type, feature names, hyper-parameters
    calibration.json    prediction-interval + direction/confidence calibration
    record.json         registry record (see below)
```

* `coin_id` — the platform's internal coin id (the same 24-hex id used by the API).
* `horizon` — `1h`, `4h`, `24h`, `7d` or `30d`.
* `model_type` — `xgboost`, `lightgbm`, `lstm`, `ridge` (linear baseline) or `ensemble`.
* `version` — `v1`, `v2`, … Several versions can coexist.

`record.json` is the registry entry: `model_name`, `model_type`, `version`, `coin_id`,
`timeframe` (the horizon), `training_timestamp`, `feature_version`, `metrics`
(train / validation / test), `artifact_path` (relative, so the directory is
relocatable), and `status`:

| status | meaning |
|--------|---------|
| `active` | passed the activation gate; used for predictions (one per coin/horizon/model type) |
| `rejected` | trained and evaluated but did **not** beat the baselines on held-out test data; never served |
| `superseded` | an older version replaced by a newer active one |

There is no central index file: the registry is the set of `record.json` files, so
there is nothing to corrupt and a damaged record is simply skipped.

## How models are generated

Training is an explicit, manual step. It is never run by the API, at start-up, or
when a page is opened. From the repository root (needs network access to Binance's
public API for real candles):

```bash
# a coin that exists in MongoDB (internal id, CoinGecko id, or symbol)
python -m ml.pipelines.training_pipeline --coin bitcoin --horizons 1h 24h --models xgboost lightgbm --ensemble

# the 10 largest coins that have a Binance trading pair
python -m ml.pipelines.training_pipeline --top 10 --horizons 24h --models xgboost

# no MongoDB: a Binance pair plus an artifact key
python -m ml.pipelines.training_pipeline --symbol BTCUSDT --coin-key btc-test --horizons 24h --models ridge
```

Coins without a Binance pair, or with too little history, are reported as
`insufficient_data` and produce no model. A model that does not beat the
zero-return and majority-direction baselines on the held-out test segment is
stored as `rejected` and is **not** used — the API then answers
`model_unavailable` rather than serving a number with no demonstrated skill.

## How models are loaded

`ml.prediction.predictor.Predictor` looks up the `active` records for a
coin/horizon in the registry, loads the preferred one (`ML_DEFAULT_MODEL`, falling
back to the best validated alternative), and refuses a model whose
`feature_version` differs from the current feature set. Loading uses JSON/text
formats (XGBoost JSON, LightGBM text, Ridge JSON) or `torch.load(weights_only=True)`
— no arbitrary pickle files are read.

## What not to commit

Everything generated in this directory: model files, `*.pt`, `*.pkl`, `*.joblib`,
`calibration.json`, `record.json`, and any other output of the training pipeline.
They are specific to your data snapshot and can be large. To share a model, copy
the directory out-of-band (object storage, a release asset) — not through Git.
