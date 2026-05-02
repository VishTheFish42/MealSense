# Food Recommendation & Diet Planning App — Product Specification

**Owner:** Vishwa Prakash  
**Status:** Draft  
**Date:** 2026-04-26

---

## 1. Overview

A mobile/web app that gives university students a single, personalized food recommendation for their current meal based on what is actually available in their school cafeteria right now. Students set up a health profile once; the app handles the rest each time they walk into the dining hall.

---

## 2. Background

University students frequently make poor nutritional choices — not from lack of intent, but from decision fatigue, limited time, and no easy way to map their personal health needs to a changing cafeteria menu. Existing nutrition apps require manual food logging and don't know what's on the line today.

---

## 3. Goals

- A student can set up their health profile in under 3 minutes.
- At any meal time, the app surfaces **one top recommendation** from today's available cafeteria items in under 5 seconds.
- Recommendations respect hard constraints (allergies, intolerances) with zero false negatives.
- Students report feeling like the recommendation was made for them (target: >75% "relevant" rating on post-meal feedback).
- Students can place food orders directly through the app, replacing the cafeteria's native point-of-sale system with a recommendation-first ordering experience.
- Dining staff can view and manage incoming orders in real time through a kitchen dashboard.

---

## 4. Non-Goals

- Full meal logging or calorie tracking journal.
- Recommendations for food outside the campus cafeteria.
- Grocery shopping lists or home cooking suggestions.
- Multi-day meal plan generation (v1).
- Integration with wearables or fitness trackers (v1).
- Live payment processing (v1 includes a payment UI with placeholder card data; no cards are charged).

---

## 5. Users

**Primary:** University students who eat at campus dining facilities.  
**Secondary:** Campus dining administrators who manage menu and availability data.

---

## 6. User Profiles

Students configure their profile on first launch and can update it at any time.

### 6.1 Body Stats

