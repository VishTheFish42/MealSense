# Food Recommendation & Diet Planning App — Technical Design Document

**Owner:** Vishwa Prakash  
**Status:** Draft  
**Date:** 2026-04-26  
**Spec Reference:** [README.md](README.md)

---

## 1. Overview

This document describes the technical design for the Food Recommendation & Diet Planning App. The app gives university students a single personalized cafeteria meal recommendation in real time, filtered against hard dietary constraints and scored against their health profile. This doc covers system architecture, data models, API contracts, the recommendation engine, auth flow, and infrastructure.

---

## 2. System Architecture

### 2.1 High-Level Diagram

```
┌─────────────────────────────────────────────────────┐
│            Mobile App (React Native + Expo Go)      │
│              iOS App   │   Android App               │
└──────────────────────┬──────────────────────────────┘
                       │ HTTPS
                       ▼
┌─────────────────────────────────────────────────────┐
│            Vercel Edge (API Gateway)                │
│   Rate limiting │ Auth token validation │ Routing   │
└───┬─────────┬─────────┬──────────────┬──────────────┘
    │         │         │              │
    ▼         ▼         ▼              ▼
┌───────┐ ┌───────┐ ┌────────┐ ┌──────────────┐
│ Auth  │ │Profile│ │ Menu   │ │Recommendation│
│Service│ │Service│ │Service │ │   Service    │
└───┬───┘ └───┬───┘ └───┬────┘ └──────┬───────┘
    │         │         │              │
    │         └────┬────┘              │
    │              ▼                   │
    │        ┌──────────┐              │
    │        │Firestore │◄─────────────┘
    │        │(Firebase)│
    │        └──────────┘
    │
    ▼
Firebase Auth + University SSO
(OAuth 2.0 / SAML)
```

### 2.2 Services

| Service | Responsibility |
|---|---|
| **API Gateway** | TLS termination, JWT validation, rate limiting, request routing |
| **Auth Service** | University SSO handshake, JWT issuance and refresh |
| **Profile Service** | CRUD for student health profiles (encrypted at rest) |
| **Menu Service** | Ingest, store, and serve cafeteria menu data; real-time availability |
| **Recommendation Service** | Stateless scoring engine; calls Profile + Menu services per request |

### 2.3 Key Design Decisions

**Stateless Recommendation Service.** Each recommendation request fetches profile and menu data fresh. This keeps the service horizontally scalable and avoids cache invalidation complexity around profile/menu changes.

**Firebase Firestore as primary datastore.** Firestore (NoSQL document store) handles all app data: student profiles, menu items, allergen data, and recommendation history. As a managed Firebase service it pairs naturally with Firebase Authentication, eliminates RDS/VPC operational overhead, and scales automatically. Because Firestore lacks relational foreign-key constraints, allergen integrity — previously enforceable by the database — is enforced entirely at the application layer: the Recommendation Service's hard filter (§5.1) always validates allergen fields before any item surfaces. Items with missing or malformed allergen documents are excluded, not surfaced.

**No async queue for v1.** Menu ingestion (CSV upload or vendor webhook) writes directly to the Menu Service. A message queue (SQS/Kafka) can be added in v2 if ingestion volume grows.

---

## 3. Data Models

> **Note:** Models below are expressed as relational schemas for precision and readability. The actual implementation uses Firebase Firestore; each table maps to a top-level collection, each row to a document, and foreign-key relationships are maintained at the application layer. Allergen referential integrity (previously a DB constraint) is enforced by the hard filter in the Recommendation Service (§5.1).

### 3.4 Orders (Firestore Collection)

```
orders/{orderId}
  studentId:       string
  items: [
    { menuItemId: string, name: string, quantity: int, price: float }
  ]
  totalPrice:      float
  status:          'placed' | 'preparing' | 'ready' | 'completed' | 'cancelled'
  placedAt:        timestamp
  preparingAt?:    timestamp
  readyAt?:        timestamp
  completedAt?:    timestamp
  paymentStatus:   'placeholder'   -- no real charge in v1
  notes?:          string
```

### 3.1 Student Profile

