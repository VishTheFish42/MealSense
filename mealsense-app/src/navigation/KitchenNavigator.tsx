import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import KitchenDashboardScreen from '../screens/kitchen/KitchenDashboardScreen';
import AddMenuItemScreen from '../screens/kitchen/AddMenuItemScreen';
import { KitchenStackParamList } from '../types';

const Stack = createNativeStackNavigator<KitchenStackParamList>();

export default function KitchenNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Dashboard" component={KitchenDashboardScreen} />
      <Stack.Screen name="AddMenuItem" component={AddMenuItemScreen} />
    </Stack.Navigator>
  );
}
