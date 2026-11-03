# ShopEx — Architecture & Contracts

> **ShopEx** — *Eat smarter & shop master.*
> Saves money on groceries: finds the cheapest offer for every item of a grocery list across the
> grocery stores around the user, then plans the fastest route between the chosen stores.

This document is the **single source of truth** shared by every part of the codebase. If code and
this document disagree, fix the code (or update this document deliberately, in the same change).

---

## 1. Product requirements (from the ShopEx spec)

1. Detect the user's location.
2. Discover every grocery store in the area (OpenStreetMap / Overpass).
3. For every store, hold a price for every catalog item; filterable by section, price, brand,
   organic, on-sale, dietary tags, chain, distance; sortable by price / unit price / distance.
4. Refresh the database **every day** (stores + prices).
5. User enters a grocery list (item name, optional favourite brand, quantity) and submits it.
6. For each item: the **cheapest** offer + **2 alternative** offers nearby.
7. Show per item: product name, brand, store, distance to store, price. An **"i"** button opens
   "See more options" with the 2 alternatives; the user can swap to one.
8. After the user approves every item, compute the **fastest itinerary** visiting each chosen store.
9. Look & feel inspired by food-delivery apps (bold, card-based, carousels, sticky CTA, bottom tabs),
   **bilingual French / English**, very intuitive, **tutorial on first launch**.
10. Every user has an **account**; past lists are remembered (history) and lists can be
    **bookmarked** as reusable templates.
11. Prices are **demo prices** (generated) behind a pluggable price-source interface; the UI must
    clearly say so (`prices_are_demo`). Store locations are real (OpenStreetMap, ODbL — the UI must
    show "© OpenStreetMap contributors" wherever OSM data/maps are shown).

### Non-negotiable rules
- Clean code; do not break existing features.
- Only copyright-free / permissively licensed content (MIT/Apache/BSD/OFL/CC0, OSM under ODbL with
  attribution). Demo product brands are **fictional**. No third-party logos.
- No backdoors. No secrets/passwords in code — secrets come from environment variables only.
- Security checks must pass before deploying. Code is verified twice before publishing.

---

## 2. Repository layout

