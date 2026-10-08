"""
Tests for coin-search query handling and relevance ranking (Phase 10)

Verifies:
- user input is regex-escaped before reaching MongoDB
- search covers name, symbol, slug, and CoinGecko ID
- search is case-insensitive
- surrounding whitespace is trimmed
- exact/strong matches are ranked before weaker matches
- result limits are respected
"""

import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.coin_repository import CoinRepository


class _FakeAggregateCursor:
    """Minimal stand-in for the async MongoDB aggregate cursor."""

    def __init__(self, docs: list):
        self._docs = docs

    async def to_list(self, length=None):
        return self._docs


def _repo_with_captured_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    docs: list | None = None,
):
    """
    Returns (repo, captured).

    captured["pipeline"] contains the aggregation pipeline sent
    to MongoDB.
    """

    captured: dict = {}

    collection = AsyncMock()

    async def aggregate(pipeline):
        captured["pipeline"] = pipeline
        return _FakeAggregateCursor(docs or [])

    collection.aggregate = aggregate

    repo = CoinRepository()

    monkeypatch.setattr(
        CoinRepository,
        "collection",
        property(lambda self: collection),
    )

    return repo, captured


def _match_stage(pipeline):
    return next(
        stage["$match"]
        for stage in pipeline
        if "$match" in stage
    )


@pytest.mark.asyncio
async def test_search_escapes_regex_metacharacters(
    monkeypatch,
):
    """
    An unbalanced "(" typed into the search box must not reach
    MongoDB as a live regex.
    """

    repo, captured = _repo_with_captured_pipeline(monkeypatch)

    await repo.search("bit(coin")

    conditions = _match_stage(
        captured["pipeline"]
    )["$or"]

    pattern = conditions[0]["name"]["$regex"]

    assert pattern == re.escape("bit(coin")
    assert r"\(" in pattern


@pytest.mark.asyncio
async def test_search_covers_name_symbol_slug_and_provider_id(
    monkeypatch,
):
    repo, captured = _repo_with_captured_pipeline(monkeypatch)

    await repo.search("bitcoin")

    searched_fields = {
        next(iter(condition))
        for condition in _match_stage(
            captured["pipeline"]
        )["$or"]
    }

    assert searched_fields == {
        "name",
        "symbol",
        "slug",
        "providers.coingecko.id",
    }


@pytest.mark.asyncio
async def test_search_is_case_insensitive(monkeypatch):
    repo, captured = _repo_with_captured_pipeline(monkeypatch)

    await repo.search("BiTcOiN")

    assert (
        _match_stage(
            captured["pipeline"]
        )["$or"][0]["name"]["$options"]
        == "i"
    )


@pytest.mark.asyncio
async def test_search_trims_surrounding_whitespace(
    monkeypatch,
):
    repo, captured = _repo_with_captured_pipeline(monkeypatch)

    await repo.search("  bitcoin  ")

    assert (
        _match_stage(
            captured["pipeline"]
        )["$or"][0]["name"]["$regex"]
        == re.escape("bitcoin")
    )


@pytest.mark.asyncio
async def test_search_ranks_exact_name_match_above_substring_match(
    monkeypatch,
):
    """
    Exact/strong matches must appear before weaker matches.

    Ranking is now performed by CoinRepository.search() in Python,
    so this test verifies the returned result order instead of
    inspecting an old MongoDB $addFields ranking stage.
    """

    repo, captured = _repo_with_captured_pipeline(monkeypatch)

    mock_cursor = MagicMock()

    mock_cursor.to_list = AsyncMock(
        return_value=[
            {
                "name": "Bitcoin",
                "symbol": "BTC",
                "slug": "bitcoin",
                "providers": {
                    "coingecko": {
                        "id": "bitcoin",
                    }
                },
                "market_cap_rank": 1,
            },
            {
                "name": "Bitcoin Cash",
                "symbol": "BCH",
                "slug": "bitcoin-cash",
                "providers": {
                    "coingecko": {
                        "id": "bitcoin-cash",
                    }
                },
                "market_cap_rank": 20,
            },
        ]
    )

    repo.collection.aggregate = AsyncMock(
        return_value=mock_cursor
    )

    results = await repo.search("bitcoin")

    assert len(results) == 2
    assert results[0]["name"] == "Bitcoin"
    assert results[1]["name"] == "Bitcoin Cash"


@pytest.mark.asyncio
async def test_search_limits_results(monkeypatch):
    """
    search(limit=N) must return at most N results.

    Limiting is now performed after ranking in Python, so this
    test checks the returned result count instead of expecting
    a MongoDB $limit stage.
    """

    repo, captured = _repo_with_captured_pipeline(monkeypatch)

    mock_cursor = MagicMock()

    mock_cursor.to_list = AsyncMock(
        return_value=[
            {
                "name": "Bitcoin",
                "symbol": "BTC",
                "slug": "bitcoin",
                "providers": {
                    "coingecko": {
                        "id": "bitcoin",
                    }
                },
                "market_cap_rank": 1,
            },
            {
                "name": "Bitcoin Cash",
                "symbol": "BCH",
                "slug": "bitcoin-cash",
                "providers": {
                    "coingecko": {
                        "id": "bitcoin-cash",
                    }
                },
                "market_cap_rank": 20,
            },
            {
                "name": "Bitcoin SV",
                "symbol": "BSV",
                "slug": "bitcoin-sv",
                "providers": {
                    "coingecko": {
                        "id": "bitcoin-sv",
                    }
                },
                "market_cap_rank": 50,
            },
            {
                "name": "Bitcoin Gold",
                "symbol": "BTG",
                "slug": "bitcoin-gold",
                "providers": {
                    "coingecko": {
                        "id": "bitcoin-gold",
                    }
                },
                "market_cap_rank": 100,
            },
            {
                "name": "Bitcoin Cash ABC",
                "symbol": "BCHA",
                "slug": "bitcoin-cash-abc",
                "providers": {
                    "coingecko": {
                        "id": "bitcoin-cash-abc",
                    }
                },
                "market_cap_rank": 200,
            },
            {
                "name": "Bitcoin Private",
                "symbol": "BTCP",
                "slug": "bitcoin-private",
                "providers": {
                    "coingecko": {
                        "id": "bitcoin-private",
                    }
                },
                "market_cap_rank": 300,
            },
        ]
    )

    repo.collection.aggregate = AsyncMock(
        return_value=mock_cursor
    )

    results = await repo.search(
        "bitcoin",
        limit=5,
    )

    assert len(results) == 5