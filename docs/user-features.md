# Phase 16 — User Features

Authenticated, **user-scoped** features: Watchlist, Portfolio, Analysis History, Alerts, Profile, Settings.
Record-keeping only: nothing here trades, connects to an exchange, or moves money.

## User scoping (the security model)

```
JWT  →  get_current_user  →  current_user["_id"]  →  every MongoDB query filter includes user_id
```

* Every route in `watchlist/portfolio/history/alerts/profile/settings` depends on `get_current_user`.
* The user id is **never** read from a request body or query string. Request models use `extra="forbid"`, so a
  `user_id` in a body is a 422, not silently ignored.
* Repositories expose no method that reads or writes user data without a `user_id`. The only cross-user
  operations are `AlertRepository.list_active(user_id=None)` / `transition_if_active`, used solely by the alert
  evaluation service.
* A record that belongs to someone else is indistinguishable from one that does not exist (404), so ids can't
  be probed.

## Collections and indexes

| Collection | One document per | Indexes (all lead with `user_id`) |
|---|---|---|
| `watchlists` | (user, coin) | **unique** `user_id + coin_id` |
| `portfolios` | (user, coin) holding: `quantity`, `average_buy_price`, `notes` | **unique** `user_id + coin_id` |
| `portfolio_transactions` | recorded buy / adjustment (append-only ledger) | `user_id + created_at` |
| `analysis_history` | viewed/generated analysis | `user_id + created_at`; `user_id + coin_id + analysis_type + created_at` |
| `alerts` | price alert | `user_id + status`; `status + created_at` (evaluation scan) |
| `users` | user; preferences live in the `settings` sub-document | existing |

Note: `portfolios` is now one document **per holding** (the earlier design sketch was a named portfolio with
embedded positions); `analysis_history` timestamps are `created_at`, matching the other collections.

## Endpoints (`/api/v1`)

| | |
|---|---|
| `GET /watchlist` · `POST /watchlist` · `GET /watchlist/{coin_id}` · `DELETE /watchlist/{coin_id}` | list (with live market data) / add (409 `WATCHLIST_ALREADY_EXISTS`) / "is it watched?" / remove |
| `GET /portfolio` · `POST /portfolio` · `PUT /portfolio/{coin_id}` · `DELETE /portfolio/{coin_id}` · `GET /portfolio/transactions` | valued holdings + totals / record a purchase (merges into an existing holding by weighted average) / correct a holding / remove it and its ledger / ledger |
| `GET /history` · `POST /history` · `GET /history/{id}` · `DELETE /history/{id}` | paginated newest-first (`page`, `limit`, `coin_id`, `analysis_type`) / record a view / read / delete |
| `GET /alerts` · `POST /alerts` · `PUT /alerts/{id}` · `DELETE /alerts/{id}` · `POST /alerts/check` | list / create / update (`ACTIVE`↔`DISABLED` only) / delete / run one real evaluation of **my** alerts |
| `GET /profile` · `PUT /profile` · `POST /profile/password` | read / change name / change password |
| `GET /settings` · `PUT /settings` | read / partial update (`theme`, `notifications.price_alerts`) |

## Behaviour worth knowing

* **Prices are never invented.** Watchlist/portfolio/alert prices are read from the stored market snapshot at
  request time. A coin with no usable price has `current_value`/P&L = `null`; portfolio totals then cover only
  the priced holdings and the summary says so (`is_partial`).
* **Portfolio maths** (`services/portfolio_calculations.py`): value = qty × price; invested = qty × avg buy
  price; P&L = value − invested; P&L % = P&L ÷ invested × 100 (`null` when invested is 0). Fees are kept in the
  ledger and are not folded into the average price.
* **History is recorded server-side**: the client says which analysis of which coin was viewed; the server reads
  the decision / risk level from what is actually stored (`UNAVAILABLE` if nothing is). An identical entry within
  5 minutes is reused, so re-renders don't write duplicates.
* **Alerts** (`services/alert_service.py`): `AlertEvaluationService.evaluate()` compares ACTIVE alerts with the
  stored snapshot. It skips (and counts) alerts whose coin has no price or whose snapshot is stale (> the
  existing stale threshold), and a status flip is a guarded atomic update, so an alert can't trigger twice.
  There is **no scheduler** in this phase — `POST /alerts/check` runs it for the caller; Phase 18's scheduler
  should call `evaluate()` (no argument = all users). Nothing is sent anywhere: "notifications" is an in-app
  banner on the Alerts page.
* **Password change** verifies the current Argon2 hash, validates the new password (8–128 chars, confirmed,
  different), stores a fresh Argon2 hash, never logs/stores plaintext. Existing JWTs stay valid until they expire
  (stateless tokens; revocation is Phase 18 territory).
* **Email is read-only** (changing a login identifier needs re-verification, which is out of scope).
* **Theme**: `ThemeContext` still owns light/dark. Signed in, the choice is also saved to the account and applied
  once per sign-in; a user who never chose keeps their device theme. Currency isn't a setting (USD only).
* **Limits**: 250 watchlist coins, 250 holdings, 100 alerts per user.

## Frontend

Pages `/watchlist /portfolio /history /alerts /profile /settings` (all `ProtectedRoute`). Stores:
`watchlistStore`, `portfolioStore`, `settingsStore` (the old device-local watchlist was removed from
`userListsStore`; recently-viewed/compare stay local). Services `*.api.ts`, hooks `useWatchlist usePortfolio
useHistory useAlerts useProfile useSettings useThemePreference useUserData useRecordHistory`.
Stores are cleared when the signed-in user changes.