```
shopEx/
├── backend/                     Python 3.12+ · FastAPI · SQLAlchemy 2 · Pydantic 2
│   ├── app/
│   │   ├── main.py              FastAPI app, CORS, router wiring, startup (create tables, seed catalog)
│   │   ├── config.py            Settings (pydantic-settings, env vars — §6)
│   │   ├── db.py                engine, SessionLocal, Base, get_db()
│   │   ├── deps.py              get_current_user(), require_admin_token()
│   │   ├── security.py          password hashing (argon2), JWT encode/decode, login rate limiter
│   │   ├── schemas.py           ALL Pydantic request/response models (§4) — shared contract
│   │   ├── models/
│   │   │   ├── __init__.py      re-exports every model
│   │   │   ├── user.py          User
│   │   │   ├── lists.py         GroceryList
│   │   │   └── catalog.py       Store, AreaFetch, Section, Product, Price
│   │   ├── routers/
│   │   │   ├── auth.py          /auth/*
│   │   │   ├── users.py         /users/me
│   │   │   ├── lists.py         /lists/*
│   │   │   ├── stores.py        /stores, /catalog/*
│   │   │   ├── search.py        /search
│   │   │   ├── itinerary.py     /itinerary
│   │   │   └── admin.py         /admin/refresh, /health
│   │   ├── services/
│   │   │   ├── geo.py           haversine, bounding helpers, area cell keys
│   │   │   ├── stores.py        Overpass discovery + caching + demo-store fallback
│   │   │   ├── catalog.py       catalog seeding, product queries with filters
│   │   │   ├── matching.py      grocery-list item → offers (cheapest + 2 alternatives)
│   │   │   ├── routing.py       OSRM table/route client + estimate fallback
│   │   │   ├── itinerary.py     TSP solver (Held-Karp ≤ 12, else NN + 2-opt), maps URL
│   │   │   └── price_sources/
│   │   │       ├── base.py      PriceSource protocol, PriceQuote dataclass, registry
│   │   │       └── demo.py      deterministic daily demo prices
│   │   ├── data/
│   │   │   └── catalog_seed.py  sections + products (fictional brands, fr/en names, keywords)
│   │   └── jobs/
│   │       └── refresh.py       daily refresh (CLI: python -m app.jobs.refresh) + optional in-process loop
│   ├── tests/                   pytest (one test module per router/service)
│   ├── requirements.txt         runtime deps (pinned)
│   ├── requirements-dev.txt     -r requirements.txt + pytest, ruff, bandit, pip-audit
│   ├── pyproject.toml           ruff + pytest config
│   └── .env.example
├── client/                      Expo (React Native + web) · TypeScript strict · expo-router
│   ├── app/                     expo-router routes (§5)
│   ├── src/
│   │   ├── api/types.ts         TS mirror of §4 (shared contract)
│   │   ├── api/client.ts        typed fetch wrapper + one function per endpoint
│   │   ├── auth/                AuthProvider, token storage (SecureStore native / localStorage web)
│   │   ├── i18n/                I18nProvider, useT(), locales/{fr,en}/*.ts
│   │   ├── theme.ts             design tokens (light + dark)
│   │   ├── components/ui/       shared primitives (Button, Card, Screen, TextField, Chip, Badge, ...)
│   │   ├── components/          feature components
│   │   ├── hooks/               useLocation, useSettings, ...
│   │   └── utils/               formatting (price, distance), maps URLs
│   ├── assets/                  icon.png, splash, adaptive-icon (generated, original artwork)
│   ├── app.json · eas.json · tsconfig.json · package.json
│   └── .env.example             EXPO_PUBLIC_API_URL, EXPO_PUBLIC_TILE_URL
├── .github/workflows/
│   ├── ci.yml                   backend tests + lint + bandit + pip-audit; client typecheck + lint + tests + npm audit + web export
│   └── daily-refresh.yml        cron → POST /api/v1/admin/refresh with secret token
├── render.yaml                  Render blueprint (API web service, static web app; database on Neon)
├── docs/                        ARCHITECTURE.md, DEPLOY_RENDER.md, MOBILE_BUILD.md, SECURITY.md
└── README.md
```

---

## 3. Data model (SQLAlchemy 2.0, typed `Mapped[...]`)

`Base` lives in `app/db.py`. All timestamps are timezone-aware UTC.

**User** (`users`): `id` int PK · `email` str unique, stored lower-case · `password_hash` str ·
`display_name` str · `language` `"fr"|"en"` (default `"fr"`) · `search_radius_km` float (default 10) ·
`travel_mode` `"driving"|"walking"|"cycling"` (default `"driving"`) · `tutorial_completed` bool (default
false) · `created_at`.

**GroceryList** (`grocery_lists`): `id` · `user_id` FK users (cascade delete) · `name` str ·
`items` JSON (list of `GroceryItemInput` dicts) · `bookmarked` bool · `created_at` · `last_used_at`.
History = all lists of the user ordered by `last_used_at desc`; bookmarks = `bookmarked = true`.

**Store** (`stores`): `id` · `osm_id` str unique nullable (e.g. `"node/123"`) · `name` · `chain`
nullable (OSM `brand` tag, else name) · `address` nullable · `lat` · `lon` · `source` `"osm"|"demo"` ·
`price_tier` `"discount"|"standard"|"premium"` · `last_seen_at`.

**AreaFetch** (`area_fetches`): `id` · `cell_key` str unique (lat/lon rounded to 0.05° + radius bucket)
· `lat` · `lon` · `radius_km` · `fetched_at`. An area is re-fetched from Overpass when older than 24 h
(by the daily job, which treats areas older than 23 h as due so a cell refreshed slightly later in
the previous run is not skipped) or on demand when missing. When Overpass fails, a cached area keeps
its stores and is retried after 1 h; an uncached area gets clearly-labelled demo stores when
`DEMO_STORES_FALLBACK` is on, otherwise the endpoint answers 503.

