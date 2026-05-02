import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, FlatList, SafeAreaView, ActivityIndicator,
} from 'react-native';
import { collection, query, where, orderBy, onSnapshot } from 'firebase/firestore';
import { db } from '../../config/firebase';
import { useAuth } from '../../contexts/AuthContext';
import { colors } from '../../constants/colors';
import { Order, OrderStatus } from '../../types';

const STATUS_COLORS: Record<OrderStatus, string> = {
  placed: colors.statusPlaced,
  preparing: colors.statusPreparing,
  ready: colors.statusReady,
  completed: colors.primary,
  cancelled: colors.error,
};

const STATUS_LABELS: Record<OrderStatus, string> = {
  placed: 'Placed',
  preparing: 'Preparing',
  ready: 'Ready',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

export default function OrderHistoryScreen() {
  const { user } = useAuth();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    const q = query(
      collection(db, 'orders'),
      where('studentId', '==', user.uid),
      orderBy('placedAt', 'desc'),
    );
    const unsub = onSnapshot(q, (snap) => {
      setOrders(snap.docs.map((d) => ({ id: d.id, ...d.data() } as Order)));
      setLoading(false);
    });
    return unsub;
  }, [user]);

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}>
        <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.title}>Order History</Text>
      </View>
      {orders.length === 0 ? (
        <View style={styles.emptyBox}>
          <Text style={styles.emptyIcon}>🛒</Text>
          <Text style={styles.emptyTitle}>No orders yet</Text>
          <Text style={styles.emptySubtitle}>Your order history will appear here after your first order.</Text>
        </View>
      ) : (
        <FlatList
          data={orders}
          keyExtractor={(o) => o.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => <OrderCard order={item} />}
        />
      )}
    </SafeAreaView>
  );
}

function OrderCard({ order }: { order: Order }) {
  const statusColor = STATUS_COLORS[order.status];
  const placedDate = order.placedAt
    ? new Date(
        typeof order.placedAt === 'string' ? order.placedAt : (order.placedAt as any).toDate?.() ?? order.placedAt,
      ).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : '—';

  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.orderId}>Order #{order.id.slice(-6).toUpperCase()}</Text>
        <View style={[styles.statusBadge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
          <Text style={[styles.statusText, { color: statusColor }]}>{STATUS_LABELS[order.status]}</Text>
        </View>
      </View>
      <Text style={styles.dateText}>{placedDate}</Text>
      {order.items.map((item) => (
        <Text key={item.menuItemId} style={styles.itemText}>• {item.name} × {item.quantity}</Text>
      ))}
      <View style={styles.totalRow}>
        <Text style={styles.totalLabel}>Total</Text>
        <Text style={styles.totalValue}>${order.totalPrice.toFixed(2)}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { padding: 20, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.card },
  title: { fontSize: 24, fontWeight: '800', color: colors.text },
  list: { padding: 20, gap: 16 },
  emptyBox: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40 },
  emptyIcon: { fontSize: 48, marginBottom: 16 },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: colors.text, marginBottom: 8 },
  emptySubtitle: { fontSize: 15, color: colors.textSecondary, textAlign: 'center', lineHeight: 22 },
  card: { backgroundColor: colors.card, borderRadius: 16, padding: 20, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 8, shadowOffset: { width: 0, height: 2 }, elevation: 2 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  orderId: { fontSize: 16, fontWeight: '700', color: colors.text },
  statusBadge: { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 3, borderWidth: 1 },
  statusText: { fontSize: 13, fontWeight: '700' },
  dateText: { fontSize: 13, color: colors.textLight, marginBottom: 10 },
  itemText: { fontSize: 14, color: colors.textSecondary, marginBottom: 4 },
  totalRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 12, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 10 },
  totalLabel: { fontSize: 15, fontWeight: '700', color: colors.text },
  totalValue: { fontSize: 15, fontWeight: '700', color: colors.primary },
});
