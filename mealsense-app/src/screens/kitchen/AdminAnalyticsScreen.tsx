import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, SafeAreaView, ActivityIndicator,
  TouchableOpacity, Alert, RefreshControl,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useAuth } from '../../contexts/AuthContext';
import { colors } from '../../constants/colors';
import { API_BASE_URL } from '../../config/api';
import { KitchenStackParamList } from '../../types';

type Props = { navigation: NativeStackNavigationProp<KitchenStackParamList, 'AdminAnalytics'> };

// Matches services/analytics_aggregation.py's response shape exactly
// (snake_case) — see types/index.ts's MenuItem comment for why this
// screen doesn't reuse a camelCase type for raw API responses.
interface MostRecommendedItem {
  menu_item_id: string;
  name: string;
  count: number;
}

interface ConstraintRow {
  value: string;
  count: number;
}

interface DietaryConstraints {
  allergies: ConstraintRow[];
  dietary_identity: ConstraintRow[];
  conditions: ConstraintRow[];
  nutritional_focus: ConstraintRow[];
}

interface AnalyticsResponse {
  most_recommended_items: MostRecommendedItem[];
  dietary_constraints: DietaryConstraints;
}

const CONSTRAINT_SECTIONS: { key: keyof DietaryConstraints; label: string }[] = [
  { key: 'allergies', label: 'Allergies' },
  { key: 'dietary_identity', label: 'Dietary Identity' },
  { key: 'conditions', label: 'Health Conditions' },
  { key: 'nutritional_focus', label: 'Nutritional Focus' },
];

function labelize(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function BarRow({ label, count, maxCount }: { label: string; count: number; maxCount: number }) {
  const pct = maxCount > 0 ? Math.max((count / maxCount) * 100, 6) : 0;
  return (
    <View style={styles.barRow}>
      <View style={styles.barRowHeader}>
        <Text style={styles.barLabel}>{label}</Text>
        <Text style={styles.barCount}>{count}</Text>
      </View>
      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width: `${pct}%` }]} />
      </View>
    </View>
  );
}

export default function AdminAnalyticsScreen({ navigation }: Props) {
  const { user } = useAuth();
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAnalytics = useCallback(async () => {
    if (!user) return;
    try {
      const idToken = await user.getIdToken();
      const resp = await fetch(`${API_BASE_URL}/admin/analytics`, {
        headers: { Authorization: `Bearer ${idToken}` },
      });
      if (!resp.ok) throw new Error('API error');
      setData(await resp.json());
    } catch {
      Alert.alert('Could not load analytics', 'Make sure the MealSense API server is running.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user]);

  useEffect(() => { fetchAnalytics(); }, [fetchAnalytics]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchAnalytics();
  };

  const maxItemCount = data?.most_recommended_items.length
    ? Math.max(...data.most_recommended_items.map((i) => i.count))
    : 0;

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Campus Analytics</Text>
        <View style={styles.backBtn} />
      </View>

      {loading ? (
        <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 60 }} />
      ) : (
        <ScrollView
          contentContainerStyle={styles.content}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
        >
          <Text style={styles.disclaimer}>
            Anonymized and aggregated only — no student identities appear anywhere below.
          </Text>

          <Text style={styles.sectionHeader}>Most Recommended Items</Text>
          <View style={styles.card}>
            {!data?.most_recommended_items.length ? (
              <Text style={styles.emptyText}>No recommendations served yet.</Text>
            ) : (
              data.most_recommended_items.map((item) => (
                <BarRow key={item.menu_item_id} label={item.name} count={item.count} maxCount={maxItemCount} />
              ))
            )}
          </View>

          {CONSTRAINT_SECTIONS.map(({ key, label }) => {
            const rows = data?.dietary_constraints[key] ?? [];
            const maxCount = rows.length ? Math.max(...rows.map((r) => r.count)) : 0;
            return (
              <View key={key}>
                <Text style={styles.sectionHeader}>{label} on Campus</Text>
                <View style={styles.card}>
                  {rows.length === 0 ? (
                    <Text style={styles.emptyText}>No data yet.</Text>
                  ) : (
                    rows.map((row) => (
                      <BarRow key={row.value} label={labelize(row.value)} count={row.count} maxCount={maxCount} />
                    ))
                  )}
                </View>
              </View>
            );
          })}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.card },
  backBtn: { width: 70 },
  backText: { color: colors.primary, fontSize: 16, fontWeight: '600' },
  headerTitle: { flex: 1, textAlign: 'center', fontSize: 17, fontWeight: '700', color: colors.text },
  content: { padding: 20, paddingBottom: 48, gap: 8 },
  disclaimer: { fontSize: 12, color: colors.textLight, textAlign: 'center', marginBottom: 12, lineHeight: 17 },
  sectionHeader: { fontSize: 13, fontWeight: '700', color: colors.textLight, letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 12, marginBottom: 4, marginLeft: 4 },
  card: { backgroundColor: colors.card, borderRadius: 16, padding: 18, gap: 12 },
  emptyText: { fontSize: 14, color: colors.textSecondary },
  barRow: { gap: 6 },
  barRowHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  barLabel: { fontSize: 14, color: colors.text, fontWeight: '600', flex: 1, marginRight: 8 },
  barCount: { fontSize: 14, color: colors.textSecondary, fontWeight: '700' },
  barTrack: { height: 8, borderRadius: 4, backgroundColor: colors.background, overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: 4, backgroundColor: colors.primary },
});
