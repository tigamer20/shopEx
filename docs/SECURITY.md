# ShopEx security

This document summarises how ShopEx protects its users and infrastructure, how secrets and
dependencies are handled, and how to report a vulnerability. The binding technical contract is
[ARCHITECTURE.md](ARCHITECTURE.md); deployment specifics are in [DEPLOY_RENDER.md](DEPLOY_RENDER.md).

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x (latest release) | Yes |
| Anything older | No: upgrade to the latest release |

---

## Threat model summary

**What we protect**

- User accounts: email, display name, password hash, preferences.
- Grocery lists (history and bookmarks), which can reveal personal habits.
- Server secrets: `JWT_SECRET` (token signing), `ADMIN_TOKEN` (refresh endpoint), `DATABASE_URL`
  (contains the database password).
- Availability of the API, the database and the daily refresh.

**What ShopEx does not hold**: no payment data, no stored location history (coordinates are sent
with searches and used to compute results; they are not saved to the user's account), no contacts,
no tracking or advertising identifiers.

**Threats and mitigations**

| Threat | Mitigation |
|---|---|
| Password guessing / credential stuffing on `/auth/login` | Argon2id hashing; 5 failed attempts per 5 minutes per (email, client IP) → 429; generic "invalid credentials" message |
| Account enumeration through login | Same error for unknown email and wrong password; a dummy Argon2 verification on the unknown-email path keeps response times similar. (Registration answers 409 for a taken email: an accepted trade-off for usability.) |
| Stolen or forged access tokens | HS256 JWTs signed with a 32+ character secret from the environment; algorithm pinned on decode; `sub`, `iat` and `exp` required; 7-day expiry; tokens of deleted accounts are rejected |
| Accessing another user's data (IDOR) | Every list operation is scoped to the authenticated user; other users' lists answer 404 |
| Abuse of the admin refresh | `X-Admin-Token` compared in constant time (`hmac.compare_digest`); endpoint answers 404 when `ADMIN_TOKEN` is unset and 403 on a wrong token; token only in Render env and GitHub secrets |
| Injection | SQLAlchemy ORM with bound parameters only; all request bodies and queries validated by Pydantic with explicit bounds (lengths, ranges, list sizes) |
| Server-side request forgery | Outbound hosts (Overpass, OSRM) come from server configuration only, never from client input; every outbound call has a timeout (`HTTP_TIMEOUT_S`, `OVERPASS_TIMEOUT_S`) |
| Resource exhaustion | Hard caps: 100 items per list/search, 15 stores per itinerary (exact solver only up to 12), radius ≤ `MAX_RADIUS_KM`, page size ≤ 100, stores per area ≤ `MAX_STORES_PER_AREA`; Overpass results cached per area for 24 h |
| Cross-site scripting on the web app | React escapes all rendered text (no raw HTML from user data); strict Content-Security-Policy (see below); no third-party scripts except Leaflet 1.9.4 from unpkg, pinned with Subresource Integrity |
| Clickjacking | `X-Frame-Options: DENY` and CSP `frame-ancestors 'none'` |
| Map WebView on mobile | `react-native-webview` with a narrow `originWhitelist`; the JWT is never injected into the WebView; it only receives map data (store coordinates and the route) |
| Secret leakage | Secrets only in environment variables; `.env` files git-ignored; settings use `SecretStr` and hide input values in validation errors; Render generates the production secrets |
| Supply-chain attacks | Dependency vetting policy, exact pins and lockfile, npm install scripts disabled, audits in CI (see below) |
| Tampered deployments | Render deploys only commits whose CI checks passed (`autoDeployTrigger: checksPass`); GitHub Actions use official `actions/*` only, with read-only permissions |

**Accepted risks and known limitations (v1)**

- The login rate limiter is in memory and per process: counters reset when the API restarts (free
  Render instances restart often) and each worker counts separately.
- The rate-limit key uses the client address as seen by Uvicorn. Behind Render's proxy this is the
  proxy's address unless Uvicorn is configured to trust forwarded headers, so the limit then applies
  effectively per email: stronger against guessing, but a third party can delay a victim's logins
  by up to five minutes. Never trust `X-Forwarded-For` blindly; it is client-controlled.
- Other endpoints have no per-user rate limit yet; the input caps above bound the cost of each call.
- Access tokens cannot be revoked individually before expiry (stateless JWTs). Rotating `JWT_SECRET`
  revokes all of them at once.
- On the web, the token is kept in `localStorage`, so an XSS bug could expose it. The CSP is the main
  defence (see the hardening note below).
- Prices are demo data: no real retailer data or credentials are involved.

---

## Secrets handling

**Rule: secrets come from environment variables only.** Nothing secret is ever committed, printed,
or embedded in the apps.

| Secret | Where it lives | How it is created |
|---|---|---|
| `JWT_SECRET` | Render env of `shopex-api` | `generateValue: true` in `render.yaml` (random 256-bit) |
| `ADMIN_TOKEN` | Render env of `shopex-api`, GitHub secret `SHOPEX_ADMIN_TOKEN` | `generateValue: true`, copied once into GitHub; in production the API refuses to start with a token shorter than 32 characters |
| `DATABASE_URL` | Render env of `shopex-api` | Neon pooled connection string, entered as a secret in the Render dashboard (`sync: false`) |
| Store signing keys, Apple/Google credentials | EAS servers (`eas credentials`) | Generated or uploaded through the EAS CLI |

- **Local development**: copy `backend/.env.example` to `backend/.env` (git-ignored). If
  `JWT_SECRET` is empty in development, the API generates a random per-process secret and logs a
  warning; in production (`ENV=production`) it refuses to start without a secret of at least 32
  characters.
- **Tests** generate any secret they need at runtime; no fixed secrets live in the test suite.
- **`EXPO_PUBLIC_*` variables and `eas.json` are public**: they are compiled into the apps. They hold
  URLs only.
- **CI**: GitHub masks secrets in logs; the refresh workflow passes the token in a header, never
  echoes it, and never enables shell tracing.
- **Rotation**: generate a new value with
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`, set it in the Render dashboard
  (and in GitHub for `ADMIN_TOKEN`). Rotating `JWT_SECRET` signs every user out.
- **If a secret leaks**: rotate it first, then remove it from wherever it leaked (rewriting Git
  history if it was committed), and review the API logs for misuse.

## Authentication and authorisation design

- **Passwords**: 8 to 128 characters, hashed with **Argon2id** through `argon2-cffi`'s
  `PasswordHasher` (library-recommended parameters). Hashes are upgraded transparently at login when
  the parameters change. Plain passwords are never logged or stored.
- **Emails**: validated with `email-validator` (syntax only, no DNS lookup) and stored lower-case.
- **Access tokens**: JWT (PyJWT), **HS256**, claims `sub` (user id), `iat`, `exp`; lifetime
  `JWT_EXPIRE_MINUTES` (7 days by default). Decoding pins the algorithm list, so unsigned or
  differently-signed tokens are rejected. The token travels in `Authorization: Bearer <jwt>` only
  (no cookies, hence no CSRF surface).
- **Authorisation**: every endpoint except `POST /auth/register`, `POST /auth/login` and
  `GET /health` requires a valid token, and the user must still exist. User-owned resources are
  always loaded with the owner's id in the query; another user's resource is reported as 404.
- **Rate limiting**: sliding window of 5 failed logins per 5 minutes per (email, client IP), answered
  with 429; a successful login clears the counter.
- **Admin endpoint**: `POST /admin/refresh` uses its own `X-Admin-Token` header, compared in
  constant time.
- **Account deletion**: `DELETE /users/me` removes the account and, by cascade, all of its lists.
- **Client storage**: iOS and Android store the token with `expo-secure-store` (Keychain / Keystore);
  the web app uses `localStorage`.

## Transport and browser security

- HTTPS everywhere: Render terminates TLS and redirects HTTP to HTTPS; release mobile builds use
  HTTPS URLs only.
- CORS: the API allows only the origins listed in `CORS_ORIGINS` (no wildcard).
- Response headers on the web app (`render.yaml`): `Content-Security-Policy`,
  `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin` (keeps the origin that the OpenStreetMap tile
  policy requires), and `Permissions-Policy` (geolocation for the app itself only; camera,
  microphone, payment and USB disabled).
- The CSP allows scripts and styles from the site itself and `https://unpkg.com` (Leaflet), images
  from the site, `data:`/`blob:` and the OSM tile server, and network calls to the site and the API
  only. `object-src 'none'`, `base-uri 'self'` and `frame-ancestors 'none'` are set.
- **Hardening note**: the itinerary map on the web is an `<iframe srcdoc>`, which inherits the page's
  CSP; its inline bootstrap script is why `script-src` contains `'unsafe-inline'`. Moving the map into
  a static HTML file served from the site (receiving its data through `postMessage`) would allow
  removing `'unsafe-inline'` from `script-src`.

---

## Dependency vetting policy

Only dependencies that passed vetting may be installed, at the exact vetted version.

**A package (or a new version of one) is accepted only if:**

1. It is the **genuine upstream project**: the repository and maintainers are verified, and the name
   is not a look-alike (for example `pyjwt`, not `jwt`).
2. Its licence is **permissive** (MIT, BSD, Apache-2.0, ISC, 0BSD, Unlicense, or similar). Any
   exception is documented with its justification; today the only one is the PostgreSQL driver
   `psycopg` (LGPL-3.0), used unmodified as a separately installed library.
3. The release is **at least 14 days old**, so that compromised or broken releases have time to be
   caught by the community.
4. [OSV](https://osv.dev/) lists **no advisory affecting that version** and **no malicious-package
   (MAL) entry** for the package.
5. Build provenance or a publish attestation is present where the ecosystem supports it, and npm
   packages need **no install scripts** to work.
6. It is actually needed: prefer the standard library or an already vetted package.

**How it is applied**

- Python: exact `==` pins in `backend/requirements.txt` (runtime) and `requirements-dev.txt`
  (tooling), including important transitive dependencies.
- JavaScript: exact versions in `client/package.json` plus the committed `package-lock.json`;
  installs use `npm ci`; `client/.npmrc` sets `ignore-scripts=true` so dependency install scripts
  never run.
- Patched transitive versions are pinned with `overrides` in `client/package.json` when the direct
  dependency still pulls a vulnerable one. Current overrides, both inside Expo's build tooling
  (`@expo/cli`, not shipped in the app bundle):
  - `node-forge` 1.4.2 (fixes GHSA-86w9-cpqp-85rv, GHSA-7wch-p9px-956x, GHSA-jc66-7q78-782g,
    GHSA-8hrf-8g6f-7xwp, GHSA-hqq3-7jhf-c5jx, GHSA-5x38-2vff-x55p and the lower-severity
    advisories of 1.4.0). **Documented exception to rule 3**: no patched release was 14 days old
    when the advisories were published (1.4.1 and 1.4.2 both date from 2026-10-27). It was accepted
    because it comes from the upstream maintainers (digitalbazaar), has no install scripts, no OSV
    advisory or MAL entry, and its diff against 1.4.0 only contains the security fixes. Revisit
    when Expo ships a release that depends on a fixed version.
  - `zod` 4.6.7 (fixes GHSA-mrhx-c7xc-m3w5; 3.x has no fix). `@expo/cli` only uses API that zod 4
    keeps (`object`, `string`, `enum`, `union`, `safeParse`...). Published with npm provenance,
    no install scripts, no OSV entry; it is the same version ESLint's React hooks plugin already
    uses.
- Browser CDN: Leaflet 1.9.4 from unpkg is loaded with Subresource Integrity hashes.
- GitHub Actions: only official `actions/*` actions pinned to a major version, workflows with
  `contents: read` (CI) or no permissions at all (daily refresh), and checkouts without persisted
  credentials.
- Adding or upgrading a dependency is a pull request that states the package, version, purpose,
  licence and the checks above; it is reviewed before merge.

## How CI enforces it

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every pull request and on every
push to `main`:

| Check | Fails the build when |
|---|---|
| `pip-audit -r requirements.txt` | a runtime Python dependency has a known vulnerability |
| `npm audit --omit=dev --audit-level=high` | a runtime JavaScript dependency has a high or critical advisory |
| `bandit -r app -ll` | the API code contains a medium- or high-severity security issue |
| `ruff check .` | lint fails, including the flake8-bandit (`S`) security rules |
| `ruff format --check .` | the API code is not formatted |
| `pytest --cov` | a test fails (auth, ownership checks, admin token, validation, ...) or coverage drops below 85 % |
| `npm run typecheck`, `npm run lint`, `npm test`, `npx expo export -p web` | the app does not type-check, lint, pass its tests or build |

Render deploys a commit only after these checks pass (`autoDeployTrigger: checksPass`). Code is
therefore verified twice before it is published: on the pull request, and again on `main` before
the deployment.

---

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

1. Use GitHub's private reporting: on the repository page, open the **Security** tab and click
   **Report a vulnerability** (the repository owner enables this under
   **Settings > Code security > Private vulnerability reporting**).
2. Describe the issue, the affected version or commit, the steps to reproduce and the impact you
   expect. Do not include real user data.
3. You will receive an acknowledgement within 5 business days. We will agree on a fix and disclosure
   timeline with you, and credit you in the release notes if you wish.

Please test only against your own local or self-deployed instance: no denial-of-service testing, no
access to other users' data, and no social engineering.
