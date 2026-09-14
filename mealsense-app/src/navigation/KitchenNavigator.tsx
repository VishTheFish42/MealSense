import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import KitchenDashboardScreen from '../screens/kitchen/KitchenDashboardScreen';
import AddMenuItemScreen from '../screens/kitchen/AddMenuItemScreen';
import TodaysMenuScreen from '../screens/kitchen/TodaysMenuScreen';
import AdminAnalyticsScreen from '../screens/kitchen/AdminAnalyticsScreen';
import { KitchenStackParamList } from '../types';

const Stack = createNativeStackNavigator<KitchenStackParamList>();

export default function KitchenNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Dashboard" component={KitchenDashboardScreen} />
      <Stack.Screen name="AddMenuItem" component={AddMenuItemScreen} />
      <Stack.Screen name="TodaysMenu" component={TodaysMenuScreen} />
      <Stack.Screen name="AdminAnalytics" component={AdminAnalyticsScreen} />
    </Stack.Navigator>
  );
}
