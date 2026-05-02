import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import { MainTabParamList, HomeStackParamList, ProfileStackParamList } from '../types';
import { colors } from '../constants/colors';

import HomeScreen from '../screens/student/HomeScreen';
import CartScreen from '../screens/student/CartScreen';
import CheckoutScreen from '../screens/student/CheckoutScreen';
import OrderStatusScreen from '../screens/student/OrderStatusScreen';
import OrderHistoryScreen from '../screens/student/OrderHistoryScreen';
import ProfileScreen from '../screens/student/ProfileScreen';
import EditPreferencesScreen from '../screens/student/EditPreferencesScreen';

const Tab = createBottomTabNavigator<MainTabParamList>();
const HomeStack = createNativeStackNavigator<HomeStackParamList>();
const ProfileStack = createNativeStackNavigator<ProfileStackParamList>();

function HomeStackNavigator() {
  return (
    <HomeStack.Navigator screenOptions={{ headerShown: false }}>
      <HomeStack.Screen name="Home" component={HomeScreen} />
      <HomeStack.Screen name="Cart" component={CartScreen} />
      <HomeStack.Screen name="Checkout" component={CheckoutScreen} />
      <HomeStack.Screen name="OrderStatus" component={OrderStatusScreen} />
    </HomeStack.Navigator>
  );
}

function ProfileStackNavigator() {
  return (
    <ProfileStack.Navigator screenOptions={{ headerShown: false }}>
      <ProfileStack.Screen name="ProfileMain" component={ProfileScreen} />
      <ProfileStack.Screen name="EditProfile" component={EditPreferencesScreen} />
    </ProfileStack.Navigator>
  );
}

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

const TAB_ICONS: Record<keyof MainTabParamList, IoniconName> = {
  HomeStack: 'home',
  Orders: 'receipt-outline',
  ProfileStack: 'person-outline',
};

const TAB_LABELS: Record<keyof MainTabParamList, string> = {
  HomeStack: 'Home',
  Orders: 'Orders',
  ProfileStack: 'Profile',
};

export default function MainNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textSecondary,
        tabBarStyle: {
          backgroundColor: colors.card,
          borderTopColor: colors.border,
        },
        tabBarIcon: ({ color, size }) => (
          <Ionicons name={TAB_ICONS[route.name as keyof MainTabParamList]} size={size} color={color} />
        ),
        tabBarLabel: TAB_LABELS[route.name as keyof MainTabParamList],
      })}
    >
      <Tab.Screen name="HomeStack" component={HomeStackNavigator} />
      <Tab.Screen name="Orders" component={OrderHistoryScreen} />
      <Tab.Screen name="ProfileStack" component={ProfileStackNavigator} />
    </Tab.Navigator>
  );
}
