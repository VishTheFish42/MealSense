# Requirements — MealSense (Full Project)

**Status:** Draft — audited against actual code
**Date:** 2026-08-21 (re-audited 2026-09-05 for multi-location isolation and generic menu ingestion)
**Related docs:** [README.md](README.md) (product spec), [design-spec.md](design-spec.md) (technical design)

Every requirement below is tagged against what's actually in the repo, not the spec's aspirations:

- ✅ **Done** — implemented and traceable to a real file
- 🟡 **Partial** — some of it exists, meaningfully incomplete
- ❌ **Not started** — spec'd in README/design-spec only, no code

---

## 1. Student Onboarding & Profile

- ✅ 7-step onboarding flow (name/age → body stats → activity/goal → allergies → diet → conditions → focus) — `screens/onboarding/OnboardingScreen.tsx`
- ✅ Profile view + edit — `screens/student/ProfileScreen.tsx`, `EditPreferencesScreen.tsx`
- ✅ Unit toggling (cm/in, kg/lb) with live conversion
- ✅ Custom "Other" free-text entries merged into allergy/diet/condition/focus lists
- ✅ Profile deletion flow (README §11) — "Delete My Account & Data" in `ProfileScreen.tsx`, batch-deletes orders + profile doc + the Auth account itself
- ❌ Encryption-at-rest verification (README §11 claims this; Firestore default encryption may satisfy it, but this hasn't been confirmed or documented)
- ✅ **Fixed (2026-09-07):** leaving any optional field blank (height, weight, age) during onboarding or profile edit crashed the save with an uncaught Firestore error. Root cause: `OnboardingScreen.tsx` and `EditPreferencesScreen.tsx` both set unfilled optional fields to literal JS `undefined` in the update object passed to `setDoc()`; the Firestore JS SDK throws on any `undefined` field value (not configured with `ignoreUndefinedProperties`). Fixed with a shared `stripUndefined()` helper (`src/utils/firestore.ts`) applied at both call sites — found via live device testing, not caught by any existing test.

## 2. Recommendation Engine

- ✅ Hard filters: allergen exclusion, dietary identity matching, meal-period bucket, **and real clock-time availability window** — `mealsense-api/services/recommendation_engine.py::_passes_hard_filters`
- ✅ **Fixed (2026-09-11, tasks.md 3.5):** real `available_from`/`available_until` time-window filtering, previously only conceptual (README §7.3). An item is now excluded from recommendations if the current time falls outside its window, defaulting to standard per-meal-period hours when a source doesn't specify one.
- ✅ **Added (2026-09-13, tasks.md 4.3):** a sold-out hard filter, independent of the time-window check — items dining staff mark sold out via `TodaysMenuScreen.tsx` are excluded from recommendations immediately, no caching layer.
- ✅ Five-signal weighted scoring (macro/calorie, protein, fiber, sugar/sodium, variety) — `_score_item`
- ✅ Condition-based weight reweighting (diabetes, hypertension, high cholesterol, IBS) — `_weights_for_profile`
- ✅ Mifflin-St Jeor calorie targeting with activity multiplier + meal apportionment — `_calorie_target`
- ✅ "Why this?" human-readable reasoning string — `_primary_reason`
- ✅ No-safe-items fallback (`reason: "no_safe_items"`) instead of a bad recommendation
- ❌ **ML-enhanced scoring (Profile-Adaptive Contextual Bandit, design-spec §14)** — fully designed (LinUCB, k=15 clustering, cold-start handling, shadow-mode/A-B rollout) but zero implementation. This is the piece the old resume bullets described as done — it is not.
- 🟡 **Recommendation history is now stored (tasks.md 8.0, 2026-09-13), but there's still no view for it.** `services/recommendation_history.py` writes one record per served top recommendation and captures thumbs-up/down feedback against it — the storage half of README §9.4's "view recommendation history (last 7 days)." The viewing UI itself doesn't exist yet; `get_recommendation` is the read path it would use.
- ✅ **Thumbs-up/down feedback** (README §9.2/§13, tasks.md 8.0, done 2026-09-13) — previously claimed as "already collected in v1" but wasn't; now actually built. `POST /recommendation/{id}/feedback`, buttons on `HomeScreen.tsx`'s top pick only (not alternatives — the bandit's reward signal in design-spec.md §14.2 only has a causal story for the item actually served).

## 3. Menu Data

- ✅ **Firestore-backed, with a static fallback** (2026-09-08) — `mealsense-api/services/menu_store.py`, layout `menus/{servedOn}/items/{itemId}`. `/menu` and `/recommendation` now read via `menu_store.get_menu_for_date`, falling back to the static 20-item `sample_menu.py` list only when nothing has been uploaded for the requested date (or when Firestore isn't configured in the current environment at all). This is the first time `mealsense-api` has talked to Firestore — access goes through `google.cloud.firestore.Client` directly rather than `firebase_admin.firestore.client()`, since the latter's credential loading fails against the emulator with no real GCP environment configured.
- ✅ **Admin upload endpoint** (2026-09-08) — `POST /admin/menu/upload` (`routers/admin_menu.py`), accepts either CSV or the messy-ad-hoc-JSON shape, runs it through the matching `menu_ingestion` adapter, and persists accepted items. Requires a verified Firebase ID token belonging to a `kitchen`-role account (`services/auth.py`); no separate `admin` role exists yet, so this is intentionally scoped to reuse `kitchen` for now.
- ✅ **Vendor integration — Santa Clara University** (tasks.md 3.4, done 2026-09-11) — `mealsense-api/services/vendor_ingestion/`, live-verified against `scudining.cafebonappetit.com` (Bon Appétit, not Nutrislice/Cbord as originally guessed). Their documented JSON API now requires vendor credentials we don't have; instead scrapes each café's public page's embedded `Bamco.dayparts`/`Bamco.menu_items` data — real, structured, but not a contract Bon Appétit committed to. Config-driven per campus (`campus_config.py`) so a second Bon Appétit school is one new entry, not new code. Allergen icons are trusted positive-only — zero icons means unknown and routes to the new admin review queue (`services/menu_review_queue.py`), never silently treated as safe. Triggered via `POST /admin/menu/sync-vendor`, manually (no nightly job — no scheduler infra exists yet, Phase 7).
- ❌ Admin CSV/JSON upload (README §7.2 priority #2) — not started
- ✅ **Manual entry by dining staff** (README §7.2 priority #3) — `mealsense-app/src/screens/kitchen/AddMenuItemScreen.tsx` (tasks.md 3.3, done 2026-09-11), reachable from `KitchenDashboardScreen.tsx`. A full form for every `MenuItem` field, submitting through the existing `POST /admin/menu/upload` endpoint (3.2) rather than a new route. Surfaced and fixed a real gap in `messy_json_adapter.py`: `available_from`/`available_until` were hardcoded to `None` regardless of the source record, and `ingredients`/`description` were never extracted at all.
- ❌ Any persistence layer for menu data — Firestore isn't used for menu at all; nothing survives a backend restart or varies by day/campus
- ✅ **Generic ingestion/normalization adapter** (design-spec.md §7.0, tasks.md 3.1a) — `mealsense-api/services/menu_ingestion/`, a CSV adapter and a messy-ad-hoc-JSON adapter both normalize into one canonical schema, verified to produce identical stable IDs for the same logical dish regardless of which adapter processed it. Enforces missing-allergen-data rejection at the ingestion boundary, not just as a documented intent. 97/97 tests, 99% coverage. **Not yet wired to anything** — no FastAPI route or Firestore write calls these adapters; `/menu` and `/recommendation` still read the static sample list exclusively.
- ✅ **Incomplete data handling** (design-spec.md §7.0a, tasks.md 3.6, done 2026-09-11) — `mealsense-api/services/menu_ingestion/llm_enrichment.py`, Claude-backed (`claude-opus-5`, structured JSON output), wired into the vendor-sync path (`bon_appetit.py`) only — CSV/messy-JSON manual uploads still reject on missing data, unchanged. Missing nutrition fields are estimated and flagged per-field (`estimated_fields`); missing allergen data with ingredient text present is only accepted at ≥90% extraction confidence, and even then still lands in the review queue for a human to double-check — an LLM clearing the safety bar is never treated as equivalent to a vendor's own structured data. Price is deliberately excluded from LLM estimation (money-safety, not recommendation-quality). 19 new tests, all using an injectable fake client — no live API calls in the test suite.
- ✅ **Fixed (2026-09-08, tasks.md 3.7):** the engine's own hard filter (`recommendation_engine.py::_passes_hard_filters`) previously defaulted a missing `allergens` key to fail-*open* (treated as zero allergens), the opposite of the ingestion layer's fail-closed rule. Harmless in practice only because the current menu source is always complete, but a real defense-in-depth gap. Now fails closed independently of the ingestion layer, rejecting a missing allergens field unconditionally before ever comparing against the student's own allergy list.

## 4. Ordering (Cart → Checkout → Status)

- ✅ Cart with quantity control — `screens/student/CartScreen.tsx`
- ✅ Checkout writes an order to Firestore (`orders` collection) — `CheckoutScreen.tsx`
- ✅ Placeholder payment UI, clearly labeled "Demo — no charge," no real processing — matches README §4 non-goal
- ✅ Real-time order status via Firestore `onSnapshot` — `OrderStatusScreen.tsx`
- ✅ Timer-based status progression (30s placed→preparing, 90s preparing→ready) — `constants/orderTimers.ts`. Intentionally a demo mechanism per README §9.8; not read as a shortcoming, but the timer fires from the **client**, so it silently stops if the student closes the app before it elapses — no server-side or kitchen-triggered fallback.
- ✅ **Fixed (2026-09-11, tasks.md 3.6a):** `price` is now a required field at ingestion, validated and parsed the same way as the seven nutrition fields (`schema.py::build_menu_item` — missing or unparseable `price` is rejected, not defaulted to `null`). `csv_adapter.py` reads a `price` column (added to the documented column spec, design-spec.md §7.2) and `messy_json_adapter.py` accepts `price`/`Price`/`cost`/`Cost` key aliases, parsed through the same currency-symbol-tolerant `_parse_numeric` used for calorie/macro values (`"$9.50"` → `9.50`). This closes both the immediate crash (`HomeScreen.tsx`'s unguarded `item.price.toFixed(2)`, already patched 2026-09-10) and the quieter one: `CartScreen.tsx`/`CheckoutScreen.tsx`/`OrderStatusScreen.tsx` can no longer silently order a priceless item as free, since no item without a valid price can pass ingestion at all. 6 new tests added to `test_menu_ingestion.py` and `test_admin_menu.py` fixtures updated; 123/123 passing, 98% coverage maintained.
- ✅ **Live-verified end to end (2026-09-07):** registration → onboarding → recommendation (scoring, allergen exclusion, and reasoning text all cross-checked directly against `recommendation_engine.py`) → cart → checkout → all three real-time order-status transitions → order history, all confirmed on a physical device against the deployed `mealsense-cb5ab` project, not just inferred from reading the code.
- ✅ Order history list — `OrderHistoryScreen.tsx`
- ✅ **Added (2026-09-13, tasks.md 8.2):** orders placed straight from the top recommendation card now carry a `recommendationId` field, threaded through `HomeScreen.tsx` → `CartScreen.tsx` → `CheckoutScreen.tsx`. Absent (not null) for anything else — ordering an alternative, or navigating to Cart some other way. Feeds `scripts/metrics_report.py`'s order-conversion-rate calculation; not otherwise read anywhere in the app.

## 5. Kitchen Dashboard (Staff)

- ✅ Live order queue via Firestore subscription, active/ready tabs, mark-ready/mark-complete actions — `screens/kitchen/KitchenDashboardScreen.tsx`
- ✅ **Live-verified end to end (2026-09-07):** a manually-provisioned kitchen account correctly routed to the dashboard, saw a real student-placed order in the Ready tab, and marking it "Picked Up" both correctly exercised the kitchen-only `ready → completed` rule transition (student accounts cannot make this specific transition per `firestore.rules`) and correctly reflected back as "Completed" in the student's own Order History.
- ❌ Role-based routing has no server-side enforcement — `RootNavigator.tsx` routes to the kitchen view purely off a client-read `profile.role` field with no Firestore rule verifying who can set that field (see §8 below)
- ❌ **Multi-location isolation** (design-spec.md §2.3, tasks.md 4.5) — there is no `locationId` anywhere in the schema or rules; any kitchen account can read and act on every dining hall's orders. Fine for a single-kitchen pilot, a real gap for more than one dining hall or more than one university

## 6. Admin Dashboard (Dining Staff — README §9.5)

- 🟡 **Menu entry and sold-out toggling exist (via the Kitchen Dashboard, tasks.md 3.3 + 4.3); the aggregate analytics view is still unbuilt.** `AddMenuItemScreen.tsx` covers menu upload/sync (one item at a time, manually — no CSV file picker in-app yet, only the API endpoint). `TodaysMenuScreen.tsx` (tasks.md 4.3, done 2026-09-13) lists today's menu with a per-item sold-out `Switch`, backed by `PATCH /admin/menu/{item_id}/availability` — the recommendation engine's hard filter now excludes sold-out items independently of the time-window check from 3.5. No screen exists yet for the aggregate anonymized-data view (most-recommended items, common dietary constraints). No separate admin role or navigator branch either — this reuses the kitchen role and kitchen navigation stack, per 3.2's scope decision, not a distinct Admin Dashboard as README §9.5 originally envisioned. Remaining scope: tasks.md 4.4 (analytics) and 4.5 (location isolation).

## 7. Auth

- 🟡 Firebase email/password sign-in and registration — `screens/auth/LoginScreen.tsx`, `RegisterScreen.tsx`
- ❌ University SSO (OAuth 2.0 / SAML, README §10) — not implemented; any student with an email can register regardless of campus affiliation

## 8. Security & Privacy

- ✅ `firestore.rules` committed and tested — `mealsense-app/firestore.rules`, verified by 16 emulator tests (`mealsense-app/tests/firestore.rules.test.js`, `npm run test:rules`)
- ✅ Students can only read/write their own `users/{uid}` and `orders`; kitchen-only writes are gated on a server-verified `role` field, not client navigation logic
- ✅ **Found and closed a real privilege-escalation bug**: `RegisterScreen.tsx` previously let any user self-select `role: "kitchen"` at signup with no gatekeeping, granting full access to every student's order queue. Rules now reject any client-created profile with `role != "student"`; the picker UI is removed; kitchen provisioning is documented in `mealsense-app/README-kitchen-accounts.md`.
- ✅ Profile + associated data deletion — `ProfileScreen.tsx` "Delete My Account & Data" (§1)
- ✅ **Rules deployed to production** (2026-09-07) — a fresh Firebase project (`mealsense-cb5ab`, Standard-edition Firestore, Email/Password Auth) replaced the old undocumented `myproject-dc745`; `firestore.rules` is now confirmed released via `firebase deploy --only firestore:rules`, not just governing the local emulator.

## 9. Testing

- ✅ **Backend recommendation engine and API routes** — `mealsense-api/tests/` (`conftest.py`, `test_recommendation_engine.py`, `test_routes.py`), 47/47 passing, `services/recommendation_engine.py` at 100% line coverage. Covers the allergen-safety hard filter (case-insensitivity, multi-allergy, zero-false-negative, and fail-closed on missing allergen data), dietary-identity AND logic, condition-based weight reweighting, Mifflin-St Jeor targeting, and the `/menu` and `/recommendation` routes. See `tasks.md` Phase 2.
- ✅ **Menu ingestion, persistence, and upload** — `test_menu_ingestion.py` (97 tests, adapter-agnostic), `test_menu_store.py` and `test_admin_menu.py` (against a real local Firestore emulator, not mocked), `test_auth.py` (the upload endpoint's role-gating logic). 116/116 tests passing overall, 98% coverage across `services/` and `routers/`; the Firestore/Firestore-dependent tests skip cleanly with a clear reason if the emulator isn't running, rather than the rest of the suite requiring it.
- ❌ **Frontend has no test setup** — no equivalent coverage exists for `mealsense-app/src` beyond the already-passing `firestore.rules.test.js` (§8).

## 10. Deployment & Infrastructure

- 🟡 Runs locally only: FastAPI via `uvicorn` on a dev machine, Expo Go pointed at the Mac's LAN IP (`mealsense-app/src/config/api.ts`, hardcoded, manually updated per network — confirmed via live testing this value silently goes stale whenever the Mac's IP changes, e.g. switching networks, with no error surfaced, just requests that hang)
- ❌ No `vercel.json` or any hosting config — "hosted on Vercel" in the README architecture diagram is aspirational, not real
- ❌ No CI/CD pipeline
- ❌ No environment separation (dev/staging/prod)
- ✅ **Fixed (2026-09-07):** `mealsense-app` upgraded from Expo SDK 54 to SDK 57 (react 19.2.3, react-native 0.86.3, and all Expo-managed peer packages realigned to their SDK-locked versions). `app.json` also had three fields (`newArchEnabled`, top-level `splash`, `android.edgeToEdgeEnabled`) that are no longer valid under the SDK 57 config schema; `splash` was migrated to the `expo-splash-screen` config plugin, the other two removed as now-mandatory defaults. `npx expo-doctor` passes 18/18 checks post-upgrade.
- ✅ **Fixed (2026-09-07):** two live Firestore queries (`OrderHistoryScreen.tsx`'s `where(studentId) + orderBy(placedAt)`, `KitchenDashboardScreen.tsx`'s `where(status, in) + orderBy(placedAt)`) require composite indexes that were never committed to the repo (no `firestore.indexes.json` existed at all). This meant every fresh Firestore project — including the one created this session — silently broke both the order-history view and the kitchen dashboard on first use, surfacing only as an uncaught `failed-precondition` console error, not a visible in-app message. Added `firestore.indexes.json`, wired into `firebase.json`, and deployed.

## 11. Success Metrics (README §14)

- ✅ **Five of nine metrics now measurable** (tasks.md Phase 8, done 2026-09-13): profile completion rate (derived from existing `onboardingComplete` data, no new instrumentation needed), recommendation relevance and feedback submission rate (from Phase 8.0's `recommendation_history`), time-to-recommendation (new `analytics_events` Firestore collection, logged client-side around the `/recommendation` fetch), and order conversion rate (`recommendationId` threaded from the top recommendation card through to the placed order). `mealsense-api/scripts/metrics_report.py` computes and prints all five against their README §14 targets — a script, not a dashboard, per tasks.md 8.3's own scope.
- ❌ **Four metrics remain unmeasured, deliberately**: allergen-safe recommendation rate is a structural guarantee proved by `recommendation_engine.py`'s own test suite, not something live instrumentation would add anything to; weekly active users and order-status accuracy were never part of Phase 8's agreed scope (tasks.md 8.2); the ML thumbs-up-vs-baseline metric has no meaning until Phase 6 (the bandit) exists at all.

---

## Summary

| Area | Status |
|---|---|
| Onboarding/Profile | 🟡 mostly done, missing deletion |
| Recommendation engine (rule-based) | ✅ done |
| Recommendation engine (ML/bandit) | ❌ design only |
| Menu data pipeline | ✅ Firestore-backed with sample-menu fallback; adapters + admin upload endpoint + live SCU vendor sync all wired |
| Generic ingestion/normalization adapter | ✅ done, tested, and now wired into a live endpoint (design-spec.md §7.0) |
| LLM-assisted incomplete-data handling | ✅ done (design-spec.md §7.0a) — Claude-backed nutrition estimation + confidence-gated allergen extraction, vendor-sync path only |
| Ordering flow | ✅ done (demo payment, as intended) |
| Kitchen dashboard | ✅ done |
| Multi-location kitchen isolation | ❌ not started (design-spec.md §2.3) |
| Admin dashboard | 🟡 manual menu entry + sold-out toggle (via Kitchen Dashboard); aggregate analytics still not started |
| Auth | 🟡 email/password only, no SSO |
| Security rules | ✅ written, tested, and deployed to production |
| Testing | 🟡 recommendation engine + API routes covered (100% on the engine); frontend uncovered |
| Deployment | ❌ local-only |
| Metrics instrumentation | 🟡 5 of 9 README §14 metrics measurable via `scripts/metrics_report.py`; the other 4 deliberately out of scope (see §11) |

This is a working prototype of the core ordering + rule-based recommendation loop, not the platform described end-to-end in the README.
