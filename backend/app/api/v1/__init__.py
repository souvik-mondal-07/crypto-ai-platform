import logging

from fastapi import APIRouter

from app.api.v1 import ai_analysis, auth, coins, decisions, health, market, news, predictions
from app.config import get_settings

logger = logging.getLogger("crypto_ai_platform")

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(coins.router)
api_router.include_router(market.router)
api_router.include_router(news.router)
api_router.include_router(predictions.router)
api_router.include_router(decisions.router)
api_router.include_router(ai_analysis.router)

# Dev-only sync trigger — only registered (route exists at all) when
# explicitly enabled. See app/api/v1/dev_sync.py: this endpoint does
# not require authentication even though auth now exists (Step 4) —
# it's a local-development convenience, not a user-facing feature, so
# the route being entirely absent by default remains the safeguard
# rather than requiring a login.
if get_settings().ENABLE_DEV_SYNC_ENDPOINT:
    from app.api.v1 import dev_sync

    api_router.include_router(dev_sync.router)
    logger.warning(
        "ENABLE_DEV_SYNC_ENDPOINT is true — the development-only market "
        "sync trigger (/dev/sync/market) is active. Do not enable this "
        "in a publicly reachable deployment."
    )

__all__ = ["api_router"]
