"""Tiny in-memory stand-in for PyMongo's async collections (equality/$in/$gt/$gte/$lt/$lte/$ne filters,
$set, sort/skip/limit). It lets the Phase 16 tests run the REAL repositories/services/routes — including
their `user_id` scoping — without a MongoDB server."""

from copy import deepcopy
from types import SimpleNamespace
from typing import Any, Optional

from bson import ObjectId
from pymongo.errors import DuplicateKeyError


def _get(doc: dict[str, Any], key: str) -> Any:
    cur: Any = doc
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _matches(doc: dict[str, Any], flt: dict[str, Any]) -> bool:
    for key, cond in flt.items():
        value = _get(doc, key)
        if isinstance(cond, dict) and any(k.startswith("$") for k in cond):
            for op, arg in cond.items():
                if op == "$in" and value not in arg:
                    return False
                if op == "$ne" and value == arg:
                    return False
                if op in ("$gt", "$gte", "$lt", "$lte"):
                    if value is None:
                        return False
                    ok = {"$gt": value > arg, "$gte": value >= arg, "$lt": value < arg, "$lte": value <= arg}[op]
                    if not ok:
                        return False
        elif value != cond:
            return False
    return True


def _set_path(doc: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    cur = doc
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


class FakeCursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    def sort(self, spec, direction=None):
        if isinstance(spec, str):
            spec = [(spec, direction or 1)]
        for key, d in reversed(list(spec)):
            self._docs.sort(key=lambda doc: (_get(doc, key) is None, _get(doc, key)), reverse=d < 0)
        return self

    def skip(self, n: int):
        self._docs = self._docs[n:]
        return self

    def limit(self, n: int):
        if n:
            self._docs = self._docs[:n]
        return self

    async def to_list(self, length: Optional[int] = None):
        return deepcopy(self._docs[:length] if length else self._docs)


class FakeCollection:
    def __init__(self, unique: Optional[list[tuple[str, ...]]] = None) -> None:
        self.docs: list[dict[str, Any]] = []
        self._unique = unique or []

    async def insert_one(self, doc: dict[str, Any]):
        for keys in self._unique:
            if any(all(_get(d, k) == _get(doc, k) for k in keys) for d in self.docs):
                raise DuplicateKeyError("duplicate key")
        stored = deepcopy(doc)
        stored.setdefault("_id", ObjectId())
        self.docs.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    def _select(self, flt: dict[str, Any]) -> list[dict[str, Any]]:
        return [d for d in self.docs if _matches(d, flt)]

    async def find_one(self, flt=None, projection=None, sort=None):
        docs = self._select(flt or {})
        if sort:
            docs = FakeCursor(docs).sort(sort)._docs
        return deepcopy(docs[0]) if docs else None

    def find(self, flt=None, projection=None):
        return FakeCursor(self._select(flt or {}))

    async def count_documents(self, flt=None, limit: Optional[int] = None):
        n = len(self._select(flt or {}))
        return min(n, limit) if limit else n

    async def update_one(self, flt, update, upsert=False):
        docs = self._select(flt)
        if not docs:
            return SimpleNamespace(matched_count=0, modified_count=0)
        for key, value in update.get("$set", {}).items():
            _set_path(docs[0], key, value)
        return SimpleNamespace(matched_count=1, modified_count=1)

    async def update_many(self, flt, update):
        docs = self._select(flt)
        for doc in docs:
            for key, value in update.get("$set", {}).items():
                _set_path(doc, key, value)
        return SimpleNamespace(matched_count=len(docs), modified_count=len(docs))

    async def delete_one(self, flt):
        docs = self._select(flt)
        if docs:
            self.docs.remove(docs[0])
        return SimpleNamespace(deleted_count=1 if docs else 0)

    async def delete_many(self, flt):
        docs = self._select(flt)
        for d in docs:
            self.docs.remove(d)
        return SimpleNamespace(deleted_count=len(docs))
