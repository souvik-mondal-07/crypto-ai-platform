"""Turns real recent candles + a validated, trained model into a standardized prediction.

Statuses (the API/UI branch on these; nothing is ever invented):
    ok                 a prediction was produced from model output
    insufficient_data  not enough (or too stale / gappy) real history to build features
    model_unavailable  no validated model is registered for this coin/horizon (or it can't be loaded)
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

import pandas as pd

from ml.config.feature_config import FEATURE_VERSION
from ml.config.model_config import MLConfig, get_horizon
from ml.data.dataset_builder import InsufficientDataError, build_inference_row
from ml.models.base_model import ModelDependencyError
from ml.models.model_registry import ModelRecord, ModelRegistry
from ml.prediction.confidence import confidence_for, direction_for, return_range
from ml.training.model_selection import rank_models

logger = logging.getLogger("crypto_ai_platform.ml.prediction")

DISCLAIMER = (
    "This is a machine-learning estimate based on historical data and available features. "
    "It is not a guarantee of future performance."
)


@dataclass
class PredictionResult:
    status: str                                  # ok | insufficient_data | model_unavailable
    coin_id: str
    horizon: str
    symbol: Optional[str] = None
    reason: Optional[str] = None
    kind: str = "model_prediction"               # never a market fact
    # --- populated only when status == "ok" ---
    current_price: Optional[float] = None        # last CLOSED candle close = the forecast origin
    reference_time: Optional[datetime] = None    # close time of that candle
    target_time: Optional[datetime] = None       # reference_time + horizon
    predicted_return: Optional[float] = None     # fractional, e.g. 0.024 == +2.4%
    predicted_return_range: Optional[dict[str, float]] = None
    predicted_price_range: Optional[dict[str, float]] = None
    range_nominal_coverage: Optional[float] = None
    direction: Optional[str] = None              # up | down | flat
    confidence: Optional[float] = None           # P(direction correct), calibrated; else None
    confidence_status: str = "unavailable"       # calibrated | unavailable
    confidence_note: Optional[str] = None
    model: Optional[str] = None
    model_version: Optional[str] = None
    feature_version: Optional[str] = None
    model_metrics: Optional[dict[str, Any]] = None
    trained_at: Optional[str] = None
    generated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("reference_time", "target_time", "generated_at", "expires_at"):
            if d[k] is not None:
                d[k] = d[k].isoformat()
        return d


def _num(x: Any) -> Optional[float]:
    return float(x) if isinstance(x, (int, float)) and math.isfinite(x) else None


class Predictor:
    def __init__(self, registry: ModelRegistry, config: MLConfig):
        self.registry = registry
        self.config = config

    # -- model choice -------------------------------------------------------------
    def _candidates(self, coin_id: str, horizon: str, model_type: Optional[str]) -> list[ModelRecord]:
        active = self.registry.active_for(coin_id, horizon)
        prefer = model_type or self.config.default_model
        if model_type:  # an explicit request is honoured exactly — no silent substitution
            return [r for r in active if r.model_type == model_type]
        return rank_models(active, prefer)

    def available_horizons(self, coin_id: str) -> list[str]:
        from ml.config.model_config import HORIZONS

        return [h for h in HORIZONS if self.registry.active_for(coin_id, h)]

    # -- main entry ---------------------------------------------------------------
    def predict(
        self,
        coin_id: str,
        horizon: str,
        candles: Optional[pd.DataFrame],
        *,
        symbol: Optional[str] = None,
        sentiment_articles: Optional[Iterable[dict]] = None,
        model_type: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> PredictionResult:
        spec = get_horizon(horizon)  # ValueError for unsupported horizons (callers validate first)
        base = dict(coin_id=coin_id, horizon=spec.name, symbol=symbol)
        now = now or datetime.now(timezone.utc)

        candidates = self._candidates(coin_id, spec.name, model_type)
        if not candidates:
            return PredictionResult(
                "model_unavailable", reason=(
                    f"No validated {model_type + ' ' if model_type else ''}model is available for the {spec.name} "
                    "horizon. Models are trained explicitly (python -m ml.pipelines.training_pipeline) and only "
                    "activated when they beat baseline checks on held-out data."), **base)

        last_error: Optional[str] = None
        for record in candidates:
            if record.feature_version != FEATURE_VERSION:
                last_error = f"{record.model_name} was trained with feature set {record.feature_version}, current is {FEATURE_VERSION}"
                continue
            try:
                model = self.registry.load(record)
                cal = self.registry.load_calibration(record)
            except (ModelDependencyError, FileNotFoundError, ValueError, OSError, KeyError) as exc:
                logger.warning("Cannot load %s: %s", record.model_name, exc)
                last_error = f"{record.model_name} could not be loaded ({exc.__class__.__name__})"
                continue

            if candles is None or len(candles) == 0:
                return PredictionResult("insufficient_data", reason="No historical candles are available for this coin.", **base)
            try:
                rows, info = build_inference_row(
                    candles, spec, model.feature_names, self.config,
                    sentiment_articles=sentiment_articles, required_context=model.required_context, now=now,
                )
            except InsufficientDataError as exc:
                return PredictionResult("insufficient_data", reason=str(exc), **base)

            preds = model.predict(rows)
            pred = float(preds[-1])
            if not math.isfinite(pred):
                return PredictionResult("insufficient_data", reason="Model could not produce a finite output from the latest candles.", **base)
            return self._assemble(record, cal, pred, info, spec, now, base)

        return PredictionResult("model_unavailable", reason=last_error or "No usable model.", **base)

    # -- output --------------------------------------------------------------------
    def _assemble(self, record, cal, pred, info, spec, now, base) -> PredictionResult:
        price = float(info["close"])
        reference_time = info["as_of"].to_pydatetime()
        rr = return_range(pred, cal)
        conf = confidence_for(pred, cal) if cal.get("confidence_reliable") else None
        direction = direction_for(pred, cal)
        note: Optional[str] = None
        if conf is None:
            note = ("Confidence could not be calibrated reliably for this model."
                    if not cal.get("confidence_reliable") else "No confidence is shown for a flat prediction.")
        if direction == "flat":
            conf, note = None, "No directional call: the expected move is smaller than typical model error."
        test = (record.metrics or {}).get("test") or {}
        return PredictionResult(
            "ok", **base,
            current_price=price,
            reference_time=reference_time,
            target_time=reference_time + timedelta(seconds=spec.horizon_seconds),
            predicted_return=pred,
            predicted_return_range=({"lower": rr[0], "upper": rr[1]} if rr else None),
            predicted_price_range=(
                {"lower": price * (1 + rr[0]), "upper": price * (1 + rr[1])} if rr else None),
            range_nominal_coverage=(cal.get("interval") or {}).get("nominal_coverage"),
            direction=direction,
            confidence=conf,
            confidence_status="calibrated" if conf is not None else "unavailable",
            confidence_note=note,
            model=record.model_type, model_version=record.version, feature_version=record.feature_version,
            model_metrics={
                "test_mae": _num(test.get("mae")), "baseline_mae": _num(test.get("baseline_mae")),
                "test_directional_accuracy": _num(test.get("directional_accuracy")),
                "test_samples": test.get("n"),
                "interval_coverage_test": _num((record.metrics or {}).get("interval_coverage_test")),
            },
            trained_at=record.training_timestamp,
            generated_at=now,
            expires_at=now + timedelta(seconds=self.config.prediction_ttl_seconds),
        )
