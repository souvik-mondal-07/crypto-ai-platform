# WebSocket services (placeholder — Step 5)

**Not implemented yet.** No real-time market streaming exists in this
step — every market/coin update in the app comes from a REST fetch
(`services/api/coins.api.ts`, `services/api/market.api.ts`) triggered
by `marketStore`.

This folder exists so a future step can add live price updates
without restructuring the data layer:

- `marketStore` already separates *fetching a snapshot* (`fetchCoins`,
  `fetchGainers`, `fetchMarketOverview`, etc. — implemented, REST) from
  *how the store gets updated* (a plain Zustand `set(...)` call). A
  future WebSocket client would call the same store setters the REST
  actions call today, so components (`CoinTable`, `MoverList`,
  `MarketOverviewCards`) would need no changes at all.
- When implemented, the client should live here as e.g.
  `marketSocket.ts`, exposing a small `connect()` / `disconnect()` /
  `subscribe()` interface — not scattered `new WebSocket(...)` calls
  inside components.

No WebSocket dependency is installed and no connection code exists
yet — adding either now would be complexity with nothing to use it,
which Step 5 explicitly avoids.
