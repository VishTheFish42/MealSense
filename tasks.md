# Tasks — MealSense (Full Project)

**Status:** Not started (Phase 0 partially applicable — see notes)
**Date:** 2026-08-21
**Requirements:** [requirements.md](requirements.md)

Phases are ordered by risk and dependency, not by how interesting they are. Security comes first because health data and order records are currently unprotected by anything in this repo. Each phase should land as its own PR — that keeps every resume/interview claim about this project traceable to real, reviewable work.

---

## Phase 1 — Security Hardening (do this first) ✅ code complete, one manual step left

Traces to requirements §8. This is the biggest real gap in the project — not a stretch goal.

- [x] 1.1 Write `firestore.rules` and commit it to the repo — `mealsense-app/firestore.rules`
- [x] 1.2 Rule: a student can only read/write their own `users/{uid}` document
- [x] 1.3 Rule: a student can only read their own `orders` (query by `studentId`), never another student's
- [x] 1.4 Rule: only accounts with `role: "kitchen"` can transition `orders.status` toward `ready`/`completed`; the owning student can independently advance `placed → preparing → ready` (matches the existing client-side demo timer in `OrderStatusScreen.tsx` — this is enforced by the same rule that also guarantees `items`/`totalPrice`/`studentId` are immutable on every status-advancing write
- [x] 1.5 Audited how `role: "kitchen"` actually got assigned: **`RegisterScreen.tsx` let any user self-select it at signup with zero gatekeeping** — a real privilege-escalation bug, not hypothetical. Fixed by (a) rules that reject any client-created user doc with `role != "student"`, (b) removing the role picker from `RegisterScreen.tsx` entirely, (c) documenting the real provisioning path in `mealsense-app/README-kitchen-accounts.md` (manual console edit for now; a real admin flow is Phase 4)
- [x] 1.6 Tested rules with the Firebase emulator (`@firebase/rules-unit-testing` + Node's built-in test runner, no Jest needed) — `mealsense-app/tests/firestore.rules.test.js`, 16/16 passing via `npm run test:rules`
- [x] 1.7 Added a profile + associated data deletion flow — `ProfileScreen.tsx`'s "Delete My Account & Data" batch-deletes the student's orders, deletes their `users/{uid}` doc, then deletes the Auth account itself
- [ ] 1.8 **Manual, needs you:** deploy the rules to the live project — `npx firebase login` then `npx firebase deploy --only firestore:rules` from `mealsense-app/`. Nothing above touches production until this runs; right now `firestore.rules` only governs the local emulator.

## Phase 2 — Testing Infrastructure

Traces to requirements §9. Scoped tightly to the recommendation engine's real safety invariant (zero-false-negative allergen filtering) plus API route coverage.

### 2.1 Test Infrastructure Setup
- [ ] 2.1.1 Add `pytest` and `httpx` to `mealsense-api/requirements.txt` (or a new `requirements-dev.txt`)
- [ ] 2.1.2 Create `mealsense-api/tests/` package with `__init__.py`
- [ ] 2.1.3 Add `pytest.ini` (or `pyproject.toml` `[tool.pytest.ini_options]`) setting `testpaths = tests`
- [ ] 2.1.4 Verify `pytest` runs from `mealsense-api/` with `python -m pytest`
- [ ] 2.1.5 Add `conftest.py` with shared fixtures: a minimal valid student profile, a small fixture menu (allergen item, vegan item, high-protein item, off-period item)

### 2.2 Recommendation Engine Unit Tests (`test_recommendation_engine.py`)
- [ ] 2.2.1 Allergen hard filter: single flagged allergen excludes matching item
- [ ] 2.2.2 Allergen hard filter: case-insensitive matching
- [ ] 2.2.3 Allergen hard filter: multiple simultaneous allergies all enforced
- [ ] 2.2.4 Dietary identity filter: single identity (e.g. vegetarian) enforced
- [ ] 2.2.5 Dietary identity filter: multiple identities enforced as AND, not OR
- [ ] 2.2.6 Meal-period availability filter enforced correctly
- [ ] 2.2.7 No-safe-items fallback returns `null` + `"no_safe_items"`
- [ ] 2.2.8 Macro/calorie alignment score decreases monotonically as calories diverge from target
- [ ] 2.2.9 Protein/fiber scores capped at reference max (50g / 15g)
- [ ] 2.2.10 Variety penalty applied for items in `recent_ids`
- [ ] 2.2.11 Final item score bounded to [0, 100]
- [ ] 2.2.12 Diabetes profile shifts weight toward `sugar_sodium`
- [ ] 2.2.13 Hypertension (without diabetes) applies the same shift
- [ ] 2.2.14 Diabetes + hypertension together: no double-adjustment
- [ ] 2.2.15 Adjusted weights sum to 1.0, parametrized over all condition combinations
- [ ] 2.2.16 BMR fixed test vectors for male and female profiles
- [ ] 2.2.17 All four activity multipliers applied correctly
- [ ] 2.2.18 Goal adjustments (lose/gain/maintain) applied correctly
- [ ] 2.2.19 Meal-period apportionment matches README §8.4 table
- [ ] 2.2.20 Top recommendation is always the highest-scoring candidate
- [ ] 2.2.21 Alternatives capped at 3, sorted descending
- [ ] 2.2.22 Reasoning signals capped at 4

### 2.3 API Route Tests (`test_routes.py`)
- [ ] 2.3.1 `GET /menu` with no params returns all items + correct `count`
- [ ] 2.3.2 `GET /menu?meal_period=X` filters correctly, including `all_day` items
- [ ] 2.3.3 `POST /recommendation` with a minimal valid profile returns 200 + expected shape
- [ ] 2.3.4 `POST /recommendation` with malformed/missing fields returns a 4xx (document actual behavior)

### 2.4 Coverage
- [ ] 2.4.1 Add `pytest-cov`; run `pytest --cov=services --cov-report=term-missing`
- [ ] 2.4.2 Confirm `services/recommendation_engine.py` hits ≥90% line coverage

**Definition of done for the resume claim:** 2.1–2.3 complete. At that point "wrote a pytest suite covering the recommendation engine's hard-filter and scoring logic" is accurate and defensible in an interview.

## Phase 3 — Menu Data Pipeline

Traces to requirements §3. Currently the entire menu is one hardcoded Python file; nothing here is built yet despite being a documented architecture decision.

- [ ] 3.1 Design the `MenuItem` persistence layer (Firestore collection, matching `README.md §7.1` schema) — decide whether to keep the sample menu as a seed/fallback or replace it outright
- [ ] 3.2 Build admin CSV/JSON upload endpoint (README §7.2 priority #2 — cheaper to build than a vendor integration, do this before #3.3)
- [ ] 3.3 Build manual entry UI for dining staff (README §7.2 priority #3) — this is also the entry point needed for Phase 4's admin dashboard
- [ ] 3.4 Research and scope a real vendor API integration (Nutrislice or Cbord, README §7.2 priority #1) — this depends on picking a target school with a known vendor (README §12 Open Question #1), so don't start building against a guessed API shape
- [ ] 3.5 Implement `available_from`/`available_until` time-window availability logic server-side (currently only conceptual in README §7.3 — the sample menu has the fields but nothing computes "is this available right now" beyond the meal-period match in `_passes_hard_filters`)

## Phase 4 — Admin Dashboard (Dining Staff)

Traces to requirements §6. Fully unbuilt — distinct from the Kitchen Dashboard, which only handles order fulfillment.

- [ ] 4.1 New navigator branch + role (`role: "admin"` or reuse `"kitchen"` with a sub-permission — decide based on Phase 1.5's role model)
- [ ] 4.2 Upload/sync UI wired to Phase 3.2's endpoint
- [ ] 4.3 Mark items sold out / unavailable in real time
- [ ] 4.4 Aggregate anonymized view: most-recommended items, common dietary constraints on campus (README §9.5) — needs an aggregation query or a scheduled rollup job; don't do this as a naive per-request scan once order volume is nonzero

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
