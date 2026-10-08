"""Shared pagination validation — bounds page/limit so no route accepts unbounded values."""

import math

MAX_LIMIT = 250
DEFAULT_LIMIT = 100


def clamp_pagination(page: int, limit: int) -> tuple[int, int]:
    """Clamp page/limit to safe bounds. Never trust raw query params directly."""
    safe_page = max(1, page)
    safe_limit = min(max(1, limit), MAX_LIMIT)
    return safe_page, safe_limit


def total_pages(total: int, limit: int) -> int:
    if limit <= 0:
        return 0
    return math.ceil(total / limit)