```sql
CREATE TABLE students (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sso_subject   TEXT NOT NULL UNIQUE,        -- opaque ID from university SSO
  university_id UUID NOT NULL REFERENCES universities(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at    TIMESTAMPTZ                  -- soft delete; triggers data purge job
);

CREATE TABLE student_profiles (
  student_id     UUID PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
  age            SMALLINT,
  sex            TEXT,                       -- 'male' | 'female' | 'undisclosed'
  height_cm      NUMERIC(5,1),
  weight_kg      NUMERIC(5,1),
  activity_level TEXT,                       -- 'sedentary' | 'light' | 'moderate' | 'very_active'
  health_goal    TEXT,                       -- 'lose_weight' | 'maintain' | 'gain_muscle' | 'energy' | 'wellness'
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE student_allergies (
  student_id UUID REFERENCES students(id) ON DELETE CASCADE,
  allergen   TEXT NOT NULL,                  -- normalized allergen key
  notes      TEXT,                           -- free text for 'Other'
  PRIMARY KEY (student_id, allergen)
);

CREATE TABLE student_dietary_identity (
  student_id UUID REFERENCES students(id) ON DELETE CASCADE,
  identity   TEXT NOT NULL,                  -- 'vegetarian' | 'vegan' | 'halal' | 'kosher'
  PRIMARY KEY (student_id, identity)
);

CREATE TABLE student_conditions (
  student_id UUID REFERENCES students(id) ON DELETE CASCADE,
  condition  TEXT NOT NULL,                  -- 'diabetes' | 'hypertension' | 'high_cholesterol' | etc.
  notes      TEXT,
  PRIMARY KEY (student_id, condition)
);

CREATE TABLE student_nutritional_focus (
  student_id UUID REFERENCES students(id) ON DELETE CASCADE,
  focus      TEXT NOT NULL,                  -- 'high_protein' | 'low_carb' | 'low_sodium' | 'high_fiber' | 'low_sugar'
  PRIMARY KEY (student_id, focus)
);
```

### 3.2 Cafeteria Menu

```sql
CREATE TABLE universities (
  id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE
);

CREATE TABLE dining_locations (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id UUID NOT NULL REFERENCES universities(id),
  name          TEXT NOT NULL
);

CREATE TABLE menu_items (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  location_id      UUID NOT NULL REFERENCES dining_locations(id),
  name             TEXT NOT NULL,
  station          TEXT,
  meal_period      TEXT NOT NULL,             -- 'breakfast' | 'lunch' | 'dinner' | 'all_day'
  available_from   TIME,
  available_until  TIME,
  served_on        DATE NOT NULL,
  calories         INT,
  protein_g        NUMERIC(6,2),
  carbs_g          NUMERIC(6,2),
  fat_g            NUMERIC(6,2),
  fiber_g          NUMERIC(6,2),
  sodium_mg        NUMERIC(7,2),
  sugar_g          NUMERIC(6,2),
  ingredients_text TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE menu_item_allergens (
  menu_item_id UUID REFERENCES menu_items(id) ON DELETE CASCADE,
  allergen     TEXT NOT NULL,
  PRIMARY KEY (menu_item_id, allergen)
);

CREATE TABLE menu_item_dietary_tags (
  menu_item_id UUID REFERENCES menu_items(id) ON DELETE CASCADE,
  tag          TEXT NOT NULL,
  PRIMARY KEY (menu_item_id, tag)
);

-- Tracks sold-out overrides set by dining staff in real time
CREATE TABLE menu_item_availability_overrides (
  menu_item_id UUID PRIMARY KEY REFERENCES menu_items(id) ON DELETE CASCADE,
  available     BOOLEAN NOT NULL DEFAULT true,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 3.3 Recommendation History

```sql
CREATE TABLE recommendation_history (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id    UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  menu_item_id  UUID NOT NULL REFERENCES menu_items(id),
  score         NUMERIC(5,2),
  recommended_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  feedback      TEXT                           -- 'thumbs_up' | 'thumbs_down' | null
);
```

---

## 4. API Design

All endpoints are REST over HTTPS. Requests include `Authorization: Bearer <jwt>`. Responses are JSON.

### 4.1 Auth

| Method | Path | Description |
|---|---|---|
| `GET` | `/auth/sso/login` | Redirect to university SSO |
| `GET` | `/auth/sso/callback` | SSO callback; issues JWT + refresh token |
| `POST` | `/auth/token/refresh` | Exchange refresh token for new JWT |
| `POST` | `/auth/logout` | Revoke refresh token |

### 4.2 Profile

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/profile` | Fetch current student's profile |
| `PUT` | `/v1/profile` | Update profile (full replace) |
| `PATCH` | `/v1/profile` | Partial update |
| `DELETE` | `/v1/profile` | Delete account and all health data |

