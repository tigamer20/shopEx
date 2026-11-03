# ShopEx

> **Eat smarter & shop master.**

ShopEx saves you money on groceries. Type your grocery list, and ShopEx finds the cheapest offer for
every item across the grocery stores around you, shows you two alternatives for each item, and then
plans the fastest route between the stores you picked.

It runs on **web, Android and iOS** from one codebase, in **French and English**.

> **Status: in development.** The application code is being added to this repository; v1.0.0 has
> not been released yet.

---

## Features

- **Location-aware store discovery**: finds every grocery store around you using real OpenStreetMap
  data (supermarkets, grocers, greengrocers, wholesale clubs).
- **Smart grocery list**: item name, optional favourite brand and quantity, with suggestions as you
  type.
- **Cheapest offer per item**: fuzzy matching in French and English (accents and case are ignored),
  ranked by price or unit price, with ties broken by distance.
- **"i" for more options**: each result has two nearby alternatives you can swap in with one tap.
- **Fastest itinerary**: an exact route optimiser for up to 12 stores (and a fast heuristic above
  that), drawn on an OpenStreetMap map, with an "Open in Google Maps" shortcut.
- **Browse the catalog**: filter by section, price, brand, chain, organic and dietary tags, on-sale
  items and distance; sort by price, unit price or distance.
- **Accounts, history and bookmarks**: past lists are remembered, and any list can be bookmarked as
  a reusable template.
- **Daily refresh**: stores and prices are refreshed every day.
- **Bilingual and friendly**: French (default) and English, light and dark themes, and a tutorial
  on first launch that you can replay from your profile.
- **Honest about data**: prices are clearly labelled as demo prices, and OpenStreetMap is credited
  wherever its data or maps appear.

## Screenshots

> Screenshots will be added before the first store release. Put them in `docs/screenshots/` and
> reference them here.

| Home | List editor | Results | Itinerary |
|---|---|---|---|
| *coming soon* | *coming soon* | *coming soon* | *coming soon* |

## Tech stack

| Layer | Technology |
|---|---|
| API | Python 3.14 (3.12+ supported), FastAPI, SQLAlchemy 2 (typed), Pydantic 2, Uvicorn |
| Database | SQLite for local development, PostgreSQL in production (psycopg 3) |
| Auth | Argon2id password hashing (argon2-cffi), JWT access tokens (PyJWT, HS256), login rate limiting |
| Data | OpenStreetMap via the Overpass API (stores), OSRM (travel times and routes), demo price source |
| App | Expo SDK 58, React Native 0.88, React 19, expo-router, TypeScript (strict), react-native-web |
| Maps | Leaflet 1.9.4 with OpenStreetMap tiles (iframe on web, react-native-webview on mobile) |
| Quality | pytest + coverage, ruff, bandit, pip-audit; tsc, ESLint (eslint-config-expo), Jest, npm audit |
| Hosting | Render (API web service, static web app), Neon (Postgres), GitHub Actions (CI and daily refresh), EAS Build (mobile) |

## Architecture

```
 Expo app (web / iOS / Android)
        │  HTTPS, JSON, Bearer JWT
        ▼
 FastAPI  /api/v1  ──────►  PostgreSQL (users, lists, stores, catalog, prices)
        │
        ├──► Overpass API  (store discovery, cached per area for 24 h)
        └──► OSRM          (travel-time matrix + route geometry; distance estimate as fallback)

 GitHub Actions (daily 09:00 UTC) ──► POST /api/v1/admin/refresh  (X-Admin-Token)
```

- `backend/`: FastAPI app split into routers (HTTP), services (store discovery, matching, routing,
  itinerary solver, pluggable price sources) and SQLAlchemy models.
- `client/`: Expo app with file-based routes in `client/app/` and shared code in `client/src/`
  (typed API client, auth, i18n, theme, UI components).

The full contract (data model, every endpoint and payload, environment variables, routes, theme,
i18n and quality gates) lives in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Quick start (local development)

