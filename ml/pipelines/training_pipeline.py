"""Explicit, manually-triggered training pipeline.

    Historical candles -> validation/cleaning -> features -> targets
        -> chronological split -> train -> calibrate -> evaluate -> artifact -> registry

Run from the repository root (never started by the API):

    # one coin from MongoDB (internal id, CoinGecko id like "bitcoin", or symbol "BTC")
    python -m ml.pipelines.training_pipeline --coin bitcoin --horizons 24h --models xgboost lightgbm --ensemble

    # without MongoDB: name a Binance pair and an artifact key directly
    python -m ml.pipelines.training_pipeline --symbol BTCUSDT --coin-key btc-test --horizons 24h --models ridge

    # the N largest coins that have a Binance mapping
    python -m ml.pipelines.training_pipeline --top 10 --horizons 24h 7d --models xgboost

Requires network access to Binance's public API. Coins/horizons without enough real
history are reported as ``insufficient_data`` and no model is produced for them.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import pandas as pd

from ml.config.model_config import HORIZONS, SUPPORTED_MODEL_TYPES, MLConfig, get_horizon
from ml.data.dataset_builder import Dataset, InsufficientDataError, build_dataset
from ml.models.base_model import ModelDependencyError
from ml.models.ensemble_support import train_ensemble
from ml.models.model_registry import STATUS_ACTIVE, ModelRegistry
from ml.training.trainer import TrainResult, train_one, walk_forward_evaluate

logger = logging.getLogger("crypto_ai_platform.ml.training")


@dataclass
class HorizonOutcome:
    coin_id: str
    horizon: str
    status: str                       # trained | insufficient_data | failed
    detail: str = ""
    models: list[dict[str, Any]] = field(default_factory=list)
    walk_forward: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


def train_coin_horizon(
    candles: pd.DataFrame,
    *,
    coin_id: str,
    horizon_name: str,
    model_types: Iterable[str],
    config: MLConfig,
    registry: ModelRegistry,
    symbol: Optional[str] = None,
    sentiment_articles: Optional[Iterable[dict]] = None,
    ensemble: bool = False,
    walk_forward: int = 0,
) -> HorizonOutcome:
    """Train every requested model type for one (coin, horizon) from already-loaded real candles."""
    spec = get_horizon(horizon_name)
    out = HorizonOutcome(coin_id, spec.name, "trained")
    try:
        dataset: Dataset = build_dataset(candles, spec, config, sentiment_articles=sentiment_articles)
    except InsufficientDataError as exc:
        out.status, out.detail = "insufficient_data", str(exc)
        return out

    results: list[TrainResult] = []
    for model_type in model_types:
        try:
            res = train_one(dataset, model_type, config, registry, coin_id=coin_id, symbol=symbol)
        except ModelDependencyError as exc:
            out.models.append({"model_type": model_type, "status": "unavailable", "detail": str(exc)})
            continue
        except Exception as exc:  # one model failing must not stop the others
            logger.exception("Training %s failed for %s/%s", model_type, coin_id, horizon_name)
            out.models.append({"model_type": model_type, "status": "failed", "detail": f"{exc.__class__.__name__}: {exc}"})
            continue
        results.append(res)
        out.models.append({
            "model_type": model_type, "version": res.record.version, "status": res.record.status,
            "test": res.record.metrics.get("test"), "gate_reasons": res.gate_reasons,
        })
        if walk_forward:
            try:
                out.walk_forward[model_type] = walk_forward_evaluate(dataset, model_type, config, n_splits=walk_forward)
            except Exception as exc:
                out.walk_forward[model_type] = [{"error": str(exc)}]

    if ensemble:
        ens = train_ensemble(results, dataset, config, registry, coin_id=coin_id, symbol=symbol)
        if ens is not None:
            out.models.append({"model_type": "ensemble", "version": ens.record.version, "status": ens.record.status,
                               "test": ens.record.metrics.get("test"), "gate_reasons": ens.gate_reasons})
        else:
            out.models.append({"model_type": "ensemble", "status": "skipped",
                               "detail": "needs at least two active, validated member models"})
    if not any(m.get("status") in (STATUS_ACTIVE, "rejected") for m in out.models):
        out.status, out.detail = "failed", "no model could be trained"
    return out


# ------------------------------------------------------------------------ CLI helpers


def _resolve_coins_from_mongo(args: argparse.Namespace) -> list[dict[str, Any]]:
    import os
    from pymongo import MongoClient  # backend dependency

    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.environ.get("MONGODB_DATABASE", "crypto_ai_platform")
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    coins = client[db_name]["coins"]
    docs: list[dict[str, Any]] = []
    if args.top:
        docs = list(coins.find({"providers.binance.symbol": {"$exists": True, "$ne": None}, "is_active": {"$ne": False},
                                "market_cap_rank": {"$ne": None}}).sort("market_cap_rank", 1).limit(args.top))
    for key in args.coin or []:
        doc = None
        if len(key) == 24:
            from bson import ObjectId

            try:
                doc = coins.find_one({"_id": ObjectId(key)})
            except Exception:
                doc = None
        doc = doc or coins.find_one({"providers.coingecko.id": key.lower()}) or coins.find_one(
            {"symbol": {"$regex": f"^{key}$", "$options": "i"}}, sort=[("market_cap_rank", 1)])
        if doc is None:
            print(f"! coin {key!r} not found in MongoDB", file=sys.stderr)
        else:
            docs.append(doc)
    out = []
    for d in docs:
        out.append({"coin_id": str(d["_id"]), "oid": d["_id"], "symbol": d.get("symbol"),
                    "binance_symbol": (d.get("providers") or {}).get("binance", {}).get("symbol")})
    return out


def _load_articles(oid: Any) -> list[dict]:
    """Analyzed news for one coin (real stored articles; may be empty)."""
    import os
    from pymongo import MongoClient

    client = MongoClient(os.environ.get("MONGODB_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=5000)
    cur = client[os.environ.get("MONGODB_DATABASE", "crypto_ai_platform")]["news"].find(
        {"related_coin_ids": oid, "sentiment_status": "analyzed"},
        {"published_at": 1, "sentiment.label": 1, "sentiment.score": 1})
    return [{"published_at": d["published_at"], "label": d["sentiment"]["label"], "score": d["sentiment"]["score"]}
            for d in cur if isinstance(d.get("sentiment"), dict) and "score" in d["sentiment"]]


def _record_metrics_in_mongo(registry: ModelRegistry, coin_ids: set[str]) -> None:
    """Best-effort mirror of registry records into the existing `model_metrics` collection."""
    import os
    from pymongo import MongoClient

    try:
        client = MongoClient(os.environ.get("MONGODB_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=3000)
        col = client[os.environ.get("MONGODB_DATABASE", "crypto_ai_platform")]["model_metrics"]
        for coin_id in coin_ids:
            for rec in registry.list_records(coin_id):
                doc = rec.to_dict()
                doc["model_name"] = rec.model_name
                doc["training_timestamp"] = pd.Timestamp(rec.training_timestamp).to_pydatetime()
                col.update_one({"model_name": rec.model_name}, {"$set": doc}, upsert=True)
    except Exception as exc:  # metrics mirroring must never fail a training run
        logger.warning("Could not mirror model metrics to MongoDB: %s", exc.__class__.__name__)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ml.pipelines.training_pipeline", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--coin", nargs="*", help="coin internal id / CoinGecko id / symbol (needs MongoDB)")
    parser.add_argument("--top", type=int, default=0, help="train the N largest coins that have a Binance pair (needs MongoDB)")
    parser.add_argument("--symbol", help="Binance pair, e.g. BTCUSDT (MongoDB-free mode; needs --coin-key)")
    parser.add_argument("--coin-key", help="artifact key to use with --symbol")
    parser.add_argument("--horizons", nargs="+", default=None, choices=list(HORIZONS))
    parser.add_argument("--models", nargs="+", default=["xgboost"], choices=list(SUPPORTED_MODEL_TYPES))
    parser.add_argument("--ensemble", action="store_true", help="also build an ensemble of the validated models")
    parser.add_argument("--walk-forward", type=int, default=0, metavar="N", help="also report N walk-forward folds")
    parser.add_argument("--no-sentiment", action="store_true", help="do not load news sentiment from MongoDB")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

    config = MLConfig.from_env()
    registry = ModelRegistry(config.artifact_dir)
    horizons = args.horizons or [config.default_horizon]

    targets: list[dict[str, Any]] = []
    if args.symbol:
        if not args.coin_key:
            parser.error("--symbol requires --coin-key")
        targets.append({"coin_id": args.coin_key, "oid": None, "symbol": args.symbol, "binance_symbol": args.symbol})
    if args.coin or args.top:
        targets += _resolve_coins_from_mongo(args)
    if not targets:
        parser.error("nothing to train: pass --coin, --top, or --symbol with --coin-key")

    from ml.data.loaders import BinanceKlineLoader
    import os

    loader = BinanceKlineLoader(os.environ.get("BINANCE_API_BASE_URL", "https://api.binance.com"))
    summary: list[dict[str, Any]] = []
    for t in targets:
        if not t.get("binance_symbol"):
            summary.append({"coin_id": t["coin_id"], "status": "insufficient_data",
                            "detail": "no Binance trading pair — no real historical OHLCV source for this coin"})
            continue
        articles = None if (args.no_sentiment or t.get("oid") is None) else _load_articles(t["oid"])
        raw_cache: dict[str, pd.DataFrame] = {}
        for h in horizons:
            spec = get_horizon(h)
            key = f"{spec.interval}:{spec.train_candles}"
            if key not in raw_cache:
                raw_cache[key] = loader.fetch(t["binance_symbol"], spec.interval, spec.train_candles)
            outcome = train_coin_horizon(raw_cache[key], coin_id=t["coin_id"], horizon_name=h, model_types=args.models,
                                         config=config, registry=registry, symbol=t.get("symbol"),
                                         sentiment_articles=articles, ensemble=args.ensemble,
                                         walk_forward=args.walk_forward)
            summary.append(outcome.__dict__)
    _record_metrics_in_mongo(registry, {t["coin_id"] for t in targets}) if (args.coin or args.top) else None
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
