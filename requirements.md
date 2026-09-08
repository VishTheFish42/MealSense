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

- ✅ Hard filters: allergen exclusion, dietary identity matching, meal-period availability — `mealsense-api/services/recommendation_engine.py::_passes_hard_filters`
- ✅ Five-signal weighted scoring (macro/calorie, protein, fiber, sugar/sodium, variety) — `_score_item`
- ✅ Condition-based weight reweighting (diabetes, hypertension, high cholesterol, IBS) — `_weights_for_profile`
- ✅ Mifflin-St Jeor calorie targeting with activity multiplier + meal apportionment — `_calorie_target`
- ✅ "Why this?" human-readable reasoning string — `_primary_reason`
- ✅ No-safe-items fallback (`reason: "no_safe_items"`) instead of a bad recommendation
- ❌ **ML-enhanced scoring (Profile-Adaptive Contextual Bandit, design-spec §14)** — fully designed (LinUCB, k=15 clustering, cold-start handling, shadow-mode/A-B rollout) but zero implementation. This is the piece the old resume bullets described as done — it is not.
- ❌ Recommendation history view (README §9.4: "view recommendation history (last 7 days)") — not stored or displayed anywhere

## 3. Menu Data

- 🟡 **Static only.** `mealsense-api/data/sample_menu.py` is a hardcoded 20-item Python list. Both `/menu` and `/recommendation` read from it directly.
- ❌ Vendor API integration (Nutrislice/Cbord, README §7.2 priority #1) — not started
- ❌ Admin CSV/JSON upload (README §7.2 priority #2) — not started
- ❌ Manual entry by dining staff (README §7.2 priority #3) — not started
- ❌ Any persistence layer for menu data — Firestore isn't used for menu at all; nothing survives a backend restart or varies by day/campus
- ❌ **Generic ingestion/normalization adapter** (design-spec.md §7.0, tasks.md 3.1a) — the "one integration any college plugs into regardless of feed shape" claim has no code behind it yet; there is one hardcoded Python list, not an adapter layer

## 4. Ordering (Cart → Checkout → Status)

- ✅ Cart with quantity control — `screens/student/CartScreen.tsx`
- ✅ Checkout writes an order to Firestore (`orders` collection) — `CheckoutScreen.tsx`
- ✅ Placeholder payment UI, clearly labeled "Demo — no charge," no real processing — matches README §4 non-goal
- ✅ Real-time order status via Firestore `onSnapshot` — `OrderStatusScreen.tsx`
- ✅ Timer-based status progression (30s placed→preparing, 90s preparing→ready) — `constants/orderTimers.ts`. Intentionally a demo mechanism per README §9.8; not read as a shortcoming, but the timer fires from the **client**, so it silently stops if the student closes the app before it elapses — no server-side or kitchen-triggered fallback.
- ✅ **Live-verified end to end (2026-09-07):** registration → onboarding → recommendation (scoring, allergen exclusion, and reasoning text all cross-checked directly against `recommendation_engine.py`) → cart → checkout → all three real-time order-status transitions → order history, all confirmed on a physical device against the deployed `mealsense-cb5ab` project, not just inferred from reading the code.
- ✅ Order history list — `OrderHistoryScreen.tsx`

## 5. Kitchen Dashboard (Staff)

- ✅ Live order queue via Firestore subscription, active/ready tabs, mark-ready/mark-complete actions — `screens/kitchen/KitchenDashboardScreen.tsx`
- ✅ **Live-verified end to end (2026-09-07):** a manually-provisioned kitchen account correctly routed to the dashboard, saw a real student-placed order in the Ready tab, and marking it "Picked Up" both correctly exercised the kitchen-only `ready → completed` rule transition (student accounts cannot make this specific transition per `firestore.rules`) and correctly reflected back as "Completed" in the student's own Order History.
- ❌ Role-based routing has no server-side enforcement — `RootNavigator.tsx` routes to the kitchen view purely off a client-read `profile.role` field with no Firestore rule verifying who can set that field (see §8 below)
- ❌ **Multi-location isolation** (design-spec.md §2.3, tasks.md 4.5) — there is no `locationId` anywhere in the schema or rules; any kitchen account can read and act on every dining hall's orders. Fine for a single-kitchen pilot, a real gap for more than one dining hall or more than one university

## 6. Admin Dashboard (Dining Staff — README §9.5)

- ❌ **Entirely unbuilt.** No screen, no route, no navigator branch exists for menu upload/sync, marking items sold out, or the aggregate anonymized-data view. This is a distinct, fully-missing feature from the Kitchen Dashboard (§5 above), which only handles order fulfillment.

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

- ✅ **Backend recommendation engine and API routes** — `mealsense-api/tests/` (`conftest.py`, `test_recommendation_engine.py`, `test_routes.py`), 47/47 passing, `services/recommendation_engine.py` at 100% line coverage. Covers the allergen-safety hard filter (case-insensitivity, multi-allergy, zero-false-negative), dietary-identity AND logic, condition-based weight reweighting, Mifflin-St Jeor targeting, and the `/menu` and `/recommendation` routes. See `tasks.md` Phase 2.
- ❌ **Frontend has no test setup** — no equivalent coverage exists for `mealsense-app/src` beyond the already-passing `firestore.rules.test.js` (§8).

## 10. Deployment & Infrastructure

- 🟡 Runs locally only: FastAPI via `uvicorn` on a dev machine, Expo Go pointed at the Mac's LAN IP (`mealsense-app/src/config/api.ts`, hardcoded, manually updated per network — confirmed via live testing this value silently goes stale whenever the Mac's IP changes, e.g. switching networks, with no error surfaced, just requests that hang)
- ❌ No `vercel.json` or any hosting config — "hosted on Vercel" in the README architecture diagram is aspirational, not real
- ❌ No CI/CD pipeline
- ❌ No environment separation (dev/staging/prod)
- ✅ **Fixed (2026-09-07):** `mealsense-app` upgraded from Expo SDK 54 to SDK 57 (react 19.2.3, react-native 0.86.3, and all Expo-managed peer packages realigned to their SDK-locked versions). `app.json` also had three fields (`newArchEnabled`, top-level `splash`, `android.edgeToEdgeEnabled`) that are no longer valid under the SDK 57 config schema; `splash` was migrated to the `expo-splash-screen` config plugin, the other two removed as now-mandatory defaults. `npx expo-doctor` passes 18/18 checks post-upgrade.
- ✅ **Fixed (2026-09-07):** two live Firestore queries (`OrderHistoryScreen.tsx`'s `where(studentId) + orderBy(placedAt)`, `KitchenDashboardScreen.tsx`'s `where(status, in) + orderBy(placedAt)`) require composite indexes that were never committed to the repo (no `firestore.indexes.json` existed at all). This meant every fresh Firestore project — including the one created this session — silently broke both the order-history view and the kitchen dashboard on first use, surfacing only as an uncaught `failed-precondition` console error, not a visible in-app message. Added `firestore.indexes.json`, wired into `firebase.json`, and deployed.

## 11. Success Metrics (README §14)

All nine metrics in the table (profile completion rate, recommendation relevance, allergen-safe rate, time-to-recommendation, WAU, ML thumbs-up vs. baseline, feedback submission rate, order conversion, order status accuracy) are **targets with no instrumentation** — no analytics/event tracking exists anywhere in the app to measure any of them.

---

## Summary

| Area | Status |
|---|---|
| Onboarding/Profile | 🟡 mostly done, missing deletion |
| Recommendation engine (rule-based) | ✅ done |
| Recommendation engine (ML/bandit) | ❌ design only |
| Menu data pipeline | ❌ hardcoded sample only |
| Generic ingestion/normalization adapter | ❌ not started (design-spec.md §7.0) |
| Ordering flow | ✅ done (demo payment, as intended) |
| Kitchen dashboard | ✅ done |
| Multi-location kitchen isolation | ❌ not started (design-spec.md §2.3) |
| Admin dashboard | ❌ not started |
| Auth | 🟡 email/password only, no SSO |
| Security rules | ✅ written, tested, and deployed to production |
| Testing | 🟡 recommendation engine + API routes covered (100% on the engine); frontend uncovered |
| Deployment | ❌ local-only |
| Metrics instrumentation | ❌ not started |

This is a working prototype of the core ordering + rule-based recommendation loop, not the platform described end-to-end in the README.