**Section** (`sections`): `id` str slug PK · `name_fr` · `name_en` · `sort_order` int.

**Product** (`products`): `id` · `slug` unique · `name_fr` · `name_en` · `brand` · `section_id` FK ·
`size_value` float · `size_unit` `"g"|"kg"|"ml"|"L"|"unit"` · `tags` JSON list (subset of
`organic, gluten_free, vegan, vegetarian, lactose_free, local, store_brand`) · `keywords` JSON list
(lower-case, accent-free fr + en synonyms used for matching).

**Price** (`prices`): `id` · `store_id` FK · `product_id` FK · `price` float (CAD) · `regular_price`
float · `on_sale` bool · `unit_price` float · `unit_price_unit` `"kg"|"L"|"unit"` · `source` str
(price-source name) · `updated_at`. Unique `(store_id, product_id)`.

Tables are created with `Base.metadata.create_all()` at startup (no migration tool for v1); the catalog
seed is idempotent (upsert by slug / section id).

---

## 4. HTTP API — base path `/api/v1`, JSON, auth = `Authorization: Bearer <jwt>`

All endpoints require auth **except** `POST /auth/register`, `POST /auth/login`, `GET /health`, and
`POST /admin/refresh` (which uses `X-Admin-Token`). Errors use FastAPI's `{"detail": ...}` with proper
status codes (400/401/403/404/409/422/429/503). Pydantic models live in `app/schemas.py`; TypeScript
mirrors live in `client/src/api/types.ts` with **identical field names (snake_case)**. Resource ids are
32-bit (`1..2³¹−1`); larger values are rejected with 422. A 429 carries `Retry-After` (exposed to
browsers through CORS). `/stores`, `/catalog/offers` and `/search` answer 503 when no store can be
discovered for the area.

### Shared types
```
Language       = "fr" | "en"
TravelMode     = "driving" | "walking" | "cycling"
SortBy         = "price" | "unit_price" | "distance"
DietaryTag     = "organic" | "gluten_free" | "vegan" | "vegetarian" | "lactose_free" | "local" | "store_brand"

User           { id, email, display_name, language, search_radius_km, travel_mode, tutorial_completed, created_at }
TokenResponse  { access_token, token_type: "bearer", user: User }

GroceryItemInput { name: str(1..100), brand: str(≤60)|null = null, quantity: int(1..99) = 1 }
GroceryList      { id, name, items: GroceryItemInput[], bookmarked, created_at, last_used_at }
GroceryListSummary { id, name, items_count, bookmarked, created_at, last_used_at }

Store   { id, name, chain|null, address|null, lat, lon, distance_km|null, source: "osm"|"demo", price_tier }
Section { id, name_fr, name_en }
Product { id, slug, name_fr, name_en, brand, section_id, size_value, size_unit, tags: DietaryTag[] }
Offer   { price_id, product: Product, store: Store, price, regular_price, on_sale,
          unit_price, unit_price_unit, updated_at, source }
```

