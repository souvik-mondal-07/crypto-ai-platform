"""Static checks for Phase 13 wiring: settings defaults, env examples, index definitions."""

from pathlib import Path

from app.config.settings import Settings

REPO = Path(__file__).resolve().parents[2]


def test_ml_settings_defaults_have_no_machine_specific_paths():
    s = Settings()
    assert s.ML_DEFAULT_HORIZON == "24h" and s.ML_DEFAULT_MODEL == "xgboost"
    assert s.ML_MIN_HISTORY_LENGTH > 0 and s.ML_PREDICTION_TTL_SECONDS > 0
    assert not Path(s.ML_ARTIFACT_DIR).is_absolute()


def test_env_examples_document_every_ml_variable():
    for path in (REPO / ".env.example", REPO / "backend" / ".env.example"):
        text = path.read_text()
        for key in ("ML_ARTIFACT_DIR", "ML_DEFAULT_HORIZON", "ML_DEFAULT_MODEL", "ML_MIN_HISTORY_LENGTH"):
            assert f"{key}=" in text, (path, key)


def test_predictions_use_the_existing_collection_and_indexes_are_declared():
    from app.database.collections import CollectionName

    assert CollectionName.PREDICTIONS.value == "predictions"
    src = (REPO / "backend" / "app" / "database" / "indexes.py").read_text()
    assert "idx_predictions_coin_horizon_generatedat" in src
    assert "idx_predictions_coin_horizon_createdat" in src            # Phase 2 index kept
    assert "expireAfterSeconds" not in src                             # predictions are kept for history
    assert "PREDICTION_HISTORY" not in "".join(c.name for c in CollectionName)   # no duplicate collection
