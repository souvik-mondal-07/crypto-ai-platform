"""
Session-wide test setup.

`app/api/v1/__init__.py` decides ONCE, at import time, whether the
dev-sync router is registered at all (`if
get_settings().ENABLE_DEV_SYNC_ENDPOINT: ...`). Because Python caches
modules, that decision is baked in the first time anything imports
`app.main` / `app.api.v1` during the whole pytest session — no
in-test monkeypatch of a later test can add or remove the route
afterwards.

`Settings` is also `@lru_cache`d, so if an ambient environment
variable (set in the shell, a CI job, or a stray `os.environ` write
from another test module) makes `ENABLE_DEV_SYNC_ENDPOINT` truthy
before that first import happens, `test_dev_sync_endpoint_not_registered_by_default`
would see the route actually registered and fail for reasons that
have nothing to do with application logic.

This fixture runs before test collection imports anything from `app`,
clears any cached `Settings` instance, and forces
`ENABLE_DEV_SYNC_ENDPOINT` to the documented default ("false") for the
whole test session, so the suite's behavior only ever depends on the
checked-in defaults (see app/config/settings.py,
app/api/v1/__init__.py) rather than on whatever happens to be in the
ambient shell environment when `pytest` is invoked.

The same reasoning applies to `MARKET_REFRESH_ENABLED` (the real-time refresh upgrade):
several test modules construct `TestClient(app)`, which runs
`app.main`'s lifespan — and that lifespan starts the background market
refresh scheduler if enabled. Left at its normal default of "true",
every such test would spin up a real asyncio task making live
CoinGecko/Binance HTTP calls in the background, entirely incidental to
whatever that test is actually checking. Forcing it "false" here means
the scheduler itself is exercised only by tests that explicitly build
their own `MarketRefreshScheduler` with a fake sync service (see
tests/test_market_refresh_scheduler.py) — never implicitly, via
whatever module happens to construct the app first.
"""

import os

os.environ["ENABLE_DEV_SYNC_ENDPOINT"] = "false"
os.environ["MARKET_REFRESH_ENABLED"] = "false"

from app.config import get_settings  # noqa: E402  (must follow the env var writes above)

get_settings.cache_clear()
