import React from 'react';
import { ActivityIndicator, View } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { useAuth } from '../contexts/AuthContext';
import AuthNavigator from './AuthNavigator';
import OnboardingNavigator from './OnboardingNavigator';
import MainNavigator from './MainNavigator';
import KitchenNavigator from './KitchenNavigator';
import { colors } from '../constants/colors';

export default function RootNavigator() {
  const { user, profile, loading } = useAuth();

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background }}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  const renderNavigator = () => {
    if (!user) return <AuthNavigator />;
    if (profile?.role === 'kitchen') return <KitchenNavigator />;
    if (!profile?.onboardingComplete) return <OnboardingNavigator />;
    return <MainNavigator />;
  };

  return (
    <NavigationContainer>
      {renderNavigator()}
    </NavigationContainer>
  );
}
