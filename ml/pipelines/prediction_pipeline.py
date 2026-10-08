"""Prediction pipeline: real recent candles + a registered model -> a standardized prediction.

Library use (what the backend service calls):

    PredictionPipeline(config).run(coin_id, horizon, candles_df, symbol=..., sentiment_articles=...)

Manual check from the repository root (loads LIVE Binance candles; reads a trained
model from the artifact directory; never trains anything):

    python -m ml.pipelines.prediction_pipeline --coin-key btc-test --symbol BTCUSDT --horizon 24h
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Iterable, Optional

import pandas as pd

from ml.config.model_config import HORIZONS, MLConfig, get_horizon
from ml.models.model_registry import ModelRegistry
from ml.prediction.predictor import PredictionResult, Predictor


class PredictionPipeline:
    def __init__(self, config: MLConfig):
        self.config = config
        self.registry = ModelRegistry(config.artifact_dir)
        self.predictor = Predictor(self.registry, config)

    def has_model(self, coin_id: str, horizon: str) -> bool:
        return bool(self.registry.active_for(coin_id, horizon))

    def available_horizons(self, coin_id: str) -> list[str]:
        return self.predictor.available_horizons(coin_id)

    def run(
        self, coin_id: str, horizon: str, candles: Optional[pd.DataFrame], *, symbol: Optional[str] = None,
        sentiment_articles: Optional[Iterable[dict]] = None, model_type: Optional[str] = None,
    ) -> PredictionResult:
        return self.predictor.predict(coin_id, horizon, candles, symbol=symbol,
                                      sentiment_articles=sentiment_articles, model_type=model_type)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m ml.pipelines.prediction_pipeline")
    p.add_argument("--coin-key", required=True)
    p.add_argument("--symbol", required=True, help="Binance pair, e.g. BTCUSDT")
    p.add_argument("--horizon", default=None, choices=list(HORIZONS))
    p.add_argument("--model", default=None)
    args = p.parse_args(argv)

    config = MLConfig.from_env()
    horizon = args.horizon or config.default_horizon
    spec = get_horizon(horizon)
    from ml.data.loaders import BinanceKlineLoader

    candles = BinanceKlineLoader(os.environ.get("BINANCE_API_BASE_URL", "https://api.binance.com")).fetch(
        args.symbol, spec.interval, spec.predict_candles + 50)
    result = PredictionPipeline(config).run(args.coin_key, horizon, candles, symbol=args.symbol, model_type=args.model)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
