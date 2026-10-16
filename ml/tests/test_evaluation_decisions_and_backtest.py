"""Phase 17 — decision evaluation, backtest engine, statistics and look-ahead-bias tests."""

from datetime import datetime, timedelta, timezone

import pytest

from ml.evaluation import backtest_metrics as bm
from ml.evaluation.backtest import BacktestConfig, Signal, run_backtest
from ml.evaluation.decision_eval import DecisionRecord, decision_metrics, evaluate_decision
from ml.tests.evaluation_helpers import H, T0, series_from_closes

NOW = T0 + timedelta(days=400)


# ------------------------------------------------------------------ decision evaluation
def _dec(decision, at=T0 + timedelta(hours=1), price=100.0, sid="d1"):
    return DecisionRecord(sid, "c1", "BTC", decision, at, price, "1.0", None)


def _flat_then(target_idx, value, n=60):
    closes = [100.0] * n
    closes[target_idx] = value
    return series_from_closes(closes)


def test_forward_return_uses_recorded_reference_price():
    # decision at +1h, 24h horizon -> target +25h == candle index 24
    o = evaluate_decision(_dec("BUY"), "24h", _flat_then(24, 110.0), NOW)
    assert o.status == "matched" and o.forward_return == pytest.approx(0.10) and o.reference_source == "recorded"


def test_reference_price_falls_back_to_point_in_time_candle_close_never_later():
    closes = [100.0, 101.0, 999.0] + [100.0] * 60       # candle 2 closes at +3h: AFTER the decision at +1h30
    s = series_from_closes(closes)
    o = evaluate_decision(_dec("BUY", at=T0 + timedelta(hours=1, minutes=30), price=None), "24h", s, NOW)
    # last candle complete at +1h30 closes at +1h (price 100.0), not the 999 candle.
    assert o.reference_price == 100.0 and o.reference_source == "candle_close"


def test_stale_reference_candle_is_rejected():
    s = series_from_closes([100.0] * 5)                   # data ends at +5h
    o = evaluate_decision(_dec("BUY", at=T0 + timedelta(hours=50), price=None), "24h", s, NOW)
    assert o.status == "missing_reference_price"


def test_decisions_not_matured_or_invalid_are_not_evaluated():
    s = _flat_then(24, 110.0)
    assert evaluate_decision(_dec("BUY"), "24h", s, T0 + timedelta(hours=20)).status == "not_matured"
    assert evaluate_decision(_dec(None), "24h", s, NOW).status == "invalid_record"
    assert evaluate_decision(_dec("BUY"), "2h", s, NOW).status == "unsupported_horizon"


def _outs(decision, returns, horizon="24h"):
    from ml.evaluation.decision_eval import DecisionOutcome
    return [DecisionOutcome(_dec(decision, sid=f"{decision}{i}"), horizon, "matched", None, 100.0, "recorded", r, T0) for i, r in enumerate(returns)]


def test_decision_metrics_rules():
    outs = (_outs("BUY", [0.05, -0.02, 0.01, 0.03]) + _outs("SELL", [-0.04, 0.02, -0.01, -0.03])
            + _outs("HOLD", [0.01, 0.015, 0.05, -0.03]))
    m = decision_metrics(outs, min_samples=4)
    cell = {(c["decision"], c["horizon"]): c for c in m["by_decision_horizon"]}
    assert cell[("BUY", "24h")]["directional_agreement"] == pytest.approx(3 / 4)
    assert cell[("SELL", "24h")]["directional_agreement"] == pytest.approx(3 / 4)   # SELL aligned only if price FELL
    hold = cell[("HOLD", "24h")]
    assert hold["directional_agreement"] is None                                     # HOLD makes no directional claim
    assert hold["within_neutral_band_rate"] == pytest.approx(2 / 4)                  # |r| <= 2%
    assert m["pooled_directional"][0]["directional_agreement"] == pytest.approx(6 / 8)
    assert m["evaluated_decisions"] == 12


