"""
Unit tests for app/services/fundamental_calculations.py — pure math, no I/O.

Expected values are worked out by hand in the comments, not copied
from the implementation's output.
"""

import re
from datetime import date

import pytest

from app.services import fundamental_calculations as calc

TODAY = date(2026, 9, 30)


def _metrics(**overrides):
    args = dict(
        price_usd=50.0, market_cap_usd=1_000_000_000.0, volume_24h_usd=50_000_000.0,
        circulating_supply=15_000_000.0, total_supply=18_000_000.0, max_supply=21_000_000.0,
        fully_diluted_valuation_usd=1_400_000_000.0, ath_usd=200.0, atl_usd=10.0,
    )
    args.update(overrides)
    return calc.compute_metrics(**args)


# ---- derived metrics -------------------------------------------------------


def test_all_metrics_from_complete_inputs():
    m = _metrics()
    assert m.volume_to_market_cap.value == pytest.approx(0.05)  # 50M / 1B
    assert m.market_cap_to_fdv.value == pytest.approx(1 / 1.4)  # 1B / 1.4B
    assert m.circulating_to_max_supply_percent.value == pytest.approx(15 / 21 * 100)
    assert m.remaining_to_max_supply_percent.value == pytest.approx(6 / 21 * 100)
    assert m.remaining_supply_to_max.value == pytest.approx(6_000_000.0)
    assert m.circulating_to_total_supply_percent.value == pytest.approx(15 / 18 * 100)
    assert m.distance_from_ath_percent.value == pytest.approx(-75.0)  # 50/200 - 1
    assert m.distance_from_atl_percent.value == pytest.approx(400.0)  # 50/10 - 1
    assert all(x.unavailable_reason is None for x in vars(m).values())


def test_circulating_and_remaining_percent_sum_to_100():
    m = _metrics()
    assert m.circulating_to_max_supply_percent.value + m.remaining_to_max_supply_percent.value == pytest.approx(100.0)


def test_metrics_are_labelled_with_formula_and_unit():
    m = _metrics()
    assert m.volume_to_market_cap.unit == "ratio"
    assert m.distance_from_ath_percent.unit == "percent"
    assert m.remaining_supply_to_max.unit == "tokens"
    assert "market cap" in m.volume_to_market_cap.formula


def test_missing_max_supply_makes_only_max_based_metrics_unavailable():
    m = _metrics(max_supply=None)
    for metric in (m.circulating_to_max_supply_percent, m.remaining_to_max_supply_percent, m.remaining_supply_to_max):
        assert metric.value is None
        assert "Maximum supply is not reported" in metric.unavailable_reason
    # Unrelated metrics are unaffected — nothing is assumed or borrowed.
    assert m.circulating_to_total_supply_percent.value == pytest.approx(15 / 18 * 100)
    assert m.volume_to_market_cap.value is not None


def test_missing_total_supply():
    m = _metrics(total_supply=None)
    assert m.circulating_to_total_supply_percent.value is None
    assert "Total supply" in m.circulating_to_total_supply_percent.unavailable_reason


def test_missing_circulating_supply_disables_all_supply_ratios():
    m = _metrics(circulating_supply=None)
    assert m.circulating_to_max_supply_percent.value is None
    assert m.circulating_to_total_supply_percent.value is None
    assert "Circulating supply" in m.circulating_to_max_supply_percent.unavailable_reason


def test_zero_circulating_supply_is_a_real_zero_not_missing():
    m = _metrics(circulating_supply=0)
    assert m.circulating_to_max_supply_percent.value == 0.0
    assert m.remaining_to_max_supply_percent.value == pytest.approx(100.0)


def test_circulating_above_max_is_rejected_not_clamped():
    m = _metrics(circulating_supply=30_000_000.0)
    assert m.circulating_to_max_supply_percent.value is None
    assert "inconsistent" in m.circulating_to_max_supply_percent.unavailable_reason
    assert m.remaining_supply_to_max.value is None  # never a negative token count


def test_circulating_above_total_is_rejected():
    m = _metrics(circulating_supply=19_000_000.0, max_supply=None)
    assert m.circulating_to_total_supply_percent.value is None
    assert "inconsistent" in m.circulating_to_total_supply_percent.unavailable_reason


def test_zero_market_cap_avoids_division_by_zero():
    m = _metrics(market_cap_usd=0)
    assert m.volume_to_market_cap.value is None
    assert m.market_cap_to_fdv.value is None
    assert "Market cap" in m.volume_to_market_cap.unavailable_reason


def test_zero_volume_is_valid_and_gives_zero_ratio():
    assert _metrics(volume_24h_usd=0).volume_to_market_cap.value == 0.0


