"""Horizons, model hyper-parameters and environment-driven ML settings.

Adding a horizon later = add one ``HorizonSpec`` to ``HORIZONS``.
Adding a model later   = register it in ``ml.models.model_registry.MODEL_CLASSES``
                         and add its name to ``SUPPORTED_MODEL_TYPES``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

# Repository root (…/ml/config/model_config.py -> parents[2]). Used only to build
# *relative-to-repo* default paths; no machine-specific absolute path is stored.
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class HorizonSpec:
    """How one user-facing horizon maps onto real exchange candles.

    ``steps`` candles of ``interval`` ahead == the horizon. The interval is chosen
    so that enough *real* history can be fetched (Binance returns <= 1000 klines
    per request; the loader pages backwards for more).
    """

    name: str            # "1h", "4h", "24h", "7d", "30d"
    interval: str        # Binance kline interval used for features + target
    steps: int           # target = close[t + steps] / close[t] - 1
    interval_seconds: int
    #: Candles the loader tries to fetch for training (before cleaning).
    train_candles: int
    #: Candles needed at prediction time to warm up the slowest indicator
    #: (SMA-200 -> 200) plus a safety margin.
    predict_candles: int = 400

    @property
    def horizon_seconds(self) -> int:
        return self.steps * self.interval_seconds


HORIZONS: dict[str, HorizonSpec] = {
    "1h": HorizonSpec("1h", "1h", 1, 3600, 3000),
    "4h": HorizonSpec("4h", "1h", 4, 3600, 3000),
    "24h": HorizonSpec("24h", "1h", 24, 3600, 3000),
    "7d": HorizonSpec("7d", "4h", 42, 14400, 3000),
    "30d": HorizonSpec("30d", "1d", 30, 86400, 1500),
}

SUPPORTED_MODEL_TYPES = ("xgboost", "lightgbm", "lstm", "ridge")
#: Types that can be combined by the ensemble (``ensemble`` itself is not a member).
ENSEMBLE_MEMBER_TYPES = ("xgboost", "lightgbm", "lstm", "ridge")

_COIN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def get_horizon(name: str) -> HorizonSpec:
    try:
        return HORIZONS[name.lower()]
    except (KeyError, AttributeError):
        raise ValueError(f"Unsupported horizon {name!r}. Supported: {', '.join(HORIZONS)}") from None


def validate_coin_key(coin_id: str) -> str:
    """Coin ids become directory names — reject anything that could escape the artifact dir."""
    if not isinstance(coin_id, str) or not _COIN_ID_RE.match(coin_id):
        raise ValueError("coin_id may only contain letters, digits, '-' and '_' (max 64 chars).")
    return coin_id


#: Conservative defaults — small enough to train on a laptop in seconds/minutes.
DEFAULT_MODEL_PARAMS: dict[str, dict[str, Any]] = {
    "xgboost": {
        "n_estimators": 300,
        "max_depth": 3,
        "learning_rate": 0.03,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 5,
        "reg_lambda": 5.0,
        "n_jobs": 2,
        "random_state": 42,
        "early_stopping_rounds": 30,
    },
    "lightgbm": {
        "n_estimators": 300,
        "num_leaves": 15,
        "max_depth": 4,
        "learning_rate": 0.03,
        "subsample": 0.8,
        "subsample_freq": 1,
        "colsample_bytree": 0.8,
        "min_child_samples": 30,
        "reg_lambda": 5.0,
        "n_jobs": 2,
        "random_state": 42,
        "verbose": -1,
        "early_stopping_rounds": 30,
    },
    "lstm": {
        "sequence_length": 24,
        "hidden_size": 32,
        "num_layers": 1,
        "dropout": 0.2,
        "batch_size": 64,
        "epochs": 30,
        "learning_rate": 0.001,
        "patience": 5,
        "weight_decay": 1e-4,
        "cell": "lstm",  # or "gru"
        "random_state": 42,
    },
    "ridge": {"alpha": 10.0},
}


@dataclass
class MLConfig:
    """Runtime ML settings. Built from the environment (CLI) or from backend settings (API)."""

    artifact_dir: Path = field(default_factory=lambda: REPO_ROOT / "ml" / "artifacts")
    default_horizon: str = "24h"
    default_model: str = "xgboost"
    min_history_length: int = 500
    prediction_ttl_seconds: int = 900
    #: Share of rows (oldest first) used for train / validation; rest is the test set.
    train_fraction: float = 0.70
    validation_fraction: float = 0.15
    #: Prediction-interval miscoverage: 0.2 -> an 80% interval.
    interval_alpha: float = 0.20
    #: Minimum number of validation rows needed to calibrate confidence.
    min_calibration_samples: int = 100
    #: Minimum test rows before a model can be judged / activated.
    min_test_samples: int = 50
    #: |predicted return| below this fraction of validation MAE counts as "flat".
    flat_threshold_mae_fraction: float = 0.25
    #: Ensemble weights override, e.g. {"xgboost": 0.6, "lightgbm": 0.4}. None = data-driven.
    ensemble_weights: Optional[dict[str, float]] = None
    #: Drop a candidate feature if fewer than this share of training rows have it.
    min_feature_coverage: float = 0.80
    #: Activation gate (judged on the untouched TEST segment): the model's MAE must beat
    #: the "predict zero return" baseline by at least this relative margin ...
    min_mae_improvement: float = 0.0
    #: ... and its directional accuracy must beat max(50%, majority-direction baseline).
    require_directional_edge: bool = True
    #: Confidence is withheld if |mean confidence - observed hit rate| on the test set exceeds this.
    max_calibration_error: float = 0.15
    model_params: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {k: dict(v) for k, v in DEFAULT_MODEL_PARAMS.items()}
    )

    def __post_init__(self) -> None:
        self.artifact_dir = Path(self.artifact_dir)
        if not self.artifact_dir.is_absolute():
            # Relative paths in .env are interpreted relative to the repository root.
            self.artifact_dir = REPO_ROOT / self.artifact_dir
        self.default_horizon = self.default_horizon.lower()
        get_horizon(self.default_horizon)
        if self.default_model not in SUPPORTED_MODEL_TYPES and self.default_model != "ensemble":
            raise ValueError(f"Unsupported ML_DEFAULT_MODEL {self.default_model!r}")
        if not 0.3 <= self.train_fraction < 0.95 or not 0.05 <= self.validation_fraction < 0.4:
            raise ValueError("train/validation fractions out of range")
        if self.train_fraction + self.validation_fraction >= 0.95:
            raise ValueError("train + validation fractions must leave room for a test set")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "MLConfig":
        """Build from a mapping of ML_* settings (e.g. backend ``Settings``-derived)."""
        kwargs: dict[str, Any] = {}
        if values.get("ML_ARTIFACT_DIR"):
            kwargs["artifact_dir"] = Path(str(values["ML_ARTIFACT_DIR"]))
        if values.get("ML_DEFAULT_HORIZON"):
            kwargs["default_horizon"] = str(values["ML_DEFAULT_HORIZON"])
        if values.get("ML_DEFAULT_MODEL"):
            kwargs["default_model"] = str(values["ML_DEFAULT_MODEL"]).lower()
        if values.get("ML_MIN_HISTORY_LENGTH") not in (None, ""):
            kwargs["min_history_length"] = int(values["ML_MIN_HISTORY_LENGTH"])
        if values.get("ML_PREDICTION_TTL_SECONDS") not in (None, ""):
            kwargs["prediction_ttl_seconds"] = int(values["ML_PREDICTION_TTL_SECONDS"])
        return cls(**kwargs)

    @classmethod
    def from_env(cls) -> "MLConfig":
        """CLI entry point: reads backend/.env (if python-dotenv is available) then os.environ."""
        try:
            from dotenv import load_dotenv  # type: ignore

            load_dotenv(REPO_ROOT / "backend" / ".env")
        except ImportError:  # pragma: no cover - dotenv is a backend dependency
            pass
        keys = (
            "ML_ARTIFACT_DIR", "ML_DEFAULT_HORIZON", "ML_DEFAULT_MODEL",
            "ML_MIN_HISTORY_LENGTH", "ML_PREDICTION_TTL_SECONDS",
        )
        return cls.from_mapping({k: os.environ.get(k) for k in keys})
