"""Pure unit tests for app/services/portfolio_calculations.py."""

import math

import pytest

from app.services import portfolio_calculations as c


def test_valuation_formulas():
    v = c.valuate(quantity=2, average_buy_price=50, price=100)
    assert (v.invested, v.current, v.pnl, v.pnl_pct) == (100, 200, 100, 100)


def test_loss_is_negative():
    v = c.valuate(4, 100, 75)
    assert v.pnl == -100 and v.pnl_pct == -25


@pytest.mark.parametrize("price", [None, 0, -1, math.nan, math.inf])
def test_unusable_price_means_no_value_and_no_pnl(price):
    v = c.valuate(1, 10, price)
    assert v.current is None and v.pnl is None and v.pnl_pct is None


def test_zero_invested_gives_no_percentage():
    assert c.valuate(1, 0, 10).pnl_pct is None
    assert c.pnl_percent(5.0, 0) is None and c.pnl_percent(None, 10) is None


def test_weighted_average():
    assert c.weighted_average_price(1, 100, 3, 200) == 175
    assert c.weighted_average_price(0, 0, 0, 0) == 0.0


def test_summary_covers_only_priced_holdings_for_pnl():
    s = c.summarize([c.valuate(1, 80, 100), c.valuate(3, 10, None)])
    assert (s.total_current_value, s.total_invested, s.priced_invested, s.total_pnl) == (100, 110, 80, 20)
    assert s.is_partial and s.unpriced_count == 1 and s.holdings_count == 2


def test_empty_summary():
    s = c.summarize([])
    assert s.total_pnl is None and s.total_pnl_pct is None and not s.is_partial


def test_allocation():
    assert c.allocation_percent(25, 100) == 25
    assert c.allocation_percent(None, 100) is None and c.allocation_percent(5, 0) is None
