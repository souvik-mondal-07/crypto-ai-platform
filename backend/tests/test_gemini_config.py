"""Gemini configuration, environment files and secret hygiene (Phase 15)."""

from pathlib import Path

from app.config.gemini_config import GEMINI_MODEL_ID, GeminiConfig, gemini_config_from_settings
from app.config.settings import Settings

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "backend" / "app"


def test_model_is_exactly_gemini_3_1_flash_lite_by_default():
    assert GEMINI_MODEL_ID == "gemini-3.1-flash-lite"
    assert Settings().GEMINI_MODEL == "gemini-3.1-flash-lite"
    assert gemini_config_from_settings(Settings()).model == "gemini-3.1-flash-lite"


def test_missing_api_key_means_not_configured():
    assert not GeminiConfig().is_configured
    assert not GeminiConfig(api_key="   ").is_configured
    assert not gemini_config_from_settings(Settings(GEMINI_API_KEY="")).is_configured


def test_placeholder_key_from_env_example_is_not_a_real_key():
    assert not GeminiConfig(api_key="your_gemini_api_key").is_configured
    assert GeminiConfig(api_key="a-real-looking-key").is_configured


def test_environment_loading(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("GEMINI_MAX_RETRIES", "1")
    cfg = gemini_config_from_settings(Settings())
    assert cfg.api_key == "test-key" and cfg.is_configured
    assert cfg.timeout_seconds == 12 and cfg.max_retries == 1


def test_values_are_clamped_to_safe_ranges():
    cfg = gemini_config_from_settings(Settings(GEMINI_TEMPERATURE=5, GEMINI_MAX_RETRIES=99, GEMINI_TIMEOUT_SECONDS=0))
    assert cfg.temperature == 1.0 and cfg.max_retries == 5 and cfg.timeout_seconds >= 1.0


def test_api_key_is_never_in_repr():
    assert "secret-value" not in repr(GeminiConfig(api_key="secret-value"))


def test_env_examples_document_gemini_settings():
    for path in (REPO / ".env.example", REPO / "backend" / ".env.example"):
        text = path.read_text(encoding="utf-8")
        assert "GEMINI_API_KEY=" in text and "GEMINI_MODEL=gemini-3.1-flash-lite" in text
        assert "sk-" not in text and "AIza" not in text  # no real-looking key committed


def test_env_files_are_git_ignored():
    assert ".env" in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in (REPO / "backend" / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_model_id_is_not_hard_coded_outside_config():
    offenders = [
        str(p.relative_to(APP)) for p in APP.rglob("*.py")
        if "gemini-3.1-flash-lite" in p.read_text(encoding="utf-8") and p.name not in {"gemini_config.py", "settings.py"}
    ]
    assert offenders == []


def test_no_other_ai_providers_or_old_gemini_models():
    forbidden = ("ollama", "openai", "anthropic", "gemini-2", "gemini-1", "google.generativeai")
    for p in APP.rglob("*.py"):
        text = p.read_text(encoding="utf-8").lower()
        for word in forbidden:
            assert word not in text, (p.name, word)


def test_frontend_never_holds_a_gemini_key():
    src = REPO / "frontend"
    for p in list(src.glob(".env*")) + list((src / "src").rglob("*.ts*")):
        text = p.read_text(encoding="utf-8")
        assert "VITE_GEMINI" not in text, p.name
        assert "generativelanguage.googleapis.com" not in text, p.name
