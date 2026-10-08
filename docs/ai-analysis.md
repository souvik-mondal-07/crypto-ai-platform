# Gemini AI Analysis (Phase 15)

Gemini (`gemini-3.1-flash-lite`) is an **explanation layer**. It reads the platform's own structured
analysis and writes a plain-language explanation. It never decides, never predicts a price, and is
never required for the rest of the app to work.

```
Market ─┐
Technical ─┤
Fundamental ┤
News ───────┼─> structured payload ─> GeminiService ─> validation ─> ai_analysis (cache) ─> API ─> React
Sentiment ──┤      (app/ai/payload.py)
ML prediction ┤
Phase 14 Risk & Decision ┘  (official BUY/HOLD/SELL — copied into the payload and the stored snapshot)
```

| File | Role |
|---|---|
| `backend/app/config/gemini_config.py` | `GeminiConfig` (key, model, timeout, max tokens, temperature, retries) built from `Settings` |
| `backend/app/ai/prompts/market_analysis_prompt.py` | System instruction + prompt builder, `PROMPT_VERSION` |
| `backend/app/ai/payload.py` | Pure builders for the structured input; unavailable data becomes `{"available": false, "reason": ...}` |
| `backend/app/ai/schemas/ai_analysis.py` | Gemini output schema + API response models |
| `backend/app/ai/validation.py` | Rejects empty sections, a contradicting BUY/SELL/HOLD, and invented forward-looking prices |
| `backend/app/services/gemini_service.py` | The only module that calls the SDK: request, parsing, timeout, retries, error classification |
| `backend/app/services/ai_analysis_service.py` | Orchestration, caching, cooldown, de-duplication, backoff |
| `backend/app/repositories/ai_analysis_repository.py` | `ai_analysis` collection |

## Configuration (backend only)

`GEMINI_API_KEY`, `GEMINI_MODEL=gemini-3.1-flash-lite`, `GEMINI_TIMEOUT_SECONDS`, `GEMINI_MAX_OUTPUT_TOKENS`,
`GEMINI_TEMPERATURE`, `GEMINI_MAX_RETRIES`, `GEMINI_RETRY_BACKOFF_SECONDS`, `AI_ANALYSIS_TTL_SECONDS`,
`AI_ANALYSIS_MIN_REGENERATE_INTERVAL_SECONDS`, `AI_ANALYSIS_MAX_CONCURRENT_GENERATIONS`. The key is never sent
to the frontend (there is no `VITE_` variable for it). SDK: `google-genai` (`from google import genai`).

## API

| Method | Path | Behaviour |
|---|---|---|
| GET | `/api/v1/ai-analysis/{coin_id}` | Latest stored explanation. Never calls Gemini. 404 `AI_ANALYSIS_NOT_FOUND` if none. |
| POST | `/api/v1/ai-analysis/{coin_id}/generate` | Fresh stored one if it exists, else one Gemini call. `?force_refresh=true` asks for a new one (cooldown applies). Requires login. |

Error codes: `AI_NOT_CONFIGURED`, `AI_AUTH_FAILED`, `AI_UNAVAILABLE`, `AI_TIMEOUT` (504), `AI_RATE_LIMITED` (429),
`AI_ANALYSIS_COOLDOWN` (429), `AI_INVALID_RESPONSE`, `AI_REQUEST_REJECTED`, `AI_INSUFFICIENT_DATA` (422). Messages are
user-safe; keys and stack traces are never returned.

## Caching and cost protection

* Stored in `ai_analysis` (insert-only): `coin_id, model, model_version, prompt_version, analysis, decision_snapshot,
  data_availability, source_data_timestamp, generated_at, expires_at, status`, plus latency/token metadata.
  Indexes: `idx_aianalysis_coin_generatedat`, `idx_aianalysis_prompt_model_generatedat`.
* Reused until `expires_at` (default 30 min) **or** until the Phase 14 decision changes materially (decision/status/risk
  level changed, or score/confidence moved ≥ 15 points) — then it is marked `is_outdated`.
* One generation at a time per coin (concurrent requests share one call), a global concurrency cap, a per-coin
  regeneration cooldown, backoff after a 429/failure, and no retry for auth or rate-limit errors.
* The frontend reads first and generates only when nothing usable is stored; re-renders never call the backend.

## What keeps Gemini honest

The prompt forbids invented data, prices and news; the payload carries only platform values; validation rejects output
that tells the reader to take a different action than the official decision, or states a forward-looking dollar figure
that is not in the supplied data. These checks are narrow phrase-based guards, not a guarantee — the UI always labels the
text as AI-generated and the official decision always comes from Phase 14.
