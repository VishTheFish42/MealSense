import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, SafeAreaView, ActivityIndicator,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RouteProp } from '@react-navigation/native';
import { doc, onSnapshot, updateDoc } from 'firebase/firestore';
import { db } from '../../config/firebase';
import { colors } from '../../constants/colors';
import { HomeStackParamList, Order, OrderStatus } from '../../types';
import { ORDER_TIMERS } from '../../constants/orderTimers';

type Props = {
  navigation: NativeStackNavigationProp<HomeStackParamList, 'OrderStatus'>;
  route: RouteProp<HomeStackParamList, 'OrderStatus'>;
};

const STATUS_STEPS: { status: OrderStatus; label: string; icon: string; description: string }[] = [
  { status: 'placed', label: 'Order Placed', icon: '📋', description: 'Your order has been received.' },
  { status: 'preparing', label: 'Preparing', icon: '👨‍🍳', description: 'The kitchen is preparing your meal.' },
  { status: 'ready', label: 'Ready for Pickup', icon: '🎉', description: 'Your order is ready! Head to the pickup window.' },
];

function statusIndex(status: OrderStatus): number {
  return STATUS_STEPS.findIndex((s) => s.status === status);
}

export default function OrderStatusScreen({ navigation, route }: Props) {
  const { orderId } = route.params;
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);

  // Subscribe to order in real time
  useEffect(() => {
    const unsub = onSnapshot(doc(db, 'orders', orderId), (snap) => {
      if (snap.exists()) {
        setOrder({ id: snap.id, ...snap.data() } as Order);
      }
      setLoading(false);
    });
    return unsub;
  }, [orderId]);

  // Timer-based status progression (demo)
  useEffect(() => {
    if (!order || order.status !== 'placed') return;
    const t = setTimeout(async () => {
      await updateDoc(doc(db, 'orders', orderId), {
        status: 'preparing',
        preparingAt: new Date().toISOString(),
      });
    }, ORDER_TIMERS.PLACED_TO_PREPARING_MS);
    return () => clearTimeout(t);
  }, [order?.status, orderId]);

  useEffect(() => {
    if (!order || order.status !== 'preparing') return;
    const t = setTimeout(async () => {
      await updateDoc(doc(db, 'orders', orderId), {
        status: 'ready',
        readyAt: new Date().toISOString(),
      });
    }, ORDER_TIMERS.PREPARING_TO_READY_MS);
    return () => clearTimeout(t);
  }, [order?.status, orderId]);

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}>
        <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  if (!order) {
    return (
      <SafeAreaView style={styles.safe}>
        <Text style={styles.errorText}>Order not found.</Text>
      </SafeAreaView>
    );
  }

  const currentIndex = statusIndex(order.status);
  const currentStep = STATUS_STEPS[Math.max(currentIndex, 0)];
  const isReady = order.status === 'ready';

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Text style={styles.title}>Order #{orderId.slice(-6).toUpperCase()}</Text>
      </View>

      <View style={styles.content}>
        {/* Big status icon */}
        <View style={[styles.statusCircle, isReady && styles.statusCircleReady]}>
          <Text style={styles.statusIcon}>{currentStep.icon}</Text>
        </View>
        <Text style={styles.statusLabel}>{currentStep.label}</Text>
        <Text style={styles.statusDescription}>{currentStep.description}</Text>

        {/* Progress steps */}
        <View style={styles.stepsRow}>
          {STATUS_STEPS.map((step, idx) => {
            const done = idx <= currentIndex;
            const active = idx === currentIndex;
            return (
              <React.Fragment key={step.status}>
                <View style={styles.stepItem}>
                  <View style={[styles.stepDot, done && styles.stepDotDone, active && styles.stepDotActive]}>
                    {done && !active && <Text style={styles.stepDotCheck}>✓</Text>}
                    {active && !isReady && <ActivityIndicator size="small" color="#fff" />}
                    {active && isReady && <Text style={styles.stepDotCheck}>✓</Text>}
                  </View>
                  <Text style={[styles.stepLabel, done && styles.stepLabelDone]}>{step.label}</Text>
                </View>
                {idx < STATUS_STEPS.length - 1 && (
                  <View style={[styles.stepLine, idx < currentIndex && styles.stepLineDone]} />
                )}
              </React.Fragment>
            );
          })}
        </View>

        {/* Items summary */}
        <View style={styles.itemsSummary}>
          <Text style={styles.itemsSummaryTitle}>Your Order</Text>
          {order.items.map((item) => (
            <View key={item.menuItemId} style={styles.itemRow}>
              <Text style={styles.itemName}>{item.name} × {item.quantity}</Text>
              <Text style={styles.itemPrice}>${(item.price * item.quantity).toFixed(2)}</Text>
            </View>
          ))}
          <View style={styles.totalRow}>
            <Text style={styles.totalLabel}>Total</Text>
            <Text style={styles.totalValue}>${order.totalPrice.toFixed(2)}</Text>
          </View>
        </View>

        {isReady && (
          <TouchableOpacity
            style={styles.doneBtn}
            onPress={() => navigation.popToTop()}
          >
            <Text style={styles.doneBtnText}>Order Again →</Text>
          </TouchableOpacity>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { padding: 20, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.card, alignItems: 'center' },
  title: { fontSize: 18, fontWeight: '800', color: colors.text },
  content: { flex: 1, padding: 24, alignItems: 'center' },
  statusCircle: { width: 100, height: 100, borderRadius: 50, backgroundColor: colors.primaryLight + '30', alignItems: 'center', justifyContent: 'center', marginTop: 24, marginBottom: 16 },
  statusCircleReady: { backgroundColor: colors.success + '30' },
  statusIcon: { fontSize: 44 },
  statusLabel: { fontSize: 24, fontWeight: '800', color: colors.text, marginBottom: 8 },
  statusDescription: { fontSize: 15, color: colors.textSecondary, textAlign: 'center', marginBottom: 36, lineHeight: 22 },
  stepsRow: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'center', marginBottom: 32, width: '100%' },
  stepItem: { alignItems: 'center', width: 80 },
  stepDot: { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.border, alignItems: 'center', justifyContent: 'center', marginBottom: 6 },
  stepDotDone: { backgroundColor: colors.primary },
  stepDotActive: { backgroundColor: colors.primary },
  stepDotCheck: { color: '#fff', fontWeight: '700', fontSize: 16 },
  stepLabel: { fontSize: 11, color: colors.textLight, textAlign: 'center' },
  stepLabelDone: { color: colors.primary, fontWeight: '600' },
  stepLine: { flex: 1, height: 2, backgroundColor: colors.border, marginTop: 17 },
  stepLineDone: { backgroundColor: colors.primary },
  errorText: { textAlign: 'center', marginTop: 60, color: colors.textSecondary, fontSize: 16 },
  itemsSummary: { width: '100%', backgroundColor: colors.card, borderRadius: 16, padding: 20 },
  itemsSummaryTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 12 },
  itemRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  itemName: { fontSize: 15, color: colors.textSecondary },
  itemPrice: { fontSize: 15, color: colors.text, fontWeight: '600' },
  totalRow: { borderTopWidth: 1, borderTopColor: colors.border, marginTop: 8, paddingTop: 12, flexDirection: 'row', justifyContent: 'space-between' },
  totalLabel: { fontSize: 16, fontWeight: '700', color: colors.text },
  totalValue: { fontSize: 16, fontWeight: '700', color: colors.primary },
  doneBtn: { marginTop: 24, backgroundColor: colors.primary, borderRadius: 14, paddingVertical: 16, paddingHorizontal: 40 },
  doneBtnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
});
