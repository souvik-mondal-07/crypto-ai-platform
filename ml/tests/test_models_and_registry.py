import json

import numpy as np
import pandas as pd
import pytest

from ml.config import get_horizon
from ml.config.model_config import MLConfig
from ml.data.dataset_builder import build_dataset
from ml.models.base_model import BasePredictionModel, ModelNotFittedError
from ml.models.model_registry import (
    MODEL_CLASSES, STATUS_ACTIVE, STATUS_SUPERSEDED, ModelRegistry, create_model,
)
from ml.models.ridge_model import RidgeBaselineModel
from ml.prediction.ensemble import EnsembleModel, normalise_config_weights, weights_from_validation_mae


@pytest.fixture
def dataset(predictable_candles):
    now = (predictable_candles["timestamp"].iloc[-1] + pd.Timedelta(hours=2)).to_pydatetime()
    return build_dataset(predictable_candles, get_horizon("1h"), MLConfig(), now=now)


def _fit(model, ds):
    s = ds.split(MLConfig())
    model.fit(ds.X.iloc[s.train], ds.y.iloc[s.train], ds.X.iloc[s.validation], ds.y.iloc[s.validation])
    return s


def test_registry_knows_all_model_types():
    assert set(MODEL_CLASSES) == {"xgboost", "lightgbm", "lstm", "ridge"}
    with pytest.raises(ValueError):
        create_model("random_forest_of_doom")
    for cls in MODEL_CLASSES.values():
        assert issubclass(cls, BasePredictionModel)


# ---------------------------------------------------------------- ridge (always runnable)


def test_ridge_trains_predicts_and_evaluates(dataset):
    model = create_model("ridge", {"alpha": 5.0})
    s = _fit(model, dataset)
    preds = model.predict(dataset.X.iloc[s.test])
    assert preds.shape == (s.sizes()["test"],) and np.isfinite(preds).all()
    metrics = model.evaluate(dataset.X.iloc[s.test], dataset.y.iloc[s.test])
    assert metrics["mae"] is not None and metrics["directional_accuracy"] is not None
    imp = model.feature_importance()
    assert sum(imp.values()) == pytest.approx(1.0)


def test_persistence_roundtrip_gives_identical_predictions(dataset, tmp_path):
    model = RidgeBaselineModel({"alpha": 5.0})
    s = _fit(model, dataset)
    model.save(tmp_path / "m")
    loaded = RidgeBaselineModel.load(tmp_path / "m")
    X = dataset.X.iloc[s.test]
    np.testing.assert_allclose(model.predict(X), loaded.predict(X))
    assert loaded.feature_names == model.feature_names
    meta = json.loads((tmp_path / "m" / "model_meta.json").read_text())
    assert meta["model_type"] == "ridge"


def test_loading_wrong_type_or_missing_artifact_fails_clearly(dataset, tmp_path):
    model = RidgeBaselineModel()
    _fit(model, dataset)
    model.save(tmp_path / "m")
    with pytest.raises(ValueError):
        MODEL_CLASSES["xgboost"].load(tmp_path / "m")
    with pytest.raises(FileNotFoundError):
        RidgeBaselineModel.load(tmp_path / "nothing-here")


def test_invalid_inputs_are_rejected(dataset):
    model = RidgeBaselineModel()
    with pytest.raises(ModelNotFittedError):
        model.predict(dataset.X.iloc[:5])
    with pytest.raises(ModelNotFittedError):
        model.save("/tmp/never-written")
    with pytest.raises(ValueError):
        model.fit(dataset.X.iloc[:100], dataset.y.iloc[:50])      # length mismatch
    with pytest.raises(ValueError):
        model.fit(dataset.X.iloc[:5], dataset.y.iloc[:5])          # too few rows
    _fit(model, dataset)
    with pytest.raises(ValueError):
        model.predict(dataset.X.iloc[:5].drop(columns=[dataset.feature_names[0]]))
    with pytest.raises(ValueError):
        model.predict(dataset.X.iloc[0:0])


def test_predict_handles_nan_features_via_train_median(dataset):
    model = RidgeBaselineModel()
    s = _fit(model, dataset)
    X = dataset.X.iloc[s.test].copy()
    X.iloc[0, 0] = np.nan
    assert np.isfinite(model.predict(X)).all()


