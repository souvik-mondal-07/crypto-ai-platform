"""Static guards for the Phase 13 hard rules: no random/hard-coded predictions, no
decision engine, no Gemini, and no committed model binaries."""

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Code that produces or serves predictions. (Model *training* legitimately seeds RNGs.)
PREDICTION_PATH_FILES = [
    *sorted((REPO / "ml" / "prediction").glob("*.py")),
    REPO / "ml" / "pipelines" / "prediction_pipeline.py",
    REPO / "backend" / "app" / "services" / "prediction_service.py",
    REPO / "backend" / "app" / "api" / "v1" / "predictions.py",
    REPO / "backend" / "app" / "schemas" / "predictions.py",
    REPO / "backend" / "app" / "repositories" / "prediction_repository.py",
]


def _existing(files):
    return [f for f in files if f.is_file()]


def test_prediction_path_has_no_randomness():
    pattern = re.compile(r"\b(import random|from random|np\.random|numpy\.random|random\.(random|uniform|choice|randint|gauss)|secrets\.)")
    offenders = [str(f.relative_to(REPO)) for f in _existing(PREDICTION_PATH_FILES) if pattern.search(f.read_text(encoding="utf-8"))]
    assert not offenders, offenders


def test_ml_and_prediction_code_has_no_decision_engine_or_llm():
    files = _existing(PREDICTION_PATH_FILES) + [f for f in (REPO / "ml").rglob("*.py") if "tests" not in f.parts]
    banned = re.compile(r"(gemini|ollama|google\.generativeai|\"(BUY|SELL|HOLD)\"|'(BUY|SELL|HOLD)')", re.I)
    offenders = [str(f.relative_to(REPO)) for f in files if banned.search(f.read_text(encoding="utf-8"))]
    assert not offenders, offenders


def test_no_hardcoded_symbol_predictions():
    pattern = re.compile(r"(predicted_return\s*=\s*-?\d|confidence\s*=\s*0?\.\d|\"BTC\"|\"ETH\"|'BTC'|'ETH')")
    offenders = [str(f.relative_to(REPO)) for f in _existing(PREDICTION_PATH_FILES) if pattern.search(f.read_text(encoding="utf-8"))]
    assert not offenders, offenders


def test_model_binaries_are_git_ignored():
    gitignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "ml/artifacts/*" in gitignore and "!ml/artifacts/README.md" in gitignore
    result = subprocess.run(["git", "check-ignore", "-q", "ml/artifacts/coin/24h/xgboost/v1/model.json"],
                            cwd=REPO, capture_output=True)
    if result.returncode in (0, 1):                       # 128 == not a git checkout -> skip silently
        assert result.returncode == 0
