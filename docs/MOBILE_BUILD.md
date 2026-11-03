# Building and publishing the ShopEx mobile apps

ShopEx's Android and iOS apps are built from `client/` with **EAS Build** (Expo Application Services)
and published with **EAS Submit**. No local Android Studio or Xcode setup is needed for store builds;
EAS builds in the cloud and manages signing keys for you.

All commands run from `client/`. The EAS CLI is used through `npx` with a pinned version (it is not a
project dependency):

```bash
npx eas-cli@25.2.0 --version
```

> Store fees and policies quoted here were current in November 2026. Check the Google Play Console
> and Apple Developer sites before you rely on them.

---

## 1. Build profiles (`client/eas.json`)

| Profile | Output | Distribution | `EXPO_PUBLIC_API_URL` | Use it for |
|---|---|---|---|---|
| `development` | Dev client (APK / IPA) | Internal | `http://localhost:8000` | Debugging native code with a development build (needs `expo-dev-client`, see note) |
| `preview` | **Android APK**, iOS ad hoc IPA | Internal | production API | Side-loading on testers' phones |
| `preview-simulator` | iOS Simulator `.app` | n/a | production API | Running a release-like build on the iOS Simulator |
| `production` | **Android AAB**, iOS App Store IPA | Store | production API | Google Play and the App Store; build numbers auto-increment |

`submit.production` sends Android builds to the Play **internal testing** track as a **draft**
release. iOS submissions go to App Store Connect / TestFlight.

