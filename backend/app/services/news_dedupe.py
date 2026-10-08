"""
Deterministic article identity (Phase 12).

Two keys are derived for every article:

  * `dedupe_key` — what makes two records "the same article". Built from
    the normalized article URL (so the same story from two providers, or
    the same URL with different tracking parameters, collapses to one
    record). If a URL is somehow missing, it falls back to
    publisher + normalized title + publication day.
  * `news_id` — the public identifier. `<provider>:<provider article id>`
    when the provider supplies a stable id, otherwise derived from the
    dedupe key.
"""

import hashlib
import re
from datetime import datetime
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit

from app.providers.news.models import NormalizedNewsArticle

_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "igshid", "cmpid", "source"}
_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    port = f":{parts.port}" if parts.port and parts.port not in (80, 443) else ""
    path = parts.path.rstrip("/") or ""
    query = urlencode(
        sorted(
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=False)
            if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
        )
    )
    # http/https and fragments are deliberately ignored for identity.
    return f"{host}{port}{path}" + (f"?{query}" if query else "")


def normalize_title(title: str) -> str:
    return _NON_WORD.sub(" ", title.lower()).strip()


def build_dedupe_key(
    url: Optional[str], source: str, title: str, published_at: datetime
) -> str:
    if url and url.strip():
        basis = "url:" + normalize_url(url)
    else:
        basis = f"meta:{source.strip().lower()}|{normalize_title(title)}|{published_at.date().isoformat()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def build_news_id(article: NormalizedNewsArticle, dedupe_key: str) -> str:
    if article.provider_article_id:
        return f"{article.provider}:{article.provider_article_id}"
    return f"{article.provider}:h{dedupe_key[:20]}"
