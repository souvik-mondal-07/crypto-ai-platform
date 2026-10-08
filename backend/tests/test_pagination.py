"""Unit tests for the pagination validation utility."""

from app.utils.pagination import MAX_LIMIT, clamp_pagination, total_pages


def test_clamp_pagination_normal_values():
    assert clamp_pagination(2, 50) == (2, 50)


def test_clamp_pagination_rejects_zero_or_negative_page():
    page, _ = clamp_pagination(0, 10)
    assert page == 1
    page, _ = clamp_pagination(-5, 10)
    assert page == 1


def test_clamp_pagination_enforces_max_limit():
    _, limit = clamp_pagination(1, 999999)
    assert limit == MAX_LIMIT


def test_clamp_pagination_rejects_zero_or_negative_limit():
    _, limit = clamp_pagination(1, 0)
    assert limit == 1
    _, limit = clamp_pagination(1, -10)
    assert limit == 1


def test_total_pages_basic():
    assert total_pages(250, 100) == 3
    assert total_pages(300, 100) == 3
    assert total_pages(0, 100) == 0


def test_total_pages_zero_limit_is_safe():
    assert total_pages(100, 0) == 0
