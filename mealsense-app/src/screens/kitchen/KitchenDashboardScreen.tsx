import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, FlatList, SafeAreaView,
  ActivityIndicator, TouchableOpacity, Alert,
} from 'react-native';
import { collection, query, where, onSnapshot, updateDoc, doc, orderBy } from 'firebase/firestore';
import { signOut } from 'firebase/auth';
import { db, auth } from '../../config/firebase';
import { colors } from '../../constants/colors';
import { Order, OrderStatus } from '../../types';

const ACTIVE_STATUSES: OrderStatus[] = ['placed', 'preparing'];

const STATUS_LABELS: Record<OrderStatus, string> = {
  placed: '📋 Placed',
  preparing: '👨‍🍳 Preparing',
  ready: '✅ Ready',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

const STATUS_COLORS: Record<OrderStatus, string> = {
  placed: colors.statusPlaced,
  preparing: colors.statusPreparing,
  ready: colors.statusReady,
  completed: colors.primary,
  cancelled: colors.error,
};

function timeSince(dateStr: string | any): string {
  try {
    const date = typeof dateStr === 'string' ? new Date(dateStr) : dateStr?.toDate?.() ?? new Date();
    const diff = Math.floor((Date.now() - date.getTime()) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  } catch {
    return '—';
  }
}

export default function KitchenDashboardScreen() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'active' | 'ready'>('active');

  useEffect(() => {
    const q = query(
      collection(db, 'orders'),
      where('status', 'in', ['placed', 'preparing', 'ready']),
      orderBy('placedAt', 'asc'),
    );
    const unsub = onSnapshot(q, (snap) => {
      setOrders(snap.docs.map((d) => ({ id: d.id, ...d.data() } as Order)));
      setLoading(false);
    });
    return unsub;
  }, []);

  const handleMarkReady = async (orderId: string) => {
    await updateDoc(doc(db, 'orders', orderId), {
      status: 'ready',
      readyAt: new Date().toISOString(),
    });
  };

  const handleMarkComplete = async (orderId: string) => {
    await updateDoc(doc(db, 'orders', orderId), {
      status: 'completed',
      completedAt: new Date().toISOString(),
    });
  };

  const filtered = orders.filter((o) =>
    tab === 'active' ? ACTIVE_STATUSES.includes(o.status) : o.status === 'ready',
  );

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Kitchen Dashboard</Text>
          <Text style={styles.subtitle}>{orders.filter(o => ACTIVE_STATUSES.includes(o.status)).length} active orders</Text>
        </View>
        <TouchableOpacity
          onPress={() => Alert.alert('Sign Out', 'Sign out of kitchen view?', [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Sign Out', style: 'destructive', onPress: () => signOut(auth) },
          ])}
        >
          <Text style={styles.signOutText}>Sign Out</Text>
        </TouchableOpacity>
      </View>

      {/* Tabs */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tab, tab === 'active' && styles.tabActive]}
          onPress={() => setTab('active')}
        >
          <Text style={[styles.tabText, tab === 'active' && styles.tabTextActive]}>
            Active ({orders.filter(o => ACTIVE_STATUSES.includes(o.status)).length})
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, tab === 'ready' && styles.tabActive]}
          onPress={() => setTab('ready')}
        >
          <Text style={[styles.tabText, tab === 'ready' && styles.tabTextActive]}>
            Ready ({orders.filter(o => o.status === 'ready').length})
          </Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 60 }} />
      ) : filtered.length === 0 ? (
        <View style={styles.emptyBox}>
          <Text style={styles.emptyIcon}>{tab === 'active' ? '🎉' : '📋'}</Text>
          <Text style={styles.emptyTitle}>{tab === 'active' ? 'No active orders' : 'No orders ready yet'}</Text>
        </View>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(o) => o.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <OrderCard
              order={item}
              onMarkReady={() => handleMarkReady(item.id)}
              onMarkComplete={() => handleMarkComplete(item.id)}
            />
          )}
        />
      )}
    </SafeAreaView>
  );
}

function OrderCard({
  order, onMarkReady, onMarkComplete,
}: {
  order: Order;
  onMarkReady: () => void;
  onMarkComplete: () => void;
}) {
  const statusColor = STATUS_COLORS[order.status];

  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.orderId}>#{order.id.slice(-6).toUpperCase()}</Text>
        <View style={[styles.statusBadge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
          <Text style={[styles.statusBadgeText, { color: statusColor }]}>{STATUS_LABELS[order.status]}</Text>
        </View>
        <Text style={styles.timeAgo}>{timeSince(order.placedAt)}</Text>
      </View>

      {order.items.map((item) => (
        <Text key={item.menuItemId} style={styles.itemText}>• {item.name} × {item.quantity}</Text>
      ))}

      {order.notes ? (
        <View style={styles.notesBox}>
          <Text style={styles.notesText}>📝 {order.notes}</Text>
        </View>
      ) : null}

      <View style={styles.actionRow}>
        {order.status === 'placed' && (
          <TouchableOpacity style={[styles.actionBtn, styles.prepBtn]} onPress={onMarkReady}>
            <Text style={styles.actionBtnText}>Mark Ready ✓</Text>
          </TouchableOpacity>
        )}
        {order.status === 'preparing' && (
          <TouchableOpacity style={[styles.actionBtn, styles.prepBtn]} onPress={onMarkReady}>
            <Text style={styles.actionBtnText}>Mark Ready ✓</Text>
          </TouchableOpacity>
        )}
        {order.status === 'ready' && (
          <TouchableOpacity style={[styles.actionBtn, styles.completeBtn]} onPress={onMarkComplete}>
            <Text style={styles.actionBtnText}>Mark Picked Up</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', padding: 20, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.card },
  title: { fontSize: 22, fontWeight: '800', color: colors.text },
  subtitle: { fontSize: 14, color: colors.textSecondary, marginTop: 2 },
  signOutText: { color: colors.error, fontSize: 14, fontWeight: '600', marginTop: 4 },
  tabBar: { flexDirection: 'row', backgroundColor: colors.card, borderBottomWidth: 1, borderBottomColor: colors.border },
  tab: { flex: 1, paddingVertical: 14, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: colors.primary },
  tabText: { fontSize: 15, fontWeight: '600', color: colors.textSecondary },
  tabTextActive: { color: colors.primary },
  list: { padding: 16, gap: 14 },
  emptyBox: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  emptyIcon: { fontSize: 48, marginBottom: 12 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: colors.textSecondary },
  card: { backgroundColor: colors.card, borderRadius: 16, padding: 18, shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 8, shadowOffset: { width: 0, height: 2 }, elevation: 2 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 },
  orderId: { fontSize: 17, fontWeight: '800', color: colors.text },
  statusBadge: { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 3, borderWidth: 1 },
  statusBadgeText: { fontSize: 13, fontWeight: '700' },
  timeAgo: { marginLeft: 'auto', fontSize: 13, color: colors.textLight },
  itemText: { fontSize: 15, color: colors.text, marginBottom: 5 },
  notesBox: { marginTop: 8, backgroundColor: colors.background, borderRadius: 8, padding: 10 },
  notesText: { fontSize: 13, color: colors.textSecondary },
  actionRow: { marginTop: 14 },
  actionBtn: { borderRadius: 10, paddingVertical: 12, alignItems: 'center' },
  prepBtn: { backgroundColor: colors.primary },
  completeBtn: { backgroundColor: colors.success },
  actionBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
});