### Auth & user
| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/register` | `{email, password(8..128), display_name(1..60), language?}` | 201 `TokenResponse` · 409 email taken |
| POST | `/auth/login` | `{email, password}` | `TokenResponse` · 401 generic "invalid credentials" · 429 rate-limited (5 failures / 5 min per email+IP) |
| GET | `/users/me` | — | `User` |
| PATCH | `/users/me` | `{display_name?, language?, search_radius_km?(1..50), travel_mode?, tutorial_completed?}` | `User` |
| DELETE | `/users/me` | — | 204 (deletes account + lists) |

### Lists (history & bookmarks)
| Method | Path | Body / query | Response |
|---|---|---|---|
| GET | `/lists` | `?bookmarked=true|false` (omit = all) | `GroceryListSummary[]` (by `last_used_at desc`) |
| POST | `/lists` | `{name(1..80), items(1..100), bookmarked=false}` | 201 `GroceryList` |
| GET | `/lists/{id}` | — | `GroceryList` (404 if not owner) |
| PATCH | `/lists/{id}` | `{name?, items?, bookmarked?}` | `GroceryList` |
| DELETE | `/lists/{id}` | — | 204 |

### Stores & catalog
| Method | Path | Query | Response |
|---|---|---|---|
| GET | `/stores` | `lat, lon, radius_km?` (default user's, max `MAX_RADIUS_KM`) | `Store[]` sorted by distance (discovers + prices the area if not cached) |
| GET | `/catalog/sections` | — | `Section[]` |
| GET | `/catalog/offers` | `lat, lon, radius_km?, q?, section?, brand?, chain?, tags?(comma list), on_sale?, min_price?, max_price?, store_id?, sort=price|unit_price|distance, limit(1..100)=30, offset=0` | `{ items: Offer[], total: int, prices_are_demo: bool }` |

### Search (the core flow)
`POST /search`
```
request  { lat, lon, radius_km?: float, items: GroceryItemInput[](1..100),
           filters?: { tags?: DietaryTag[], on_sale_only?: bool, max_price?: float,
                       exclude_chains?: str[], sort_by?: "price"|"unit_price" = "price" },
           save_to_history: bool = true, list_name?: str, list_id?: int }
response { list_id: int|null, prices_are_demo: bool, currency: "CAD",
           results: ItemResult[], stores: Store[], best_total: float }
ItemResult { query: GroceryItemInput, matched: bool, brand_matched: bool|null,
             best: Offer|null, alternatives: Offer[] (0..2), line_total: float|null,
             message_key: str|null }
```
- `brand_matched` is `null` when no brand was requested; `false` when the brand was requested but not
  found (results fall back to any brand).
- `message_key` is an i18n key for the client: `"search.no_match"`, `"search.brand_not_found"`.
- Ranking: candidate products = fuzzy match of the item name against product names/keywords
  (accent/case-insensitive, fr + en); candidate offers = their prices in stores within the radius,
  after filters; sorted by `price` (or `unit_price`), ties by distance. `best` = first, `alternatives`
  = next 2 distinct (product, store) offers. `line_total = best.price * quantity`.
- `stores` = unique stores of all `best` offers, sorted by distance. `best_total` = Σ line_total.
- When `save_to_history` is true: updates `list_id` if given (touches `last_used_at`, replaces items)
  else creates a new non-bookmarked list named `list_name` or a dated default name. A `list_id` that is
  not one of the caller's lists is a 404 (checked before any other work); `list_name` given together
  with `list_id` renames that list.

### Itinerary
`POST /itinerary`
```
request  { start: {lat, lon}, store_ids: int[](1..15, unique), travel_mode?: TravelMode,
           return_to_start: bool = false }
response { stops: ItineraryStop[], total_distance_km, total_duration_min,
           geometry: [lat, lon][] | null, routing_source: "osrm"|"estimate", maps_url: str }
ItineraryStop { order (1-based), store: Store, leg_distance_km, leg_duration_min, arrival_min }
```
- Travel-time matrix from OSRM `/table/v1/{profile}`; on failure/timeout fall back to haversine ×
  1.3 detour at 35 km/h (driving), 15 (cycling), 5 (walking) → `routing_source: "estimate"`.
- Order minimises total duration: exact Held-Karp DP for ≤ 12 stores, else nearest neighbour + 2-opt.
- `geometry` from OSRM `/route` (`overview=full&geometries=geojson`, converted to `[lat, lon]`), else null.
- `maps_url`: Google Maps directions URL (`https://www.google.com/maps/dir/?api=1&origin=..&destination=..&waypoints=a|b&travelmode=..`).
  Google honours about 9 waypoints, so a route with more than 10 stops may lose stops in that link;
  the in-app map and stop list are always complete.
