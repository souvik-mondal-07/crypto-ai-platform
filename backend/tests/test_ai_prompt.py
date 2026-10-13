"""Prompt builder and structured payload (Phase 15)."""

import json

from app.ai.payload import availability_of, collect_numbers, insufficient_reason, unavailable
from app.ai.prompts.market_analysis_prompt import (
    PROMPT_VERSION, SYSTEM_INSTRUCTION, build_market_analysis_prompt, render_payload,
)
from tests.ai_fixtures import available_payload, payload_without_prediction


def test_prompt_version_is_set():
    assert PROMPT_VERSION == "1.0"


def test_prompt_contains_the_structured_data():
    prompt = build_market_analysis_prompt(available_payload())
    for needle in ("BTC", "64000.0", "\"decision\": \"BUY\"", "\"risk\"", "\"sentiment\"", "ExampleWire"):
        assert needle in prompt
    # The instructions mention the tag too, so take the LAST opening tag: that is the data block.
    body = prompt.rsplit("<analysis_data>", 1)[1].split("</analysis_data>")[0]
    assert json.loads(body)["decision"]["decision"] == "BUY"


def test_prompt_is_deterministic():
    assert build_market_analysis_prompt(available_payload()) == build_market_analysis_prompt(available_payload())
    assert render_payload({"b": 1, "a": 2}) == render_payload({"a": 2, "b": 1})


def test_unavailable_fields_are_represented_explicitly_not_as_defaults():
    payload = payload_without_prediction()
    assert payload["prediction"] == {"available": False, "reason": "Prediction engine unavailable"}
    rendered = render_payload(payload)
    assert "Prediction engine unavailable" in rendered
    # Nothing was coerced to a stand-in value.
    assert payload["prediction"].get("direction") is None and payload["prediction"].get("confidence") is None


def test_system_instruction_forbids_invention_overrides_and_price_predictions():
    text = SYSTEM_INSTRUCTION.lower()
    for rule in (
        "only the supplied json", "do not invent", "never produce a new price prediction",
        "official decision", "never state or imply a different buy/hold/sell", "available\": false",
        "guaranteed profit", "do not recompute",
    ):
        assert rule in text, rule


def test_prompt_asks_for_no_exact_future_price_or_independent_values():
    text = SYSTEM_INSTRUCTION.lower()
    assert "exact future price" in text
    for banned in ("predict the price of", "estimate the current price", "what is the current price"):
        assert banned not in text


def test_availability_and_insufficient_data_rules():
    avail = availability_of(payload_without_prediction())
    assert avail["prediction"].available is False and avail["market"].available is True
    assert insufficient_reason(available_payload()) is None
    assert insufficient_reason(payload_without_prediction()) is None  # other modules can still be explained

    empty = available_payload()
    for k in ("technical", "fundamental", "news", "sentiment", "prediction"):
        empty[k] = unavailable("nope")
    assert "Not enough platform data" in insufficient_reason(empty)

    no_market = available_payload()
    no_market["market"] = unavailable("no snapshot")
    assert "market" in insufficient_reason(no_market)


def test_collect_numbers_reads_numbers_in_values_and_strings():
    nums = collect_numbers({"a": 64000.0, "b": {"c": [1.5]}, "d": "range 63,000 to 66,000", "e": True})
    assert {64000.0, 1.5, 63000.0, 66000.0} <= set(nums)
    assert 1.0 not in nums  # booleans are not numbers
