# Crypto AI Platform — Backend (Steps 1–10 and Phase 11: foundation through fundamental analysis)

FastAPI backend with a MongoDB database architecture layer, a crypto
market-data engine (CoinGecko + Binance), and JWT authentication with
Argon2 password hashing. No OTP, email verification, password reset,
social login, AI/ML, or trading features are implemented yet.

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

MongoDB must be installed and reachable at `MONGODB_URI` (default
`mongodb://localhost:27017`) for the database to report as connected —
see `../docs/development.md` for local setup. The API will still start
without it, reporting a degraded health status.

**Set a real `JWT_SECRET_KEY`** before running anywhere other than
your own machine — see `../docs/authentication.md`.

## Run

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Root: http://127.0.0.1:8000/
- Health: http://127.0.0.1:8000/api/v1/health
- Interactive docs: http://127.0.0.1:8000/docs

## Test

```bash
pytest                        # everything
pytest -m "not integration"   # unit tests only, no MongoDB required
pytest -m integration         # only tests requiring a running MongoDB
```

## Structure

```
app/
├── main.py            # FastAPI app, CORS, lifespan (MongoDB connect/close), exception handlers, router registration
├── config/             # Centralized settings (env-driven, incl. MongoDB, providers, JWT)
├── core/               # security.py (Argon2 + JWT), dependencies.py (get_current_user), exceptions.py
├── database/           # MongoDB client, db/collection accessors, collection registry, indexes
├── models/             # DB models (empty — added alongside first real collection use)
├── schemas/            # Pydantic request/response models + Mongo-doc-to-schema converters
├── api/v1/              # Versioned API routers (auth, coins, market, health, dev-only sync)
├── providers/           # CoinGecko + Binance clients/mappers behind a common interface
├── services/            # Business logic (AuthService, CoinService, MarketService, MarketSyncService)
├── repositories/        # Data access layer (UserRepository, CoinRepository, MarketDataRepository)
└── utils/               # Shared helpers (pagination validation)
```

See [`../docs/database-schema.md`](../docs/database-schema.md) for the
full MongoDB schema, [`../docs/market-data.md`](../docs/market-data.md)
for the provider/sync architecture, and
[`../docs/authentication.md`](../docs/authentication.md) for the auth
flow.
