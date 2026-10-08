"""
Unit tests for CoinGecko /coins/{id} profile normalization (Phase 11).
Pure data transformation — no HTTP, no MongoDB.

The payloads are inline fixtures shaped like CoinGecko's documented
response; they exist only to exercise the mapper.
"""

from app.providers.coingecko.mapper import map_coin_profile


def _payload(**overrides):
    raw = {
        "id": "examplecoin",
        "asset_platform_id": None,
        "platforms": {"": ""},
        "block_time_in_minutes": 10,
        "hashing_algorithm": "SHA-256",
        "categories": ["Cryptocurrency", "Layer 1 (L1)", "", None],
        "description": {"en": "  A peer-to-peer electronic cash system.  "},
        "links": {
            "homepage": ["https://example.org", "", "https://example.org"],
            "whitepaper": "https://example.org/whitepaper.pdf",
            "blockchain_site": ["https://explorer.example.org", "", None],
            "official_forum_url": ["https://forum.example.org", ""],
            "announcement_url": ["", None],
            "chat_url": ["https://chat.example.org"],
            "twitter_screen_name": "examplecoin",
            "subreddit_url": "https://www.reddit.com/r/examplecoin",
            "telegram_channel_identifier": "",
            "repos_url": {"github": ["https://github.com/example/core", ""], "bitbucket": []},
        },
        "genesis_date": "2009-01-03",
        "max_supply_infinite": False,
        "sentiment_votes_up_percentage": 80.0,
        "watchlist_portfolio_users": 12345,
        "community_data": {"reddit_subscribers": 5000, "telegram_channel_user_count": None, "facebook_likes": None},
        "developer_data": {
            "forks": 36000, "stars": 72000, "subscribers": 3900, "total_issues": 7500, "closed_issues": 7000,
            "pull_requests_merged": 11000, "pull_request_contributors": 850, "commit_count_4_weeks": 120,
            "code_additions_deletions_4_weeks": {"additions": 4500, "deletions": 2100},
        },
        "last_updated": "2026-09-30T10:00:00.000Z",
    }
    raw.update(overrides)
    return raw


def test_maps_project_information():
    p = map_coin_profile(_payload())
    assert p.coingecko_id == "examplecoin"
    assert p.description == "A peer-to-peer electronic cash system."
    assert p.whitepaper_url == "https://example.org/whitepaper.pdf"
    assert p.hashing_algorithm == "SHA-256"
    assert p.block_time_in_minutes == 10.0
    assert p.genesis_date == "2009-01-03"
    assert p.twitter_screen_name == "examplecoin"
    assert p.last_updated is not None


def test_drops_blank_entries_and_duplicates_from_lists():
    p = map_coin_profile(_payload())
    assert p.homepage_urls == ["https://example.org"]
    assert p.blockchain_explorer_urls == ["https://explorer.example.org"]
    assert p.categories == ["Cryptocurrency", "Layer 1 (L1)"]
    assert p.github_repos == ["https://github.com/example/core"]
    assert p.announcement_urls == []
    assert p.telegram_channel_identifier is None  # blank string -> None


def test_maps_developer_and_community_data():
    p = map_coin_profile(_payload())
    assert p.developer.stars == 72000
    assert p.developer.commit_count_4_weeks == 120
    assert p.developer.code_additions_4_weeks == 4500
    assert p.developer.code_deletions_4_weeks == 2100
    assert p.community.reddit_subscribers == 5000
    assert p.community.telegram_channel_user_count is None


def test_placeholder_platform_entry_is_not_a_contract_address():
    assert map_coin_profile(_payload()).contract_addresses == {}


def test_maps_real_contract_addresses_and_platform():
    p = map_coin_profile(_payload(
        asset_platform_id="ethereum",
        platforms={"ethereum": "0xabc", "tron": " TXyz ", "empty": ""},
    ))
    assert p.asset_platform_id == "ethereum"
    assert p.contract_addresses == {"ethereum": "0xabc", "tron": "TXyz"}


def test_does_not_map_sentiment_or_watchlist_fields():
    p = map_coin_profile(_payload())
    assert not hasattr(p, "sentiment_votes_up_percentage")
    assert not hasattr(p, "watchlist_portfolio_users")


def test_max_supply_infinite_flag_true_false_and_unknown():
    assert map_coin_profile(_payload(max_supply_infinite=True)).max_supply_infinite is True
    assert map_coin_profile(_payload(max_supply_infinite=False)).max_supply_infinite is False
    raw = _payload()
    del raw["max_supply_infinite"]
    assert map_coin_profile(raw).max_supply_infinite is None
    # A non-boolean is "unknown", never coerced.
    assert map_coin_profile(_payload(max_supply_infinite="true")).max_supply_infinite is None
    assert map_coin_profile(_payload(max_supply_infinite=1)).max_supply_infinite is None


def test_max_supply_infinite_accepted_under_market_data_block():
    raw = _payload()
    del raw["max_supply_infinite"]
    raw["market_data"] = {"max_supply_infinite": True}
    assert map_coin_profile(raw).max_supply_infinite is True


def test_minimal_payload_yields_empty_profile_without_errors():
    p = map_coin_profile({"id": "tiny"})
    assert p.description is None and p.homepage_urls == [] and p.categories == []
    assert p.github_repos == [] and p.contract_addresses == {}
    assert p.developer.commit_count_4_weeks is None
    assert p.community.reddit_subscribers is None
    assert p.genesis_date is None and p.last_updated is None


def test_wrong_types_become_none_instead_of_being_guessed():
    p = map_coin_profile(_payload(
        description="not a dict", links="oops", developer_data={"stars": "12", "forks": True, "commit_count_4_weeks": float("nan")},
        community_data=[], block_time_in_minutes="10", genesis_date=20090103, categories="Cryptocurrency",
    ))
    assert p.description is None and p.homepage_urls == [] and p.github_repos == []
    assert p.developer.stars is None
    assert p.developer.forks is None  # bool is not a count
    assert p.developer.commit_count_4_weeks is None
    assert p.community.reddit_subscribers is None
    assert p.block_time_in_minutes is None
    assert p.genesis_date is None
    assert p.categories == []


def test_null_genesis_date_stays_null():
    assert map_coin_profile(_payload(genesis_date=None)).genesis_date is None
