# Requirements — MealSense (Full Project)

**Status:** Draft — audited against actual code
**Date:** 2026-08-21
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

## 4. Ordering (Cart → Checkout → Status)

- ✅ Cart with quantity control — `screens/student/CartScreen.tsx`
- ✅ Checkout writes an order to Firestore (`orders` collection) — `CheckoutScreen.tsx`
- ✅ Placeholder payment UI, clearly labeled "Demo — no charge," no real processing — matches README §4 non-goal
- ✅ Real-time order status via Firestore `onSnapshot` — `OrderStatusScreen.tsx`
- ✅ Timer-based status progression (30s placed→preparing, 90s preparing→ready) — `constants/orderTimers.ts`. Intentionally a demo mechanism per README §9.8; not read as a shortcoming, but the timer fires from the **client**, so it silently stops if the student closes the app before it elapses — no server-side or kitchen-triggered fallback.
- ✅ Order history list — `OrderHistoryScreen.tsx`

## 5. Kitchen Dashboard (Staff)

- ✅ Live order queue via Firestore subscription, active/ready tabs, mark-ready/mark-complete actions — `screens/kitchen/KitchenDashboardScreen.tsx`
- ❌ Role-based routing has no server-side enforcement — `RootNavigator.tsx` routes to the kitchen view purely off a client-read `profile.role` field with no Firestore rule verifying who can set that field (see §8 below)

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
- 🟡 **Rules are written and tested locally but not yet deployed** — `firebase deploy --only firestore:rules` hasn't been run against the live project. Until that happens, whatever rules are currently live in the Firebase console (undocumented) are still what's actually protecting production data.

## 9. Testing

- ❌ **Zero automated tests anywhere in the repo** — no `mealsense-api/tests/`, no frontend test setup. See `tasks.md` Phase 2 for the full breakdown; the recommendation engine (§2) is the highest-value target since it carries the allergen-safety invariant.

## 10. Deployment & Infrastructure

- 🟡 Runs locally only: FastAPI via `uvicorn` on a dev machine, Expo Go pointed at the Mac's LAN IP (`mealsense-app/src/config/api.ts`, hardcoded, manually updated per network)
- ❌ No `vercel.json` or any hosting config — "hosted on Vercel" in the README architecture diagram is aspirational, not real
- ❌ No CI/CD pipeline
- ❌ No environment separation (dev/staging/prod)

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
| Ordering flow | ✅ done (demo payment, as intended) |
| Kitchen dashboard | ✅ done |
| Admin dashboard | ❌ not started |
| Auth | 🟡 email/password only, no SSO |
| Security rules | 🟡 written + tested, not yet deployed |
| Testing | ❌ zero coverage |
| Deployment | ❌ local-only |
| Metrics instrumentation | ❌ not started |

This is a working prototype of the core ordering + rule-based recommendation loop, not the platform described end-to-end in the README.