# ---------------------------------------------------------------- optional heavy libraries


def _train_small(model_type, dataset, params):
    model = create_model(model_type, params)
    s = dataset.split(MLConfig())
    model.fit(dataset.X.iloc[s.train], dataset.y.iloc[s.train], dataset.X.iloc[s.validation], dataset.y.iloc[s.validation])
    return model, s


@pytest.mark.parametrize("model_type,module,params", [
    ("xgboost", "xgboost", {"n_estimators": 30, "max_depth": 2, "learning_rate": 0.1, "early_stopping_rounds": 5, "n_jobs": 1}),
    ("lightgbm", "lightgbm", {"n_estimators": 30, "num_leaves": 7, "learning_rate": 0.1, "early_stopping_rounds": 5, "n_jobs": 1, "verbose": -1}),
])
def test_tree_models_train_persist_and_report_importance(model_type, module, params, dataset, tmp_path):
    pytest.importorskip(module)
    model, s = _train_small(model_type, dataset, params)
    X = dataset.X.iloc[s.test]
    preds = model.predict(X)
    assert preds.shape == (len(X),) and np.isfinite(preds).all()
    imp = model.feature_importance()
    assert set(imp) == set(dataset.feature_names) and sum(imp.values()) == pytest.approx(1.0)
    model.save(tmp_path / "t")
    loaded = MODEL_CLASSES[model_type].load(tmp_path / "t")
    np.testing.assert_allclose(model.predict(X), loaded.predict(X), rtol=1e-5, atol=1e-8)
    with pytest.raises(ValueError):
        model.predict(X.drop(columns=[dataset.feature_names[0]]))


@pytest.mark.parametrize("cell", ["lstm", "gru"])
def test_sequence_model_trains_and_marks_warmup_rows_nan(cell, dataset, tmp_path):
    pytest.importorskip("torch")
    params = {"sequence_length": 6, "hidden_size": 8, "num_layers": 1, "dropout": 0.0, "batch_size": 64,
              "epochs": 2, "learning_rate": 0.01, "patience": 2, "cell": cell, "random_state": 1}
    model, s = _train_small("lstm", dataset, params)
    X = dataset.X.iloc[s.test]
    preds = model.predict(X)
    assert np.isnan(preds[:5]).all() and np.isfinite(preds[5:]).all()
    assert model.required_context == 5
    model.save(tmp_path / "l")
    loaded = MODEL_CLASSES["lstm"].load(tmp_path / "l")
    np.testing.assert_allclose(preds[5:], loaded.predict(X)[5:], rtol=1e-4, atol=1e-6)


# ---------------------------------------------------------------- registry


def _record(reg, coin="coin1", horizon="24h", mtype="ridge", status="rejected", version=None):
    version = version or reg.next_version(coin, horizon, mtype)
    d = reg.version_dir(coin, horizon, mtype, version)
    d.mkdir(parents=True, exist_ok=True)
    rec = ModelRegistry.new_record(model_type=mtype, version=version, coin_id=coin, horizon=horizon,
                                   feature_version="v1", metrics={"test": {"mae_improvement": 0.1}},
                                   artifact_path=reg.relative(d), status=status)
    reg.write_record(rec)
    return rec


def test_registry_versions_listing_and_single_active(tmp_path):
    reg = ModelRegistry(tmp_path)
    assert reg.list_records() == [] and reg.next_version("coin1", "24h", "ridge") == "v1"
    r1 = reg.activate(_record(reg))
    r2 = _record(reg)
    assert (r1.version, r2.version) == ("v1", "v2")
    reg.activate(r2)
    statuses = {r.version: r.status for r in reg.list_records("coin1", "24h", "ridge")}
    assert statuses == {"v1": STATUS_SUPERSEDED, "v2": STATUS_ACTIVE}
    assert reg.get_active("coin1", "24h", "ridge").version == "v2"
    assert reg.get_active("coin1", "7d", "ridge") is None
    _record(reg, mtype="lightgbm", status=STATUS_ACTIVE)
    assert {r.model_type for r in reg.active_for("coin1", "24h")} == {"ridge", "lightgbm"}
    rec = reg.get_active("coin1", "24h", "ridge")
    for field in ("model_name", "model_type", "version", "coin_id", "timeframe", "training_timestamp",
                  "feature_version", "metrics", "artifact_path", "status"):
        assert getattr(rec, field) not in (None, "")
    assert rec.model_name == "coin1-ridge-24h-v2"
    assert not rec.artifact_path.startswith("/")   # portable, relative


