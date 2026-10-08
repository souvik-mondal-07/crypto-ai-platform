# Database

MongoDB is the platform's data store. As of Step 3, `coins` and
`market_data` are actively populated by the market-data sync service —
every other planned collection remains schema-only (documented, no
data).

## Technology

- **MongoDB**, accessed via **PyMongo's native async API**
  (`AsyncMongoClient`, PyMongo 4.9+). No ODM (e.g. Beanie/MongoEngine)
  and no Motor — see `docs/database-schema.md` for the reasoning.

## Structure

```
database/
├── README.md
├── schemas/       # (reserved — schema is currently documented in
│                     docs/database-schema.md, not as code here yet)
└── migrations/    # (reserved — no migrations needed until data exists)
```

## Where things actually live

- **Connection management:** `backend/app/database/client.py`
- **Database/collection accessors:** `backend/app/database/database.py`
- **Collection name registry:** `backend/app/database/collections.py`
- **Index definitions:** `backend/app/database/indexes.py`
- **Full schema documentation:** [`docs/database-schema.md`](../docs/database-schema.md)
- **Repositories:** `backend/app/repositories/` (`CoinRepository`,
  `MarketDataRepository`, and the `BaseRepository` pattern)
- **Market-data sync (writes to `coins`/`market_data`):**
  `backend/app/services/market_sync_service.py` — see
  [`docs/market-data.md`](../docs/market-data.md)

## Local setup

See [`docs/development.md`](../docs/development.md) for how to install
and start MongoDB locally, and how to point the backend at a different
URI or database name.

## Status

- Connection: implemented (Step 2)
- `coins`, `market_data`: actively synchronized from CoinGecko (+
  Binance enrichment) — see `docs/market-data.md` (Step 3)
- All other collections: named/documented, created lazily on first
  write — none exist yet
- Data: no fake/sample data anywhere; `coins`/`market_data` only ever
  contain what a real sync run wrote
