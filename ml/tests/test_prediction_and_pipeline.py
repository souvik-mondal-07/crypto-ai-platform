import json
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from ml.config import FEATURE_VERSION
from ml.config.model_config import MLConfig
from ml.models import model_registry as mr
from ml.models.model_registry import ModelRegistry
from ml.models.ridge_model import RidgeBaselineModel
from ml.pipelines.prediction_pipeline import PredictionPipeline
from ml.pipelines.training_pipeline import train_coin_horizon
from ml.prediction.predictor import DISCLAIMER
from ml.tests.conftest import make_candles

REQUIRED_KEYS = {
    "status", "coin_id", "symbol", "horizon", "reason", "kind", "current_price", "reference_time", "target_time",
    "predicted_return", "predicted_return_range", "predicted_price_range", "range_nominal_coverage", "direction",
    "confidence", "confidence_status", "confidence_note", "model", "model_version", "feature_version",
    "model_metrics", "trained_at", "generated_at", "expires_at", "disclaimer",
}


def _now(df, minutes=90):  # 30 min after the last candle CLOSES (it opened 1h before that)
    return (df["timestamp"].iloc[-1] + pd.Timedelta(minutes=minutes)).to_pydatetime()


@pytest.fixture
def trained(tmp_path, predictable_candles):
    cfg = MLConfig(artifact_dir=tmp_path, default_model="ridge")
    reg = ModelRegistry(tmp_path)
    out = train_coin_horizon(predictable_candles, coin_id="coin1", horizon_name="1h", model_types=["ridge"],
                             config=cfg, registry=reg, symbol="AAA")
    assert out.status == "trained"
    return cfg, reg, predictable_candles


def test_random_walk_gets_no_active_model_and_honest_unavailable(tmp_path, candles):
    cfg = MLConfig(artifact_dir=tmp_path)
    reg = ModelRegistry(tmp_path)
    random_walk = make_candles(3500, seed=11)       # no exploitable structure
    out = train_coin_horizon(random_walk, coin_id="coin9", horizon_name="1h", model_types=["ridge"], config=cfg, registry=reg)
    assert out.models[0]["status"] == "rejected" and out.models[0]["gate_reasons"]
    res = PredictionPipeline(cfg).run("coin9", "1h", random_walk)  # real clock: data is stale, but no model exists either
    assert res.status == "model_unavailable" and res.predicted_return is None and res.confidence is None
    assert "trained explicitly" in res.reason


def test_training_reports_insufficient_data_instead_of_a_model(tmp_path):
    cfg = MLConfig(artifact_dir=tmp_path)
    out = train_coin_horizon(make_candles(150), coin_id="coin2", horizon_name="24h", model_types=["ridge"],
                             config=cfg, registry=ModelRegistry(tmp_path))
    assert out.status == "insufficient_data" and out.models == []
    assert ModelRegistry(tmp_path).list_records() == []


def test_training_without_installed_library_is_reported_not_faked(tmp_path, predictable_candles, monkeypatch):
    from ml.models import xgboost_model
    def boom():
        raise xgboost_model.ModelDependencyError("xgboost is not installed")
    monkeypatch.setattr(xgboost_model, "_xgb", boom)
    cfg = MLConfig(artifact_dir=tmp_path)
    out = train_coin_horizon(predictable_candles, coin_id="c3", horizon_name="1h", model_types=["xgboost"],
                             config=cfg, registry=ModelRegistry(tmp_path))
    assert out.models[0]["status"] == "unavailable"
    assert ModelRegistry(tmp_path).list_records() == []


