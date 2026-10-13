"""Portfolio business logic (Phase 16): record holdings, value them at CURRENT market prices.

Record-keeping only. Nothing here talks to an exchange, places an order, or moves money.
Every method takes the authenticated user's ObjectId and every query is scoped by it.
"""

import math
from datetime import datetime
from typing import Any, Optional

from bson import ObjectId

from app.core.exceptions import AppError
from app.repositories.coin_repository import CoinRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.portfolio_repository import (
    HoldingExistsError,
    PortfolioRepository,
    PortfolioTransactionRepository,
)
from app.schemas.converters import is_snapshot_stale
from app.schemas.portfolio import (
    HoldingCreateRequest,
    HoldingRemoveResponse,
    HoldingResponse,
    HoldingUpdateRequest,
    PortfolioResponse,
    PortfolioSummary,
    TransactionListResponse,
    TransactionResponse,
)
from app.services import portfolio_calculations as calc
from app.services.user_feature_common import parse_coin_id, require_coin, utcnow
from app.utils.pagination import clamp_pagination

MAX_HOLDINGS = 250


def _build_holding(
    doc: dict[str, Any], coin: dict[str, Any], market: Optional[dict[str, Any]], total_current_value: Optional[float] = None
) -> HoldingResponse:
    market = market or {}
    price = calc.usable_price(market.get("price_usd"))
    valuation = calc.valuate(doc["quantity"], doc["average_buy_price"], price)
    return HoldingResponse(
        coin_id=str(doc["coin_id"]),
        name=coin["name"],
        symbol=coin["symbol"],
        logo_url=coin.get("logo_url"),
        quantity=doc["quantity"],
        average_buy_price=doc["average_buy_price"],
        invested_value=valuation.invested,
        has_price=price is not None,
        current_price=price,
        current_value=valuation.current,
        unrealized_pnl=valuation.pnl,
        unrealized_pnl_pct=valuation.pnl_pct,
        percent_change_24h=market.get("percent_change_24h"),
        allocation_pct=calc.allocation_percent(valuation.current, total_current_value) if total_current_value else None,
        price_last_updated=market.get("last_updated") or market.get("updated_at"),
        price_is_stale=is_snapshot_stale(market.get("updated_at")),
        notes=doc.get("notes"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


class PortfolioService:
    def __init__(
        self,
        holdings: Optional[PortfolioRepository] = None,
        transactions: Optional[PortfolioTransactionRepository] = None,
        coins: Optional[CoinRepository] = None,
        market_data: Optional[MarketDataRepository] = None,
    ) -> None:
        self._holdings = holdings or PortfolioRepository()
        self._transactions = transactions or PortfolioTransactionRepository()
        self._coins = coins or CoinRepository()
        self._market = market_data or MarketDataRepository()

    # ------------------------------------------------------------------ read

    async def get_portfolio(self, user_id: ObjectId) -> PortfolioResponse:
        docs = await self._holdings.list_for_user(user_id, MAX_HOLDINGS)
        coin_ids = [doc["coin_id"] for doc in docs]
        coin_docs = await self._coins.find_by_internal_ids(coin_ids) if coin_ids else {}
        market_docs = await self._market.get_many_by_coin_ids(coin_ids) if coin_ids else {}

        rows = [(doc, coin_docs[doc["coin_id"]]) for doc in docs if doc["coin_id"] in coin_docs]
        valuations = [
            calc.valuate(doc["quantity"], doc["average_buy_price"], (market_docs.get(doc["coin_id"]) or {}).get("price_usd"))
            for doc, _ in rows
        ]
        totals = calc.summarize(valuations)

        holdings = [_build_holding(doc, coin, market_docs.get(doc["coin_id"]), totals.total_current_value) for doc, coin in rows]
        # Largest positions first; holdings without a price sit at the end.
        holdings.sort(key=lambda h: (h.current_value is None, -(h.current_value or 0.0)))

        return PortfolioResponse(
            summary=PortfolioSummary(
                total_current_value=totals.total_current_value,
                total_invested=totals.total_invested,
                priced_invested=totals.priced_invested,
                total_unrealized_pnl=totals.total_pnl,
                total_unrealized_pnl_pct=totals.total_pnl_pct,
                holdings_count=totals.holdings_count,
                unpriced_count=totals.unpriced_count,
                is_partial=totals.is_partial,
            ),
            holdings=holdings,
        )

    async def list_transactions(
        self, user_id: ObjectId, page: int, limit: int, coin_id: Optional[str] = None
    ) -> TransactionListResponse:
        page, limit = clamp_pagination(page, limit)
        coin_oid = parse_coin_id(coin_id) if coin_id else None
        docs, total = await self._transactions.list_for_user(user_id, (page - 1) * limit, limit, coin_oid)
        coin_docs = await self._coins.find_by_internal_ids(list({d["coin_id"] for d in docs})) if docs else {}
        items = []
        for doc in docs:
            coin = coin_docs.get(doc["coin_id"]) or {}
            items.append(
                TransactionResponse(
                    id=str(doc["_id"]),
                    coin_id=str(doc["coin_id"]),
                    name=coin.get("name"),
                    symbol=coin.get("symbol"),
                    transaction_type=doc["transaction_type"],
                    quantity=doc["quantity"],
                    price=doc["price"],
                    fee=doc.get("fee"),
                    notes=doc.get("notes"),
                    transaction_at=doc["timestamp"],
                    created_at=doc["created_at"],
                )
            )
        return TransactionListResponse(items=items, total=total, page=page, limit=limit, pages=math.ceil(total / limit) if limit else 0)

    # ------------------------------------------------------------------ write

    async def add_holding(self, user_id: ObjectId, request: HoldingCreateRequest) -> HoldingResponse:
        coin_oid, coin = await require_coin(self._coins, request.coin_id)
        now = utcnow()
        existing = await self._holdings.get(user_id, coin_oid)

        if existing is not None:
            quantity = existing["quantity"] + request.quantity
            average = calc.weighted_average_price(existing["quantity"], existing["average_buy_price"], request.quantity, request.price)
            fields: dict[str, Any] = {"quantity": quantity, "average_buy_price": average, "updated_at": now}
            if request.notes:
                fields["notes"] = request.notes
            doc = await self._holdings.update(user_id, coin_oid, fields)
            if doc is None:  # removed between the read and the write
                raise AppError(409, "PORTFOLIO_CONFLICT", "Your portfolio changed while saving. Please retry.")
        else:
            if await self._holdings.count_for_user(user_id) >= MAX_HOLDINGS:
                raise AppError(409, "PORTFOLIO_LIMIT_REACHED", f"Your portfolio is full ({MAX_HOLDINGS} assets).")
            try:
                doc = await self._holdings.insert(
                    {
                        "user_id": user_id,
                        "coin_id": coin_oid,
                        "quantity": request.quantity,
                        "average_buy_price": request.price,
                        "notes": request.notes,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
            except HoldingExistsError:
                raise AppError(409, "PORTFOLIO_CONFLICT", "Your portfolio changed while saving. Please retry.")

        await self._transactions.insert(
            self._transaction_doc(user_id, coin_oid, "buy", request.quantity, request.price, request.fee, request.notes, request.bought_at or now, now)
        )
        market = await self._market.get_by_coin_id(coin_oid)
        return _build_holding(doc, coin, market)

    async def update_holding(self, user_id: ObjectId, coin_id: str, request: HoldingUpdateRequest) -> HoldingResponse:
        coin_oid = parse_coin_id(coin_id)
        existing = await self._holdings.get(user_id, coin_oid)
        if existing is None:
            raise AppError(404, "HOLDING_NOT_FOUND", "This coin is not in your portfolio.")

        now = utcnow()
        fields: dict[str, Any] = {"updated_at": now}
        if "quantity" in request.model_fields_set:
            fields["quantity"] = request.quantity
        if "average_buy_price" in request.model_fields_set:
            fields["average_buy_price"] = request.average_buy_price
        if "notes" in request.model_fields_set:
            fields["notes"] = request.notes

        doc = await self._holdings.update(user_id, coin_oid, fields)
        if doc is None:
            raise AppError(404, "HOLDING_NOT_FOUND", "This coin is not in your portfolio.")

        if "quantity" in fields or "average_buy_price" in fields:
            await self._transactions.insert(
                self._transaction_doc(user_id, coin_oid, "adjustment", doc["quantity"], doc["average_buy_price"], None, request.notes, now, now)
            )
        coin = await self._coins.find_by_internal_id(coin_id) or {"name": "Unknown", "symbol": "?"}
        market = await self._market.get_by_coin_id(coin_oid)
        return _build_holding(doc, coin, market)

    async def remove_holding(self, user_id: ObjectId, coin_id: str) -> HoldingRemoveResponse:
        coin_oid = parse_coin_id(coin_id)
        if not await self._holdings.delete(user_id, coin_oid):
            raise AppError(404, "HOLDING_NOT_FOUND", "This coin is not in your portfolio.")
        await self._transactions.delete_for_coin(user_id, coin_oid)
        return HoldingRemoveResponse(coin_id=coin_id)

    @staticmethod
    def _transaction_doc(
        user_id: ObjectId, coin_oid: ObjectId, kind: str, quantity: float, price: float,
        fee: Optional[float], notes: Optional[str], timestamp: datetime, created_at: datetime,
    ) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "coin_id": coin_oid,
            "transaction_type": kind,
            "quantity": quantity,
            "price": price,
            "fee": fee,
            "notes": notes,
            "timestamp": timestamp,
            "created_at": created_at,
        }
