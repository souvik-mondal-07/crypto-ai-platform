"""CryptoCompare news normalization: valid mapping, cleaning, malformed handling, error envelopes."""

import pytest

from app.providers.errors import ProviderRateLimitError, ProviderResponseError
from app.providers.news.cryptocompare import clean_text, map_article, map_response
from tests.news_fixtures import NOW, raw_article


def test_maps_a_valid_article():
    a = map_article(raw_article())
    assert a.provider == "cryptocompare"
    assert a.provider_article_id == "9001"
    assert a.title == "Test headline one"
    assert a.source == "Example Publisher"  # source_info.name preferred over the slug
    assert a.url.startswith("https://example-publisher.test/story-1")
    assert a.published_at.tzinfo is not None and a.published_at < NOW
    assert a.categories == ["BTC", "Exchange"] and a.tags == ["Market", "Trading"]
    assert a.language == "en"
    assert a.image_url == "https://img.example-publisher.test/1.jpg"


def test_description_is_html_stripped_unescaped_and_truncated():
    a = map_article(raw_article(body="<p>" + "word " * 200 + "&amp; end</p>"), description_max_chars=50)
    assert "<" not in a.description and len(a.description) <= 51 and a.description.endswith("…")
    assert clean_text("<b>A &amp; B</b>") == "A & B"
    assert clean_text("   ") is None and clean_text(None) is None


@pytest.mark.parametrize(
    "override",
    [
        {"title": ""},
        {"title": None},
        {"url": "javascript:alert(1)", "guid": "not a url"},
        {"url": None, "guid": None},
        {"published_on": None},
        {"published_on": "yesterday"},
        {"published_on": -5},
        {"published_on": 10**20},
        {"source": "", "source_info": {}},
    ],
)
def test_unusable_entries_are_dropped_not_repaired(override):
    assert map_article(raw_article(**override)) is None


def test_non_dict_entry_is_dropped():
    assert map_article("garbage") is None and map_article(None) is None


def test_falls_back_to_guid_when_url_missing_and_to_source_slug():
    a = map_article(raw_article(url=None, source_info=None))
    assert a.url == "https://example-publisher.test/story-1" and a.source == "examplepub"


def test_missing_provider_id_is_none_not_invented():
    assert map_article(raw_article(id=None)).provider_article_id is None


def test_non_http_image_is_ignored():
    assert map_article(raw_article(imageurl="data:image/png;base64,xx")).image_url is None


def test_response_counts_malformed_and_sorts_newest_first():
    older = raw_article(id="1", url="https://x.test/a", published_on=int(NOW.timestamp()) - 5000)
    newer = raw_article(id="2", url="https://x.test/b", published_on=int(NOW.timestamp()) - 50)
    result = map_response({"Type": 100, "Data": [older, {"title": "no url"}, newer]})
    assert [a.provider_article_id for a in result.articles] == ["2", "1"]
    assert result.malformed_count == 1
    assert result.oldest_published_at == result.articles[-1].published_at


def test_empty_data_list_is_valid():
    assert map_response({"Data": []}).articles == []


def test_rate_limit_error_envelope():
    with pytest.raises(ProviderRateLimitError):
        map_response({"Response": "Error", "Message": "You are over your rate limit please upgrade"})


def test_other_error_envelope_and_bad_shapes():
    with pytest.raises(ProviderResponseError):
        map_response({"Response": "Error", "Message": "something else"})
    for bad in ([], "x", None, {"Data": "nope"}, {"Type": 100}):
        with pytest.raises(ProviderResponseError):
            map_response(bad)