def test_successful_prediction_has_the_standard_schema(trained):
    cfg, reg, df = trained
    res = PredictionPipeline(cfg).predictor.predict("coin1", "1h", df, symbol="AAA", now=_now(df))
    d = res.to_dict()
    assert set(d) == REQUIRED_KEYS
    assert d["status"] == "ok" and d["kind"] == "model_prediction" and d["disclaimer"] == DISCLAIMER
    assert d["model"] == "ridge" and d["model_version"] == "v1" and d["feature_version"] == FEATURE_VERSION
    rr, pr = d["predicted_return_range"], d["predicted_price_range"]
    assert rr["lower"] < rr["upper"] and pr["lower"] < pr["upper"]
    assert pr["lower"] == pytest.approx(d["current_price"] * (1 + rr["lower"]))
    assert d["direction"] in {"up", "down", "flat"}
    assert (d["confidence"] is None) == (d["confidence_status"] == "unavailable")
    if d["confidence"] is not None:
        assert 0.0 <= d["confidence"] <= 1.0
    assert d["target_time"] > d["reference_time"] and d["expires_at"] > d["generated_at"]
    json.dumps(d)  # fully serialisable


def test_prediction_is_deterministic_and_uses_only_closed_candles(trained):
    cfg, reg, df = trained
    now = _now(df)
    p = PredictionPipeline(cfg)
    a = p.predictor.predict("coin1", "1h", df, now=now).to_dict()
    b = p.predictor.predict("coin1", "1h", df, now=now).to_dict()
    for k in ("predicted_return", "confidence", "predicted_price_range", "direction"):
        assert a[k] == b[k]
    # An extra still-open candle (with absurd values) must not change the prediction.
    extra = df.iloc[[-1]].copy()
    extra["timestamp"] = df["timestamp"].iloc[-1] + pd.Timedelta(hours=1)
    extra[["open", "high", "low", "close"]] *= 40
    with_open = pd.concat([df, extra], ignore_index=True)
    c = p.predictor.predict("coin1", "1h", with_open, now=extra["timestamp"].iloc[0].to_pydatetime() + pd.Timedelta(minutes=10)).to_dict()
    assert c["predicted_return"] == a["predicted_return"]


def test_insufficient_history_stale_and_missing_data_states(trained):
    cfg, reg, df = trained
    p = PredictionPipeline(cfg)
    short = p.predictor.predict("coin1", "1h", df.iloc[-120:], now=_now(df))
    assert short.status == "insufficient_data" and short.predicted_return is None and short.confidence is None
    stale = p.predictor.predict("coin1", "1h", df, now=_now(df) + pd.Timedelta(days=5))
    assert stale.status == "insufficient_data" and "old" in stale.reason
    assert p.predictor.predict("coin1", "1h", None).status == "insufficient_data"
    assert p.predictor.predict("coin1", "1h", df.iloc[0:0]).status == "insufficient_data"


def test_unavailable_model_states(trained):
    cfg, reg, df = trained
    p = PredictionPipeline(cfg)
    assert p.predictor.predict("coin1", "24h", df).status == "model_unavailable"     # no model for that horizon
    assert p.predictor.predict("never-trained", "1h", df).status == "model_unavailable"
    assert p.predictor.predict("coin1", "1h", df, model_type="xgboost").status == "model_unavailable"
    # feature-set mismatch: an old model must never be fed differently-defined features
    rec = reg.get_active("coin1", "1h", "ridge")
    rec.feature_version = "v0"
    reg.write_record(rec)
    mismatch = p.predictor.predict("coin1", "1h", df, now=_now(df))
    assert mismatch.status == "model_unavailable" and "feature set" in mismatch.reason
    # a damaged artifact is reported, not crashed on
    rec.feature_version = FEATURE_VERSION
    reg.write_record(rec)
    (cfg.artifact_dir / rec.artifact_path / "ridge.json").unlink()
    assert p.predictor.predict("coin1", "1h", df, now=_now(df)).status == "model_unavailable"


def test_invalid_horizon_is_rejected(trained):
    cfg, reg, df = trained
    with pytest.raises(ValueError):
        PredictionPipeline(cfg).run("coin1", "2h", df)
    with pytest.raises(ValueError):
        MLConfig(default_horizon="13h")


