"""Gemini configuration (Phase 15) — one frozen object built from the central Settings.

Nothing in the AI layer reads environment variables or hard-codes the model id; everything takes a
`GeminiConfig`. The API key never leaves the backend and is never included in `repr`/logs.
"""

from dataclasses import dataclass, field

from app.config import Settings, get_settings

#: The ONLY model this project uses for AI analysis (also the Settings default).
GEMINI_MODEL_ID = "gemini-3.1-flash-lite"

#: Values that mean "no real key was configured" (e.g. the .env.example placeholder).
_PLACEHOLDER_KEYS = frozenset({"", "your_gemini_api_key", "your-gemini-api-key", "changeme", "change-me"})


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str = field(default="", repr=False)  # repr=False: never print the secret
    model: str = GEMINI_MODEL_ID
    timeout_seconds: float = 30.0
    max_output_tokens: int = 4096
    temperature: float = 0.2
    max_retries: int = 2
    retry_backoff_seconds: float = 1.5

    @property
    def is_configured(self) -> bool:
        return self.api_key.strip().lower() not in _PLACEHOLDER_KEYS


def gemini_config_from_settings(settings: Settings) -> GeminiConfig:
    return GeminiConfig(
        api_key=(settings.GEMINI_API_KEY or "").strip(),
        model=(settings.GEMINI_MODEL or GEMINI_MODEL_ID).strip(),
        timeout_seconds=max(1.0, settings.GEMINI_TIMEOUT_SECONDS),
        max_output_tokens=max(256, settings.GEMINI_MAX_OUTPUT_TOKENS),
        temperature=min(max(settings.GEMINI_TEMPERATURE, 0.0), 1.0),
        max_retries=min(max(settings.GEMINI_MAX_RETRIES, 0), 5),
        retry_backoff_seconds=max(0.0, settings.GEMINI_RETRY_BACKOFF_SECONDS),
    )


def get_gemini_config() -> GeminiConfig:
    return gemini_config_from_settings(get_settings())


__all__ = ["GEMINI_MODEL_ID", "GeminiConfig", "gemini_config_from_settings", "get_gemini_config"]
