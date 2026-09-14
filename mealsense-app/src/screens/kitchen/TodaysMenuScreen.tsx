import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, FlatList, SafeAreaView, ActivityIndicator,
  TouchableOpacity, Switch, Alert, RefreshControl,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useAuth } from '../../contexts/AuthContext';
import { colors } from '../../constants/colors';
import { API_BASE_URL } from '../../config/api';
import { KitchenStackParamList, MenuItem } from '../../types';

type Props = { navigation: NativeStackNavigationProp<KitchenStackParamList, 'TodaysMenu'> };

function mealPeriodLabel(mp: string) {
  return mp === 'all_day' ? 'All Day' : mp.charAt(0).toUpperCase() + mp.slice(1);
}

export default function TodaysMenuScreen({ navigation }: Props) {
  const { user } = useAuth();
  const [items, setItems] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());

  const fetchMenu = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE_URL}/menu`);
      if (!resp.ok) throw new Error('API error');
      const body = await resp.json();
      setItems(body.items ?? []);
    } catch {
      Alert.alert('Could not load today’s menu', 'Make sure the MealSense API server is running.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchMenu(); }, [fetchMenu]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchMenu();
  };

  const toggleSoldOut = async (item: MenuItem) => {
    if (!user) return;
    const nextSoldOut = !item.sold_out;

    setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, sold_out: nextSoldOut } : i)));
    setPendingIds((prev) => new Set(prev).add(item.id));

    try {
      const idToken = await user.getIdToken();
      const resp = await fetch(`${API_BASE_URL}/admin/menu/${item.id}/availability`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({ sold_out: nextSoldOut }),
      });
      if (!resp.ok) throw new Error(`Update failed (${resp.status})`);
    } catch (err: any) {
      // Revert on failure — the toggle must reflect real server state,
      // never an optimistic guess that silently drifted from it.
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, sold_out: !nextSoldOut } : i)));
      Alert.alert('Could not update', err?.message ?? 'Please try again.');
    } finally {
      setPendingIds((prev) => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Today's Menu</Text>
        <View style={styles.backBtn} />
      </View>

      {loading ? (
        <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 60 }} />
      ) : items.length === 0 ? (
        <View style={styles.emptyBox}>
          <Text style={styles.emptyIcon}>🍽️</Text>
          <Text style={styles.emptyTitle}>Nothing on the menu yet</Text>
          <Text style={styles.emptySubtitle}>Upload or sync today's menu to manage availability here.</Text>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(i) => i.id}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
          renderItem={({ item }) => (
            <View style={[styles.card, item.sold_out && styles.cardSoldOut]}>
              <View style={styles.cardInfo}>
                <Text style={[styles.itemName, item.sold_out && styles.itemNameSoldOut]}>{item.name}</Text>
                <Text style={styles.itemMeta}>
                  {item.station} · {mealPeriodLabel(item.meal_period)}
                  {item.price != null ? ` · $${item.price.toFixed(2)}` : ''}
                </Text>
              </View>
              <View style={styles.switchColumn}>
                <Text style={styles.switchLabel}>{item.sold_out ? 'Sold Out' : 'Available'}</Text>
                <Switch
                  value={!!item.sold_out}
                  onValueChange={() => toggleSoldOut(item)}
                  disabled={pendingIds.has(item.id)}
                  trackColor={{ false: colors.disabled, true: colors.error }}
                  thumbColor="#fff"
                />
              </View>
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
  emptySubtitle: { fontSize: 14, color: colors.textSecondary, textAlign: 'center' },
  card: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: colors.card, borderRadius: 14, padding: 16,
    shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 6, shadowOffset: { width: 0, height: 2 }, elevation: 1,
  },
  cardSoldOut: { opacity: 0.7 },
  cardInfo: { flex: 1, marginRight: 12 },
  itemName: { fontSize: 16, fontWeight: '700', color: colors.text },
  itemNameSoldOut: { textDecorationLine: 'line-through', color: colors.textSecondary },
  itemMeta: { fontSize: 13, color: colors.textSecondary, marginTop: 3 },
  switchColumn: { alignItems: 'center', gap: 4 },
  switchLabel: { fontSize: 11, fontWeight: '700', color: colors.textLight, textTransform: 'uppercase' },
});
