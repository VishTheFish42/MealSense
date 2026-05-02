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
}

export interface MenuItem {
  id: string;
  name: string;
  station: string;
  mealPeriod: MealPeriod;
  availableFrom?: string;
  availableUntil?: string;
  calories: number;
  proteinG: number;
  carbsG: number;
  fatG: number;
  fiberG: number;
  sodiumMg: number;
  sugarG: number;
  allergens: string[];
  dietaryTags: string[];
  ingredients: string[];
  price: number;
  description: string;
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
  mealPeriod: MealPeriod;
  reason?: string;
}

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
  Cart: { item: MenuItem };
  Checkout: { items: OrderItem[]; totalPrice: number };
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
