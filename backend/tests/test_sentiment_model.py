"""Sentiment model service: probabilities -> label/score, lazy load-once, failure handling, replaceability."""

import sys

import pytest

from app.config import get_settings
from app.services.sentiment_model import (
    FinBertClassifier,
    SentimentClassifier,
    SentimentModelError,
    SentimentModelService,
    SentimentModelUnavailableError,
    SentimentPrediction,
    prediction_from_probabilities,
)


def test_positive_classification():
    p = prediction_from_probabilities({"positive": 0.8, "neutral": 0.15, "negative": 0.05})
    assert p.label == "positive" and p.score == pytest.approx(0.75) and p.confidence == pytest.approx(0.8)


def test_negative_classification():
    p = prediction_from_probabilities({"positive": 0.05, "neutral": 0.15, "negative": 0.8})
    assert p.label == "negative" and p.score == pytest.approx(-0.75)


def test_neutral_classification():
    p = prediction_from_probabilities({"positive": 0.1, "neutral": 0.8, "negative": 0.1})
    assert p.label == "neutral" and p.score == pytest.approx(0.0) and p.confidence == pytest.approx(0.8)


def test_score_is_bounded_and_probabilities_preserved():
    p = prediction_from_probabilities({"positive": 1.0, "neutral": 0.0, "negative": 0.0})
    assert p.score == 1.0 and set(p.probabilities) == {"positive", "neutral", "negative"}


def test_unexpected_label_set_is_rejected():
    with pytest.raises(SentimentModelError):
        prediction_from_probabilities({"bullish": 0.5, "bearish": 0.5})


class CountingClassifier(SentimentClassifier):
    name = "fake-model"
    loads = 0

    def load(self):
        CountingClassifier.loads += 1

    def classify(self, texts):
        return [prediction_from_probabilities({"positive": 0.2, "neutral": 0.7, "negative": 0.1}) for _ in texts]


async def test_model_is_loaded_once_across_many_requests():
    CountingClassifier.loads = 0
    service = SentimentModelService(factory=CountingClassifier)
    assert service.status == "not_loaded"
    for _ in range(3):
        out = await service.classify(["a", "b"])
        assert len(out) == 2
    assert CountingClassifier.loads == 1 and service.status == "ready" and service.model_name == "fake-model"


async def test_empty_input_does_not_load_the_model():
    CountingClassifier.loads = 0
    service = SentimentModelService(factory=CountingClassifier)
    assert await service.classify([]) == [] and CountingClassifier.loads == 0


class FailingClassifier(SentimentClassifier):
    name = "broken"
    loads = 0

    def load(self):
        FailingClassifier.loads += 1
        raise SentimentModelUnavailableError("weights missing")

    def classify(self, texts):  # pragma: no cover
        raise AssertionError


async def test_failed_load_is_unavailable_and_not_retried_during_cooldown(monkeypatch):
    FailingClassifier.loads = 0
    monkeypatch.setattr(get_settings(), "SENTIMENT_MODEL_RETRY_SECONDS", 600)
    service = SentimentModelService(factory=FailingClassifier)
    for _ in range(3):
        with pytest.raises(SentimentModelUnavailableError):
            await service.classify(["x"])
    assert FailingClassifier.loads == 1 and service.status == "unavailable"


async def test_load_is_retried_after_the_cooldown(monkeypatch):
    FailingClassifier.loads = 0
    monkeypatch.setattr(get_settings(), "SENTIMENT_MODEL_RETRY_SECONDS", 0)
    service = SentimentModelService(factory=FailingClassifier)
    for _ in range(2):
        with pytest.raises(SentimentModelUnavailableError):
            await service.classify(["x"])
    assert FailingClassifier.loads == 2


async def test_unexpected_factory_error_becomes_unavailable():
    def boom():
        raise RuntimeError("secret internal detail")

    service = SentimentModelService(factory=boom)
    with pytest.raises(SentimentModelUnavailableError) as exc:
        await service.classify(["x"])
    assert "secret" not in str(exc.value)


async def test_disabled_setting(monkeypatch):
    monkeypatch.setattr(get_settings(), "SENTIMENT_ENABLED", False)
    service = SentimentModelService(factory=CountingClassifier)
    assert service.status == "disabled"
    with pytest.raises(SentimentModelUnavailableError):
        await service.classify(["x"])


async def test_unknown_backend_is_unavailable(monkeypatch):
    monkeypatch.setattr(get_settings(), "SENTIMENT_MODEL_BACKEND", "does-not-exist")
    with pytest.raises(SentimentModelUnavailableError):
        await SentimentModelService().classify(["x"])


def test_finbert_without_ml_packages_reports_unavailable_instead_of_crashing(monkeypatch):
    monkeypatch.setitem(sys.modules, "transformers", None)  # makes `import transformers` raise ImportError
    monkeypatch.setitem(sys.modules, "torch", None)
    clf = FinBertClassifier("ProsusAI/finbert")
    with pytest.raises(SentimentModelUnavailableError):
        clf.load()
    with pytest.raises(SentimentModelUnavailableError):
        clf.classify(["x"])  # never silently returns something


@pytest.mark.integration
def test_real_finbert_classifies_clear_headlines():
    """Needs transformers + torch and the model files (downloaded on first run). Run with: pytest -m integration"""
    pytest.importorskip("transformers")
    pytest.importorskip("torch")
    clf = FinBertClassifier("ProsusAI/finbert", local_files_only=False)
    clf.load()
    positive, negative = clf.classify(
        [
            "Bitcoin surges to a record high as institutional demand soars and adoption accelerates.",
            "Exchange collapses after hack: hundreds of millions stolen and customers lose their funds.",
        ]
    )
    assert isinstance(positive, SentimentPrediction)
    assert positive.label == "positive" and negative.label == "negative"
