"""Gemini output schema and validation (Phase 15)."""

import pytest
from pydantic import ValidationError

from app.ai.schemas.ai_analysis import AI_DISCLAIMER, AIAnalysisContent, GeminiAnalysisOutput
from app.ai.validation import (
    AnalysisValidationError, find_decision_override, find_unsupported_price_claim, validate_analysis,
)
from tests.ai_fixtures import available_payload, good_output


def test_valid_structured_output_passes():
    out = validate_analysis(good_output(), available_payload())
    assert out.summary and out.bullish_factors == ["Bullish trend", "Positive sentiment"]


def test_missing_fields_are_rejected_by_the_schema():
    data = good_output().model_dump()
    del data["risk_analysis"]
    with pytest.raises(ValidationError):
        GeminiAnalysisOutput(**data)


def test_wrong_types_are_rejected():
    data = good_output().model_dump()
    data["bullish_factors"] = "not a list"
    with pytest.raises(ValidationError):
        GeminiAnalysisOutput(**data)


def test_malformed_json_is_not_a_valid_output():
    with pytest.raises(ValidationError):
        GeminiAnalysisOutput.model_validate_json("{not json")


def test_empty_sections_are_rejected():
    with pytest.raises(AnalysisValidationError):
        validate_analysis(good_output(technical_analysis="   "), available_payload())


def test_lengths_are_bounded_and_blank_items_dropped():
    out = validate_analysis(
        good_output(summary="x" * 5000, key_risks=["a"] * 20 + ["   "]), available_payload()
    )
    assert len(out.summary) <= 1800 and len(out.key_risks) <= 8 and "" not in out.key_risks


def test_decision_override_is_rejected():
    with pytest.raises(AnalysisValidationError, match="contradicts the official decision"):
        validate_analysis(good_output(summary="Despite the BUY label, you should sell immediately."), available_payload("BUY"))


def test_explaining_the_official_decision_is_allowed():
    assert find_decision_override("The engine's official decision is BUY.", "BUY") is None
    assert find_decision_override("Conflicting evidence exists, but the official decision stays HOLD.", "HOLD") is None
    assert find_decision_override("I recommend you hold.", "BUY") is not None


def test_decision_explanation_must_mention_the_official_decision():
    with pytest.raises(AnalysisValidationError, match="does not mention"):
        validate_analysis(good_output(decision_explanation="Most signals are aligned."), available_payload("BUY"))


def test_invented_future_price_is_rejected():
    with pytest.raises(AnalysisValidationError, match="unsupported price"):
        validate_analysis(good_output(summary="Bitcoin will reach $150,000 by year end."), available_payload())


def test_quoting_supplied_numbers_is_allowed():
    assert find_unsupported_price_claim("The model's range is $63,000 to $66,000.", [63000.0, 66000.0]) is None
    assert find_unsupported_price_claim("Market cap of $1.2 trillion could be volatile.", [1.2e12]) is None
    assert find_unsupported_price_claim("ETH will reach $8,000.", [3000.0]) is not None


def test_no_decision_means_any_buy_sell_hold_instruction_is_rejected():
    payload = available_payload()
    payload["decision"] = {"available": False, "reason": "insufficient", "status": "INSUFFICIENT_DATA"}
    with pytest.raises(AnalysisValidationError):
        validate_analysis(good_output(summary="You should buy now."), payload)


def test_content_model_carries_the_server_disclaimer():
    content = AIAnalysisContent(**good_output().model_dump())
    assert content.disclaimer == AI_DISCLAIMER
    assert "not a guarantee of future performance or financial advice" in AI_DISCLAIMER
