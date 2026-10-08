"""
Sentiment model service (Phase 12).

Model loading lives here, completely separate from the API routes:

  * `SentimentClassifier` — the replaceable interface. A new model
    (another finance/crypto model, a fine-tuned checkpoint) implements it
    and is registered in `_BACKENDS`; nothing else changes.
  * `FinBertClassifier` — ProsusAI/finbert via Hugging Face
    `transformers`. Imported lazily, loaded ONCE per process (the weights
    are cached by Hugging Face on disk, so they are not re-downloaded),
    and run in a worker thread so inference never blocks the event loop.
  * `SentimentModelService` — owns the (single) loaded classifier, the
    load lock, and a retry cool-down after a failed load.

If the model cannot be loaded (package missing, no network for the first
download, out of memory, ...) the service raises
`SentimentModelUnavailableError`. Callers then leave articles
unanalyzed — there is NO fallback that fabricates sentiment.

Output convention: `score = P(positive) - P(negative)` in [-1, 1];
`label` is the most probable class; `confidence` is its probability.
"""

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional

from app.config import get_settings

logger = logging.getLogger("crypto_ai_platform.services.sentiment_model")

LABELS = ("positive", "neutral", "negative")


class SentimentModelError(Exception):
    """Inference failed for a batch (the model itself is loaded)."""


class SentimentModelUnavailableError(SentimentModelError):
    """The model could not be loaded / is disabled."""


@dataclass(frozen=True)
class SentimentPrediction:
    label: str
    score: float
    confidence: float
    probabilities: dict[str, float]


def prediction_from_probabilities(probabilities: dict[str, float]) -> SentimentPrediction:
    """Class probabilities -> prediction. Pure; shared by every backend."""
    if set(probabilities) != set(LABELS):
        raise SentimentModelError("Model did not return positive/neutral/negative probabilities.")
    label = max(LABELS, key=lambda name: probabilities[name])
    return SentimentPrediction(
        label=label,
        score=round(probabilities["positive"] - probabilities["negative"], 6),
        confidence=round(probabilities[label], 6),
        probabilities={name: round(probabilities[name], 6) for name in LABELS},
    )


class SentimentClassifier(ABC):
    #: Stored with every result so scores from different models are never mixed up unknowingly.
    name: str

    @abstractmethod
    def load(self) -> None:
        """Load weights. Raises SentimentModelUnavailableError on failure."""

    @abstractmethod
    def classify(self, texts: list[str]) -> list[SentimentPrediction]:
        """Classify texts (synchronous, CPU-bound — called from a worker thread)."""


class FinBertClassifier(SentimentClassifier):
    def __init__(self, model_name: str, cache_dir: str = "", local_files_only: bool = False,
                 max_tokens: int = 256) -> None:
        self.name = model_name
        self._cache_dir = cache_dir or None
        self._local_only = local_files_only
        self._max_tokens = max_tokens
        self._tokenizer = None
        self._model = None
        self._torch = None
        self._id2label: dict[int, str] = {}

    def load(self) -> None:
        try:
            import torch  # noqa: WPS433 — heavy, imported only when the model is actually needed
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise SentimentModelUnavailableError(
                "The 'transformers' and 'torch' packages are not installed."
            ) from exc
        try:
            kwargs = {"cache_dir": self._cache_dir, "local_files_only": self._local_only}
            tokenizer = AutoTokenizer.from_pretrained(self.name, **kwargs)
            model = AutoModelForSequenceClassification.from_pretrained(self.name, **kwargs)
            model.eval()
        except Exception as exc:  # noqa: BLE001 — download/IO/format failures all mean "unavailable"
            raise SentimentModelUnavailableError(
                f"Could not load sentiment model '{self.name}': {exc.__class__.__name__}"
            ) from exc

        id2label = {int(i): str(label).lower() for i, label in model.config.id2label.items()}
        if set(id2label.values()) != set(LABELS):
            raise SentimentModelUnavailableError(
                f"Model '{self.name}' does not expose positive/neutral/negative labels."
            )
        self._torch, self._tokenizer, self._model, self._id2label = torch, tokenizer, model, id2label

    def classify(self, texts: list[str]) -> list[SentimentPrediction]:
        if self._model is None or self._tokenizer is None or self._torch is None:
            raise SentimentModelUnavailableError("Sentiment model is not loaded.")
        try:
            encoded = self._tokenizer(
                texts, padding=True, truncation=True, max_length=self._max_tokens, return_tensors="pt"
            )
            with self._torch.no_grad():
                logits = self._model(**encoded).logits
            probs = self._torch.softmax(logits, dim=-1).tolist()
        except Exception as exc:  # noqa: BLE001
            raise SentimentModelError(f"Sentiment inference failed: {exc.__class__.__name__}") from exc
        return [
            prediction_from_probabilities({self._id2label[i]: p for i, p in enumerate(row)})
            for row in probs
        ]


