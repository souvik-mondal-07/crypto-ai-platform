"""Analysis-history business logic (Phase 16).

The client only says WHICH analysis of WHICH coin was viewed. The outcome (status, decision,
risk level) is read server-side from what was actually stored, so history can't be forged
into showing a decision that never existed. Only short labels and references are kept.
"""

import math
from datetime import timedelta
from typing import Any, Optional

from bson import ObjectId

from app.core.exceptions import AppError
from app.repositories.ai_analysis_repository import AIAnalysisRepository
from app.repositories.coin_repository import CoinRepository
from app.repositories.decision_repository import DecisionRepository
from app.repositories.history_repository import HistoryRepository
from app.repositories.prediction_repository import PredictionRepository
from app.schemas.history import (
    ANALYSIS_TYPES,
    HistoryCreateRequest,
    HistoryDeleteResponse,
    HistoryEntry,
    HistoryListResponse,
)
from app.services.user_feature_common import parse_coin_id, parse_object_id, require_coin, utcnow
from app.utils.pagination import clamp_pagination

#: Re-rendering a page must not write a new row each time: an identical entry inside this window is reused.
DEDUPE_WINDOW = timedelta(minutes=5)


def _doc_to_entry(doc: dict[str, Any]) -> HistoryEntry:
    return HistoryEntry(
        id=str(doc["_id"]),
        coin_id=str(doc["coin_id"]),
        coin_name=doc.get("coin_name"),
        symbol=doc.get("symbol"),
        analysis_type=doc["analysis_type"],
        status=doc.get("status", "COMPLETED"),
        decision=doc.get("decision"),
        risk_level=doc.get("risk_level"),
        risk_score=doc.get("risk_score"),
        summary=doc.get("summary"),
        created_at=doc["created_at"],
    )


def _decision_summary(decision: Optional[str], risk_level: Optional[str]) -> Optional[str]:
    parts = []
    if decision:
        parts.append(f"Decision {decision}")
    if risk_level:
        parts.append(f"{risk_level} risk")
    return ", ".join(parts) or None


class HistoryService:
    def __init__(
        self,
        history: Optional[HistoryRepository] = None,
        coins: Optional[CoinRepository] = None,
        decisions: Optional[DecisionRepository] = None,
        predictions: Optional[PredictionRepository] = None,
        ai_analyses: Optional[AIAnalysisRepository] = None,
    ) -> None:
        self._history = history or HistoryRepository()
        self._coins = coins or CoinRepository()
        self._decisions = decisions or DecisionRepository()
        self._predictions = predictions or PredictionRepository()
        self._ai = ai_analyses or AIAnalysisRepository()

    async def record(self, user_id: ObjectId, request: HistoryCreateRequest) -> tuple[HistoryEntry, bool]:
        """Returns (entry, created). `created` is False when an identical recent entry was reused."""
        coin_oid, coin = await require_coin(self._coins, request.coin_id)
        now = utcnow()

        duplicate = await self._history.find_recent_duplicate(user_id, coin_oid, request.analysis_type, now - DEDUPE_WINDOW)
        if duplicate is not None:
            return _doc_to_entry(duplicate), False

        snapshot = await self._snapshot(coin_oid, request.analysis_type)
        document = {
            "user_id": user_id,
            "coin_id": coin_oid,
            "coin_name": coin.get("name"),
            "symbol": coin.get("symbol"),
            "analysis_type": request.analysis_type,
            "created_at": now,
            **snapshot,
        }
        return _doc_to_entry(await self._history.insert(document)), True

    async def _snapshot(self, coin_oid: ObjectId, analysis_type: str) -> dict[str, Any]:
        """What the stored analysis currently says. UNAVAILABLE when nothing was stored — never invented."""
        empty = {"status": "UNAVAILABLE", "decision": None, "risk_level": None, "risk_score": None, "summary": None}

        if analysis_type == "coin_analysis":
            return {**empty, "status": "COMPLETED", "summary": "Coin analysis viewed"}

        if analysis_type == "risk_decision":
            doc = await self._decisions.get_latest(coin_oid)
            if doc is None or (doc.get("decision") is None and doc.get("risk_level") is None):
                return empty
            return {
                "status": "COMPLETED",
                "decision": doc.get("decision"),
                "risk_level": doc.get("risk_level"),
                "risk_score": doc.get("risk_score"),
                "summary": _decision_summary(doc.get("decision"), doc.get("risk_level")),
                "decision_id": doc.get("_id"),
            }

        if analysis_type == "ai_analysis":
            doc = await self._ai.get_latest(coin_oid)
            if doc is None:
                return empty
            snapshot = doc.get("decision_snapshot") or {}
            return {
                "status": "COMPLETED",
                "decision": snapshot.get("decision"),
                "risk_level": snapshot.get("risk_level"),
                "risk_score": None,
                "summary": "AI explanation of the decision",
            }

        if analysis_type == "prediction":
            doc = await self._predictions.get_latest_any_horizon(coin_oid)
            if doc is None:
                return empty
            horizon, direction = doc.get("horizon"), doc.get("direction")
            summary = f"{horizon} outlook: {direction}" if horizon and direction else "Prediction viewed"
            return {**empty, "status": "COMPLETED", "summary": summary}

        raise AppError(400, "INVALID_ANALYSIS_TYPE", f"analysis_type must be one of: {', '.join(ANALYSIS_TYPES)}.")

    async def list_entries(
        self, user_id: ObjectId, page: int, limit: int, coin_id: Optional[str], analysis_type: Optional[str]
    ) -> HistoryListResponse:
        page, limit = clamp_pagination(page, limit)
        if analysis_type is not None and analysis_type not in ANALYSIS_TYPES:
            raise AppError(400, "INVALID_ANALYSIS_TYPE", f"analysis_type must be one of: {', '.join(ANALYSIS_TYPES)}.")
        coin_oid = parse_coin_id(coin_id) if coin_id else None
        docs, total = await self._history.list_for_user(user_id, (page - 1) * limit, limit, coin_oid, analysis_type)
        return HistoryListResponse(
            items=[_doc_to_entry(doc) for doc in docs],
            total=total,
            page=page,
            limit=limit,
            pages=math.ceil(total / limit) if limit else 0,
        )

    async def get_entry(self, user_id: ObjectId, entry_id: str) -> HistoryEntry:
        oid = parse_object_id(entry_id, "INVALID_HISTORY_ID", "History id is not valid.")
        doc = await self._history.get(user_id, oid)
        if doc is None:  # same answer for "doesn't exist" and "belongs to someone else"
            raise AppError(404, "HISTORY_NOT_FOUND", "History entry not found.")
        return _doc_to_entry(doc)

    async def delete_entry(self, user_id: ObjectId, entry_id: str) -> HistoryDeleteResponse:
        oid = parse_object_id(entry_id, "INVALID_HISTORY_ID", "History id is not valid.")
        if not await self._history.delete(user_id, oid):
            raise AppError(404, "HISTORY_NOT_FOUND", "History entry not found.")
        return HistoryDeleteResponse(id=entry_id)
