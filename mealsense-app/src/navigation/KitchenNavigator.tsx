import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import KitchenDashboardScreen from '../screens/kitchen/KitchenDashboardScreen';

type KitchenStackParamList = { Dashboard: undefined };
const Stack = createNativeStackNavigator<KitchenStackParamList>();

export default function KitchenNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Dashboard" component={KitchenDashboardScreen} />
    </Stack.Navigator>
  );
}
