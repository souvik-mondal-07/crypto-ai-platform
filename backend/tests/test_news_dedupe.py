from datetime import timedelta

from app.services.news_dedupe import build_dedupe_key, build_news_id, normalize_title, normalize_url
from tests.news_fixtures import NOW, article


def test_url_normalization_ignores_tracking_scheme_www_fragment_trailing_slash():
    base = normalize_url("https://pub.test/a/b")
    for variant in (
        "http://www.pub.test/a/b/",
        "https://PUB.test/a/b?utm_source=x&utm_medium=y&fbclid=1",
        "https://pub.test/a/b#comments",
    ):
        assert normalize_url(variant) == base


def test_meaningful_query_params_are_kept_and_order_independent():
    assert normalize_url("https://pub.test/p?id=2&x=1") == normalize_url("https://pub.test/p?x=1&id=2")
    assert normalize_url("https://pub.test/p?id=2") != normalize_url("https://pub.test/p?id=3")


def test_same_url_same_key_different_url_different_key():
    a = build_dedupe_key("https://pub.test/a", "S", "T", NOW)
    assert a == build_dedupe_key("https://www.pub.test/a/?utm_campaign=z", "Other", "Other title", NOW)
    assert a != build_dedupe_key("https://pub.test/b", "S", "T", NOW)


def test_metadata_fallback_when_no_url():
    k1 = build_dedupe_key("", "Pub", "Bitcoin   Rises!", NOW)
    assert k1 == build_dedupe_key(None, " pub ", "bitcoin rises", NOW + timedelta(hours=1))  # same day
    assert k1 != build_dedupe_key("", "Pub", "bitcoin rises", NOW + timedelta(days=1))
    assert normalize_title("A,  B!") == "a b"


def test_news_id_uses_provider_id_when_available_else_hash():
    key = build_dedupe_key("https://pub.test/a", "S", "T", NOW)
    assert build_news_id(article(provider_article_id="42"), key) == "cryptocompare:42"
    no_id = build_news_id(article(provider_article_id=None), key)
    assert no_id == f"cryptocompare:h{key[:20]}"