def test_market_cap_far_above_fdv_is_flagged_inconsistent():
    m = _metrics(market_cap_usd=2_000_000_000.0, fully_diluted_valuation_usd=1_000_000_000.0)
    assert m.market_cap_to_fdv.value is None
    assert "inconsistent" in m.market_cap_to_fdv.unavailable_reason


def test_market_cap_marginally_above_fdv_is_tolerated_as_timing_skew():
    m = _metrics(market_cap_usd=1_005_000_000.0, fully_diluted_valuation_usd=1_000_000_000.0)
    assert m.market_cap_to_fdv.value == pytest.approx(1.005)


def test_price_above_recorded_ath_gives_positive_distance():
    assert _metrics(price_usd=250.0).distance_from_ath_percent.value == pytest.approx(25.0)


def test_zero_atl_avoids_division_by_zero():
    m = _metrics(atl_usd=0)
    assert m.distance_from_atl_percent.value is None
    assert "All-time low" in m.distance_from_atl_percent.unavailable_reason


def test_missing_price_disables_ath_and_atl_distance():
    m = _metrics(price_usd=None)
    assert m.distance_from_ath_percent.value is None
    assert m.distance_from_atl_percent.value is None


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "12", True, -5.0])
def test_invalid_inputs_are_treated_as_missing(bad):
    m = _metrics(market_cap_usd=bad)
    assert m.volume_to_market_cap.value is None


def test_everything_missing_yields_all_null_with_reasons():
    m = calc.compute_metrics(
        price_usd=None, market_cap_usd=None, volume_24h_usd=None, circulating_supply=None,
        total_supply=None, max_supply=None, fully_diluted_valuation_usd=None, ath_usd=None, atl_usd=None,
    )
    for metric in vars(m).values():
        assert metric.value is None
        assert metric.unavailable_reason


# ---- supply classification -------------------------------------------------


def test_supply_capped():
    assert calc.classify_supply(21_000_000, None) == ("capped", [])
    assert calc.classify_supply(21_000_000, False)[0] == "capped"


def test_supply_unlimited_only_when_provider_says_so():
    assert calc.classify_supply(None, True)[0] == "unlimited"


def test_null_max_supply_without_flag_is_not_assumed_unlimited():
    assert calc.classify_supply(None, None)[0] == "not_reported"
    assert calc.classify_supply(None, False)[0] == "not_reported"
    assert calc.classify_supply(0, None)[0] == "not_reported"


def test_contradictory_flag_prefers_reported_max_supply_and_notes_it():
    supply_type, notes = calc.classify_supply(1_000, True)
    assert supply_type == "capped"
    assert len(notes) == 1


# ---- score -----------------------------------------------------------------


def _inputs(**overrides):
    args = dict(
        market_cap_usd=1_000_000_000.0, metrics=_metrics(), profile_present=True,
        has_description=True, has_homepage=True, has_whitepaper=True, has_explorer=True,
        has_repository=True, has_categories=True, genesis_date="2009-01-03",
        development=calc.DevelopmentInput(github_repo_count=1, stars=100, commit_count_4_weeks=120),
    )
    args.update(overrides)
    return calc.ScoreInputs(**args)


def _component(result, key):
    return next(c for c in result.components if c.key == key)


def test_weights_sum_to_100():
    result = calc.compute_fundamental_score(_inputs(), today=TODAY)
    assert sum(c.weight for c in result.components) == 100


def test_full_score_matches_hand_calculation():
    result = calc.compute_fundamental_score(_inputs(), today=TODAY)
    # market_size: $1B  -> 80          (w25)
    # liquidity: 5%     -> 100         (w20)
    # supply: 71.4%     -> 65 (>=50)   (w20)
    # development: 120  -> 100         (w15)
    # maturity: ~17.7y  -> 100         (w10)
    # information: 6/6  -> 100         (w10)
    expected = (25 * 80 + 20 * 100 + 20 * 65 + 15 * 100 + 10 * 100 + 10 * 100) / 100
    assert result.status == "scored"
    assert result.coverage_percent == 100.0
    assert result.score == pytest.approx(expected, abs=0.05)
    assert result.score == pytest.approx(88.0, abs=0.05)  # 2000+2000+1300+1500+1000+1000 = 8800 / 100


def test_component_points_add_up_to_score_when_fully_covered():
    result = calc.compute_fundamental_score(_inputs(), today=TODAY)
    assert sum(c.points for c in result.components) == pytest.approx(result.score, abs=0.1)