def test_decision_metrics_insufficient_sample():
    m = decision_metrics(_outs("BUY", [0.1, 0.2]), min_samples=20)
    buy = [c for c in m["by_decision_horizon"] if c["decision"] == "BUY"][0]
    assert buy["status"] == "insufficient_data" and buy["mean_return"] is None and buy["count"] == 2


# ------------------------------------------------------------------ statistics
def test_max_drawdown_and_returns():
    assert bm.max_drawdown([100, 120, 90, 110, 80, 130]) == pytest.approx((120 - 80) / 120)
    assert bm.max_drawdown([100, 101, 102]) == 0.0
    assert bm.max_drawdown([]) is None
    assert bm.total_return(100, 125) == pytest.approx(0.25) and bm.total_return(0, 5) is None


def test_annualised_return_requires_a_long_enough_period():
    s = T0
    assert bm.annualized_return(100, 110, s, s + timedelta(days=10)) is None
    assert bm.annualized_return(100, 121, s, s + timedelta(days=730.5)) == pytest.approx(0.10, rel=1e-6)
    assert bm.annualized_return(100, 0, s, s + timedelta(days=365)) is None


def test_sharpe_needs_enough_observations_and_variance():
    v, note = bm.sharpe_ratio([100, 101, 102], 3600)
    assert v is None and note
    v, note = bm.sharpe_ratio([100.0 * 1.001 ** i for i in range(60)], 3600)
    assert v is None and "zero" in note
    wobble = [100 + (i % 7) + i * 0.1 for i in range(80)]
    v, note = bm.sharpe_ratio(wobble, 3600)
    assert v is not None and note is None


def test_downsample_keeps_endpoints():
    pts = list(range(1000))
    out = bm.downsample(pts, 50)
    assert out[0] == 0 and out[-1] == 999 and len(out) <= 51
    assert bm.downsample(pts, 5000) == pts


# ------------------------------------------------------------------ backtest engine
def _cfg(**kw):
    base = dict(coin_ids=("c1",), start=T0, end=T0 + timedelta(days=60), starting_capital=1000.0, position_size=0.5,
                max_allocation_pct=1.0, fee_rate=0.0, slippage_rate=0.0)
    base.update(kw)
    return BacktestConfig(**base)


def _bars(closes, opens=None):
    return {"c1": series_from_closes(closes, opens=opens)}


def test_no_decisions_means_no_trades_and_flat_equity():
    r = run_backtest(_cfg(), _bars([100.0, 110.0, 120.0]), {})
    assert r.status == "ok" and r.summary["number_of_trades"] == 0 and r.summary["final_value"] == 1000.0
    assert r.summary["win_rate"] is None and any("No stored decisions" in w for w in r.warnings)
    assert r.summary["benchmark_return"] is not None


def test_no_candles_is_insufficient_data_not_zero():
    r = run_backtest(_cfg(), {"c1": series_from_closes([])}, {})
    assert r.status == "insufficient_data" and r.summary == {}


def test_buy_then_sell_zero_costs_exact_numbers():
    # opens: [100,100,110,120,120]; BUY known at bar 1's open, SELL known at bar 3's open.
    opens = [100.0, 100.0, 110.0, 120.0, 120.0]
    closes = [100.0, 110.0, 120.0, 120.0, 120.0]
    sigs = {"c1": [Signal(T0 + timedelta(hours=1), "BUY", "a"), Signal(T0 + timedelta(hours=3), "SELL", "b")]}
    r = run_backtest(_cfg(), _bars(closes, opens), sigs)
    # buys 500 @100 (bar 1 open) -> 5 units; sells @120 (bar 3 open) -> +100 profit
    assert r.summary["final_value"] == pytest.approx(1100.0)
    assert r.summary["number_of_trades"] == 1 and r.summary["win_rate"] == 1.0
    assert r.summary["average_win_return"] == pytest.approx(0.2) and r.summary["average_loss_return"] is None
    assert [t["side"] for t in r.trades] == ["BUY", "SELL"]
    assert r.summary["total_fees"] == 0 and r.summary["estimated_slippage"] == 0