**PUT /v1/profile — Request Body**

```json
{
  "age": 20,
  "sex": "male",
  "height_cm": 175.0,
  "weight_kg": 72.0,
  "activity_level": "moderately_active",
  "health_goal": "gain_muscle",
  "allergies": ["nuts", "shellfish"],
  "dietary_identity": ["halal"],
  "conditions": ["high_cholesterol"],
  "nutritional_focus": ["high_protein", "low_sodium"]
}
```

### 4.3 Recommendation

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/recommendation` | Get top recommendation for current meal period |
| `GET` | `/v1/recommendation?location_id=<id>` | Scoped to a specific dining location |
| `POST` | `/v1/recommendation/:id/feedback` | Submit thumbs up/down |

**GET /v1/recommendation — Response**

```json
{
  "recommendation": {
    "menu_item_id": "uuid",
    "name": "Grilled Chicken Bowl",
    "station": "Hot Entrees",
    "score": 87.4,
    "meal_period": "lunch",
    "available_until": "14:00",
    "nutrition": {
      "calories": 520,
      "protein_g": 42,
      "carbs_g": 38,
      "fat_g": 14,
      "fiber_g": 6,
      "sodium_mg": 480,
      "sugar_g": 3
    },
    "reasoning": {
      "primary": "High protein aligns with your muscle-gain goal.",
      "signals": ["high_protein", "low_sugar", "low_sodium"]
    }
  },
  "alternatives": [
    { "menu_item_id": "uuid", "name": "Lentil Soup", "score": 74.1 },
    { "menu_item_id": "uuid", "name": "Turkey Wrap", "score": 68.9 }
  ],
  "meal_period": "lunch",
  "generated_at": "2026-04-26T12:03:17Z"
}
```

**Error: no safe items available**

```json
{
  "recommendation": null,
  "reason": "no_safe_items",
  "message": "Nothing available right now matches your dietary restrictions.",
  "generated_at": "2026-04-26T12:03:17Z"
}
```

### 4.4 Menu (Admin)

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/admin/menu/upload` | Upload CSV or JSON menu for a date |
| `GET` | `/v1/admin/menu` | List today's menu items |
| `PATCH` | `/v1/admin/menu/:id/availability` | Mark item sold out / available |
| `GET` | `/v1/admin/analytics` | Aggregate anonymized stats |

### 4.5 Orders

Orders are written directly to Firestore by the client; the FastAPI service is not in the order write path for v1. The table below describes client-initiated Firestore operations and the kitchen dashboard's real-time subscription.

| Operation | Firestore Path | Actor | Description |
|---|---|---|---|
| Write | `orders/{orderId}` | Student app | Place a new order (status: `placed`) |
| Update | `orders/{orderId}` | Student app | Timer-driven status transitions (`placed → preparing → ready`) |
| Subscribe | `orders` where status ∈ {placed, preparing} | Kitchen app | Real-time incoming order feed |
| Update | `orders/{orderId}` | Kitchen app | Manual status override (future) |

**Order document written at placement:**

```json
{
  "studentId": "firebase-uid",
  "items": [
    { "menuItemId": "uuid", "name": "Grilled Chicken Bowl", "quantity": 1, "price": 9.50 }
  ],
  "totalPrice": 9.50,
  "status": "placed",
  "placedAt": "2026-04-26T12:05:00Z",
  "paymentStatus": "placeholder",
  "notes": ""
}
```

---

## 5. Recommendation Engine

### 5.1 Algorithm (Stateless, Per-Request)

```
function recommend(student, menuItems, now):

  # Step 1 — Hard filter
  candidates = menuItems
    .filter(item => isAvailableNow(item, now))
    .filter(item => noAllergenOverlap(item, student.allergies))
    .filter(item => dietaryIdentityMatch(item, student.dietary_identity))

  if candidates is empty:
    return { recommendation: null, reason: "no_safe_items" }

  # Step 2 — Score
  scored = candidates.map(item => (item, score(item, student, history)))

  # Step 3 — Sort and return
  sorted = scored.sortByScoreDesc()
  return { top: sorted[0], alternatives: sorted[1..3] }
```

### 5.2 Scoring Function

Base weights (sum to 100):