Prerequisites: **Python 3.12+** (3.14 recommended), **Node.js 24** with npm, and Git.
For mobile: the **Expo Go** app or an Android emulator / iOS simulator.

### 1. API (backend)

**Windows (PowerShell)**

```powershell
cd backend
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**macOS / Linux**

```bash
cd backend
python3.14 -m venv .venv          # or python3 if it is 3.12 or newer
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Check it: <http://localhost:8000/api/v1/health> should return `{"status": "ok", ...}`, and the
interactive API documentation is at <http://localhost:8000/docs>.
In development the API uses a local SQLite file (`backend/shopex.db`) and creates its tables and
catalog on startup. `--host 0.0.0.0` lets a phone or emulator on your network reach it; drop it to
listen on `localhost` only.

### 2. App (client)

In a second terminal:

```bash
cd client
npm ci                       # installs the exact versions from package-lock.json
cp .env.example .env         # Windows PowerShell: Copy-Item .env.example .env
npx expo start
```

Then press:

- `w`: open in the browser (web)
- `a`: open on an Android emulator or a connected device
- `i`: open on the iOS simulator (macOS only)

Or scan the QR code with Expo Go on your phone.

**Pointing the app at your API**: set `EXPO_PUBLIC_API_URL` in `client/.env`, then restart
`npx expo start` (values are read when the bundle is built).

| Where the app runs | `EXPO_PUBLIC_API_URL` |
|---|---|
| Web browser, iOS simulator | `http://localhost:8000` (the default) |
| **Android emulator** | `http://10.0.2.2:8000` (the emulator's alias for your computer's `localhost`) |
| Physical phone (same Wi-Fi) | `http://<your computer's LAN IP>:8000`, with the API started with `--host 0.0.0.0` |

## Configuration (environment variables)

Secrets are only ever read from the environment; never commit a `.env` file (only the
`.env.example` templates are tracked).

**API** (`backend/.env`; full reference in `backend/.env.example` and ARCHITECTURE.md §6)

| Variable | Default | Purpose |
|---|---|---|
| `ENV` | `development` | `production` enables strict checks |
| `DATABASE_URL` | `sqlite:///./shopex.db` | SQLAlchemy URL; `postgres://` URLs are accepted |
| `JWT_SECRET` | (random in development) | Token signing key, **required in production** (32+ characters) |
| `JWT_EXPIRE_MINUTES` | `10080` | Token lifetime (7 days) |
| `CORS_ORIGINS` | `http://localhost:8081,http://localhost:19006` | Browser origins allowed to call the API |
| `ADMIN_TOKEN` | (unset) | Enables `POST /api/v1/admin/refresh` |
| `OVERPASS_URL` | `https://overpass-api.de/api/interpreter` | Store discovery endpoint |
| `OSRM_URL` | `https://router.project-osrm.org` | Routing server (public demo server: replace it for real traffic) |
| `HTTP_TIMEOUT_S` | `20` | Timeout for outbound calls to OSRM |
| `OVERPASS_TIMEOUT_S` | `45` | Overpass query timeout (store discovery) |
| `MAX_RADIUS_KM` | `50` | Largest search radius accepted |
| `MAX_STORES_PER_AREA` | `60` | Nearest stores kept per discovery |
| `PRICE_SOURCE` | `demo` | Price source plug-in |
| `DEMO_STORES_FALLBACK` | `true` in dev, `false` in prod | Labelled demo stores when Overpass is unreachable |
| `DAILY_REFRESH_IN_PROCESS` | `false` | Run the 24 h refresh loop inside the API process |