def test_registry_rejects_path_traversal_and_bad_names(tmp_path):
    reg = ModelRegistry(tmp_path)
    for bad in ("../etc", "a/b", "", "x" * 80, "a b"):
        with pytest.raises(ValueError):
            reg.list_records(bad)
        with pytest.raises(ValueError):
            reg.version_dir(bad, "24h", "ridge", "v1")
    with pytest.raises(ValueError):
        reg.version_dir("coin1", "13h", "ridge", "v1")
    with pytest.raises(ValueError):
        reg.version_dir("coin1", "24h", "ridge", "../v1")
    rec = _record(reg)
    rec.artifact_path = "../../outside"
    with pytest.raises(ValueError):
        reg.load(rec)


def test_corrupt_record_does_not_break_listing(tmp_path):
    reg = ModelRegistry(tmp_path)
    _record(reg)
    bad = tmp_path / "coin1" / "24h" / "ridge" / "v9"
    bad.mkdir(parents=True)
    (bad / "record.json").write_text("{not json")
    assert [r.version for r in reg.list_records("coin1")] == ["v1"]


# ---------------------------------------------------------------- ensemble


def test_ensemble_weights_follow_validated_performance_and_config():
    w = weights_from_validation_mae({"xgboost": 0.01, "lightgbm": 0.02, "lstm": None, "ridge": float("nan")})
    assert set(w) == {"xgboost", "lightgbm"} and sum(w.values()) == pytest.approx(1.0)
    assert w["xgboost"] == pytest.approx(2 / 3)
    assert weights_from_validation_mae({"a": None}) == {}
    cw = normalise_config_weights({"xgboost": 3, "lightgbm": 1, "lstm": 5}, ["xgboost", "lightgbm"])
    assert cw == {"xgboost": 0.75, "lightgbm": 0.25}      # nonexistent model gets no weight


def test_ensemble_combines_members_and_survives_roundtrip(dataset, tmp_path):
    class A(RidgeBaselineModel):
        model_type = "xgboost"

    class B(RidgeBaselineModel):
        model_type = "lightgbm"

    s = dataset.split(MLConfig())
    a, b = A({"alpha": 1.0}), B({"alpha": 500.0})
    for m in (a, b):
        m.fit(dataset.X.iloc[s.train], dataset.y.iloc[s.train])
    root = tmp_path / "coin" / "1h"
    a.save(root / "xgboost" / "v1")
    b.save(root / "lightgbm" / "v1")
    with pytest.raises(ValueError):
        EnsembleModel.from_members([("xgboost", "v1", 1.0, a, "../../xgboost/v1")])   # needs 2+
    ens = EnsembleModel.from_members([("xgboost", "v1", 0.7, a, "../../xgboost/v1"),
                                      ("lightgbm", "v1", 0.3, b, "../../lightgbm/v1")])
    X = dataset.X.iloc[s.test]
    np.testing.assert_allclose(ens.predict(X), 0.7 * a.predict(X) + 0.3 * b.predict(X))
    ens.save(root / "ensemble" / "v1")
    import ml.models.model_registry as mr
    old = dict(mr.MODEL_CLASSES)
    mr.MODEL_CLASSES["xgboost"], mr.MODEL_CLASSES["lightgbm"] = A, B
    try:
        loaded = EnsembleModel.load(root / "ensemble" / "v1")
    finally:
        mr.MODEL_CLASSES.clear(); mr.MODEL_CLASSES.update(old)
    np.testing.assert_allclose(loaded.predict(X), ens.predict(X))
    spec = json.loads((root / "ensemble" / "v1" / "ensemble.json").read_text())
    assert sum(m["weight"] for m in spec["members"]) == pytest.approx(1.0)
