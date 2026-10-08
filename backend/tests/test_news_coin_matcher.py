from bson import ObjectId

from app.services.news_coin_matcher import NewsCoinMatcher, extract_candidate_symbols
from tests.news_fixtures import BTC_ID, ETH_ID, FakeCoinRepository, article


def test_tickers_come_from_all_caps_provider_tags_only():
    a = article(categories=["BTC", "Exchange", "ETH", "Trading", "ICO", "NFT", "Mining"])
    assert extract_candidate_symbols(a) == ["BTC", "ETH"]


def test_cashtags_in_title_are_used_and_deduplicated():
    a = article(categories=["SOL"], title="$sol and $ADA rally while $SOL holders cheer, costs $5 today")
    assert extract_candidate_symbols(a) == ["SOL", "ADA"]


def test_coin_names_in_plain_text_do_not_create_associations():
    a = article(categories=[], title="Bitcoin and Ethereum are discussed")
    assert extract_candidate_symbols(a) == []


def test_malformed_labels_are_ignored():
    assert extract_candidate_symbols(article(categories=["B", "WAYTOOLONGLABEL", "BTC-USD", ""])) == []


async def test_resolves_only_known_ranked_coins_and_preserves_order():
    matcher = NewsCoinMatcher(FakeCoinRepository())
    resolved = await matcher.resolve_symbols(["ETH", "BTC", "ZZZ"])
    assert resolved == {"ETH": ETH_ID, "BTC": BTC_ID}
    ids, symbols = matcher.associate(["ETH", "ZZZ", "BTC", "ETH"], resolved)
    assert ids == [ETH_ID, BTC_ID] and symbols == ["ETH", "BTC"]


async def test_no_symbols_means_no_lookup():
    class Boom:
        async def find_best_by_symbols(self, _):
            raise AssertionError("must not query")

    assert await NewsCoinMatcher(Boom()).resolve_symbols([]) == {}