| Signal | Base Weight |
|---|---|
| Macro alignment with health goal | 35 |
| Protein content | 20 |
| Fiber content | 15 |
| Low sugar / low sodium (condition-aware) | 15 |
| Variety (penalty for recent recs) | 15 |

**Condition-based weight overrides**

| Condition | Override |
|---|---|
| `diabetes` | Low-sugar weight → 25; macro alignment → 30 |
| `hypertension` | Low-sodium weight → 25; macro alignment → 30 |
| `high_cholesterol` | Low-fat signal added (+10); fiber weight → 20 |
| `ibs` | High-fiber weight → 5; low-fat added |
| `iron_deficiency` | Iron-rich tag bonus +5 (if tag present in menu data) |

**Macro alignment (health goal)**

```
calorieTarget = mifflinStJeor(age, sex, weight_kg, height_cm)
                × activityMultiplier
                × mealShareFraction(meal_period)

calorieScore  = 1 - abs(item.calories - calorieTarget) / calorieTarget
                (clamped to [0, 1])
```

Mifflin-St Jeor:
- Male: `(10 × weight_kg) + (6.25 × height_cm) − (5 × age) + 5`
- Female: `(10 × weight_kg) + (6.25 × height_cm) − (5 × age) − 161`

Activity multipliers: Sedentary 1.2 / Lightly active 1.375 / Moderately active 1.55 / Very active 1.725

**Variety penalty**

Items recommended in the last 3 days receive a −15 point penalty on variety signal.

### 5.3 Allergen Safety

Allergen filtering uses **two passes**:

1. **Tag match:** `menu_item_allergens` table — direct structured match.
2. **Ingredient fuzzy match:** `ingredients_text` scanned for allergen synonyms (e.g., "casein" → dairy, "semolina" → gluten). When match is uncertain, **item is excluded**.

If a menu item has no allergen data at all and the student has any active allergen, the item is excluded (fail-safe default).

---

## 6. Auth Flow

```
Student opens app
      │
      ▼
App redirects to /auth/sso/login
      │
      ▼
Auth Service builds SSO redirect URL (OAuth 2.0 PKCE or SAML)
      │
      ▼
University Identity Provider authenticates student
      │
      ▼
Callback to /auth/sso/callback with auth code
      │
Auth Service:
  1. Exchanges code for SSO tokens
  2. Extracts stable `sub` (subject) claim
  3. Upserts student row (sso_subject, university_id)
  4. Issues signed JWT (24h expiry) + refresh token (30d, stored in httpOnly cookie)
      │
      ▼
Client stores JWT; includes in Authorization header on all requests
```

**JWT payload**

```json
{
  "sub": "student-uuid",
  "university_id": "university-uuid",
  "role": "student",
  "exp": 1745712000
}
```

Admin users carry `"role": "admin"` and `"location_id"`. All admin endpoints verify this claim.

---

## 7. Menu Ingestion

### 7.1 Vendor API (Primary Path)

Menu Service runs a nightly job (02:00 local campus time) that:
1. Calls the dining vendor API (Nutrislice / Cbord).
2. Normalizes the response to the `menu_items` schema.
3. Upserts records for the next day by `(location_id, name, served_on)`.
4. Flags items with incomplete allergen data for admin review.

### 7.2 CSV/JSON Upload (Fallback)

Admin uploads a file via `POST /v1/admin/menu/upload`. The Menu Service:
1. Validates required fields (`name`, `served_on`, `meal_period`, `calories`).
2. Rejects rows with no allergen data if the university has strict mode enabled.
3. Writes valid rows to `menu_items` and logs rejected rows in the response.

**Required CSV columns:** `name, station, meal_period, available_from, available_until, served_on, calories, protein_g, carbs_g, fat_g, fiber_g, sodium_mg, sugar_g, allergens (pipe-separated), dietary_tags (pipe-separated), ingredients`

### 7.3 Real-Time Availability

Dining staff mark items sold out via `PATCH /v1/admin/menu/:id/availability`. This writes to `menu_item_availability_overrides`. The Recommendation Service joins this table on every request — no caching layer, so sold-out changes take effect immediately.

---

## 8. Infrastructure

### 8.1 Target Stack

