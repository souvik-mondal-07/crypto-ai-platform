"""Validation of Gemini's output BEFORE it is stored or returned (Phase 15).

Structured output already guarantees the JSON shape; this module enforces what the shape cannot:

* every text section is present and not empty (an unavailable section must still say so);
* lengths are bounded;
* Gemini does not tell the reader to BUY/SELL/HOLD something other than the official Phase 14 decision;
* Gemini does not state a forward-looking dollar figure that is not in the supplied data
  (i.e. an invented price prediction/target).

The checks are deliberately narrow, phrase-based guards: a false positive costs one retry, a false
negative would put an invented price or a contradicting call in front of the user.
"""

import re
from typing import Any, Optional

from app.ai.payload import collect_numbers
from app.ai.schemas.ai_analysis import GeminiAnalysisOutput

TEXT_FIELDS = (
    "summary", "market_analysis", "technical_analysis", "fundamental_analysis", "sentiment_analysis",
    "prediction_analysis", "risk_analysis", "decision_explanation", "data_quality",
)
LIST_FIELDS = ("bullish_factors", "bearish_factors", "key_risks", "uncertainties")

MAX_TEXT_CHARS = 1800
MAX_LIST_ITEMS = 8
MAX_ITEM_CHARS = 400

_DECISIONS = ("BUY", "HOLD", "SELL")


class AnalysisValidationError(ValueError):
    """Gemini's output is structurally valid JSON but unacceptable (message is for logs, not users)."""


# -- advice / decision override ------------------------------------------------------------------

_ADVICE_RE = re.compile(
    r"\b(?:i|we|you)?\s*(?:strongly\s+)?"
    r"(?:recommend|recommends|advise|advises|suggest|suggests|should|ought\s+to|would\s+(?:buy|sell|hold)|"
    r"consider|better\s+to|time\s+to|go\s+ahead\s+and|decision\s+(?:is|should\s+be)|rating\s+(?:is|of)|"
    r"overrid\w+|chang\w+\s+the\s+decision\s+to|upgrad\w+\s+to|downgrad\w+\s+to)"
    r"[^.!?\n]{0,40}?\b(buy|sell|hold)\b",
    re.IGNORECASE,
)


def find_decision_override(text: str, official: Optional[str]) -> Optional[str]:
    """A BUY/SELL/HOLD instruction that differs from the official decision (or any, when there is none)."""
    for match in _ADVICE_RE.finditer(text):
        said = match.group(1).upper()
        if said != official:
            return match.group(0).strip()
    return None


# -- invented price claims -----------------------------------------------------------------------

_MONEY_RE = re.compile(
    r"\$\s?(\d[\d,]*(?:\.\d+)?)\s?(trillion|billion|million|thousand|tn|bn|mn|[tbmk])?\b", re.IGNORECASE
)
_SCALE = {"trillion": 1e12, "tn": 1e12, "t": 1e12, "billion": 1e9, "bn": 1e9, "b": 1e9,
          "million": 1e6, "mn": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
# Words that mark a dollar figure as a statement about the FUTURE rather than a quoted fact.
_FORWARD_RE = re.compile(
    r"(?:\bwill\b|\bwould\b|\bcould\b|\bmay\b|\bmight\b|\bexpect\w*|\bforecast\w*|\bproject\w*|\bpredict\w*|"
    r"\btarget\w*|\bpotential\b|\bupside\b|\breach\w*|\bhit\b|\bsurge\w*|\brally\w*|\bclimb\w*|\bdrop\w*|"
    r"\bfall\b|\bfall\w*\s+to|\bheaded\b|\bheading\b)",
    re.IGNORECASE,
)


def _matches_payload(amount: float, numbers: list[float]) -> bool:
    """True when `amount` equals a supplied number within rounding (so quoting real data is fine)."""
    for n in numbers:
        if n == 0:
            continue
        for candidate in (n, n / 1e3, n / 1e6, n / 1e9, n / 1e12):
            if abs(candidate - amount) <= 0.015 * abs(candidate) + 0.006:
                return True
    return False


def find_unsupported_price_claim(text: str, numbers: list[float]) -> Optional[str]:
    """A forward-looking dollar figure that does not appear (within rounding) in the supplied data."""
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        if not _FORWARD_RE.search(sentence):
            continue
        for m in _MONEY_RE.finditer(sentence):
            amount = float(m.group(1).replace(",", ""))
            unit = (m.group(2) or "").lower()
            scaled = amount * _SCALE.get(unit, 1.0)
            if not (_matches_payload(scaled, numbers) or _matches_payload(amount, numbers)):
                return sentence.strip()[:160]
    return None


# -- entry point ---------------------------------------------------------------------------------


def validate_analysis(output: GeminiAnalysisOutput, payload: dict[str, Any]) -> GeminiAnalysisOutput:
    """Return the output (trimmed to bounds) or raise `AnalysisValidationError`."""
    data = output.model_dump()

    for name in TEXT_FIELDS:
        value = (data[name] or "").strip()
        if not value:
            raise AnalysisValidationError(f"Field '{name}' is empty.")
        data[name] = value[:MAX_TEXT_CHARS]

    for name in LIST_FIELDS:
        items = [str(i).strip()[:MAX_ITEM_CHARS] for i in (data[name] or []) if str(i).strip()]
        data[name] = items[:MAX_LIST_ITEMS]

    decision_section = payload.get("decision") or {}
    official = decision_section.get("decision") if decision_section.get("available") else None

    numbers = collect_numbers(payload)
    all_text = [data[n] for n in TEXT_FIELDS] + [i for n in LIST_FIELDS for i in data[n]]
    for text in all_text:
        override = find_decision_override(text, official)
        if override:
            raise AnalysisValidationError(f"Output contradicts the official decision ({official}): '{override}'.")
        claim = find_unsupported_price_claim(text, numbers)
        if claim:
            raise AnalysisValidationError(f"Output contains an unsupported price figure: '{claim}'.")

    if official in _DECISIONS and official.lower() not in data["decision_explanation"].lower():
        raise AnalysisValidationError("decision_explanation does not mention the official decision.")

    return GeminiAnalysisOutput(**data)


__all__ = ["AnalysisValidationError", "validate_analysis", "find_decision_override", "find_unsupported_price_claim"]
