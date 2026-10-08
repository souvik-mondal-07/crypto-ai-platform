"""
CryptoCompare / CoinDesk Data news provider (legacy `data/v2/news` endpoint).

A public REST API — no scraping. Article text is the provider's own;
this module only maps and validates it. The optional API key is sent as
the documented `authorization: Apikey ...` header and never logged.
"""

import html
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.providers.errors import ProviderRateLimitError, ProviderResponseError
from app.providers.http import request_json
from app.providers.news.base import NewsProvider
from app.providers.news.models import NewsFetchResult, NormalizedNewsArticle

logger = logging.getLogger("crypto_ai_platform.providers.cryptocompare_news")

PROVIDER_NAME = "cryptocompare"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(value: Any, max_chars: Optional[int] = None) -> Optional[str]:
    """Strip HTML, unescape entities, collapse whitespace, optionally truncate at a word boundary."""
    if not isinstance(value, str):
        return None
    text = _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", value))).strip()
    if not text:
        return None
    if max_chars and len(text) > max_chars:
        cut = text[:max_chars].rsplit(" ", 1)[0].rstrip(" ,.;:-")
        text = (cut or text[:max_chars]) + "…"
    return text


def _split_pipe(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    seen: list[str] = []
    for part in value.split("|"):
        part = part.strip()
        if part and part not in seen:
            seen.append(part)
    return seen


def _http_url(value: Any) -> Optional[str]:
    if isinstance(value, str):
        value = value.strip()
        if value.lower().startswith(("http://", "https://")):
            return value
    return None


def map_article(raw: Any, description_max_chars: int = 400) -> Optional[NormalizedNewsArticle]:
    """
    Map one raw entry, or return None if it is unusable (not an object,
    no title, no real http(s) URL, or no valid publication time). Such
    entries are dropped and counted — never repaired with invented values.
    """
    if not isinstance(raw, dict):
        return None

    title = clean_text(raw.get("title"))
    url = _http_url(raw.get("url")) or _http_url(raw.get("guid"))
    published_on = raw.get("published_on")
    if not title or not url:
        return None
    if isinstance(published_on, bool) or not isinstance(published_on, (int, float)) or published_on <= 0:
        return None
    try:
        published_at = datetime.fromtimestamp(float(published_on), tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None

    source_info = raw.get("source_info") if isinstance(raw.get("source_info"), dict) else {}
    source = clean_text(source_info.get("name")) or clean_text(raw.get("source"))
    if not source:
        return None

    raw_id = raw.get("id")
    provider_id = str(raw_id).strip() if raw_id not in (None, "", False) else None
    lang = raw.get("lang")

    return NormalizedNewsArticle(
        provider=PROVIDER_NAME,
        provider_article_id=provider_id,
        title=title,
        url=url,
        source=source,
        published_at=published_at,
        description=clean_text(raw.get("body"), description_max_chars),
        image_url=_http_url(raw.get("imageurl")),
        author=None,  # this endpoint does not report an author
        categories=_split_pipe(raw.get("categories")),
        tags=_split_pipe(raw.get("tags")),
        language=lang.strip().lower() if isinstance(lang, str) and lang.strip() else None,
    )


def map_response(payload: Any, description_max_chars: int = 400) -> NewsFetchResult:
    """Validate the response envelope and map every entry."""
    if not isinstance(payload, dict):
        raise ProviderResponseError("cryptocompare news: unexpected response shape")

    if str(payload.get("Response", "")).lower() == "error":
        message = str(payload.get("Message", ""))
        if "rate limit" in message.lower():
            raise ProviderRateLimitError("cryptocompare news rate limit exceeded")
        raise ProviderResponseError("cryptocompare news: provider reported an error")

    data = payload.get("Data")
    if not isinstance(data, list):
        raise ProviderResponseError("cryptocompare news: missing article list")

    articles: list[NormalizedNewsArticle] = []
    malformed = 0
    for entry in data:
        article = map_article(entry, description_max_chars)
        if article is None:
            malformed += 1
        else:
            articles.append(article)

    articles.sort(key=lambda a: a.published_at, reverse=True)
    if malformed:
        logger.warning("cryptocompare news: dropped %d malformed article(s)", malformed)
    return NewsFetchResult(
        articles=articles,
        malformed_count=malformed,
        oldest_published_at=min((a.published_at for a in articles), default=None),
    )


class CryptoCompareNewsProvider(NewsProvider):
    provider_name = PROVIDER_NAME

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None) -> None:
        settings = get_settings()
        self._base_url = settings.CRYPTOCOMPARE_API_BASE_URL.rstrip("/")
        self._api_key = settings.CRYPTOCOMPARE_API_KEY or None
        self._default_language = settings.NEWS_LANGUAGE
        self._description_max_chars = settings.NEWS_DESCRIPTION_MAX_CHARS
        self._http_client = http_client

    def _headers(self) -> dict[str, str]:
        return {"authorization": f"Apikey {self._api_key}"} if self._api_key else {}

    async def fetch_latest(
        self, *, before: Optional[datetime] = None, language: Optional[str] = None
    ) -> NewsFetchResult:
        params: dict[str, Any] = {
            "lang": (language or self._default_language).upper(),
            "sortOrder": "latest",
        }
        if before is not None:
            params["lTs"] = int(before.timestamp())

        url = f"{self._base_url}/data/v2/news/"
        if self._http_client is not None:
            payload = await request_json(
                self._http_client, "GET", url, params=params,
                headers=self._headers(), provider_name=PROVIDER_NAME,
            )
        else:
            async with httpx.AsyncClient() as client:
                payload = await request_json(
                    client, "GET", url, params=params,
                    headers=self._headers(), provider_name=PROVIDER_NAME,
                )
        return map_response(payload, self._description_max_chars)