| Layer | Choice | Rationale |
|---|---|---|
| Mobile client | React Native + Expo Go (TypeScript) | Single codebase for iOS + Android; Expo Go enables rapid iteration |
| API service | Python + FastAPI | Async-native, strong typing, auto-generated OpenAPI docs |
| Database | Firebase Firestore | Managed NoSQL, no VPC/RDS ops, integrates directly with Firebase Auth |
| File storage | Firebase Storage | Menu CSV/JSON uploads; consistent with Firebase data layer |
| Auth | Firebase Authentication + University SSO | Token lifecycle managed by Firebase; SSO identity via OAuth 2.0 / SAML |
| API hosting | Vercel (serverless functions) | Zero-config deploys, global edge network, pairs with FastAPI via ASGI adapter |
| CI/CD | GitHub Actions | Build, test, deploy pipeline |

### 8.2 Scaling

- Recommendation Service is stateless — Vercel serverless functions scale automatically per request with no ALB configuration required.
- Firestore scales transparently; no connection pooling required. Monitor read unit costs if menu documents per location per day approach the ~500 item upper bound for v1.
- Cache layer (e.g., Vercel Edge Cache on the recommendation endpoint) can be added in v2 if Firestore read costs become significant under load.

### 8.3 SLOs (v1 Targets)

| Metric | Target |
|---|---|
| Recommendation API p95 latency | < 500 ms |
| Recommendation API availability | 99.5% |
| Allergen false-negative rate | 0% |

---

## 9. Security & Privacy

- **Payment placeholder:** v1 does not process real payments. The checkout screen accepts card input for UX completeness but submits no data to any payment processor. A real payment integration (Stripe or similar) will be wired in a future phase before any production launch.
- **Encryption at rest:** Firestore data encrypted at rest by Google (AES-256). Sensitive profile fields (allergies, conditions) should be additionally encrypted at the application layer in a future hardening pass.
- **Encryption in transit:** TLS 1.2+ enforced at API Gateway. Internal service-to-service traffic stays within VPC.
- **Data minimization:** SSO `sub` claim stored; no PII (name, email) stored in the app database.
- **Data deletion:** `DELETE /v1/profile` sets `deleted_at` on the student row. A nightly job hard-deletes all associated rows older than 30 days (gives students a window to undo).
- **Admin access:** Admin JWT required for all `/v1/admin/*` routes. Admins are scoped to their dining location — they cannot access other locations' data.
- **Audit log:** All writes to `student_profiles`, `student_allergies`, and admin availability overrides are logged to an append-only audit table.
- **Disclaimer:** A disclaimer ("This is a recommendation tool, not medical advice") is shown at onboarding and in the "Why this?" modal. Stored in the student's acknowledgement record on first login.

---

## 10. Testing Strategy

| Layer | Approach |
|---|---|
| Unit | Recommendation scoring function: table-driven tests covering goal × condition × menu combinations. Allergen fuzzy match: exhaustive synonym tests. |
| Integration | Profile CRUD, menu ingestion (CSV + vendor mock), auth token flow — all hitting a real Firestore emulator instance (Firebase Local Emulator Suite). |
| Contract | OpenAPI spec validated against each service's actual responses via Dredd or Schemathesis. |
| End-to-end | Happy path: onboard → receive recommendation → submit feedback. Allergen safety path: ensure zero unsafe items appear for a student with a given allergen across a seeded menu. |
| Load | Recommendation endpoint at 10× expected concurrent users (k6). Must hold < 500 ms p95. |

**Allergen safety tests are treated as blocking.** A failing allergen test fails the entire CI pipeline, regardless of other results.

---

## 11. Rollout Plan

| Phase | Scope | Success Gate |
|---|---|---|
| Alpha | Internal team + 1 campus dining staff | Allergen filter correct on real menu data; latency < 500 ms |
| Beta | 1 university, voluntary student signup (target: 50–100 students) | > 70% profile completion; > 75% recommendation relevance rating |
| v1 Launch | 1 university, open to all students | SLOs met; zero allergen incidents |
| v2 | Multi-university, wearable integrations, LLM-enhanced reasoning | TBD |

---

## 12. Open Questions

| # | Question | Owner | Due |
|---|---|---|---|
| 1 | Which dining vendor API does the target school use? (Nutrislice vs. Cbord vs. other) | PM | — |
| 2 | Multi-location support in v1 or deferred? Impacts `dining_locations` schema usage. | PM | — |
| 3 | Default-exclude or flag-and-show for items with incomplete allergen data? | Eng + Legal | — |
| 4 | Is university SSO required, or do we also need email/password fallback? Affects Auth Service scope. | PM | — |
| 5 | Which platform ships first — iOS, Android, or web (PWA)? | PM + Eng | — |
| 6 | What is the expected peak concurrent user count? (needed to finalize ECS task sizing and DB instance class) | Eng | — |
| 7 | Should recommendation history be shown to students beyond the 7-day window in the spec? | PM | — |

