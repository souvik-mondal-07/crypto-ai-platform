"""Price-alert business logic and evaluation (Phase 16).

Two parts:

* `AlertService` — CRUD for the authenticated user's alerts.
* `AlertEvaluationService` — compares ACTIVE alerts with the market snapshots stored in
  MongoDB. It is a plain async service with NO scheduler of its own: the user-triggered
  `POST /alerts/check` runs it for one user, and Phase 18's production scheduler can call
  `evaluate()` for everyone. An alert is only ever marked TRIGGERED when a real, fresh,
  usable price was read and the condition actually held at that price.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from bson import ObjectId

from app.core.exceptions import AppError
from app.repositories.alert_repository import AlertRepository
from app.repositories.coin_repository import CoinRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.schemas.alerts import (
    AlertCheckResponse,
    AlertCreateRequest,
    AlertDeleteResponse,
    AlertListResponse,
    AlertResponse,
    AlertUpdateRequest,
)
from app.schemas.converters import STALE_AFTER
from app.services.portfolio_calculations import usable_price
from app.services.user_feature_common import as_aware, parse_object_id, require_coin, utcnow
from app.utils.pagination import clamp_pagination

logger = logging.getLogger("crypto_ai_platform.services.alerts")

MAX_ALERTS_PER_USER = 100
#: Upper bound on alerts examined in one evaluation pass (the next pass picks up the rest).
EVALUATION_BATCH = 2000
VALID_STATUSES = ("ACTIVE", "TRIGGERED", "DISABLED", "EXPIRED")


def condition_met(condition: str, price: float, target_price: float) -> bool:
    """ABOVE: price strictly greater than the target. BELOW: price strictly less than the target."""
    if condition == "ABOVE":
        return price > target_price
    if condition == "BELOW":
        return price < target_price
    return False


def _alert_to_response(doc: dict[str, Any], coin: Optional[dict[str, Any]], current_price: Optional[float]) -> AlertResponse:
    coin = coin or {}
    return AlertResponse(
        id=str(doc["_id"]),
        coin_id=str(doc["coin_id"]),
        name=coin.get("name"),
        symbol=coin.get("symbol"),
        logo_url=coin.get("logo_url"),
        condition=doc["condition"],
        target_price=doc["target_price"],
        status=doc["status"],
        current_price=current_price,
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        triggered_at=doc.get("triggered_at"),
        triggered_price=doc.get("triggered_price"),
        expires_at=doc.get("expires_at"),
        last_checked_at=doc.get("last_checked_at"),
    )


class AlertService:
    def __init__(
        self,
        alerts: Optional[AlertRepository] = None,
        coins: Optional[CoinRepository] = None,
        market_data: Optional[MarketDataRepository] = None,
    ) -> None:
        self._alerts = alerts or AlertRepository()
        self._coins = coins or CoinRepository()
        self._market = market_data or MarketDataRepository()

    async def create(self, user_id: ObjectId, request: AlertCreateRequest) -> AlertResponse:
        coin_oid, coin = await require_coin(self._coins, request.coin_id)
        if await self._alerts.count_for_user(user_id) >= MAX_ALERTS_PER_USER:
            raise AppError(409, "ALERT_LIMIT_REACHED", f"You can have at most {MAX_ALERTS_PER_USER} alerts. Delete one first.")
        now = utcnow()
        doc = await self._alerts.insert(
            {
                "user_id": user_id,
                "coin_id": coin_oid,
                "alert_type": "price",
                "condition": request.condition,
                "target_price": request.target_price,
                "status": "ACTIVE",
                "enabled": True,
                "created_at": now,
                "updated_at": now,
                "triggered_at": None,
                "triggered_price": None,
                "expires_at": request.expires_at,
                "last_checked_at": None,
            }
        )
        market = await self._market.get_by_coin_id(coin_oid)
        return _alert_to_response(doc, coin, usable_price((market or {}).get("price_usd")))

    async def list_alerts(self, user_id: ObjectId, page: int, limit: int, status: Optional[str]) -> AlertListResponse:
        page, limit = clamp_pagination(page, limit)
        if status is not None and status not in VALID_STATUSES:
            raise AppError(400, "INVALID_ALERT_STATUS", f"status must be one of: {', '.join(VALID_STATUSES)}.")
        docs, total = await self._alerts.list_for_user(user_id, (page - 1) * limit, limit, status)
        coin_ids = list({doc["coin_id"] for doc in docs})
        coin_docs = await self._coins.find_by_internal_ids(coin_ids) if coin_ids else {}
        market_docs = await self._market.get_many_by_coin_ids(coin_ids) if coin_ids else {}
        items = [
            _alert_to_response(doc, coin_docs.get(doc["coin_id"]), usable_price((market_docs.get(doc["coin_id"]) or {}).get("price_usd")))
            for doc in docs
        ]
        return AlertListResponse(items=items, total=total, page=page, limit=limit, pages=math.ceil(total / limit) if limit else 0)

    async def update(self, user_id: ObjectId, alert_id: str, request: AlertUpdateRequest) -> AlertResponse:
        oid = parse_object_id(alert_id, "INVALID_ALERT_ID", "Alert id is not valid.")
        existing = await self._alerts.get(user_id, oid)
        if existing is None:  # not found OR someone else's — indistinguishable on purpose
            raise AppError(404, "ALERT_NOT_FOUND", "Alert not found.")

        fields: dict[str, Any] = {"updated_at": utcnow()}
        fields_set = request.model_fields_set
        if "condition" in fields_set:
            fields["condition"] = request.condition
        if "target_price" in fields_set:
            fields["target_price"] = request.target_price
        if "expires_at" in fields_set:
            fields["expires_at"] = request.expires_at

        if "status" in fields_set:
            fields["status"] = request.status
            fields["enabled"] = request.status == "ACTIVE"
        # Changing what an alert watches for re-arms a finished one: the old trigger no longer applies.
        rearming = request.status == "ACTIVE" or (
            existing["status"] in ("TRIGGERED", "EXPIRED") and ("condition" in fields_set or "target_price" in fields_set)
        )
        if rearming and existing["status"] in ("TRIGGERED", "EXPIRED", "DISABLED"):
            fields.update({"status": "ACTIVE", "enabled": True, "triggered_at": None, "triggered_price": None})
            expiry = fields.get("expires_at", existing.get("expires_at"))
            if expiry is not None and as_aware(expiry) <= utcnow():  # re-arming an alert whose expiry already passed
                raise AppError(422, "ALERT_EXPIRY_IN_PAST", "Set a new future expiry (or clear it) to re-activate this alert.")

        doc = await self._alerts.update(user_id, oid, fields)
        if doc is None:
            raise AppError(404, "ALERT_NOT_FOUND", "Alert not found.")
        coin = await self._coins.find_by_internal_id(str(doc["coin_id"]))
        market = await self._market.get_by_coin_id(doc["coin_id"])
        return _alert_to_response(doc, coin, usable_price((market or {}).get("price_usd")))

    async def delete(self, user_id: ObjectId, alert_id: str) -> AlertDeleteResponse:
        oid = parse_object_id(alert_id, "INVALID_ALERT_ID", "Alert id is not valid.")
        if not await self._alerts.delete(user_id, oid):
            raise AppError(404, "ALERT_NOT_FOUND", "Alert not found.")
        return AlertDeleteResponse(id=alert_id)


@dataclass
class EvaluationResult:
    checked: int = 0
    triggered: int = 0
    expired: int = 0
    skipped_no_price: int = 0
    skipped_stale: int = 0
    triggered_alert_ids: list[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=utcnow)

    def to_response(self) -> AlertCheckResponse:
        return AlertCheckResponse(**self.__dict__)


class AlertEvaluationService:
    """Evaluates ACTIVE alerts against stored market snapshots. No scheduler lives here (Phase 18)."""

    def __init__(
        self,
        alerts: Optional[AlertRepository] = None,
        market_data: Optional[MarketDataRepository] = None,
        stale_after: timedelta = STALE_AFTER,
    ) -> None:
        self._alerts = alerts or AlertRepository()
        self._market = market_data or MarketDataRepository()
        self._stale_after = stale_after

    async def evaluate(self, user_id: Optional[ObjectId] = None, now: Optional[datetime] = None) -> EvaluationResult:
        """
        One real pass. `user_id=None` evaluates every user's alerts (for the Phase 18 scheduler);
        an id restricts it to that user's alerts (the user-triggered check).
        """
        now = now or utcnow()
        result = EvaluationResult(checked_at=now)
        active = await self._alerts.list_active(EVALUATION_BATCH, user_id)
        if not active:
            return result

        market_docs = await self._market.get_many_by_coin_ids(list({doc["coin_id"] for doc in active}))
        checked_ids: list[ObjectId] = []

        for alert in active:
            expires_at = as_aware(alert.get("expires_at"))
            if expires_at is not None and expires_at <= now:
                if await self._alerts.transition_if_active(alert["_id"], {"status": "EXPIRED", "enabled": False, "updated_at": now}):
                    result.expired += 1
                continue

            market = market_docs.get(alert["coin_id"]) or {}
            price = usable_price(market.get("price_usd"))
            if price is None:
                result.skipped_no_price += 1
                continue
            snapshot_time = as_aware(market.get("updated_at"))
            if snapshot_time is None or now - snapshot_time > self._stale_after:
                # Never fire on an out-of-date price: the condition may not hold right now.
                result.skipped_stale += 1
                continue

            result.checked += 1
            checked_ids.append(alert["_id"])
            if condition_met(alert["condition"], price, alert["target_price"]):
                fired = await self._alerts.transition_if_active(
                    alert["_id"],
                    {
                        "status": "TRIGGERED",
                        "enabled": False,
                        "triggered_at": now,
                        "triggered_price": price,
                        "last_checked_at": now,
                        "updated_at": now,
                    },
                )
                if fired:
                    result.triggered += 1
                    result.triggered_alert_ids.append(str(alert["_id"]))

        await self._alerts.touch_checked(checked_ids, now)
        logger.info(
            "Alert evaluation: checked=%d triggered=%d expired=%d no_price=%d stale=%d",
            result.checked, result.triggered, result.expired, result.skipped_no_price, result.skipped_stale,
        )
        return result