def test_fees_and_slippage_are_applied_and_reported():
    opens = [100.0, 100.0, 100.0, 100.0]
    sigs = {"c1": [Signal(T0 + timedelta(hours=1), "BUY"), Signal(T0 + timedelta(hours=2), "SELL")]}
    r = run_backtest(_cfg(fee_rate=0.001, slippage_rate=0.01), _bars([100.0] * 4, opens), sigs)
    buy, sell = r.trades
    assert buy["price"] == pytest.approx(101.0) and sell["price"] == pytest.approx(99.0)   # adverse both ways
    assert buy["fee"] == pytest.approx(buy["notional"] * 0.001)
    assert r.summary["total_fees"] == pytest.approx(buy["fee"] + sell["fee"])
    assert r.summary["estimated_slippage"] > 0 and r.summary["final_value"] < 1000.0
    assert r.assumptions["fee_rate"] == 0.001 and r.assumptions["slippage_rate"] == 0.01
    assert r.summary["average_loss_return"] is not None and r.summary["win_rate"] == 0.0


def test_position_sizing_fraction_and_allocation_cap():
    sigs = {"c1": [Signal(T0 + timedelta(hours=1), "BUY")]}
    r = run_backtest(_cfg(position_size=0.5, max_allocation_pct=0.5), _bars([100.0] * 4), sigs)
    assert r.trades[0]["notional"] == pytest.approx(500.0)
    r = run_backtest(_cfg(position_size=0.8, max_allocation_pct=0.3), _bars([100.0] * 4), sigs)
    assert r.trades[0]["notional"] == pytest.approx(300.0)                                   # cap wins
    r = run_backtest(_cfg(sizing_mode="fixed_amount", position_size=200.0), _bars([100.0] * 4), sigs)
    assert r.trades[0]["notional"] == pytest.approx(200.0)
    r = run_backtest(_cfg(sizing_mode="fixed_amount", position_size=5000.0, fee_rate=0.01), _bars([100.0] * 4), sigs)
    assert r.trades[0]["notional"] + r.trades[0]["fee"] <= 1000.0 + 1e-9                    # never spends more than cash


def test_long_only_no_pyramiding_and_sell_while_flat_ignored():
    sigs = {"c1": [Signal(T0 + timedelta(hours=0), "SELL"), Signal(T0 + timedelta(hours=1), "BUY"),
                   Signal(T0 + timedelta(hours=2), "BUY"), Signal(T0 + timedelta(hours=3), "HOLD")]}
    r = run_backtest(_cfg(), _bars([100.0] * 6), sigs)
    assert [t["side"] for t in r.trades] == ["BUY", "SELL"]            # second BUY ignored; end-of-period close
    assert r.trades[-1]["reason"] == "end_of_backtest"
    assert r.summary["skipped_signals"] == {"sell_while_flat": 1, "buy_while_in_position": 1}


def test_open_position_can_stay_open_when_configured():
    sigs = {"c1": [Signal(T0 + timedelta(hours=1), "BUY")]}
    r = run_backtest(_cfg(close_open_positions_at_end=False), _bars([100.0, 100.0, 120.0, 120.0]), sigs)
    assert r.summary["number_of_trades"] == 0 and r.summary["final_value"] == pytest.approx(1000 + 5 * 20)


def test_equity_curve_and_drawdown():
    opens = [100.0, 100.0, 80.0, 80.0, 120.0]
    closes = [100.0, 80.0, 80.0, 120.0, 120.0]
    sigs = {"c1": [Signal(T0 + timedelta(hours=1), "BUY")]}
    r = run_backtest(_cfg(position_size=1.0), _bars(closes, opens), sigs)
    values = [v for _, v in r.equity_curve]
    assert values[0] == 1000.0 and len(values) == 6 and values[2] == pytest.approx(800.0)    # 10 units * 80
    assert r.summary["max_drawdown"] == pytest.approx(0.2)
    times = [t for t, _ in r.equity_curve]
    assert times == sorted(times)


def test_benchmark_equal_weight_buy_and_hold():
    r = run_backtest(_cfg(), _bars([100.0, 100.0, 150.0]), {})
    assert r.summary["benchmark_return"] == pytest.approx(0.5)
    r = run_backtest(_cfg(fee_rate=0.01), _bars([100.0, 100.0, 150.0]), {})
    assert r.summary["benchmark_return"] < 0.5                                                  # benchmark pays costs too


