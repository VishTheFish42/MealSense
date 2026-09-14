export type MealPeriod = 'breakfast' | 'lunch' | 'dinner' | 'all_day';
export type Sex = 'male' | 'female' | 'undisclosed';
export type ActivityLevel = 'sedentary' | 'light' | 'moderate' | 'very_active';
export type HealthGoal = 'lose_weight' | 'maintain' | 'gain_muscle' | 'energy' | 'wellness';
export type UserRole = 'student' | 'kitchen';
export type OrderStatus = 'placed' | 'preparing' | 'ready' | 'completed' | 'cancelled';

export interface StudentProfile {
  uid: string;
  email: string;
  displayName: string;
  role: UserRole;
  age?: number;
  sex?: Sex;
  heightCm?: number;
  weightKg?: number;
  activityLevel?: ActivityLevel;
  healthGoal?: HealthGoal;
  allergies: string[];
  dietaryIdentity: string[];
  conditions: string[];
  nutritionalFocus: string[];
  onboardingComplete: boolean;
  createdAt: string;
  // Kitchen accounts only (design-spec.md §2.3, tasks.md 4.5) — which
  // dining location this kitchen account is scoped to. Set manually
  // during provisioning (README-kitchen-accounts.md), never by the app.
  // Meaningless on a student doc; students don't have their own location.
  locationId?: string;
}

// Field names match the backend's actual JSON exactly (snake_case, same
// as schema.py::build_menu_item's canonical shape) — NOT camelCase. This
// interface previously declared camelCase names (mealPeriod, proteinG,
// availableUntil, ...) that never matched the real API response, so those
// fields silently read as `undefined` at runtime (fixed 2026-09-13,
// tasks.md 4.3's follow-up — see HomeScreen.tsx/CartScreen.tsx for where
// this actually surfaced).
export interface MenuItem {
  id: string;
  name: string;
  station: string;
  meal_period: MealPeriod;
  available_from?: string;
  available_until?: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  sodium_mg: number;
  sugar_g: number;
  allergens: string[];
  dietary_tags: string[];
  ingredients: string[];
  price: number;
  description: string;
  sold_out?: boolean;
}

export interface RecommendationResult {
  menuItem: MenuItem;
  score: number;
  reasoning: {
    primary: string;
    signals: string[];
  };
}

export interface RecommendationResponse {
  recommendation: RecommendationResult | null;
  alternatives: RecommendationResult[];
  meal_period: MealPeriod;
  reason?: string;
  // Present only when the backend could persist a history record for the
  // top pick (Firestore configured + the profile carried a uid) — that's
  // what thumbs-up/down feedback attaches to. Absent for alternatives;
  // feedback is scoped to the top pick only (see tasks.md's write-up).
  recommendation_id?: string;
}

export type FeedbackValue = 'thumbs_up' | 'thumbs_down';

export interface OrderItem {
  menuItemId: string;
  name: string;
  quantity: number;
  price: number;
}

export interface Order {
  id: string;
  studentId: string;
  items: OrderItem[];
  totalPrice: number;
  status: OrderStatus;
  placedAt: string;
  preparingAt?: string;
  readyAt?: string;
  completedAt?: string;
  paymentStatus: 'placeholder';
  notes?: string;
  // Set only when the order was placed straight from the top recommendation
  // card (never an alternative) — README §14's "order conversion rate"
  // metric, tasks.md 8.2. Absent, not null, when ordering anything else.
  recommendationId?: string;
  // Required, unlike recommendationId — design-spec.md §2.3 / tasks.md
  // 4.5. firestore.rules rejects order creation without this field. Every
  // order today gets DEFAULT_LOCATION_ID (src/constants/location.ts);
  // there's no per-location selection UI yet.
  locationId: string;
}

// Navigation param lists
export type AuthStackParamList = {
  Login: undefined;
  Register: undefined;
};

export type OnboardingStackParamList = {
  Onboarding: undefined;
};

export type HomeStackParamList = {
  Home: undefined;
  Cart: { item: MenuItem; recommendationId?: string };
  Checkout: { items: OrderItem[]; totalPrice: number; recommendationId?: string };
  OrderStatus: { orderId: string };
};

export type MainTabParamList = {
  HomeStack: undefined;
  Orders: undefined;
  ProfileStack: undefined;
};

export type ProfileStackParamList = {
  ProfileMain: undefined;
  EditProfile: undefined;
};

export type KitchenStackParamList = {
  Dashboard: undefined;
  AddMenuItem: undefined;
  TodaysMenu: undefined;
  AdminAnalytics: undefined;
};
