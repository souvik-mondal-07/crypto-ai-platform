"""
Tests for coin-search query handling and relevance ranking (Phase 10)
— that user input is regex-escaped before reaching MongoDB, and that
the ranking pipeline orders exact/strong matches before weak ones.
"""

import re
from unittest.mock import AsyncMock

import pytest

from app.repositories.coin_repository import CoinRepository


class _FakeAggregateCursor:
    """A minimal stand-in for the `AsyncCommandCursor` that PyMongo's
    async driver yields from `await collection.aggregate(...)`.
    `aggregate()` itself is a coroutine (see `_repo_with_captured_pipeline`);
    the cursor it resolves to exposes an awaitable `to_list()`.
    """

    def __init__(self, docs: list):
        self._docs = docs

    async def to_list(self, length=None):
        return self._docs


def _repo_with_captured_pipeline(monkeypatch: pytest.MonkeyPatch, docs: list | None = None):
    """Returns (repo, captured) where captured['pipeline'] holds the aggregation pipeline sent to MongoDB.

    Uses `monkeypatch` (rather than a raw `type(repo).collection = ...`
    assignment) so the `CoinRepository.collection` class attribute is
    automatically restored to the real property at the end of the
    test. Without that, the mocked collection would leak into every
    later test in the session that instantiates a bare
    `CoinRepository()` — including the real-MongoDB integration tests
    in test_market_data_integration.py, which would then silently
    call `bulk_write`/`find_one` etc. on this leftover mock instead of
    a real collection.

    The mocked collection itself is an `AsyncMock` (not a plain
    `MagicMock`), so any collection method `search()` awaits directly
    (e.g. `count_documents`, `find_one`) resolves to a harmless
    awaitable child mock instead of raising
    `TypeError: object MagicMock can't be used in 'await' expression`
    — only `.aggregate(...)` needs a specific return value. It is an
    `async def` here because PyMongo's `AsyncCollection.aggregate()`
    is a coroutine: production code must `await` it to get the cursor,
    and only then `await cursor.to_list(...)`. Mocking it as a plain
    sync function would hide exactly the bug this suite must catch.
    """
    captured: dict = {}
    collection = AsyncMock()

    async def aggregate(pipeline):
        captured["pipeline"] = pipeline
        return _FakeAggregateCursor(docs or [])

    collection.aggregate = aggregate

    repo = CoinRepository()
    monkeypatch.setattr(CoinRepository, "collection", property(lambda self: collection))
    return repo, captured


def _match_stage(pipeline):
    return next(stage["$match"] for stage in pipeline if "$match" in stage)


@pytest.mark.asyncio
async def test_search_escapes_regex_metacharacters(monkeypatch):
    """
    An unbalanced "(" typed into the search box must not reach MongoDB
    as a live regex — unescaped it would either error or open a ReDoS
    vector.
    """
    repo, captured = _repo_with_captured_pipeline(monkeypatch)

    await repo.search("bit(coin")

    conditions = _match_stage(captured["pipeline"])["$or"]
    pattern = conditions[0]["name"]["$regex"]
    assert pattern == re.escape("bit(coin")
    assert r"\(" in pattern


@pytest.mark.asyncio
async def test_search_covers_name_symbol_slug_and_provider_id(monkeypatch):
    repo, captured = _repo_with_captured_pipeline(monkeypatch)

    await repo.search("bitcoin")

    searched_fields = {next(iter(condition)) for condition in _match_stage(captured["pipeline"])["$or"]}
    assert searched_fields == {"name", "symbol", "slug", "providers.coingecko.id"}


@pytest.mark.asyncio
async def test_search_is_case_insensitive(monkeypatch):
    repo, captured = _repo_with_captured_pipeline(monkeypatch)

    await repo.search("BiTcOiN")

    assert _match_stage(captured["pipeline"])["$or"][0]["name"]["$options"] == "i"


@pytest.mark.asyncio
async def test_search_trims_surrounding_whitespace(monkeypatch):
    repo, captured = _repo_with_captured_pipeline(monkeypatch)

    await repo.search("  bitcoin  ")

    assert _match_stage(captured["pipeline"])["$or"][0]["name"]["$regex"] == re.escape("bitcoin")


@pytest.mark.asyncio
async def test_search_ranks_exact_name_match_above_substring_match(monkeypatch):
    """
    The ranking $addFields/$sort stages must be structured so an exact
    name match (_rank 1) sorts ahead of a mere substring match
    (_rank 5/6) — verified here by inspecting the pipeline shape
    rather than live Mongo behavior, since this test runs without a
    database.
    """
    repo, captured = _repo_with_captured_pipeline(monkeypatch)

    await repo.search("bitcoin")

    pipeline = captured["pipeline"]
    add_fields = next(stage["$addFields"] for stage in pipeline if "$addFields" in stage)
    branches = add_fields["_rank"]["$switch"]["branches"]

    # Exact provider-id match ranks first, exact name/symbol next,
    # then starts-with, then contains — in that order.
    assert branches[0]["then"] == 0
    assert branches[1]["then"] == 1
    assert branches[2]["then"] == 2
    assert branches[3]["then"] == 3
    assert branches[4]["then"] == 4
    assert branches[5]["then"] == 5
    assert branches[6]["then"] == 6
    assert add_fields["_rank"]["$switch"]["default"] == 7

    sort_stage = next(stage["$sort"] for stage in pipeline if "$sort" in stage)
    # Rank must be the primary sort key, ahead of market_cap_rank.
    assert list(sort_stage.keys())[0] == "_rank"


@pytest.mark.asyncio
async def test_search_limits_results(monkeypatch):
    repo, captured = _repo_with_captured_pipeline(monkeypatch)

    await repo.search("bitcoin", limit=5)

    limit_stage = next(stage["$limit"] for stage in captured["pipeline"] if "$limit" in stage)
    assert limit_stage == 5


@pytest.mark.asyncio
async def test_search_awaits_aggregate_and_returns_cursor_documents(monkeypatch):
    """
    Regression: `AsyncCollection.aggregate()` is a coroutine, so
    `search()` must await it to obtain the cursor before calling
    `to_list()`. Skipping that await raised
    `AttributeError: 'coroutine' object has no attribute 'to_list'`
    against real MongoDB while pipeline-shape-only tests still passed.
    """
    docs = [{"name": "Bitcoin", "symbol": "BTC"}]
    repo, _captured = _repo_with_captured_pipeline(monkeypatch, docs=docs)

    results = await repo.search("bitcoin")

    assert results == docs