def _build_finbert() -> SentimentClassifier:
    s = get_settings()
    return FinBertClassifier(
        s.SENTIMENT_MODEL_NAME, s.SENTIMENT_MODEL_CACHE_DIR, s.SENTIMENT_LOCAL_FILES_ONLY, s.SENTIMENT_MAX_TOKENS
    )


#: backend name (SENTIMENT_MODEL_BACKEND) -> factory. Register new models here.
_BACKENDS: dict[str, Callable[[], SentimentClassifier]] = {"finbert": _build_finbert}


class SentimentModelService:
    """Lazy, load-once, thread-safe access to the configured classifier."""

    def __init__(self, factory: Optional[Callable[[], SentimentClassifier]] = None) -> None:
        self._factory = factory
        self._classifier: Optional[SentimentClassifier] = None
        self._load_lock = threading.Lock()
        self._failed_at: Optional[float] = None
        self._last_error: Optional[str] = None

    @property
    def enabled(self) -> bool:
        return get_settings().SENTIMENT_ENABLED

    @property
    def model_name(self) -> Optional[str]:
        return self._classifier.name if self._classifier else None

    @property
    def status(self) -> str:
        """disabled | not_loaded | ready | unavailable"""
        if not self.enabled:
            return "disabled"
        if self._classifier is not None:
            return "ready"
        if self._failed_at is not None:
            return "unavailable"
        return "not_loaded"

    def _ensure_loaded(self) -> SentimentClassifier:
        if self._classifier is not None:
            return self._classifier
        with self._load_lock:
            if self._classifier is not None:  # another thread finished while we waited
                return self._classifier
            retry_after = get_settings().SENTIMENT_MODEL_RETRY_SECONDS
            if self._failed_at is not None and time.monotonic() - self._failed_at < retry_after:
                raise SentimentModelUnavailableError(self._last_error or "Sentiment model is unavailable.")
            try:
                factory = self._factory
                if factory is None:
                    backend = get_settings().SENTIMENT_MODEL_BACKEND.lower()
                    factory = _BACKENDS.get(backend)
                    if factory is None:
                        raise SentimentModelUnavailableError(f"Unknown sentiment backend '{backend}'.")
                classifier = factory()
                classifier.load()
            except SentimentModelUnavailableError as exc:
                self._failed_at, self._last_error = time.monotonic(), str(exc)
                logger.error("Sentiment model unavailable: %s", exc)
                raise
            except Exception as exc:  # noqa: BLE001
                self._failed_at, self._last_error = time.monotonic(), exc.__class__.__name__
                logger.error("Sentiment model failed to initialize: %s", exc.__class__.__name__)
                raise SentimentModelUnavailableError("Sentiment model failed to initialize.") from exc
            self._classifier, self._failed_at, self._last_error = classifier, None, None
            logger.info("Sentiment model '%s' loaded.", classifier.name)
            return classifier

    def _classify_sync(self, texts: list[str]) -> list[SentimentPrediction]:
        return self._ensure_loaded().classify(texts)

    async def classify(self, texts: list[str]) -> list[SentimentPrediction]:
        if not self.enabled:
            raise SentimentModelUnavailableError("Sentiment analysis is disabled.")
        if not texts:
            return []
        return await asyncio.to_thread(self._classify_sync, texts)


_service: Optional[SentimentModelService] = None


def get_sentiment_model_service() -> SentimentModelService:
    """Process-wide singleton — the model is loaded once, not per request."""
    global _service
    if _service is None:
        _service = SentimentModelService()
    return _service