**App** (`client/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `EXPO_PUBLIC_API_URL` | `http://localhost:8000` | API base URL (`https://` is added when the scheme is missing) |
| `EXPO_PUBLIC_TILE_URL` | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` | Map tile template |

`EXPO_PUBLIC_*` values are embedded in the app bundle, so they must never contain secrets.

## Tests and quality gates

Every gate below runs in CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) on each push to
`main` and on every pull request, and Render deploys only commits whose checks passed.

**API** (from `backend/`, with the virtual environment active):

```bash
ruff check .                                  # lint + import order + security lint rules
pytest --cov --cov-report=term-missing        # unit and API tests with coverage
bandit -r app -ll                             # static security analysis
pip-audit -r requirements.txt                 # known vulnerabilities in runtime dependencies
```

**App** (from `client/`):

```bash
npm run typecheck                             # tsc --noEmit (strict)
npm run lint                                  # expo lint
npm test                                      # Jest (i18n key parity, utilities, ...)
npm audit --omit=dev --audit-level=high       # known vulnerabilities in runtime dependencies
npx expo export -p web                        # production web build into dist/
```

## Deployment

- **Web + API on Render, database on Neon** (both in Ohio, free tiers): Render Blueprint
  ([render.yaml](render.yaml)) plus a Neon Postgres project, step by step in
  [docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md).
- **Android and iOS apps**: EAS Build and Submit, see [docs/MOBILE_BUILD.md](docs/MOBILE_BUILD.md).
- **Security model and dependency policy**: [docs/SECURITY.md](docs/SECURITY.md).

## Data sources and licences

- **Store locations**: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors,
  available under the [Open Database Licence (ODbL)](https://opendatacommons.org/licenses/odbl/).
  The app shows "© OpenStreetMap contributors" wherever OSM data or maps appear. Stores are
  retrieved through the [Overpass API](https://overpass-api.de/); please respect its usage policy.
- **Map tiles**: OpenStreetMap standard tiles, subject to the
  [OSM Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/). For significant
  traffic, switch `EXPO_PUBLIC_TILE_URL` to a tile provider you have an agreement with.
- **Routing**: [OSRM](https://project-osrm.org/) (BSD-2-Clause). The public demo server is for light
  use only; set `OSRM_URL` to your own instance for production traffic. When it is unreachable,
  ShopEx falls back to a labelled distance-based estimate.
- **Prices are demo prices.** They are generated deterministically each day by the `demo` price
  source and do not reflect real store prices. The app says so on every results screen
  (`prices_are_demo`). Real price feeds can be added behind the same price-source interface.
- **Brands are fictional.** Product brands in the demo catalog are invented; any resemblance to a
  real brand is coincidental. ShopEx ships no third-party logos. Store names and chains come from
  OpenStreetMap tags and are shown as factual information only.
- **Artwork**: the ShopEx logo and app icons are original artwork. Icons in the UI come from
  Ionicons (MIT) via `@expo/vector-icons`.
- **Libraries**: all dependencies are permissively licensed (MIT, BSD, Apache-2.0, 0BSD,
  Unlicense), except the PostgreSQL driver psycopg (LGPL-3.0), which is used unmodified as a
  separately installed library. Leaflet is BSD-2-Clause.

## Release notes

### v1.0.0 (planned)

First public release (not released yet).

- Accounts with Argon2-hashed passwords, JWT sessions and login rate limiting; profile settings
  (language, search radius, travel mode) and account deletion.
- Store discovery from OpenStreetMap with a 24-hour area cache.
- Demo catalog with fictional brands, bilingual product names and a deterministic daily demo price
  source.
- Grocery list search: cheapest offer plus two alternatives per item, favourite-brand matching,
  dietary and price filters.
- Fastest-route itinerary (exact for up to 12 stores) with map, leg times and Google Maps hand-off.
- Catalog browsing with filters and sorting; list history and bookmarks.
- French and English UI, light and dark themes, first-launch tutorial.
- Daily refresh through GitHub Actions; Render Blueprint deployment with Neon Postgres; EAS build
  profiles for Android and iOS.

## Licence

No licence has been chosen for the ShopEx source code yet: until a `LICENSE` file is added, all
rights are reserved by the author. Third-party components keep their own licences, listed above.
