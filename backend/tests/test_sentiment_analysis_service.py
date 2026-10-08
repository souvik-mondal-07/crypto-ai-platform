"""Pending-article analysis job: persists real model output, leaves articles pending on failure."""

from app.services.sentiment_analysis_service import SentimentAnalysisService, build_model_input
from app.services.sentiment_model import (
    SentimentModelError,
    SentimentModelUnavailableError,
    prediction_from_probabilities,
)

POS = prediction_from_probabilities({"positive": 0.9, "neutral": 0.05, "negative": 0.05})
NEG = prediction_from_probabilities({"positive": 0.05, "neutral": 0.05, "negative": 0.9})
NEU = prediction_from_probabilities({"positive": 0.1, "neutral": 0.8, "negative": 0.1})


class FakeRepo:
    def __init__(self, docs):
        self.docs, self.saved = docs, {}

    async def find_pending_sentiment(self, limit):
        return [d for d in self.docs if d["news_id"] not in self.saved][:limit]

    async def save_sentiments(self, updates):
        self.saved.update(dict(updates))
        return len(updates)


class FakeModel:
    def __init__(self, predictions=None, error=None, fail_batches=()):
        self.predictions, self.error, self.fail_batches = predictions or [], error, set(fail_batches)
        self.batches, self.model_name, self.status = [], "fake-finbert", "ready"

    async def classify(self, texts):
        self.batches.append(texts)
        if self.error:
            raise self.error
        if len(self.batches) - 1 in self.fail_batches:
            raise SentimentModelError("bad batch")
        return self.predictions[: len(texts)]


def docs(n):
    return [{"news_id": f"n{i}", "title": f"Title {i}", "description": "Desc" if i % 2 else None} for i in range(n)]


def test_model_input_combines_title_and_description():
    assert build_model_input({"title": "T", "description": "D"}) == "T. D"
    assert build_model_input({"title": "T", "description": None}) == "T"


async def test_saves_label_score_confidence_and_model_name():
    repo, model = FakeRepo(docs(3)), FakeModel([POS, NEG, NEU])
    result = await SentimentAnalysisService(repo, model).analyze_pending()
    assert result.analyzed == 3 and result.failed == 0
    assert repo.saved["n0"]["label"] == "positive" and repo.saved["n1"]["label"] == "negative"
    assert repo.saved["n2"]["label"] == "neutral"
    s = repo.saved["n0"]
    assert s["model"] == "fake-finbert" and s["score"] > 0.8 and 0 < s["confidence"] <= 1 and s["analyzed_at"]


async def test_batches_respect_batch_size(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "SENTIMENT_BATCH_SIZE", 2)
    repo, model = FakeRepo(docs(5)), FakeModel([NEU] * 5)
    await SentimentAnalysisService(repo, model).analyze_pending()
    assert [len(b) for b in model.batches] == [2, 2, 1]


async def test_model_unavailable_leaves_articles_pending_and_stops():
    repo, model = FakeRepo(docs(4)), FakeModel(error=SentimentModelUnavailableError("no weights"))
    result = await SentimentAnalysisService(repo, model).analyze_pending()
    assert repo.saved == {} and result.analyzed == 0 and result.error == "no weights" and len(model.batches) == 1


async def test_one_failed_batch_does_not_block_the_others(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "SENTIMENT_BATCH_SIZE", 2)
    repo, model = FakeRepo(docs(4)), FakeModel([NEU] * 4, fail_batches={0})
    result = await SentimentAnalysisService(repo, model).analyze_pending()
    assert result.failed == 2 and result.analyzed == 2 and set(repo.saved) == {"n2", "n3"}


async def test_disabled_does_nothing(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "SENTIMENT_ENABLED", False)
    repo, model = FakeRepo(docs(2)), FakeModel([POS, POS])
    result = await SentimentAnalysisService(repo, model).analyze_pending()
    assert model.batches == [] and repo.saved == {} and result.error == "disabled"
