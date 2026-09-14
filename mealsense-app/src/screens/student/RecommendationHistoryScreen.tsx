import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, FlatList, SafeAreaView, ActivityIndicator,
  TouchableOpacity, Alert, RefreshControl,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useAuth } from '../../contexts/AuthContext';
import { colors } from '../../constants/colors';
import { API_BASE_URL } from '../../config/api';
import { ProfileStackParamList } from '../../types';

type Props = { navigation: NativeStackNavigationProp<ProfileStackParamList, 'RecommendationHistory'> };

// Matches services/recommendation_history.py's stored shape exactly
// (snake_case/camelCase mix as actually written by write_recommendation)
// — not a type this screen shares with anything else, since nothing
// else in the app reads this collection.
interface HistoryEntry {
  id: string;
  menuItemId: string;
  menuItemName: string;
  score: number;
  mealPeriod: string;
  recommendedAt: string;
  feedback: 'thumbs_up' | 'thumbs_down' | null;
}

function mealPeriodLabel(mp: string): string {
  return mp === 'all_day' ? 'All Day' : mp.charAt(0).toUpperCase() + mp.slice(1);
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return '—';
  }
}

function FeedbackBadge({ feedback }: { feedback: HistoryEntry['feedback'] }) {
  if (!feedback) return null;
  const isUp = feedback === 'thumbs_up';
  return (
    <View style={[styles.feedbackBadge, { backgroundColor: (isUp ? colors.success : colors.error) + '22' }]}>
      <Text style={styles.feedbackBadgeText}>{isUp ? '👍' : '👎'}</Text>
    </View>
  );
}

export default function RecommendationHistoryScreen({ navigation }: Props) {
  const { user } = useAuth();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchHistory = useCallback(async () => {
    if (!user) return;
    try {
      const resp = await fetch(
        `${API_BASE_URL}/recommendation/history?student_id=${user.uid}&days=7`,
      );
      if (!resp.ok) throw new Error('API error');
      const body = await resp.json();
      setHistory(body.history ?? []);
    } catch {
      Alert.alert('Could not load history', 'Make sure the MealSense API server is running.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user]);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchHistory();
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Recommendation History</Text>
        <View style={styles.backBtn} />
      </View>

      {loading ? (
        <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 60 }} />
      ) : history.length === 0 ? (
        <View style={styles.emptyBox}>
          <Text style={styles.emptyIcon}>🥗</Text>
          <Text style={styles.emptyTitle}>No recommendations yet</Text>
          <Text style={styles.emptySubtitle}>
            Recommendations from the last 7 days will show up here once you've opened the app at a meal time.
          </Text>
        </View>
      ) : (
        <FlatList
          data={history}
          keyExtractor={(e) => e.id}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.itemName}>{item.menuItemName}</Text>
                <FeedbackBadge feedback={item.feedback} />
              </View>
              <Text style={styles.metaText}>
                {mealPeriodLabel(item.mealPeriod)} · {formatDate(item.recommendedAt)} · {Math.round(item.score)}% match
              </Text>
            </View>
          )}
        />
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
  list: { padding: 16, gap: 10 },
  emptyBox: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32 },
  emptyIcon: { fontSize: 48, marginBottom: 12 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: colors.text, textAlign: 'center', marginBottom: 6 },
  emptySubtitle: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 },
  card: { backgroundColor: colors.card, borderRadius: 14, padding: 16, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 6, shadowOffset: { width: 0, height: 2 }, elevation: 1 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  itemName: { fontSize: 16, fontWeight: '700', color: colors.text, flex: 1, marginRight: 8 },
  feedbackBadge: { borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4 },
  feedbackBadgeText: { fontSize: 14 },
  metaText: { fontSize: 13, color: colors.textSecondary, marginTop: 4 },
});
