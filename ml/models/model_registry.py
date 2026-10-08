"""File-based model registry.

Layout (everything under ``MLConfig.artifact_dir``, which is git-ignored):

    <coin_key>/<horizon>/<model_type>/<version>/
        model files (model.json | model.txt | weights.pt | ridge.json | ensemble.json)
        model_meta.json      feature names + params
        calibration.json     interval / direction / confidence calibration
        record.json          the ModelRecord below (metrics, status, ...)

The registry is the scan of ``record.json`` files — no central index to corrupt,
and several versions per (coin, horizon, model_type) can coexist. At most one
version per (coin, horizon, model_type) is ``active``; activating a new one marks
the previous ``superseded``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ml.config.model_config import HORIZONS, SUPPORTED_MODEL_TYPES, validate_coin_key
from ml.models.base_model import BasePredictionModel
from ml.models.lightgbm_model import LightGBMModel
from ml.models.lstm_model import LSTMModel
from ml.models.ridge_model import RidgeBaselineModel
from ml.models.xgboost_model import XGBoostModel

MODEL_CLASSES: dict[str, type[BasePredictionModel]] = {
    "xgboost": XGBoostModel,
    "lightgbm": LightGBMModel,
    "lstm": LSTMModel,
    "ridge": RidgeBaselineModel,
}

STATUS_ACTIVE = "active"
STATUS_REJECTED = "rejected"      # trained + evaluated, but failed the activation gate
STATUS_SUPERSEDED = "superseded"  # a newer active version exists
_VERSION_RE = re.compile(r"^v(\d+)$")


@dataclass
class ModelRecord:
    model_name: str
    model_type: str
    version: str
    coin_id: str
    timeframe: str                 # the prediction horizon, e.g. "24h"
    training_timestamp: str
    feature_version: str
    metrics: dict[str, Any]
    artifact_path: str             # relative to the artifact root (portable across machines)
    status: str
    symbol: Optional[str] = None
    info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelRecord":
        names = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in names})

    @property
    def version_number(self) -> int:
        m = _VERSION_RE.match(self.version)
        return int(m.group(1)) if m else 0


def create_model(model_type: str, params: Optional[dict[str, Any]] = None) -> BasePredictionModel:
    try:
        return MODEL_CLASSES[model_type](params)
    except KeyError:
        raise ValueError(f"Unknown model type {model_type!r}. Supported: {', '.join(SUPPORTED_MODEL_TYPES)}") from None


def load_model(root: Path, record: ModelRecord) -> BasePredictionModel:
    directory = _safe_dir(root, record.artifact_path)
    if record.model_type == "ensemble":
        from ml.prediction.ensemble import EnsembleModel

        return EnsembleModel.load(directory)
    try:
        cls = MODEL_CLASSES[record.model_type]
    except KeyError:
        raise ValueError(f"Unknown model type {record.model_type!r}") from None
    return cls.load(directory)


def _safe_dir(root: Path, relative: str) -> Path:
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if root != path and root not in path.parents:
        raise ValueError("Artifact path escapes the artifact directory.")
    return path


class ModelRegistry:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    # ---- paths ----
    def version_dir(self, coin_id: str, horizon: str, model_type: str, version: str) -> Path:
        validate_coin_key(coin_id)
        if horizon not in HORIZONS:
            raise ValueError(f"Unsupported horizon {horizon!r}")
        if model_type not in (*SUPPORTED_MODEL_TYPES, "ensemble"):
            raise ValueError(f"Unknown model type {model_type!r}")
        if not _VERSION_RE.match(version):
            raise ValueError("version must look like 'v3'")
        return self.root / coin_id / horizon / model_type / version

    def relative(self, directory: Path) -> str:
        return directory.resolve().relative_to(self.root.resolve()).as_posix()

    # ---- queries ----
    def list_records(
        self,
        coin_id: Optional[str] = None,
        horizon: Optional[str] = None,
        model_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[ModelRecord]:
        if not self.root.is_dir():
            return []
        if coin_id is not None:
            validate_coin_key(coin_id)
        pattern = "/".join([coin_id or "*", horizon or "*", model_type or "*", "v*", "record.json"])
        records: list[ModelRecord] = []
        for path in sorted(self.root.glob(pattern)):
            try:
                rec = ModelRecord.from_dict(json.loads(path.read_text()))
            except (OSError, ValueError, TypeError):
                continue  # a corrupt record never breaks listing
            if status is None or rec.status == status:
                records.append(rec)
        records.sort(key=lambda r: (r.coin_id, r.timeframe, r.model_type, r.version_number))
        return records

    def next_version(self, coin_id: str, horizon: str, model_type: str) -> str:
        existing = self.list_records(coin_id, horizon, model_type)
        return f"v{max((r.version_number for r in existing), default=0) + 1}"

    def get_active(self, coin_id: str, horizon: str, model_type: str) -> Optional[ModelRecord]:
        active = self.list_records(coin_id, horizon, model_type, STATUS_ACTIVE)
        return max(active, key=lambda r: r.version_number) if active else None

    def active_for(self, coin_id: str, horizon: str) -> list[ModelRecord]:
        return self.list_records(coin_id, horizon, None, STATUS_ACTIVE)

    # ---- mutations ----
    def write_record(self, record: ModelRecord) -> None:
        directory = self.version_dir(record.coin_id, record.timeframe, record.model_type, record.version)
        directory.mkdir(parents=True, exist_ok=True)
        tmp = directory / "record.json.tmp"
        tmp.write_text(json.dumps(record.to_dict(), indent=2, default=str))
        tmp.replace(directory / "record.json")

    def activate(self, record: ModelRecord) -> ModelRecord:
        """Mark ``record`` active and supersede older active versions of the same kind."""
        for other in self.list_records(record.coin_id, record.timeframe, record.model_type, STATUS_ACTIVE):
            if other.version != record.version:
                other.status = STATUS_SUPERSEDED
                self.write_record(other)
        record.status = STATUS_ACTIVE
        self.write_record(record)
        return record

    def set_status(self, record: ModelRecord, status: str) -> ModelRecord:
        record.status = status
        self.write_record(record)
        return record

    def load(self, record: ModelRecord) -> BasePredictionModel:
        return load_model(self.root, record)

    def load_calibration(self, record: ModelRecord) -> dict[str, Any]:
        path = _safe_dir(self.root, record.artifact_path) / "calibration.json"
        if not path.is_file():
            raise FileNotFoundError(f"Missing calibration for {record.model_name}")
        return json.loads(path.read_text())

    @staticmethod
    def new_record(
        *, model_type: str, version: str, coin_id: str, horizon: str, feature_version: str,
        metrics: dict[str, Any], artifact_path: str, status: str, symbol: Optional[str] = None,
        info: Optional[dict[str, Any]] = None,
    ) -> ModelRecord:
        return ModelRecord(
            model_name=f"{coin_id}-{model_type}-{horizon}-{version}", model_type=model_type, version=version,
            coin_id=coin_id, timeframe=horizon, training_timestamp=datetime.now(timezone.utc).isoformat(),
            feature_version=feature_version, metrics=metrics, artifact_path=artifact_path, status=status,
            symbol=symbol, info=info or {},
        )