---

## 13. Out of Scope (v1)

- Full meal logging or calorie journal
- Wearable / fitness tracker integrations
- Multi-day meal plan generation
- LLM-based natural language recommendation explanations
- Per-student preference learning from feedback history
- Push notifications for meal period start

---

## 14. ML-Enhanced Recommendation (Post-v1)

This section describes an original ML algorithm to replace the fixed-weight heuristic scorer (Section 5.2) once the base system has accumulated sufficient feedback data. The heuristic scorer remains the fallback and is never removed — the ML layer sits on top of it.

### 14.1 Motivation

The heuristic scorer uses a single fixed weight vector for all students. In practice, two students with identical profiles may respond very differently to the same meal. A student labeling "Lentil Soup" thumbs-down while another labels it thumbs-up is signal the heuristic cannot capture. The goal is to learn, per student context, which scoring signals actually drive satisfaction — without requiring cross-student data sharing.

### 14.2 Algorithm: Profile-Adaptive Contextual Bandit (PACB)

The core insight is to treat the scoring weight vector from Section 5.2 as a **learnable parameter** rather than a constant, and to use a contextual bandit to tune it per student context. This preserves the explainability of the existing scoring function (weights still map to named signals) while making it adaptive.

#### Overview

```
At recommendation time:
  1. Encode student profile → feature vector x
  2. Assign x to nearest learned cluster c
  3. Look up learned weight vector θ_c for cluster c
     (fall back to heuristic weights if cluster has < 50 feedback samples)
  4. Run the existing scoring function (§5.2) using θ_c instead of fixed weights
  5. Return top-scored candidate

At feedback receipt:
  6. Record reward r ∈ {+1, 0, −1} for the recommended item
  7. Queue (x, θ_c, r) for nightly model update
```

#### Step 1 — Profile Feature Vector

Each student profile is encoded into a fixed-length numeric vector before clustering or model inference:

| Feature | Encoding |
|---|---|
| `health_goal` | One-hot (5 dims) |
| `activity_level` | Ordinal 1–4 |
| `conditions` | Binary flags (one per condition) |
| `nutritional_focus` | Binary flags (one per focus) |
| `BMI` | Continuous (`weight_kg / (height_cm/100)²`); standardized |
| `age` | Continuous; standardized |

Dietary identity and allergens are **not** included — those govern the hard filter, not the scoring preferences.

#### Step 2 — Profile Clustering (Offline, Nightly)

K-means clustering (k = 15, tuned empirically) groups students by profile similarity. The cluster assignment gives the model a shared learning signal across students with similar contexts, which accelerates convergence compared to fully per-student personalization.

```
clusters = KMeans(k=15).fit(all_profile_vectors)
# Saved to DB; Recommendation Service loads on startup
```

New students are assigned to the nearest centroid at inference time with no training required — this is the cold-start solution.

#### Step 3 — Per-Cluster Weight Learning (LinUCB)

For each cluster c, the model maintains a weight vector θ_c over the k scoring signals (protein, fiber, macro alignment, etc.). LinUCB (Linear Upper Confidence Bound) is used to learn these weights from feedback.

LinUCB update rule per cluster c after observing reward r for context x and weight choice θ_c:

```
A_c  ← A_c + x · xᵀ          # ridge regression matrix (initialized to identity)
b_c  ← b_c + r · x            # reward-weighted context accumulator
θ_c  ← A_c⁻¹ · b_c            # current best-estimate weight vector
α_c  ← θ_c + α · sqrt(xᵀ A_c⁻¹ x)  # UCB exploration bonus (α is exploration param)
```

In practice, the "context" x here is the cluster centroid (not the individual profile vector), which keeps the feature space low-dimensional and A_c invertible with modest data.

The exploration bonus α_c ensures that weight configurations with high uncertainty are tried periodically, preventing the model from getting stuck on a locally good but globally suboptimal weight set.

#### Step 4 — Reward Signal

| Event | Reward |
|---|---|
| Explicit thumbs-up | +1 |
| No feedback | 0 (neutral; item is still recorded) |
| Explicit thumbs-down | −1 |
| Student returns next day (implicit) | +0.3 bonus applied to previous day's rec |