def test_missing_data_lowers_coverage_but_does_not_zero_the_component():
    result = calc.compute_fundamental_score(
        _inputs(development=calc.DevelopmentInput(), has_repository=False, genesis_date=None), today=TODAY
    )
    assert _component(result, "development_activity").available is False
    assert _component(result, "development_activity").subscore is None
    assert _component(result, "project_maturity").available is False
    assert result.coverage_percent == 75.0  # 100 - 15 - 10
    # has_repository=False -> information completeness is 5 of 6 items = 83.3.
    # Renormalised over the 75 available weight: (2000 + 2000 + 1300 + 10*83.33) / 75
    assert _component(result, "information_completeness").subscore == pytest.approx(83.3, abs=0.05)
    assert result.score == pytest.approx((25 * 80 + 20 * 100 + 20 * 65 + 10 * 500 / 6) / 75, abs=0.1)


def test_not_enough_data_returns_no_score():
    empty = calc.compute_metrics(
        price_usd=None, market_cap_usd=None, volume_24h_usd=None, circulating_supply=None,
        total_supply=None, max_supply=None, fully_diluted_valuation_usd=None, ath_usd=None, atl_usd=None,
    )
    result = calc.compute_fundamental_score(
        calc.ScoreInputs(market_cap_usd=None, metrics=empty, profile_present=False), today=TODAY
    )
    assert result.status == "not_enough_data"
    assert result.score is None
    assert result.message == "Not enough data"
    assert result.coverage_percent == 0.0


def test_coverage_below_minimum_gives_no_score_even_with_three_components():
    # market_size(25) + liquidity(20) only = 45 < 50 -> no score.
    result = calc.compute_fundamental_score(
        _inputs(
            profile_present=False, genesis_date=None, development=calc.DevelopmentInput(),
            metrics=_metrics(max_supply=None, fully_diluted_valuation_usd=None),
        ),
        today=TODAY,
    )
    assert result.coverage_percent == 45.0
    assert result.status == "not_enough_data"


@pytest.mark.parametrize(
    "market_cap,expected",
    [(2e10, 100), (1e10, 100), (5e9, 80), (1e9, 80), (5e8, 60), (1e8, 60), (5e7, 40), (1e7, 40),
     (5e6, 20), (1e6, 20), (5e5, 10)],
)
def test_market_size_bands(market_cap, expected):
    result = calc.compute_fundamental_score(_inputs(market_cap_usd=market_cap), today=TODAY)
    assert _component(result, "market_size").subscore == expected


@pytest.mark.parametrize(
    "volume,expected",
    [(1e6, 20), (5e6, 50), (5e7, 100), (2e8, 80), (5e8, 50), (0, 20)],
)
def test_liquidity_bands(volume, expected):
    # market cap $1B: 0.1% / 0.5% / 5% / 20% / 50% / 0%
    metrics = _metrics(volume_24h_usd=volume)
    result = calc.compute_fundamental_score(_inputs(metrics=metrics), today=TODAY)
    assert _component(result, "liquidity").subscore == expected


def test_supply_component_falls_back_to_fdv_ratio_without_max_supply():
    metrics = _metrics(max_supply=None)  # mcap/FDV = 71.4% -> 65
    result = calc.compute_fundamental_score(_inputs(metrics=metrics), today=TODAY)
    comp = _component(result, "supply_dilution")
    assert comp.subscore == 65
    assert "fully diluted" in comp.input_description


def test_supply_component_unavailable_without_max_supply_or_fdv():
    metrics = _metrics(max_supply=None, fully_diluted_valuation_usd=None)
    result = calc.compute_fundamental_score(_inputs(metrics=metrics), today=TODAY)
    assert _component(result, "supply_dilution").available is False


@pytest.mark.parametrize("commits,expected", [(150, 100), (100, 100), (50, 75), (30, 75), (12, 50), (3, 25), (0, 0)])
def test_development_bands(commits, expected):
    dev = calc.DevelopmentInput(github_repo_count=1, stars=10, commit_count_4_weeks=commits)
    result = calc.compute_fundamental_score(_inputs(development=dev), today=TODAY)
    assert _component(result, "development_activity").subscore == expected


def test_all_zero_developer_block_is_treated_as_no_data_not_zero_activity():
    dev = calc.DevelopmentInput(
        github_repo_count=1, stars=0, forks=0, subscribers=0, total_issues=0,
        pull_request_contributors=0, commit_count_4_weeks=0,
    )
    assert calc.development_data_available(dev) is False
    result = calc.compute_fundamental_score(_inputs(development=dev), today=TODAY)
    assert _component(result, "development_activity").available is False


def test_development_needs_a_linked_repository():
    dev = calc.DevelopmentInput(github_repo_count=0, stars=500, commit_count_4_weeks=50)
    assert calc.development_data_available(dev) is False


@pytest.mark.parametrize(
    "genesis,expected",
    [("2015-01-01", 100), ("2023-01-01", 75), ("2025-06-01", 50), ("2026-03-01", 25), ("2026-09-01", 10)],
)
def test_maturity_bands(genesis, expected):
    result = calc.compute_fundamental_score(_inputs(genesis_date=genesis), today=TODAY)
    assert _component(result, "project_maturity").subscore == expected


