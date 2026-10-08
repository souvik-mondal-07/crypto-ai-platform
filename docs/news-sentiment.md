# Phase 12 — News & Sentiment

Real cryptocurrency news, coin association, NLP sentiment, and descriptive
aggregation. **Descriptive only**: no prediction, BUY/HOLD/SELL, or risk score.

## Data flow

```
NewsProvider(s) ─► NormalizedNewsArticle ─► dedupe keys + coin association ─► MongoDB `news`
                                                                                │
                              SentimentModelService (FinBERT, loaded once) ◄────┤ (pending articles)
                                                                                ▼
                       /api/v1/news · /news/{id} · /news/sources · /coins/{id}/news · /coins/{id}/sentiment
```

Ingestion + sentiment run in a background asyncio loop
(`NewsRefreshScheduler`, same pattern as the market scheduler — no
Redis/Celery). `run_cycle_once()` is callable from a future job runner.
Manual trigger (dev only): `POST /api/v1/dev/sync/news`.

## Provider

`app/providers/news/` — `NewsProvider` interface; `CryptoCompareNewsProvider`
uses the public CoinDesk Data / CryptoCompare legacy endpoint
`GET /data/v2/news/` (no scraping). Key is optional (`CRYPTOCOMPARE_API_KEY`),
sent only as a server-side header. To add a source: implement `NewsProvider`
and append it in `get_news_providers()`.

Stored description is a short excerpt (`NEWS_DESCRIPTION_MAX_CHARS`), always
with the original `source_url`.

## Deduplication

`dedupe_key` = hash of the normalized URL (host without `www`, no
scheme/fragment/trailing slash, tracking params removed); metadata hash
(publisher + title + day) only if a URL is missing. `news_id` =
`<provider>:<provider article id>` when supplied. Both are unique-indexed;
writes are upserts on either, so re-syncing never duplicates. Re-fetching an
article only merges tags/related coins — title/description/sentiment are
never overwritten.

## Coin association (heuristic — read this)

From the provider's own tags: ALL-CAPS tickers in `categories` (topic words
like `Exchange`, `ICO`, `NFT` are excluded) plus `$CASHTAGS` in the headline.
A ticker resolves to the highest-ranked **active, ranked** coin with that
symbol (tickers are not unique across the 21k-coin universe); tickers matching
only unranked coins are not associated. Coin names in free text are
deliberately **not** matched (false positives: "Cosmos", "Polygon"). Articles
that can't be placed appear only in the global feed. Consequence: coverage
depends on the provider tagging an article, and a sentiment for an obscure
coin can legitimately be "insufficient data".

## Sentiment

- Model: `ProsusAI/finbert` via `transformers` + `torch`
  (`app/services/sentiment_model.py`). Loaded lazily, **once per process**,
  weights cached on disk by Hugging Face; inference runs in a worker thread.
- Replaceable: implement `SentimentClassifier`, register in `_BACKENDS`,
  set `SENTIMENT_MODEL_BACKEND`.
- Load failure → status `unavailable` (retry after `SENTIMENT_MODEL_RETRY_SECONDS`);
  articles stay `pending`. **No fallback produces made-up sentiment.**
- Article score = P(positive) − P(negative) ∈ [−1, 1]; label = most probable class.
- Sentiment is per *article*; an article tagged with several coins contributes
  the same tone to each.

### Aggregation (`app/services/sentiment_aggregation.py`)

Windows: `24h` (4 h buckets) and `7d` (daily buckets), by `published_at`.
Counts, percentages, mean score; label = positive/negative if |mean| ≥ 0.15
else neutral; fewer than `SENTIMENT_MIN_ARTICLES` (3) analyzed articles →
`status: "insufficient_data"` with **no label and no trend**. Trend compares
the window with the previous equal window (±0.10 threshold) and describes the
*tone of coverage*, not price.

## Setup

```bash
pip install -r backend/requirements.txt      # includes transformers + torch (CPU build: see requirements.txt)
# optional: CRYPTOCOMPARE_API_KEY in backend/.env
# first sentiment run downloads ~440 MB of model weights (set SENTIMENT_LOCAL_FILES_ONLY=true afterwards to forbid network)
pytest -q                 # unit tests (no network, no model)
pytest -m integration     # real FinBERT check (needs the model)
```

`SENTIMENT_ENABLED=false` / `NEWS_REFRESH_ENABLED=false` switch the pieces off.
The `sentiment` MongoDB collection from Step 2 is intentionally unused:
aggregates are computed on request from indexed `news` documents.