- With `return_to_start`, the totals include the leg back to the start, which has no stop entry
  (`total_duration_min − last stop's arrival_min`).
- Unknown store ids → 404 with a plain-string `detail` listing them.

### Admin & health
| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/health` | none | `{status: "ok", version: str}` |
| POST | `/admin/refresh` | header `X-Admin-Token` == env `ADMIN_TOKEN` (constant-time compare). If `ADMIN_TOKEN` is unset the endpoint returns 404. Wrong token → 403. | `{areas_refreshed, stores_refreshed, prices_updated, started_at, finished_at}` |

---

## 5. Client (Expo, expo-router, TypeScript strict)

Targets **web, iOS, Android** from one codebase. Path alias `@/` → `client/src/`.

### Routes (`client/app/`)
| Route file | Screen |
|---|---|
| `_layout.tsx` | Providers (Theme, I18n, Auth, Settings) + Stack. Gate: not onboarded → `/onboarding`; no token → `/login` |
| `onboarding.tsx` | First-launch tutorial carousel (5 slides: welcome+slogan · build your list · we find the cheapest · "i" for more options · fastest route). Skip / Next / Done. Re-playable from Profile |
| `(auth)/login.tsx`, `(auth)/register.tsx` | Auth screens, language switch visible |
| `(tabs)/_layout.tsx` | Bottom tabs: Home · Browse · Lists · Profile |
| `(tabs)/index.tsx` | Home: greeting, current location chip, big "New grocery list" CTA, bookmarks carousel, recent lists |
| `(tabs)/browse.tsx` | Catalog browse: search box, section chips carousel, filter sheet (price range, brand, chain, tags, on-sale, distance, sort) |
| `(tabs)/lists.tsx` | Segmented: History / Bookmarks; tap → reuse in editor; star toggles bookmark; swipe/delete |
| `(tabs)/profile.tsx` | Display name, language FR/EN, radius, travel mode, replay tutorial, logout, delete account, about (licences, OSM attribution, demo-price notice) |
| `list/edit.tsx` | List editor (`?listId=` to reuse): add item (name, favourite brand, qty), suggestions, reorder/remove, name, "Find the best prices" sticky CTA |
| `results.tsx` | Per item card: product name, brand, store, distance, price, line total, approve toggle, **"i"** → bottom-sheet "See more options" with 2 alternatives (swap). Demo-price banner. Totals. "Approve all" / "Plan my route" sticky CTA (enabled when all matched items approved) |
| `itinerary.tsx` | Map (Leaflet + OSM tiles: `<iframe srcDoc>` on web, `react-native-webview` on native) with numbered stops + route line, ordered stop list with leg times, totals, "Open in Google Maps" button, OSM attribution |

Search state between `list/edit → results → itinerary` is held in a `SearchSessionProvider`
(`src/search/SearchSession.tsx`) — not in URL params.

### Design system (`src/theme.ts`)
Food-delivery-app feel: white surfaces, bold black type, a single warm accent, large rounded cards,
pill chips, horizontal carousels, bottom sheet modals, sticky full-width CTA.
```
light: primary #F2542D  primaryDark #C8401E  onPrimary #FFFFFF  background #FFFFFF  surface #F5F5F5
       card #FFFFFF  text #191919  textMuted #6B6B6B  border #E6E6E6  success #10A35A  warning #E8A317
       danger #D93025  badgeSale #F2542D
dark:  primary #FF6A43  background #121212  surface #1E1E1E  card #1A1A1A  text #F5F5F5
       textMuted #A3A3A3  border #2E2E2E  (others same)
