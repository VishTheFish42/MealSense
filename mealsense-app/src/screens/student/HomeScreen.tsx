import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, SafeAreaView, Alert,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useAuth } from '../../contexts/AuthContext';
import { colors } from '../../constants/colors';
import { API_BASE_URL } from '../../config/api';
import { HomeStackParamList, MealPeriod, RecommendationResponse, RecommendationResult } from '../../types';

type Props = { navigation: NativeStackNavigationProp<HomeStackParamList, 'Home'> };

function getMealPeriod(): MealPeriod {
  const hour = new Date().getHours();
  if (hour >= 6 && hour < 11) return 'breakfast';
  if (hour >= 11 && hour < 16) return 'lunch';
  if (hour >= 16 && hour < 22) return 'dinner';
  return 'breakfast';
}

function mealPeriodLabel(mp: MealPeriod) {
  return mp === 'all_day' ? 'All Day' : mp.charAt(0).toUpperCase() + mp.slice(1);
}

function greeting(name: string): string {
  const hour = new Date().getHours();
  if (hour < 12) return `Good morning, ${name}`;
  if (hour < 18) return `Good afternoon, ${name}`;
  return `Good evening, ${name}`;
}

function NutritionPill({ label, value, unit }: { label: string; value: number; unit: string }) {
  return (
    <View style={styles.pill}>
      <Text style={styles.pillValue}>{Math.round(value)}</Text>
      <Text style={styles.pillUnit}>{unit}</Text>
      <Text style={styles.pillLabel}>{label}</Text>
    </View>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 80 ? colors.success : score >= 60 ? colors.warning : colors.error;
  return (
    <View style={[styles.scoreBadge, { backgroundColor: color + '22', borderColor: color }]}>
      <Text style={[styles.scoreText, { color }]}>{Math.round(score)}% match</Text>
    </View>
  );
}

export default function HomeScreen({ navigation }: Props) {
  const { profile } = useAuth();
  const [data, setData] = useState<RecommendationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showAlts, setShowAlts] = useState(false);
  const mealPeriod = getMealPeriod();

  const fetchRecommendation = useCallback(async () => {
    if (!profile) return;
    try {
      const resp = await fetch(`${API_BASE_URL}/recommendation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile, meal_period: mealPeriod, recent_menu_item_ids: [] }),
      });
      if (!resp.ok) throw new Error('API error');
      setData(await resp.json());
    } catch {
      Alert.alert('Could not load recommendation', 'Make sure the MealSense API server is running on your Mac.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [profile, mealPeriod]);

  useEffect(() => { fetchRecommendation(); }, [fetchRecommendation]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchRecommendation();
  };

  const handleOrder = (result: RecommendationResult) => {
    navigation.navigate('Cart', { item: result.menuItem });
  };

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greetingText}>{greeting(profile?.displayName?.split(' ')[0] ?? 'there')}</Text>
            <View style={styles.mealBadge}>
              <Text style={styles.mealBadgeText}>{mealPeriodLabel(mealPeriod)} menu</Text>
            </View>
          </View>
          <Text style={styles.logoMark}>🥗</Text>
        </View>

        {loading && (
          <View style={styles.loadingBox}>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={styles.loadingText}>Finding your best match…</Text>
          </View>
        )}

        {!loading && !data?.recommendation && (
          <View style={styles.emptyBox}>
            <Text style={styles.emptyIcon}>🚫</Text>
            <Text style={styles.emptyTitle}>No matching items right now</Text>
            <Text style={styles.emptySubtitle}>
              Nothing available for this meal period matches your dietary restrictions.
              Check back at the next meal period or update your profile.
            </Text>
          </View>
        )}

        {!loading && data?.recommendation && (
          <>
            <Text style={styles.sectionLabel}>TODAY'S TOP PICK</Text>
            <RecommendationCard result={data.recommendation} onOrder={handleOrder} />

            {data.alternatives.length > 0 && (
              <>
                <TouchableOpacity style={styles.altToggle} onPress={() => setShowAlts(!showAlts)}>
                  <Text style={styles.altToggleText}>
                    {showAlts ? '▲ Hide other options' : `▼ Show ${data.alternatives.length} other options`}
                  </Text>
                </TouchableOpacity>

                {showAlts && data.alternatives.map((alt) => (
                  <RecommendationCard key={alt.menuItem.id} result={alt} onOrder={handleOrder} compact />
                ))}
              </>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function RecommendationCard({
  result, onOrder, compact = false,
}: {
  result: RecommendationResult;
  onOrder: (r: RecommendationResult) => void;
  compact?: boolean;
}) {
  const { menuItem: item, score, reasoning } = result;
  const [showWhy, setShowWhy] = useState(false);

  return (
    <View style={[styles.card, compact && styles.cardCompact]}>
      <View style={styles.cardHeader}>
        <View style={styles.cardTitleRow}>
          <Text style={[styles.itemName, compact && styles.itemNameCompact]}>{item.name}</Text>
          <ScoreBadge score={score} />
        </View>
        <Text style={styles.stationText}>{item.station} · {item.availableUntil ? `Until ${item.availableUntil}` : ''}</Text>
      </View>

      {!compact && (
        <>
          <View style={styles.nutritionRow}>
            <NutritionPill label="cal" value={item.calories} unit="" />
            <NutritionPill label="protein" value={item.proteinG} unit="g" />
            <NutritionPill label="carbs" value={item.carbsG} unit="g" />
            <NutritionPill label="fat" value={item.fatG} unit="g" />
          </View>

          <TouchableOpacity onPress={() => setShowWhy(!showWhy)} style={styles.whyBtn}>
            <Text style={styles.whyBtnText}>{showWhy ? '▲ Hide reasoning' : '▼ Why this?'}</Text>
          </TouchableOpacity>

          {showWhy && (
            <View style={styles.reasoningBox}>
              <Text style={styles.reasoningPrimary}>{reasoning.primary}</Text>
              <View style={styles.signalRow}>
                {reasoning.signals.map((s) => (
                  <View key={s} style={styles.signalBadge}>
                    <Text style={styles.signalText}>{s.replace(/_/g, ' ')}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}
        </>
      )}

      <View style={styles.cardFooter}>
        <Text style={styles.priceText}>${item.price.toFixed(2)}</Text>
        <TouchableOpacity style={styles.orderBtn} onPress={() => onOrder(result)}>
          <Text style={styles.orderBtnText}>Order This</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  container: { padding: 20, paddingBottom: 40 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 },
  greetingText: { fontSize: 22, fontWeight: '800', color: colors.text },
  logoMark: { fontSize: 36 },
  mealBadge: { marginTop: 6, backgroundColor: colors.primaryLight + '30', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4, alignSelf: 'flex-start' },
  mealBadgeText: { fontSize: 13, fontWeight: '600', color: colors.primary },
  sectionLabel: { fontSize: 12, fontWeight: '700', color: colors.textLight, letterSpacing: 1, marginBottom: 12 },
  loadingBox: { alignItems: 'center', paddingVertical: 60, gap: 16 },
  loadingText: { color: colors.textSecondary, fontSize: 15 },
  emptyBox: { alignItems: 'center', paddingVertical: 60, paddingHorizontal: 24 },
  emptyIcon: { fontSize: 48, marginBottom: 16 },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: colors.text, textAlign: 'center', marginBottom: 10 },
  emptySubtitle: { fontSize: 15, color: colors.textSecondary, textAlign: 'center', lineHeight: 22 },
  card: { backgroundColor: colors.card, borderRadius: 18, padding: 20, marginBottom: 16, shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 12, shadowOffset: { width: 0, height: 4 }, elevation: 3 },
  cardCompact: { padding: 16 },
  cardHeader: { marginBottom: 12 },
  cardTitleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 },
  itemName: { fontSize: 20, fontWeight: '800', color: colors.text, flex: 1 },
  itemNameCompact: { fontSize: 17 },
  stationText: { fontSize: 13, color: colors.textSecondary, marginTop: 4 },
  scoreBadge: { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1 },
  scoreText: { fontSize: 13, fontWeight: '700' },
  nutritionRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 16 },
  pill: { alignItems: 'center', flex: 1 },
  pillValue: { fontSize: 18, fontWeight: '800', color: colors.text },
  pillUnit: { fontSize: 12, color: colors.textSecondary },
  pillLabel: { fontSize: 11, color: colors.textLight, marginTop: 2 },
  whyBtn: { paddingVertical: 8 },
  whyBtnText: { color: colors.primary, fontSize: 14, fontWeight: '600' },
  reasoningBox: { backgroundColor: colors.background, borderRadius: 10, padding: 14, marginBottom: 12 },
  reasoningPrimary: { fontSize: 14, color: colors.text, lineHeight: 20, marginBottom: 10 },
  signalRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  signalBadge: { backgroundColor: colors.primaryLight + '30', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  signalText: { fontSize: 12, color: colors.primary, fontWeight: '600' },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 },
  priceText: { fontSize: 20, fontWeight: '800', color: colors.text },
  orderBtn: { backgroundColor: colors.accent, borderRadius: 10, paddingHorizontal: 20, paddingVertical: 12 },
  orderBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  altToggle: { paddingVertical: 12, alignItems: 'center' },
  altToggleText: { color: colors.primary, fontWeight: '600', fontSize: 14 },
});