def test_deterministic_repeat():
    sigs = {"c1": [Signal(T0 + timedelta(hours=1), "BUY"), Signal(T0 + timedelta(hours=3), "SELL")]}
    args = (_cfg(fee_rate=0.001, slippage_rate=0.001), _bars([100, 101, 103, 99, 104.0]), sigs)
    a, b = run_backtest(*args), run_backtest(*args)
    assert a.summary == b.summary and a.equity_curve == b.equity_curve and a.trades == b.trades


# ------------------------------------------------------------------ look-ahead bias
def test_execution_never_precedes_the_decision():
    sigs = {"c1": [Signal(T0 + timedelta(hours=1, minutes=30), "BUY"), Signal(T0 + timedelta(hours=4, minutes=1), "SELL")]}
    r = run_backtest(_cfg(), _bars([100.0] * 8), sigs)
    for t in r.trades:
        if t["decision_time"] is not None:
            assert t["execution_time"] >= t["decision_time"]
    assert r.trades[0]["execution_time"] == T0 + timedelta(hours=2)      # next bar OPEN after 01:30, not the 01:00 bar


def test_future_price_never_changes_an_earlier_decision_or_trade():
    sigs = {"c1": [Signal(T0 + timedelta(hours=1), "BUY"), Signal(T0 + timedelta(hours=3), "SELL")]}
    base = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    altered = base[:5] + [1.0, 9999.0, 5.0]                              # only bars AFTER the last trade differ
    a = run_backtest(_cfg(close_open_positions_at_end=False), _bars(base), sigs)
    b = run_backtest(_cfg(close_open_positions_at_end=False), _bars(altered), sigs)
    assert a.trades == b.trades
    assert [v for _, v in a.equity_curve][:5] == [v for _, v in b.equity_curve][:5]


def test_future_decision_cannot_influence_earlier_bars():
    early = {"c1": [Signal(T0 + timedelta(hours=2), "BUY")]}
    late = {"c1": [Signal(T0 + timedelta(hours=2), "BUY"), Signal(T0 + timedelta(hours=6), "SELL")]}
    a = run_backtest(_cfg(close_open_positions_at_end=False), _bars([100.0, 100, 110, 120, 130, 140, 150, 160]), early)
    b = run_backtest(_cfg(close_open_positions_at_end=False), _bars([100.0, 100, 110, 120, 130, 140, 150, 160]), late)
    assert a.trades[0] == b.trades[0]
    assert [v for _, v in a.equity_curve][:6] == [v for _, v in b.equity_curve][:6]


def test_decisions_before_the_window_or_after_it_are_ignored():
    sigs = {"c1": [Signal(T0 - timedelta(hours=5), "BUY"), Signal(T0 + timedelta(days=90), "BUY")]}
    r = run_backtest(_cfg(), _bars([100.0] * 5), sigs)
    assert r.trades == [] and r.summary["decisions_in_period"] == 0


def test_series_as_of_blocks_unfinished_candles():
    s = series_from_closes([100.0, 100.0, 100.0], as_of=T0 + timedelta(hours=2, minutes=59))
    assert len(s) == 2


# ------------------------------------------------------------------ configuration validation
@pytest.mark.parametrize("field,value", [
    ("starting_capital", 0.0), ("starting_capital", -5.0), ("position_size", 0.0), ("position_size", 1.5),
    ("max_allocation_pct", 0.0), ("max_allocation_pct", 1.2), ("fee_rate", -0.001), ("fee_rate", 0.5),
    ("slippage_rate", -1.0), ("bar_interval", "5m"), ("sizing_mode", "kelly"), ("coin_ids", ()),
    ("coin_ids", ("c1", "c1")), ("strategy", "my_own_strategy"),
])
def test_invalid_configuration_rejected(field, value):
    with pytest.raises(ValueError):
        _cfg(**{field: value}).validate()


def test_end_before_start_rejected():
    with pytest.raises(ValueError):
        _cfg(start=T0 + timedelta(days=2), end=T0 + timedelta(days=1)).validate()