radius: sm 8 · md 12 · lg 16 · xl 24 · pill 999     spacing: 4 · 8 · 12 · 16 · 24 · 32
font: system font; weights 400/600/800; sizes xs 12 · sm 14 · md 16 · lg 20 · xl 28 · xxl 34
```
Icons: `@expo/vector-icons` (Ionicons, MIT). Logo: original artwork (basket glyph + "ShopEx" wordmark).

### i18n
`useT()` returns `t(key, params?)`; keys are dotted (`"results.see_more"`). Locale files are split per
feature: `src/i18n/locales/{fr,en}/{common,auth,onboarding,home,browse,lists,profile,editor,results,itinerary,search}.ts`.
French is the default; initial language = saved preference → device locale → `fr`. A test enforces that
fr and en have exactly the same keys. All user-visible strings go through `t()`.

### Configuration
`EXPO_PUBLIC_API_URL` (default `http://localhost:8000`; a value without scheme gets `https://`
prepended) · `EXPO_PUBLIC_TILE_URL` (default `https://tile.openstreetmap.org/{z}/{x}/{y}.png`).

---

## 6. Backend configuration (environment variables)

| Variable | Default | Notes |
|---|---|---|
| `ENV` | `development` | `production` enables strict checks |
| `DATABASE_URL` | `sqlite:///./shopex.db` | Production: Neon pooled Postgres URL, set as a secret on Render (`sync: false`). `postgres://` and `postgresql://` without a driver are normalised to `postgresql+psycopg://`, query string (`sslmode`, `channel_binding`) kept; URLs naming a driver are unchanged. Non-SQLite engines use `pool_pre_ping` and `pool_recycle=300` (Neon scales to zero after 5 idle minutes) |
| `JWT_SECRET` | — | **required in production**; in development, a random per-process secret is generated with a warning |
| `JWT_EXPIRE_MINUTES` | `10080` | 7 days |
| `CORS_ORIGINS` | `http://localhost:8081,http://localhost:19006` | comma list |
| `ADMIN_TOKEN` | — | enables `/admin/refresh` when set; at least 32 characters when `ENV=production` |
| `OVERPASS_URL` | `https://overpass-api.de/api/interpreter` | |
| `OSRM_URL` | `https://router.project-osrm.org` | public demo server — replace for production traffic. It only serves the car profile, so walking/cycling durations from it are driving times; a self-hosted OSRM with foot/bike profiles fixes this |
| `HTTP_TIMEOUT_S` | `20` | outbound calls to OSRM |
| `OVERPASS_TIMEOUT_S` | `45` | Overpass query timeout (`[timeout:N]`); the HTTP read timeout is N + 5 s. The public server often needs 20–45 s for a city |
| `MAX_RADIUS_KM` | `50` | |
| `MAX_STORES_PER_AREA` | `60` | nearest N stores kept per discovery |
| `PRICE_SOURCE` | `demo` | registry key in `price_sources`; an unknown key stops the API at startup |
| `DEMO_STORES_FALLBACK` | `true` in development, `false` in production | synthesise clearly-labelled demo stores when Overpass is unreachable |
| `DAILY_REFRESH_IN_PROCESS` | `false` | run the refresh loop inside the API process every 24 h |

Overpass query: `shop ~ ^(supermarket|grocery|greengrocer|wholesale)$` as `node`/`way` within the
radius, `out center tags;`, sent with a descriptive `User-Agent` (`ShopEx/<version>`).

Demo prices (`price_sources/demo.py`): deterministic from `(store chain or id, product slug, date)`:
base price per product × chain-tier factor (discount 0.88–0.95, standard 0.97–1.05, premium
1.08–1.20) × small daily jitter; ~12 % of offers on sale (10–35 % off). Prices change daily (at
00:00 UTC) so the daily refresh is observable. Real chain names are never hard-coded: a store's tier
comes from generic words in its name or OSM shop type (discount / premium hints), else from a stable
hash of its chain, so every store of a chain shares one tier.

---

## 7. Quality gates (must all pass)
- Backend: `pytest` (≥ 85 % of service logic covered), `ruff check`, `bandit -r app -ll`, `pip-audit`.
- Client: `npx tsc --noEmit`, `npx expo lint`, `npx jest` (i18n key parity + utils), `npm audit --omit=dev --audit-level=high`, `npx expo export -p web`.
- No secrets in the repo (`.env` ignored; only `.env.example` committed).
