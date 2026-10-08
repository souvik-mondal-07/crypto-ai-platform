# Authentication (Step 4)

This document describes the V1 authentication system: registration,
login, logout, JWT, password hashing, and the frontend auth flow.

## Scope — what V1 is and isn't

**Implemented:** register, login, logout (client-side), current user
(`/auth/me`), Argon2 password hashing, JWT access tokens, protected
routes (frontend and backend), persistent auth state across refresh.

**Explicitly NOT implemented in V1** (future work, not started, no
placeholder code/collections/routes for them exist):
- OTP / two-factor authentication
- Email verification
- Forgot password / password reset
- Social login (Google, GitHub, etc.)
- Phone authentication

The architecture is kept extensible for these (see "Future OTP
compatibility" below), but nothing about the current design assumes
they'll be bolted on in any particular way — that's deliberately left
for whichever step actually implements them.

## Registration flow

```
POST /api/v1/auth/register
{ "name", "email", "password", "confirm_password" }
        ↓
RegisterRequest validates: name non-blank, email format (Pydantic
EmailStr), password ≥ 8 chars, password == confirm_password
        ↓
AuthService.register() checks email_exists() (fast path)
        ↓
Argon2 hash the password
        ↓
UserRepository.create_user() — relies on the unique index on
`email` as the actual uniqueness guarantee (handles the race between
the pre-check and the insert)
        ↓
201 Created: { "user": {...}, "message": "Registration successful" }
```

`confirm_password` is validated at the request-schema boundary
(`RegisterRequest`'s model validator) and is never passed to
`AuthService`, never hashed, and never stored — only the confirmed
`password` is.

**V1 does not auto-login after registration.** The frontend redirects
to `/login` on success; the user authenticates normally. This was the
explicit, documented choice for this step — simpler to reason about,
and avoids ambiguity around whether a freshly-registered-but-not-yet-
verified account should already hold a valid session (relevant once
email verification is added in a future step).

## Login flow

```
POST /api/v1/auth/login
{ "email", "password" }
        ↓
UserRepository.find_by_email() (normalized: trimmed + lowercased)
        ↓
verify_password() against the stored Argon2 hash
        ↓
check is_active
        ↓
create_access_token(subject=user_id)
        ↓
200 OK: { "user": {...actual MongoDB user...}, "token": {...} }
```

**Every failure reason returns the same generic message:**
`"Invalid email or password."` (error code `AUTH_INVALID_CREDENTIALS`)
— whether the email doesn't exist, the password is wrong, or anything
else. This is deliberate: revealing "that email doesn't exist" vs.
"wrong password" lets an attacker enumerate registered emails.

An inactive account (`is_active: false`) fails login with a distinct
`403 AUTH_USER_INACTIVE` — this is not hidden behind the generic
credentials message, since account status isn't a credential-guessing
vector the same way email existence is.

## Password hashing

**Argon2id** via `argon2-cffi`, using the library's current default
parameters (which already satisfy OWASP's current minimum recommendation
for interactive password hashing). Not hand-tuned in Step 4 — that's a
deliberate choice to avoid guessing at production hardware/latency
numbers that don't exist yet for this project.

- Passwords are **never** stored, logged, or returned in any API
  response — only `password_hash` exists in the `users` collection.
- `app/core/security.py` is the **only** module that touches
  `argon2`; nothing else hashes or verifies a password directly.
- `needs_rehash()` is implemented (checks whether a stored hash used
  weaker parameters than the current hasher) but not wired into the
  login flow yet — there's no reason to add that complexity before any
  hash has actually aged under a parameter change.

## User document

```json
{
  "_id": "ObjectId(...)",
  "name": "Jane Doe",
  "email": "jane@example.com",
  "password_hash": "$argon2id$v=19$...",
  "is_active": true,
  "role": "user",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
```

No other personal information is stored. See
`docs/database-schema.md` for the full `users` collection schema
(this was already documented in Step 2; Step 4 is the first step to
actually write to it).

### Email normalization

Every read and write of `email` goes through
`normalize_email()` (`app/repositories/user_repository.py`): trim
whitespace, lowercase. `User@Example.com` and `user@example.com`
resolve to the same account. The unique index is on the raw `email`
field — since every write is already normalized before it reaches
MongoDB, this correctly enforces uniqueness on the normalized value
without needing a separate indexed field.

### Database index

`users.email` has a **unique** index (`uniq_users_email` — created in
Step 2 ahead of need, actively enforced starting in Step 4). This is
the real uniqueness guarantee — `AuthService`'s `email_exists()`
pre-check is a fast/clean-error path, not the actual mechanism;
concurrent duplicate inserts are caught by the index and translated
into `EmailAlreadyExistsError` → `409 AUTH_EMAIL_EXISTS`.

## JWT

Minimal claims only:

```json
{ "sub": "<user's MongoDB _id as a string>", "iat": 1735689600, "exp": 1735693200 }
```

Never included: password, password hash, name, email, role, or any
other profile field — a JWT is signed, not encrypted, so anything in
it is readable by whoever holds the token.

Configuration (`backend/.env.example`):

```
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

`JWT_SECRET_KEY` must be a real random secret in any non-local
environment — generate one with e.g.
`python -c "import secrets; print(secrets.token_urlsafe(64))"`.
The backend logs a loud (non-fatal) warning at startup if
`APP_ENV=production` and the secret is still the placeholder value.

## Protected backend routes

`get_current_user` (`app/core/dependencies.py`) is the single
FastAPI dependency every protected route uses:

1. Extract the `Authorization` header via `HTTPBearer`.
2. Confirm it's a Bearer token.
3. Decode/verify the JWT (`app/core/security.py`).
4. Look up the user by the token's `sub` claim.
5. Confirm the user is still active.
6. Return the actual MongoDB user document.

No route re-implements any of this. Distinct error codes:
`AUTH_INVALID_TOKEN` (missing/malformed/wrong-signature token, or the
user no longer exists) vs. `AUTH_TOKEN_EXPIRED` (valid signature, past
`exp`) vs. `AUTH_USER_INACTIVE` (valid token, deactivated account).

`/api/v1/auth/me` is currently the only route that depends on
`get_current_user` — it's the frontend's single source of truth for
"who is logged in." Step 3's market/coin endpoints are unauthenticated
and continue to work exactly as before; Step 4 does not add auth to
any existing route.

## Logout — what it actually does

```
POST /api/v1/auth/logout → { "message": "Logged out successfully" }
```

**This endpoint cannot invalidate an already-issued JWT.** Stateless
access tokens are valid until they expire, full stop — there is no
server-side revocation list/blocklist in V1. "Logout" in this system
means: the frontend deletes its stored token and clears its
authenticated state. If that same token were somehow replayed
elsewhere before its `exp`, it would still be accepted by
`get_current_user`. A future refresh-token/revocation-store step can
close this gap without requiring a rewrite of the access-token
verification path itself.

## Frontend authentication flow

```
LoginForm → authApi.login() → POST /auth/login → token received
    → setToken() (utils/authStorage.ts)
    → authApi.me() → GET /auth/me → actual MongoDB user
    → authStore.user updated
    → UI displays the actual name
    → navigate("/dashboard")
```

**`/auth/me` is always called after login** — the frontend never
trusts a name/email typed into the login form, or anything embedded
in the JWT payload (which only contains `sub` anyway), as the
authenticated user's identity.

### Auth store (`frontend/src/store/authStore.ts`)

Single Zustand store holding `user`, `isAuthenticated`, `isLoading`,
`error`. This is the **only** place the authenticated user's identity
lives in the frontend — no component keeps its own copy, and nothing
anywhere falls back to a hard-coded name.

### Page refresh / auth initialization

```
App mounts → useEffect calls authStore.initializeAuth()
    → token in storage?
        no  → isAuthenticated: false, isLoading: false (nothing else happens)
        yes → GET /auth/me
            valid   → restore actual user, isAuthenticated: true
            invalid → clear token, isAuthenticated: false
```

`ProtectedRoute` shows a loading state while this check is in
flight, specifically so a user with a genuinely valid session never
sees an unauthenticated flash (redirect-then-bounce-back) on refresh.

### Token storage

`frontend/src/utils/authStorage.ts` centralizes all `localStorage`
access behind `getToken()`/`setToken()`/`removeToken()` — no component
or service touches `localStorage` directly.

**Security trade-off, documented rather than hidden:** localStorage is
readable by any JavaScript executing on this origin, so a successful
XSS attack can steal the token. An HttpOnly cookie would not be
readable by JavaScript at all, closing that specific vector, but
requires backend changes (`Set-Cookie`, CSRF protection, `SameSite`
configuration) that are out of scope for this V1. Centralizing all
token access in one file is what makes that migration tractable later
— only `authStorage.ts` (and how `client.ts` attaches the credential)
would need to change, not every call site.

### Axios interceptor (`frontend/src/services/api/client.ts`)

- **Request interceptor:** attaches `Authorization: Bearer <token>`
  automatically when a token is stored. No service manually sets this
  header.
- **Response interceptor:** on a `401` from any endpoint *other than*
  `/auth/login`/`/auth/register` (a wrong-password rejection during
  those two calls is a normal form error, not a session invalidation),
  clears the stored token and dispatches a `window` `CustomEvent`
  (`AUTH_SESSION_INVALID_EVENT`). `authStore` listens for this event
  and clears its state the same way logout does. The event-based
  approach (rather than importing the store directly into the Axios
  client) avoids a circular dependency between the two modules.

### Protected routes

`frontend/src/routes/ProtectedRoute.tsx` wraps any route that requires
authentication. `/dashboard` is the only protected route in Step 4 (a
minimal placeholder — the real dashboard is a later step). The landing
page (`/`) remains unprotected.

### Auth components

```
components/auth/
├── AuthLayout.tsx    — shared centered-card wrapper for /login, /register
├── LoginForm.tsx     — email + password, loading/error states, disabled
│                       submit while in flight (prevents duplicate requests)
└── RegisterForm.tsx  — name + email + password + confirm, redirects to
                        /login on success (not auto-login — see above)
```

No `ForgotPasswordForm`, `ResetPasswordForm`, or OTP-related component
exists.

## Error codes

| Code | HTTP status | Meaning |
|---|---|---|
| `AUTH_EMAIL_EXISTS` | 409 | Registration with an already-registered email |
| `AUTH_INVALID_CREDENTIALS` | 401 | Login failed — generic, never reveals which part was wrong |
| `AUTH_USER_INACTIVE` | 403 | Valid credentials/token, but the account is deactivated |
| `AUTH_INVALID_TOKEN` | 401 | Missing, malformed, wrong-signature token, or the user no longer exists |
| `AUTH_TOKEN_EXPIRED` | 401 | Valid token that has passed its expiration |
| `422` (FastAPI validation) | 422 | Request body failed schema validation (e.g. passwords don't match, invalid email format) |

All auth errors follow the same shape established in Step 3:
`{"error": {"code", "message"}}` — no traceback, no MongoDB detail,
no JWT internals ever reach the client.

## Future OTP compatibility

Not implemented, and no groundwork code exists for it (no OTP
collection, no OTP routes, no OTP dependency installed) — Step 4
explicitly avoids building unused scaffolding for a feature that isn't
being implemented yet. The documented future shape, if/when it's
built:

```
Register → email verification / OTP → account activation
```

This would likely add an `is_verified` (or similar) field to the
`users` document and a verification-gate check somewhere in the login
flow — but that's a decision for whichever future step actually
implements it, made with real requirements in hand rather than guessed
now.

## Security considerations / current V1 limitations

- No token revocation — see "Logout" above.
- No refresh tokens — a user must log in again once the access token
  expires (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, default 60).
- No rate limiting on `/auth/login` or `/auth/register` — brute-force/
  enumeration protection beyond the generic error message is not
  implemented in V1.
- Token storage is localStorage, not an HttpOnly cookie — see the
  trade-off note above.
- No email verification — an account is usable immediately after
  registration with an unverified email address.
- No password complexity rules beyond a minimum length (8 characters)
  — intentional, per NIST SP 800-63B's guidance against composition
  rules that don't meaningfully improve real-world password strength.