> **Development profile:** `developmentClient: true` requires the `expo-dev-client` package, which
> is not a ShopEx dependency yet. It must go through the dependency vetting policy
> ([SECURITY.md](SECURITY.md#dependency-vetting-policy)) before that profile is used. For everyday
> development, Expo Go (`npx expo start`) is enough.

## 2. One-time setup

### 2.1 Accounts

| Account | Cost | Needed for |
|---|---|---|
| Expo account (<https://expo.dev/signup>) | Free plan includes a limited number of builds per month | All EAS builds |
| Google Play Console developer account | **$25 one-time** registration fee, identity verification | Publishing on Google Play |
| Apple Developer Program | **$99 per year** (organisations also need a D-U-N-S number) | TestFlight, App Store, ad hoc iOS installs |

Simulator builds and the Android APK need only the Expo account.

### 2.2 App identifiers (change them before the first build)

`client/app.json` ships with placeholder identifiers. Replace them with a reverse-domain name you
control, **before** the first store upload; they cannot be changed afterwards.

| Key in `app.json` | Current value | Example |
|---|---|---|
| `expo.ios.bundleIdentifier` | `com.shopex.app` | `com.yourname.shopex` |
| `expo.android.package` | `com.shopex.app` | `com.yourname.shopex` |
| `expo.name` | `ShopEx` | Store-facing name (keep or adjust) |
| `expo.slug` | `shopex` | Project slug on expo.dev |
| `expo.scheme` | `shopex` | Deep-link scheme |
| `expo.version` | `1.0.0` | User-facing version (see section 6) |

Recommended addition for iOS: `"ios": { "config": { "usesNonExemptEncryption": false } }`. ShopEx
only uses standard HTTPS, so this answers App Store Connect's export-compliance question for every
build.

### 2.3 Link the project to EAS

```bash
cd client
npx eas-cli@25.2.0 login
npx eas-cli@25.2.0 init
```

`eas init` creates the project on expo.dev and writes `expo.extra.eas.projectId` (and `owner`) into
`app.json`. Commit that change; it contains no secrets.

### 2.4 Point the app at the production API

The API URL is compiled into each build from the profile's `env` in `eas.json`:

```json
"production": { "env": { "EXPO_PUBLIC_API_URL": "https://shopex-api.onrender.com" } }
```

- Use the API URL from your Render deployment (see [DEPLOY_RENDER.md](DEPLOY_RENDER.md), step 4)
  in the `preview`, `preview-simulator` (inherited) and `production` profiles.
- Release builds must use **HTTPS**: Android blocks clear-text HTTP and iOS App Transport Security
  rejects it.
- `EXPO_PUBLIC_*` values end up inside the app, so never put secrets in `eas.json`.
- Changing the URL requires a new build (over-the-air updates are not configured).
- Native apps are not subject to browser CORS, so `CORS_ORIGINS` does not need the mobile apps.

Free Render services sleep when idle and take about a minute to wake up. For store review and real
users, run the API on an always-on instance (DEPLOY_RENDER.md, section 8).

---

## 3. Android

### 3.1 APK for side-loading (preview profile)

```bash
npx eas-cli@25.2.0 build --platform android --profile preview
```

On the first Android build EAS offers to generate a keystore; accept, and EAS stores it for you
(download a backup with `npx eas-cli@25.2.0 credentials`). When the build finishes, the CLI and the
build page on expo.dev show a link and a QR code.

To install on a phone: open the link on the device, download the `.apk`, and allow "Install unknown
apps" for the browser when Android asks. Anyone with the link can install this build, so share it
only with testers.

### 3.2 Google Play (AAB, production profile)

1. **Create the app** in the Play Console: **Create app**, name `ShopEx`, default language (for
   example French (Canada)), App, Free.
2. **Build the bundle**:

   ```bash
   npx eas-cli@25.2.0 build --platform android --profile production
   ```

   The `versionCode` is incremented automatically (`autoIncrement`, remote version source).
3. **First upload by hand.** Google's API refuses uploads for an app that has never been uploaded,
   so the first `.aab` goes through the web UI: **Testing > Internal testing > Create new release**,
   upload the `.aab` downloaded from the EAS build page. Play App Signing is enabled by default; the
   EAS keystore becomes your upload key.
4. **Automate the next uploads** with EAS Submit:
   - In Google Cloud, create a service account and a JSON key; in the Play Console, invite the
     service account under **Users and permissions** with release permissions for ShopEx.
   - Upload the JSON key to EAS (`npx eas-cli@25.2.0 credentials` → Android → Google Service Account).
     Never commit it (the repository's `.gitignore` excludes `google-play-service-account*.json`).
   - Then:

     ```bash
     npx eas-cli@25.2.0 submit --platform android --profile production --latest
     ```

   The submit profile targets the **internal** track with `releaseStatus: "draft"`, which is
   required while the app itself is still a draft. Once the app is published, switch it to
   `"completed"` (or roll out from the Play Console).
5. **Internal testing track**: add testers (email list or Google Group) under **Testing > Internal
   testing > Testers** and share the opt-in link. Internal releases are available within minutes,
   without review.
6. **Closed testing before production**: new *personal* developer accounts must run a closed test
   with at least **12 testers for 14 consecutive days** before they can apply for production access.
   Organisation accounts are exempt.

#### Store listing

Under **Grow users > Store presence > Main store listing**, in French and English:

- App name (30 characters), short description (80), full description (4,000).
- App icon 512 × 512 PNG, feature graphic 1024 × 500, at least 2 phone screenshots.
- Category **Shopping**, contact email, and a **privacy policy URL** (required: the app has
  accounts and uses location).
- State in the description that **prices are demo prices** and that store data comes from
  © OpenStreetMap contributors. Use only original artwork; no third-party logos.

#### App content (policy forms)

- **App access**: ShopEx needs an account. Create a dedicated review account (not anyone's real
  password) and enter its credentials in the form.
- **Ads**: no ads.
- **Content rating**: complete the questionnaire (utility/shopping, no user-to-user content).
- **Target audience**: adults (18+) or 13+; ShopEx is not designed for children.
- **Data safety form**, based on what ShopEx actually does:

  | Data type | Collected | Purpose | Notes |
  |---|---|---|---|
  | Email address | Yes, required | Account management | Login identifier |
  | Name | Yes, required | Account management | Display name |
  | Approximate and precise location | Yes | App functionality | Sent with searches to find nearby stores and plan the route; not saved to the account |
  | Other user-generated content | Yes | App functionality | Grocery lists (history and bookmarks) |
  | App interactions / in-app search history | Yes | App functionality | List history |

  Also answer: data is **encrypted in transit** (HTTPS); users **can request deletion** (Profile →
  Delete account in the app, which removes the account and its lists); data is **not sold** and not
  used for ads. Google also asks for a **web link** where users can request account deletion: the web
  app (sign in → Profile → Delete account) or a page on your site that explains the steps.
  The itinerary sends the start point and store coordinates to the routing server configured in
  `OSRM_URL`; if that is a third-party server, review whether it must be declared as sharing.
- **Location permission declaration**: ShopEx requests only foreground ("while using the app")
  location (`ACCESS_COARSE_LOCATION`, `ACCESS_FINE_LOCATION`). The Play Console's background-location
  declaration therefore does not apply; keep `ACCESS_BACKGROUND_LOCATION` out of `app.json`. If asked
  why location is needed, answer: "to find grocery stores near the user and compute the fastest
  route between the chosen stores".

Then promote the release from internal testing to closed testing and, when ready, to
**Production** (Google reviews production releases; allow a few days for the first one).

---

## 4. iOS

### 4.1 Apple Developer Program and App Store Connect

1. Enrol in the Apple Developer Program ($99/year) as an individual or organisation.
2. In App Store Connect: **Apps > + > New App**: platform iOS, name `ShopEx`, primary language,
   bundle ID (the `ios.bundleIdentifier` from `app.json`; EAS can register it for you on the first
   build), and an SKU such as `shopex-ios`.
3. Note the app's **Apple ID** (a number under **App Information**). For non-interactive submits, add
   it to `eas.json` as `submit.production.ios.ascAppId` (it is an identifier, not a secret).

### 4.2 Build and submit to TestFlight

```bash
npx eas-cli@25.2.0 build --platform ios --profile production
npx eas-cli@25.2.0 submit --platform ios --profile production --latest
```

The first build asks you to sign in with your Apple ID; EAS then creates and stores the distribution
certificate and provisioning profile (inspect them with `npx eas-cli@25.2.0 credentials`). The build
number is incremented automatically.

After App Store Connect finishes processing the upload (usually 10–30 minutes):

- **Internal testers** (members of your App Store Connect team, up to 100) can install it from the
  TestFlight app right away.
- **External testers** (up to 10,000, by email or public link) require a short Beta App Review of
  the first build of each version.

### 4.3 App Store submission and review notes

Fill in the version page (description, keywords, support URL, privacy policy URL, screenshots for
the required iPhone sizes, and iPad if `supportsTablet` stays `true`), the **App Privacy** answers
(same data as the Google data safety table above), and the age rating. Then **Add for Review**.

Helpful **App Review notes** for ShopEx:

- Sign-in: provide the dedicated review account's email and password.
- Location: used only while the app is in use, to find nearby grocery stores and plan the route; the
  permission text is localised in French and English.
- Prices: clearly labelled in the app as **demo prices** (generated daily); store locations are
  real OpenStreetMap data, credited in the app.
- Account deletion: Profile → Delete account (deletes the account and all its lists).
- Make sure the API is awake and on an always-on instance during review; a one-minute cold start can
  look like a broken app.

ShopEx has no third-party sign-in, so Sign in with Apple is not required.

### 4.4 Ad hoc / internal distribution (.ipa outside the App Store)

For testers who should not go through TestFlight:

1. Register each device (iPhone UDID) with EAS:

   ```bash
   npx eas-cli@25.2.0 device:create
   ```

   It produces a link or QR code; opening it on the iPhone installs a profile that sends the UDID to
   EAS. Apple allows 100 devices per device type per membership year.
2. Build with the `preview` profile (internal distribution = ad hoc provisioning profile containing
   the registered devices):

   ```bash
   npx eas-cli@25.2.0 build --platform ios --profile preview
   ```

3. Testers open the build link on their iPhone to install. On iOS 16 and later they must turn on
   **Settings > Privacy & Security > Developer Mode** once.

A device registered after the build needs a new build (or `npx eas-cli@25.2.0 build:resign`) before it
can install the app.

### 4.5 Simulator builds

No Apple Developer account is needed:

```bash
npx eas-cli@25.2.0 build --platform ios --profile preview-simulator
npx eas-cli@25.2.0 build:run --platform ios --latest   # macOS: installs and launches it in the Simulator
```

---

## 5. Pointing builds at another API

To test a staging API or a custom domain, change `EXPO_PUBLIC_API_URL` in the relevant profile of
`eas.json` (or add a new profile with `"extends": "preview"` and its own `env`), then rebuild. The
web app and the mobile apps should always use the same API so accounts and lists are shared.

## 6. Versioning

- **User-facing version**: `expo.version` in `app.json` (semantic versioning: `1.0.0`, `1.1.0`,
  `2.0.0`). Bump it by hand for each store release, and add an entry to the README's
  *Release notes*.
- **Build numbers** (Android `versionCode`, iOS `buildNumber`): stored by EAS
  (`"appVersionSource": "remote"`) and incremented on every `production` build (`autoIncrement`).
  Check or set them with `npx eas-cli@25.2.0 build:version:get` and `build:version:set`.
- Tag the release in Git (for example `v1.0.0`) on the commit you built.

## 7. Release checklist

1. CI is green on `main`; the production API is deployed and healthy.
2. `app.json` identifiers are yours and `expo.version` is bumped; the README release notes are
   updated.
3. `eas.json` production `EXPO_PUBLIC_API_URL` is the production HTTPS URL.
4. `npx eas-cli@25.2.0 build --platform all --profile production`.
5. Smoke-test the internal track / TestFlight build: sign up, search, itinerary, language switch,
   delete account.
6. Store listings mention demo prices and the OpenStreetMap attribution; privacy forms are up to date.
7. Submit for review.