| Field | Type | Notes |
|---|---|---|
| Age | Integer | Years |
| Sex | Enum | Male / Female / Prefer not to say |
| Height | Float | cm or ft/in (user's choice) |
| Weight | Float | kg or lbs (user's choice) |
| Activity level | Enum | Sedentary / Lightly active / Moderately active / Very active |
| Health goal | Enum | Lose weight / Maintain / Gain muscle / Improve energy / General wellness |

### 6.2 Dietary Constraints (Hard Filters)

These are **never violated** in a recommendation.

- Allergies (multi-select): Nuts, Dairy, Gluten, Eggs, Soy, Shellfish, Fish, Sesame, Other (free text)
- Dietary identity: Vegetarian, Vegan, Halal, Kosher, None

### 6.3 Bodily Traits & Health Conditions (Soft Signals)

These influence scoring but do not hard-block items.

- Conditions (multi-select): Diabetes / pre-diabetes, High blood pressure, High cholesterol, IBS / digestive sensitivity, Lactose intolerance, Iron deficiency, Other (free text)
- Nutritional focus (multi-select): High protein, Low carb, Low sodium, High fiber, Low sugar

---

## 7. Cafeteria Menu Data

The app is only useful if cafeteria data is current and accurate.

### 7.1 Menu Item Schema

```
MenuItem {
  id: string
  name: string
  station: string              // e.g. "Grill", "Salad Bar", "Hot Entrees"
  meal_period: Enum            // Breakfast | Lunch | Dinner | All-day
  available_from: Time         // e.g. 11:00
  available_until: Time        // e.g. 14:00
  date: Date
  nutrition: {
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    sodium_mg: float
    sugar_g: float
  }
  allergens: string[]          // matches allergy list from § 6.2
  dietary_tags: string[]       // "vegan", "vegetarian", "halal", "kosher"
  ingredients: string[]        // for fuzzy allergen matching
}
```

### 7.2 Data Sources (in priority order)

1. **Direct API integration** with dining vendor (e.g. Nutrislice, Cbord) — preferred.
2. **Admin-managed CSV/JSON upload** — fallback for schools without a vendor API.
3. Manual entry by dining staff via admin dashboard.

### 7.3 Availability

An item is considered available if the current time falls within `[available_from, available_until]` on today's date. Items with no explicit time window default to their `meal_period` hours.

---

## 8. Recommendation Engine

### 8.1 Step 1 — Hard Filter

Remove any cafeteria item that:
- Contains an allergen the student has flagged.
- Does not match the student's dietary identity (e.g., non-vegan item for a vegan student).
- Is not currently available (per § 7.3).

### 8.2 Step 2 — Score Remaining Items

Each remaining item receives a score (0–100) based on:

| Signal | Weight |
|---|---|
| Alignment with health goal (calorie/macro target) | 35% |
| Protein content (favored for most goals) | 20% |
| Fiber content | 15% |
| Low sugar / low sodium (based on conditions) | 15% |
| Variety (deprioritize items recommended in the last 3 days) | 15% |

Weights are adjusted if the student has active health conditions (e.g., diabetic students get higher weight on low-sugar signal).

> **In development:** The fixed weights above are the current v1 implementation. An ML-based adaptive scoring system (Profile-Adaptive Contextual Bandit) is actively in development as a post-v1 enhancement. It learns per-student-context weight adjustments from thumbs-up/down feedback while keeping the same scoring signals and hard-filter guarantees. See the [technical design doc](design-spec.md#14-ml-enhanced-recommendation-post-v1) for details.

### 8.3 Step 3 — Output

Return the **single highest-scoring item** as the top recommendation. Expose the top 3 as secondary options (shown on "show more").

### 8.4 Daily Caloric Target

Calculated via Mifflin-St Jeor BMR × activity multiplier, apportioned by meal:

| Meal | Share of daily calories |
|---|---|
| Breakfast | 25% |
| Lunch | 35% |
| Dinner | 35% |
| Snack | 5% |

---

## 9. Key Screens

### 9.1 Onboarding (first launch)
- Step-by-step profile setup: body stats → allergies → dietary identity → conditions → goal.
- Estimated time: ~2–3 minutes.
- Skip allowed; student can complete profile later.

### 9.2 Home / Recommendation View
- Detects current meal period automatically from time of day.
- Shows: recommended item name, station location, macro summary (calories / protein / carbs / fat).
- CTA: "Why this?" (explains reasoning) | "Show other options" (top 3 list).
- If no items pass the hard filter: show a clear message ("Nothing available right now matches your restrictions") rather than a bad recommendation.

### 9.3 Item Detail
- Full nutrition facts.
- Allergen and dietary tag badges.
- Station and availability window.

### 9.4 Profile
- Edit any profile field at any time.
- View recommendation history (last 7 days).

### 9.5 Admin Dashboard (dining staff)
- Upload or sync today's menu.
- Mark items as sold out or unavailable in real time.
- View aggregate anonymized data: most recommended items, common dietary constraints on campus.

### 9.6 Cart
- Shows the item(s) selected for order (typically the recommended item).
- Quantity control (+ / −).
- Item price and order total.
- "Proceed to Checkout" CTA.

### 9.7 Checkout
- Pickup notes field.
- Payment section with placeholder card details pre-filled (card number, expiry, CVV — no real charge in v1).
- "Place Order" CTA — writes order to Firestore; does not process payment.

### 9.8 Order Status
- Tracks the placed order through three stages: **Placed → Preparing → Ready for Pickup**.
- Timer-based status transitions in v1 (30 s to Preparing, 90 s to Ready for demo purposes).
- Real-time updates via Firestore subscription.
- "Order again" shortcut when complete.

### 9.9 Order History
- Chronological list of past orders.
- Shows: item names, total price, date, final status.

### 9.10 Kitchen Dashboard (staff)
- Live incoming orders queue updated in real time via Firestore.
- Each card shows: item(s), time since placed, current status.
- Timer-based auto-progression mirrors the student-side status transitions.

---

## 10. Technical Architecture (High-Level)

```
Mobile App (React Native + Expo Go)
      │
      ▼
API Gateway (Vercel)
      │
      ├── Auth Service (Firebase Auth + University SSO)
      ├── Profile Service (stores/retrieves student profiles)
      ├── Menu Service (ingests, stores, serves cafeteria data)
      └── Recommendation Service (runs scoring engine per request)
            │
            └── Reads from: Profile Service + Menu Service
                        │
                        ▼
               Firebase Firestore
```

- **Frontend:** React Native + Expo Go (TypeScript). Targets iOS and Android via a single codebase.
- **Backend:** Python + FastAPI, deployed on Vercel serverless functions.
- **Database:** Firebase Firestore for student profiles, menu data, and recommendation history.
- **Auth:** Firebase Authentication + University SSO (OAuth 2.0 / SAML). Firebase Auth handles token lifecycle; SSO provides the identity.
- **Data storage:** Student profiles encrypted at rest in Firestore. No sale or sharing of health data.

---

## 11. Privacy & Safety

- Health data (allergies, conditions) is treated as sensitive. Stored encrypted, never shared with third parties.
- Allergen filtering is a hard constraint with **zero tolerance for false negatives**. When allergen data for a menu item is incomplete, the item is excluded from recommendations.
- The app is a recommendation tool, not medical advice. A disclaimer appears on onboarding and in the "Why this?" explanation.
- Students can delete their profile and all associated data at any time.

---

## 12. Open Questions

| # | Question | Owner | Due |
|---|---|---|---|
| 1 | Which cafeteria data vendor/API does the target school use? | PM | — |
| 2 | Should the app support multiple campus dining locations? (v1 scope?) | PM | — |
| 3 | How do we handle items where the dining vendor's allergen data is incomplete? Default-exclude or flag-and-show? | Eng + Legal | — |
| 4 | Is university SSO required, or do we also need email/password fallback? | PM | — |
| 5 | What platform first — iOS, Android, or web? | PM + Eng | — |

---

## 13. Alternatives Considered

**Show a full ranked list instead of one top pick.**  
Rejected for v1: decision fatigue is a core problem. One confident recommendation is the differentiator. A ranked list is available via "show other options."

**Use AI/LLM for recommendations instead of a scoring function.**  
Deferred: a rule-based scoring function is auditable and explainable ("Why this?" is easy to answer). LLM integration can be layered in later for natural language interaction.

**Allow students to rate and learn preferences over time.**  
~~Deferred to v2.~~ **In development.** Thumbs-up/down feedback (§ 9.2) is already collected in v1. The ML scoring enhancement (§ 8.2) uses this signal to adapt weight vectors per student-context cluster. Per-student personalization is gated behind a shadow-mode → A/B rollout to ensure it outperforms the heuristic baseline before full exposure.

---

## 14. Success Metrics

| Metric | Target |
|---|---|
| Profile completion rate | > 70% of new users |
| Recommendation relevance (post-meal thumbs up) | > 75% |
| Allergen-safe recommendation rate | 100% |
| Time to recommendation from app open | < 5 seconds |
| Weekly active users (after 30 days) | > 40% of registered users |
| ML model thumbs-up rate vs. heuristic baseline (A/B) | ML ≥ heuristic before full rollout |
| Feedback submission rate | > 30% of recommendations receive a thumbs-up or thumbs-down |
| Order conversion rate (recommendation → order placed) | > 60% |
| Order status accuracy (timer-based transition vs. target) | Within ±30 s of target |