The implicit retention signal is optional and gated behind a feature flag for the initial rollout — it requires care around attribution.

#### Step 5 — Fallback

If cluster c has fewer than 50 feedback samples, the Recommendation Service uses the heuristic weights from Section 5.2 unchanged. This threshold is configurable. The transition from heuristic to learned weights is seamless from the API's perspective — the scoring function is identical, only the weight vector changes.

### 14.3 Training Pipeline

```
Nightly batch job (03:00 local time, after menu ingestion):
  1. Read new rows from recommendation_history where feedback IS NOT NULL
     and created_at >= last_run_timestamp
  2. Join with student_profiles to reconstruct feature vectors x
  3. For each (x, feedback) pair:
       c = nearest_cluster(x)
       r = reward(feedback)
       update A_c, b_c
       recompute θ_c = A_c⁻¹ · b_c
  4. Serialize updated {θ_c, A_c, b_c} for all clusters to ml_model_weights table
  5. Log convergence metrics (per-cluster sample count, weight delta norm)
```

**No GPU required.** LinUCB is a closed-form update; the matrix inverse for k ≈ 10 signals and k = 15 clusters is trivial on any CPU.

### 14.4 Data Schema Additions

```sql
CREATE TABLE profile_clusters (
  cluster_id    SMALLINT PRIMARY KEY,
  centroid      JSONB NOT NULL,             -- serialized float array
  sample_count  INT NOT NULL DEFAULT 0,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ml_model_weights (
  cluster_id    SMALLINT PRIMARY KEY REFERENCES profile_clusters(cluster_id),
  theta         JSONB NOT NULL,             -- learned weight vector
  a_matrix      JSONB NOT NULL,             -- ridge regression matrix (for incremental updates)
  b_vector      JSONB NOT NULL,             -- reward accumulator
  feedback_count INT NOT NULL DEFAULT 0,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add cluster assignment to history for offline analysis
ALTER TABLE recommendation_history
  ADD COLUMN cluster_id   SMALLINT REFERENCES profile_clusters(cluster_id),
  ADD COLUMN weight_source TEXT NOT NULL DEFAULT 'heuristic'; -- 'heuristic' | 'ml'
```

### 14.5 Recommendation Service Changes

The Recommendation Service loads `ml_model_weights` at startup and refreshes every 15 minutes (polling the DB for `updated_at`). No restart required on model update — the scoring function itself is unchanged.

```
function getWeights(student):
  c = nearestCluster(encode(student.profile))
  weights = modelWeights[c]
  if weights.feedback_count < FEEDBACK_THRESHOLD:
    return HEURISTIC_WEIGHTS        # §5.2 defaults
  return weights.theta
```

### 14.6 Evaluation

Before promoting ML weights into production, each nightly training run evaluates the model on a held-out validation split (20% of feedback, stratified by cluster):

| Metric | Target |
|---|---|
| Mean reward on validation split | > heuristic baseline reward |
| Thumbs-up rate (ML-weighted recs) | > 75% (Beta SLO) |
| Weight vector stability (Δθ norm) | < 0.05 between consecutive runs (convergence check) |
| Allergen safety | 0 unsafe items (same hard filter, unaffected by ML layer) |

If the ML model underperforms the heuristic on the validation split for 3 consecutive nights, the pipeline automatically reverts `weight_source` to `'heuristic'` for all clusters and pages the engineering on-call.

### 14.7 Privacy Considerations

- The ML model learns per-cluster weights, not per-student weights. No individual student's data is stored in the model itself — only the aggregate A and b matrices per cluster.
- Feedback used for training is already collected in `recommendation_history` under the existing privacy policy.
- Cluster assignment (which centroid a student maps to) is ephemeral — computed at inference time, not stored permanently beyond the `recommendation_history` row.

### 14.8 Rollout Plan

| Phase | Trigger | Action |
|---|---|---|
| Shadow mode | ≥ 50 feedback samples in any cluster | Run ML scoring in parallel with heuristic; log both scores but serve heuristic result |
| A/B test | ≥ 200 samples per cluster | Route 20% of requests to ML weights; compare thumbs-up rates over 2 weeks |
| Full rollout | A/B winner confirmed | Flip `weight_source` to `'ml'` for qualifying clusters; heuristic fallback remains |