def test_confidence_withheld_when_calibration_not_reliable(trained):
    cfg, reg, df = trained
    rec = reg.get_active("coin1", "1h", "ridge")
    cal_path = cfg.artifact_dir / rec.artifact_path / "calibration.json"
    cal = json.loads(cal_path.read_text())
    cal["confidence_reliable"] = False
    cal["flat_threshold"] = 0.0           # force a directional call
    cal_path.write_text(json.dumps(cal))
    d = PredictionPipeline(cfg).predictor.predict("coin1", "1h", df, now=_now(df)).to_dict()
    assert d["status"] == "ok" and d["confidence"] is None and d["confidence_status"] == "unavailable"
    assert d["confidence_note"]


def test_flat_prediction_makes_no_directional_claim(trained):
    cfg, reg, df = trained
    rec = reg.get_active("coin1", "1h", "ridge")
    cal_path = cfg.artifact_dir / rec.artifact_path / "calibration.json"
    cal = json.loads(cal_path.read_text())
    cal["flat_threshold"] = 10.0
    cal_path.write_text(json.dumps(cal))
    d = PredictionPipeline(cfg).predictor.predict("coin1", "1h", df, now=_now(df)).to_dict()
    assert d["direction"] == "flat" and d["confidence"] is None


def test_default_model_is_switchable_without_other_changes(tmp_path, predictable_candles, monkeypatch):
    class FakeXGB(RidgeBaselineModel):
        model_type = "xgboost"

    class FakeLGB(RidgeBaselineModel):
        model_type = "lightgbm"

    monkeypatch.setitem(mr.MODEL_CLASSES, "xgboost", FakeXGB)
    monkeypatch.setitem(mr.MODEL_CLASSES, "lightgbm", FakeLGB)
    reg = ModelRegistry(tmp_path)
    cfg = MLConfig(artifact_dir=tmp_path, default_model="xgboost")
    out = train_coin_horizon(predictable_candles, coin_id="c5", horizon_name="1h", model_types=["xgboost", "lightgbm"],
                             config=cfg, registry=reg, ensemble=True)
    assert {m["model_type"] for m in out.models if m.get("status") == "active"} == {"xgboost", "lightgbm", "ensemble"}
    now = _now(predictable_candles)
    pick = lambda default: PredictionPipeline(MLConfig(artifact_dir=tmp_path, default_model=default)).predictor.predict("c5", "1h", predictable_candles, now=now).model
    assert pick("xgboost") == "xgboost" and pick("lightgbm") == "lightgbm" and pick("ensemble") == "ensemble"
    ens_rec = reg.get_active("c5", "1h", "ensemble")
    spec = json.loads((tmp_path / ens_rec.artifact_path / "ensemble.json").read_text())
    assert len(spec["members"]) == 2 and sum(m["weight"] for m in spec["members"]) == pytest.approx(1.0)


def test_ensemble_skipped_when_fewer_than_two_validated_members(tmp_path, predictable_candles):
    out = train_coin_horizon(predictable_candles, coin_id="c6", horizon_name="1h", model_types=["ridge"],
                             config=MLConfig(artifact_dir=tmp_path), registry=ModelRegistry(tmp_path), ensemble=True)
    assert out.models[-1]["model_type"] == "ensemble" and out.models[-1]["status"] == "skipped"


def test_available_horizons_lists_only_horizons_with_validated_models(trained):
    cfg, reg, df = trained
    assert PredictionPipeline(cfg).available_horizons("coin1") == ["1h"]
    assert PredictionPipeline(cfg).available_horizons("other") == []


def test_config_from_mapping_and_env_style_paths(tmp_path):
    cfg = MLConfig.from_mapping({"ML_ARTIFACT_DIR": "ml/artifacts", "ML_DEFAULT_HORIZON": "7d", "ML_DEFAULT_MODEL": "lightgbm",
                                 "ML_MIN_HISTORY_LENGTH": "800", "ML_PREDICTION_TTL_SECONDS": "60"})
    assert cfg.default_horizon == "7d" and cfg.default_model == "lightgbm" and cfg.min_history_length == 800
    assert cfg.artifact_dir.is_absolute() and cfg.artifact_dir.parts[-2:] == ("ml", "artifacts")
    with pytest.raises(ValueError):
        MLConfig.from_mapping({"ML_DEFAULT_MODEL": "gpt"})
