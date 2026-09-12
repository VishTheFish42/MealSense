# Tasks — MealSense (Full Project)

**Status:** Not started (Phase 0 partially applicable — see notes)
**Date:** 2026-08-21
**Requirements:** [requirements.md](requirements.md)

Phases are ordered by risk and dependency, not by how interesting they are. Security comes first because health data and order records are currently unprotected by anything in this repo. Each phase should land as its own PR — that keeps every resume/interview claim about this project traceable to real, reviewable work.

---

## Phase 1 — Security Hardening (do this first) ✅ done (2026-09-07)

Traces to requirements §8. This is the biggest real gap in the project — not a stretch goal.

- [x] 1.1 Write `firestore.rules` and commit it to the repo — `mealsense-app/firestore.rules`
- [x] 1.2 Rule: a student can only read/write their own `users/{uid}` document
- [x] 1.3 Rule: a student can only read their own `orders` (query by `studentId`), never another student's
- [x] 1.4 Rule: only accounts with `role: "kitchen"` can transition `orders.status` toward `ready`/`completed`; the owning student can independently advance `placed → preparing → ready` (matches the existing client-side demo timer in `OrderStatusScreen.tsx` — this is enforced by the same rule that also guarantees `items`/`totalPrice`/`studentId` are immutable on every status-advancing write
- [x] 1.5 Audited how `role: "kitchen"` actually got assigned: **`RegisterScreen.tsx` let any user self-select it at signup with zero gatekeeping** — a real privilege-escalation bug, not hypothetical. Fixed by (a) rules that reject any client-created user doc with `role != "student"`, (b) removing the role picker from `RegisterScreen.tsx` entirely, (c) documenting the real provisioning path in `mealsense-app/README-kitchen-accounts.md` (manual console edit for now; a real admin flow is Phase 4)
- [x] 1.6 Tested rules with the Firebase emulator (`@firebase/rules-unit-testing` + Node's built-in test runner, no Jest needed) — `mealsense-app/tests/firestore.rules.test.js`, 16/16 passing via `npm run test:rules`
- [x] 1.7 Added a profile + associated data deletion flow — `ProfileScreen.tsx`'s "Delete My Account & Data" batch-deletes the student's orders, deletes their `users/{uid}` doc, then deletes the Auth account itself
- [x] 1.8 Deployed rules to the live project — a fresh Firebase project (`mealsense-cb5ab`) was created to replace the old auto-named `myproject-dc745` (whose live rules were undocumented), `.firebaserc`, `src/config/firebase.ts`, and `.env` were repointed at it, Firestore (Standard edition) and Email/Password Auth were enabled, and `npx firebase deploy --only firestore:rules` confirmed released. `firestore.rules` now actually governs production, not just the emulator.

## Phase 2 — Testing Infrastructure ✅ done (2026-09-05)

Traces to requirements §9. Scoped tightly to the recommendation engine's real safety invariant (zero-false-negative allergen filtering) plus API route coverage.

**Result:** 47/47 tests passing, `services/recommendation_engine.py` at 100% line coverage (target was ≥90%). Files: `mealsense-api/tests/conftest.py`, `test_recommendation_engine.py`, `test_routes.py`, `pytest.ini`, `requirements-dev.txt`. Run with `cd mealsense-api && venv/bin/python -m pytest --cov=services --cov-report=term-missing`. This unblocks Phase 6 (the bandit layer), which was explicitly gated on this phase landing first.

### 2.1 Test Infrastructure Setup
- [x] 2.1.1 Add `pytest` and `httpx` to `mealsense-api/requirements.txt` (or a new `requirements-dev.txt`)
- [x] 2.1.2 Create `mealsense-api/tests/` package with `__init__.py`
- [x] 2.1.3 Add `pytest.ini` (or `pyproject.toml` `[tool.pytest.ini_options]`) setting `testpaths = tests`
- [x] 2.1.4 Verify `pytest` runs from `mealsense-api/` with `python -m pytest`
- [x] 2.1.5 Add `conftest.py` with shared fixtures: a minimal valid student profile, a small fixture menu (allergen item, vegan item, high-protein item, off-period item)

### 2.2 Recommendation Engine Unit Tests (`test_recommendation_engine.py`)
- [x] 2.2.1 Allergen hard filter: single flagged allergen excludes matching item
- [x] 2.2.2 Allergen hard filter: case-insensitive matching
- [x] 2.2.3 Allergen hard filter: multiple simultaneous allergies all enforced
- [x] 2.2.4 Dietary identity filter: single identity (e.g. vegetarian) enforced
- [x] 2.2.5 Dietary identity filter: multiple identities enforced as AND, not OR
- [x] 2.2.6 Meal-period availability filter enforced correctly
- [x] 2.2.7 No-safe-items fallback returns `null` + `"no_safe_items"`
- [x] 2.2.8 Macro/calorie alignment score decreases monotonically as calories diverge from target
- [x] 2.2.9 Protein/fiber scores capped at reference max (50g / 15g)
- [x] 2.2.10 Variety penalty applied for items in `recent_ids`
- [x] 2.2.11 Final item score bounded to [0, 100]
- [x] 2.2.12 Diabetes profile shifts weight toward `sugar_sodium`
- [x] 2.2.13 Hypertension (without diabetes) applies the same shift
- [x] 2.2.14 Diabetes + hypertension together: no double-adjustment
- [x] 2.2.15 Adjusted weights sum to 1.0, parametrized over all condition combinations
- [x] 2.2.16 BMR fixed test vectors for male and female profiles
- [x] 2.2.17 All four activity multipliers applied correctly
- [x] 2.2.18 Goal adjustments (lose/gain/maintain) applied correctly
- [x] 2.2.19 Meal-period apportionment matches README §8.4 table
- [x] 2.2.20 Top recommendation is always the highest-scoring candidate
- [x] 2.2.21 Alternatives capped at 3, sorted descending
- [x] 2.2.22 Reasoning signals capped at 4

### 2.3 API Route Tests (`test_routes.py`)
- [x] 2.3.1 `GET /menu` with no params returns all items + correct `count`
- [x] 2.3.2 `GET /menu?meal_period=X` filters correctly, including `all_day` items
- [x] 2.3.3 `POST /recommendation` with a minimal valid profile returns 200 + expected shape
- [x] 2.3.4 `POST /recommendation` with malformed/missing fields returns a 4xx (document actual behavior)

### 2.4 Coverage
- [x] 2.4.1 Add `pytest-cov`; run `pytest --cov=services --cov-report=term-missing`
- [x] 2.4.2 Confirm `services/recommendation_engine.py` hits ≥90% line coverage

**Definition of done for the resume claim:** 2.1–2.3 complete. At that point "wrote a pytest suite covering the recommendation engine's hard-filter and scoring logic" is accurate and defensible in an interview.

## Phase 3 — Menu Data Pipeline

Traces to requirements §3. Currently the entire menu is one hardcoded Python file; nothing here is built yet despite being a documented architecture decision.

- [x] 3.1 **Menu persistence layer** ✅ done (2026-09-08, all four subtasks below complete) — Firestore, via `google.cloud.firestore.Client` added to `mealsense-api` for the first time (decided 2026-09-08, see requirements.md). Layout: `menus/{servedOn}/items/{itemId}` subcollection per day, `servedOn` supplied at upload time (task 3.2), not parsed per-item by the adapters — keeps `menu_ingestion/` untouched. `sample_menu.py` stays as a fallback when Firestore has nothing for the requested date, not replaced outright.
  - [x] 3.1.1 ✅ done (2026-09-08) — Added `firebase-admin==7.5.0` to `requirements.txt`. Actual Firestore access goes through `google.cloud.firestore.Client` directly (`services/firestore_client.py`), not `firebase_admin.firestore.client()` — confirmed hands-on that the latter's credential loading calls `google.auth.default()` even with `FIRESTORE_EMULATOR_HOST` set, which raises with no GCP environment configured. Anonymous credentials against the emulator, a real service account file (`GOOGLE_APPLICATION_CREDENTIALS`) in production; raises `FirestoreNotConfiguredError` if neither is set, which `menu_store.py` catches specifically to fall back to the sample menu (a real connection/permissions error still propagates, not masked). **Manual step still pending, not blocking:** a real service account key from the Firebase console, not needed until we go past emulator-only testing.
  - [x] 3.1.2 ✅ done (2026-09-08) — `services/menu_store.py`: `get_menu_for_date(served_on)` and `write_menu_items(served_on, items)` (batch write, keyed by each item's stable id so re-uploading a day overwrites matching dishes instead of duplicating). Tested against a real local Firestore emulator, not mocked (`tests/test_menu_store.py`), same reasoning as the JS rules tests — skips cleanly with a clear reason if the emulator isn't running rather than a raw connection error.
  - [x] 3.1.3 ✅ done (2026-09-08) — `routers/menu.py` and `routers/recommendations.py` now read via `menu_store.get_menu_for_date` instead of importing `SAMPLE_MENU` directly; both accept an optional `served_on` override, defaulting to today. Existing `test_routes.py` still passes unmodified with no emulator running, exercising the sample-menu fallback path.
  - [x] 3.1.4 ✅ N/A, resolved by architecture (2026-09-08) — originally scoped as new Firestore security rules for `menus/{date}/items/{itemId}`, but rules only govern Firebase Auth-authenticated client SDK access, and the mobile app never touches this collection directly — it reads menu data exclusively through the FastAPI `/menu` and `/recommendation` endpoints, which access Firestore server-side via a service account (or the emulator equivalent), bypassing rules entirely by design. The existing catch-all deny-all in `firestore.rules` already correctly blocks any accidental direct client access. Unlike `users`/`orders`, this collection needs no explicit rule unless the mobile app ever starts reading menu data directly via Firestore instead of through the API.
- [x] 3.2 **Admin CSV/JSON upload endpoint** ✅ done (2026-09-08) — `POST /admin/menu/upload?format=csv|messy_json&served_on=YYYY-MM-DD` (`routers/admin_menu.py`), runs the request body through the matching `menu_ingestion` adapter, writes accepted items via `menu_store.write_menu_items`, returns `{accepted, rejected}` (each rejected entry carries the raw record and reason) matching README §7.2. Gated by `services/auth.py::require_kitchen_role` — verifies a Firebase ID token, then checks `role == "kitchen"` in Firestore (no separate `admin` role exists yet; reusing `kitchen` is a deliberate scope decision, revisit once Phase 4 formalizes real admin accounts). Tested against the real Firestore emulator: upload/accept/reject behavior for both formats, persisted items actually readable back via `get_menu_for_date`, and — deliberately without overriding the auth dependency — a request with no Authorization header genuinely gets rejected by the live route, not just by an isolated unit test of the auth function. Found and fixed one real bug along the way: a required `Header(...)` parameter meant a *missing* header returned FastAPI's generic 422 instead of the app's own 401, inconsistent with a malformed header; changed to an optional header handled explicitly. 116/116 tests passing (98% coverage across `services/` and `routers/`; the only gaps are the real-service-account and real-token-verification production paths, which need actual Firebase infrastructure to test meaningfully and aren't worth faking).
- [x] 3.1a **Generic ingestion & normalization adapter** (design-spec.md §7.0) ✅ done (2026-09-08) — `mealsense-api/services/menu_ingestion/`: `schema.py` (canonical `MenuItem` builder + validation, matching the flat shape the engine actually reads, not README §7.1's nested sketch), `base.py` (the `MenuAdapter` protocol + `IngestionResult`/`RejectedRecord`), `csv_adapter.py` (README §7.2's column spec), `messy_json_adapter.py` (arbitrary key aliases, units embedded in numeric strings, meal-period free text). Enforces the core safety invariant end-to-end: a record with allergen data entirely absent from the source is rejected, never silently treated as zero allergens (distinct from an explicit empty list, which is accepted) — this was previously only a documented intent (design-spec.md §2.3), not actually enforced anywhere in code. 97/97 tests passing, 99% coverage (`tests/test_menu_ingestion.py`). Stable per-dish IDs (hash of name+station, not date-dependent) verified identical across both adapters for the same logical dish.
- [x] 3.3 **Manual entry UI for dining staff** ✅ done (2026-09-11) — `mealsense-app/src/screens/kitchen/AddMenuItemScreen.tsx`, reachable via a "+ Menu Item" button on `KitchenDashboardScreen.tsx` (kitchen-role accounts only, matching 3.2's reused-role decision — no separate admin role yet). A form for all `MenuItem` fields (name, station, meal period, optional time window, all seven nutrition fields, price, allergens, dietary tags, ingredients, description) that submits a single-item payload to the existing `POST /admin/menu/upload?format=messy_json` endpoint from 3.2 — no new backend route needed, just a client of the one that already existed. Allergens use an explicit three-state control (undecided / "None, verified" / one-or-more selected); undecided blocks submission client-side, mirroring the ingestion layer's own fail-closed rule so staff can't accidentally submit an item with unknown allergen status. Found and fixed a real gap this surfaced: `messy_json_adapter.py` had `available_from`/`available_until` hardcoded to `None` always (never read from the source record at all) and never extracted `ingredients`/`description` either — all four are now wired through via key aliases, with 5 new adapter tests. 134/134 backend tests passing, `npx tsc --noEmit` clean. This is the entry point Phase 4's admin dashboard will build on, not the dashboard itself — no sold-out toggle or aggregate analytics view yet (still Phase 4 scope).
- [x] 3.4 **Real vendor integration — Santa Clara University** ✅ done (2026-09-11), closes README §12 Open Question #1 for a first campus — `services/vendor_ingestion/` (`campus_config.py`, `bon_appetit.py`), wired into a new `POST /admin/menu/sync-vendor?campus=<id>` route (`routers/admin_menu.py`, same kitchen-role gating as 3.2).
  - **Vendor confirmed:** SCU dining is run by Bon Appétit Management Co. (`scudining.cafebonappetit.com`), not Nutrislice/Cbord as README §7.2 guessed — confirmed against the live site, not assumed.
  - **The documented JSON API is a dead end without a vendor relationship:** `legacy.cafebonappetit.com/api/2/...` now returns "Cafemanager no longer accepts unauthenticated requests" — needs vendor-issued credentials, same category of blocker as the original open question. Instead, each café's public page embeds a real structured data blob (`Bamco.dayparts` / `Bamco.menu_items`) with everything needed (name, station, per-daypart time window, full nutrition, price, ingredient text, allergen/dietary icons) — reachable with no auth, verified live 2026-09-11 (36 items correctly parsed off Mission Bakery Cafe's real page). Documented in `bon_appetit.py`'s module docstring as *not* a stable public contract — it can break if Bon Appétit changes their theme.
  - **Allergen trust policy — a real safety decision, not an implementation detail:** Bon Appétit's own SCU allergen-disclosure page says their online data isn't a complete substitute for asking kitchen staff directly, and every location handles all top-9 allergens in shared prep areas. Presented this as a choice to the user rather than deciding silently; chosen answer: an item's allergen icons are trusted as a positive-only signal (an icon present is real), but **zero icons means unknown, not verified-safe** — `allergens=None`, rejected by `build_menu_item`'s existing fail-closed rule, same as everywhere else in this codebase. On the live smoke test this correctly held out `Hot Coffee`/`Hot Tea`/`Espresso` (genuinely untagged) while accepting 36 items with real allergen data (e.g. `Hot Latte` → `['dairy']`, tag `['vegetarian']`).
  - **General template, not a one-off:** onboarding another Bon Appétit campus is one new `CampusConfig` entry in `campus_config.py` (base URL + café slugs) — nothing else changes. A campus on a different vendor needs one new adapter module implementing the same `fetch_campus_menu(campus) -> IngestionResult` shape, registered by vendor key in `admin_menu.py`'s `_VENDOR_FETCHERS` map — the route, the review-queue wiring, and `menu_store` persistence are all vendor-agnostic already.
  - **Also built the review-queue half of 3.6** (design-spec.md §7.0a case 3) as plumbing this needed anyway: `services/menu_review_queue.py`, a Firestore-backed queue that allergen-rejected records land in instead of being silently dropped. No admin UI reads it yet (Phase 4) — `get_review_queue`/`resolve_review_item` exist so it's a real, testable read path, not a write-only sink.
  - **Deliberately not built:** a nightly scheduled sync (README §7.1's "02:00 local time" job) — there's no cron/scheduler infrastructure in this project at all (Phase 7). `sync-vendor` is manually triggered, matching the existing manual-upload pattern from 3.2.
  - 44 new tests (`test_bon_appetit_adapter.py` — pure parsing logic, no network; `test_menu_review_queue.py` — real Firestore emulator; 4 new route tests in `test_admin_menu.py`), 172/172 passing, 98% coverage across `services/`+`routers/` (the only real gaps are the live-network fetch call itself and two malformed-JSON defensive branches — deliberately not faked, same stance as the existing real-service-account/real-token-verification gaps).
- [x] 3.5 **Real time-window availability** ✅ done (2026-09-11) — `_passes_hard_filters` (`recommendation_engine.py`) now takes an optional `now: time` and rejects items outside `[available_from, available_until]`; items with no explicit window default to `DEFAULT_MEAL_WINDOWS` per README §7.3 (breakfast 07:00–10:30, lunch 11:00–15:00, dinner 17:00–21:00, matching the sample menu's own values). `recommend()` defaults `now` to the real wall clock when not passed, so every production call is actually time-filtered now, not just meal-period-bucketed. `now=None` (the default for direct `_passes_hard_filters` calls) skips the check entirely rather than defaulting to the real clock — deliberate, so every pre-existing test that only cares about allergen/dietary/meal-period-bucket filtering stays deterministic regardless of wall-clock time when the suite runs; only `recommend()`-level tests and the new availability tests pass an explicit `now`. 8 new tests in `test_recommendation_engine.py`, engine still at 100% coverage, 131/131 passing overall.
- [x] 3.6 **Incomplete data handling** ✅ done (2026-09-11, design-spec.md §7.0a) — all three paths built, scoped to the vendor-sync ingestion path only (3.4), not the CSV/messy-JSON manual uploads.
  - **(a) Missing nutrition fields** — `services/menu_ingestion/llm_enrichment.py::estimate_missing_nutrition`, called from `bon_appetit.py` for exactly the numeric fields an item is missing (never a field already supplied — the core cost/scope constraint). Accepted outright (low-stakes if wrong per the design doc), stored on the item as `estimated_fields: [...]`. Price is explicitly excluded from this fallback — wrong nutrition data degrades a recommendation, a wrong price is a money-safety issue, so price stays fail-closed exactly like 3.6a already decided.
  - **(b) Missing structured allergens, ingredient text present** — `llm_enrichment.py::extract_allergens_from_ingredients` returns an allergen list plus a confidence score; `bon_appetit.py` only accepts it at ≥ 0.9 confidence (`ALLERGEN_CONFIDENCE_THRESHOLD`), otherwise the item stays excluded exactly as before. Decided 2026-09-11 (a real safety call, not left to default behavior): even a confident, accepted extraction **still writes a review-queue entry** ("AI-extracted allergens, please verify") — an LLM clearing the bar never gets the same zero-further-visibility treatment as a real vendor icon or a human confirmation.
  - **(c) Missing allergens, no ingredient text at all** — the review queue itself (built as part of 3.4, see that entry) — stays excluded, queued, no model involved, unchanged from that design.
  - **Model:** `claude-opus-5` via `client.messages.parse(..., output_format=<pydantic model>)` for structured output. Every call fails soft (returns `{}`/`None` on any error, never raises into the ingestion pipeline) — a Claude outage degrades to "reject like before," not a crash.
  - The LLM's role stays strictly limited to producing cleaner *input* for the adapter layer, per the design doc's closing line — `recommendation_engine.py` was not touched, and has no branch that even looks at `estimated_fields`.
  - 19 new tests (11 in `test_llm_enrichment.py` — pure logic, injectable fake client, no network/API key needed; 8 more in `test_bon_appetit_adapter.py` for the wiring itself), 191/191 passing, 98% coverage across `services/`+`routers/`.
  - **Live-verified (2026-09-11):** a real `ANTHROPIC_API_KEY` was provisioned (`mealsense-api/.env`, gitignored, loaded via `python-dotenv` in `main.py`) and both functions were exercised against the real API, not just the test suite's fake client — `estimate_missing_nutrition` correctly filled only the two fields asked for (`fiber_g`, `sugar_g`) and left everything else untouched; `extract_allergens_from_ingredients` correctly identified `gluten`/`sesame`/`soy` from a real ingredient list but reported `confidence: 0.55` — below the 0.9 bar, confirming the threshold gate actually holds back a real low-confidence result rather than only a synthetic test one.
- [x] 3.6a **Missing `price` field** ✅ done (2026-09-11) — resolved the open product decision by requiring `price` at ingestion, rejecting like allergens/nutrition rather than blocking-at-order-time: `schema.py::build_menu_item` now validates `price` through the same numeric-required path as the seven nutrition fields, so a record with no usable price never reaches the store. `csv_adapter.py` reads a `price` column (added to the documented spec, design-spec.md §7.2); `messy_json_adapter.py` accepts `price`/`Price`/`cost`/`Cost` aliases. `HomeScreen.tsx`'s "Price unavailable" fallback (2026-09-10) stays in place as defense-in-depth but should no longer trigger for anything ingested through the fixed pipeline. 6 new tests, 123/123 passing, 98% coverage.
- [x] 3.7 **Fix fail-open allergen default in the engine itself** ✅ done (2026-09-08) — `_passes_hard_filters` now checks `item.get("allergens")` for `None` (missing key) and fails closed unconditionally, before even comparing against the student's own allergy list, distinct from an explicit empty list which still passes. Two new tests (`test_allergen_filter_fails_closed_on_missing_allergen_data`, `test_allergen_filter_accepts_explicit_empty_allergen_list`); full suite still at 99/99 passing, engine still 100% coverage.

## Phase 4 — Admin Dashboard (Dining Staff)

Traces to requirements §6. Fully unbuilt — distinct from the Kitchen Dashboard, which only handles order fulfillment.

- [ ] 4.1 New navigator branch + role (`role: "admin"` or reuse `"kitchen"` with a sub-permission — decide based on Phase 1.5's role model)
- [ ] 4.2 Upload/sync UI wired to Phase 3.2's endpoint
- [ ] 4.3 Mark items sold out / unavailable in real time
- [ ] 4.4 Aggregate anonymized view: most-recommended items, common dietary constraints on campus (README §9.5) — needs an aggregation query or a scheduled rollup job; don't do this as a naive per-request scan once order volume is nonzero
- [ ] 4.5 **Location-scoped kitchen isolation** (design-spec.md §2.3) — add a `locationId` field to kitchen-role user docs and to `orders`; update `firestore.rules` so every order read/write checks `locationId` match, not just `role == "kitchen"`. Today any kitchen account can see every dining hall's orders, which is fine for a single-location pilot but is a real gap the moment a second dining hall or a second university is onboarded. Extend `mealsense-app/tests/firestore.rules.test.js` with cross-location denial cases before considering this done. This is a hard prerequisite for Phase 7's multi-university rollout, not optional polish

## Phase 5 — Auth: University SSO

Traces to requirements §7.

- [ ] 5.1 Resolve README §12 Open Question #4 (is SSO required for v1, or is email/password an acceptable fallback?) before building — this determines whether this phase is in scope at all
- [ ] 5.2 If required: integrate OAuth 2.0/SAML per the target university's IdP
- [ ] 5.3 If not required: explicitly close this out as "email/password is the v1 auth strategy" rather than leaving it as a silent gap against the README

## Phase 6 — ML-Enhanced Recommendation (Post-v1)

Traces to requirements §2, design-spec §14. Fully designed (Profile-Adaptive Contextual Bandit, LinUCB), zero implementation. Do not start this before Phase 2 (testing) — the heuristic scorer needs a regression safety net before it gets a second scoring path layered on top of it.

- [ ] 6.1 Profile feature vector encoding (health_goal one-hot, activity_level ordinal, condition/focus binary flags, standardized BMI + age)
- [ ] 6.2 Offline k-means clustering (k=15) job + storage for cluster centroids
- [ ] 6.3 Nearest-centroid cold-start assignment for new students
- [ ] 6.4 Per-cluster LinUCB weight learning from thumbs-up/down feedback
- [ ] 6.5 Fallback to heuristic weights when a cluster has <50 feedback samples
- [ ] 6.6 Shadow-mode logging (compute both heuristic and bandit recommendations, log both, serve only the heuristic one)
- [ ] 6.7 A/B rollout gate: bandit must beat heuristic baseline on thumbs-up rate before full exposure
- [ ] 6.8 Only after 6.1–6.7: measure and report an actual acceptance-rate number — do not put a percentage on this anywhere (resume included) until it's been run

## Phase 7 — Deployment & Infrastructure

Traces to requirements §10.

- [ ] 7.1 Decide actual hosting target (Vercel serverless functions, per README, or something else) and get FastAPI actually deployed there — right now this only runs on a dev machine
- [ ] 7.2 Replace the hardcoded LAN-IP config (`mealsense-app/src/config/api.ts`) with an environment-based API URL once there's a real deployed backend
- [ ] 7.3 Set up dev/staging/prod environment separation
- [ ] 7.4 GitHub Actions CI running Phase 2's test suite on push — only do this once the repo actually has a remote to push to

## Phase 8 — Metrics Instrumentation

Traces to requirements §11. All nine README §14 success metrics currently have no way to be measured.

- [ ] 8.1 Pick an analytics approach (Firebase Analytics is already in the dependency tree via the `firebase` package, or a dedicated events collection in Firestore)
- [ ] 8.2 Instrument: profile completion, recommendation relevance (thumbs up/down — UI for this doesn't exist yet either, check `HomeScreen.tsx`), time-to-recommendation, order conversion
- [ ] 8.3 Build a minimal reporting view (even a script that queries Firestore, doesn't need to be a dashboard) before claiming any of the README §14 targets are being hit