@pytest.mark.parametrize("genesis", [None, "", "not-a-date", "2030-01-01"])
def test_unparseable_or_future_genesis_date_is_unavailable(genesis):
    result = calc.compute_fundamental_score(_inputs(genesis_date=genesis), today=TODAY)
    assert _component(result, "project_maturity").available is False


def test_information_completeness_is_share_of_items_present():
    result = calc.compute_fundamental_score(
        _inputs(has_description=False, has_whitepaper=False, has_explorer=False), today=TODAY
    )
    assert _component(result, "information_completeness").subscore == 50.0  # 3 of 6


def test_score_excludes_price_action():
    """Distance from ATH and recent performance must not move the score."""
    a = calc.compute_fundamental_score(_inputs(metrics=_metrics(price_usd=20.0)), today=TODAY)
    b = calc.compute_fundamental_score(_inputs(metrics=_metrics(price_usd=190.0)), today=TODAY)
    assert a.score == b.score
    assert not any("ath" in c.key or "performance" in c.key for c in a.components)


def test_every_component_documents_its_rule_and_input():
    result = calc.compute_fundamental_score(_inputs(), today=TODAY)
    for c in result.components:
        assert c.rule and c.input_description and c.label


def test_result_carries_method_version_and_non_advice_disclaimer():
    result = calc.compute_fundamental_score(_inputs(), today=TODAY)
    assert result.method_version == calc.SCORE_METHOD_VERSION
    assert "not investment advice" in result.disclaimer


# ---- summary ---------------------------------------------------------------

_FORBIDDEN = re.compile(
    r"\b(buy|sell|hold|will (rise|fall|increase|decrease|grow)|guarantee[ds]?|profit|recommend\w*|undervalued|overvalued)\b",
    re.IGNORECASE,
)


def _summary(**overrides):
    args = dict(
        market_cap_rank=1, market_cap_usd=1_000_000_000.0, supply_type="capped", max_supply=21_000_000.0,
        metrics=_metrics(), categories=["Layer 1 (L1)"], asset_platform_id=None, genesis_date="2009-01-03",
        github_repo_count=1,
        development=calc.DevelopmentInput(github_repo_count=1, stars=10, commit_count_4_weeks=40),
    )
    args.update(overrides)
    return calc.build_summary(**args)


def test_summary_contains_factual_statements_from_the_data():
    text = " ".join(i.text for i in _summary())
    assert "Ranked #1" in text and "$1.00B" in text
    assert "5.00% of market cap" in text
    assert "capped at 21,000,000" in text and "71.4% is currently in circulation" in text
    assert "75.0% below its recorded all-time high" in text
    assert "genesis date: 2009-01-03" in text
    assert "40 commits" in text


def test_summary_never_contains_advice_or_predictions():
    variants = [
        _summary(), _summary(supply_type="unlimited", max_supply=None),
        _summary(metrics=_metrics(price_usd=500.0)),
        _summary(metrics=_metrics(price_usd=None)),
    ]
    for items in variants:
        for item in items:
            assert not _FORBIDDEN.search(item.text), item.text


def test_summary_unlimited_and_unknown_supply_wording():
    unlimited = " ".join(i.text for i in _summary(supply_type="unlimited", max_supply=None, metrics=_metrics(max_supply=None)))
    unknown = " ".join(i.text for i in _summary(supply_type="not_reported", max_supply=None, metrics=_metrics(max_supply=None)))
    assert "unlimited supply" in unlimited
    assert "supply cap is unknown" in unknown


def test_summary_omits_statements_without_inputs():
    items = _summary(metrics=_metrics(price_usd=None, volume_24h_usd=None), market_cap_rank=None, genesis_date=None)
    text = " ".join(i.text for i in items)
    assert "all-time high" not in text and "trading volume" not in text and "Ranked" not in text
    assert "genesis" not in text


def test_summary_does_not_state_gaps_as_facts_when_sections_are_missing():
    no_profile = " ".join(i.text for i in _summary(profile_present=False))
    assert "repositor" not in no_profile and "Listed under" not in no_profile
    no_market = " ".join(i.text for i in _summary(market_present=False))
    assert "supply" not in no_market.lower()


def test_summary_reports_repos_without_activity_figures_honestly():
    items = _summary(github_repo_count=2, development=calc.DevelopmentInput(github_repo_count=2))
    text = " ".join(i.text for i in items)
    assert "2 linked repositories" in text and "no activity figures" in text


def test_summary_says_no_repository_only_when_profile_present_and_none_linked():
    items = _summary(github_repo_count=0, development=calc.DevelopmentInput())
    assert any("No code repository is linked" in i.text for i in items)
