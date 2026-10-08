"""AI analysis endpoints (Phase 15). Logic lives in AIAnalysisService; this layer only routes.

    GET  /ai-analysis/{coin_id}                 latest STORED explanation; never calls Gemini (404 if none yet)
    POST /ai-analysis/{coin_id}/generate        stored fresh explanation, else a new Gemini one
                                                (?force_refresh=true asks for a new one, with a cooldown)

Gemini only EXPLAINS the Phase 14 decision; it cannot change BUY/HOLD/SELL. Generation costs money, so
POST requires a signed-in user (the stored result is readable by the same pages that already show the
decision). The Gemini API key is read server-side only and never appears in any response.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.ai.schemas.ai_analysis import AIAnalysisResponse
from app.core.dependencies import get_current_user
from app.services.ai_analysis_service import AIAnalysisService

router = APIRouter(prefix="/ai-analysis", tags=["AI Analysis"])


def _service() -> AIAnalysisService:
    return AIAnalysisService()


# Static suffix route first so "generate" can never be captured as part of a coin id.
@router.post("/{coin_id}/generate", response_model=AIAnalysisResponse)
async def generate_ai_analysis(
    coin_id: str,
    force_refresh: bool = Query(False, description="Generate a new explanation even if a fresh one is stored (cooldown applies)"),
    _user: dict[str, Any] = Depends(get_current_user),
) -> AIAnalysisResponse:
    """A fresh stored explanation if one exists; otherwise one Gemini call explaining the Phase 14 result."""
    return await _service().generate(coin_id, force=force_refresh)


@router.get("/{coin_id}", response_model=AIAnalysisResponse)
async def get_ai_analysis(coin_id: str) -> AIAnalysisResponse:
    """The latest stored explanation. Never calls Gemini; `is_stale` / `is_outdated` say if it should be regenerated."""
    return await _service().get_latest(coin_id)
