import React, { useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, SafeAreaView, ScrollView,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RouteProp } from '@react-navigation/native';
import { colors } from '../../constants/colors';
import { HomeStackParamList, OrderItem } from '../../types';

type Props = {
  navigation: NativeStackNavigationProp<HomeStackParamList, 'Cart'>;
  route: RouteProp<HomeStackParamList, 'Cart'>;
};

export default function CartScreen({ navigation, route }: Props) {
  const { item } = route.params;
  const [quantity, setQuantity] = useState(1);

  const totalPrice = item.price * quantity;

  const handleCheckout = () => {
    const orderItems: OrderItem[] = [
      { menuItemId: item.id, name: item.name, quantity, price: item.price },
    ];
    navigation.navigate('Checkout', { items: orderItems, totalPrice });
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Your Cart</Text>
        <View style={{ width: 60 }} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Item card */}
        <View style={styles.itemCard}>
          <View style={styles.itemInfo}>
            <Text style={styles.itemName}>{item.name}</Text>
            <Text style={styles.itemStation}>{item.station}</Text>
            <View style={styles.nutritionRow}>
              {[
                { label: 'Cal', value: item.calories },
                { label: 'Protein', value: `${item.proteinG}g` },
                { label: 'Carbs', value: `${item.carbsG}g` },
                { label: 'Fat', value: `${item.fatG}g` },
              ].map(({ label, value }) => (
                <View key={label} style={styles.nutritionPill}>
                  <Text style={styles.nutritionValue}>{value}</Text>
                  <Text style={styles.nutritionLabel}>{label}</Text>
                </View>
              ))}
            </View>
          </View>

          <View style={styles.qtyRow}>
            <TouchableOpacity
              style={styles.qtyBtn}
              onPress={() => setQuantity(Math.max(1, quantity - 1))}
            >
              <Text style={styles.qtyBtnText}>−</Text>
            </TouchableOpacity>
            <Text style={styles.qtyValue}>{quantity}</Text>
            <TouchableOpacity
              style={styles.qtyBtn}
              onPress={() => setQuantity(quantity + 1)}
            >
              <Text style={styles.qtyBtnText}>+</Text>
            </TouchableOpacity>
            <Text style={styles.itemPrice}>${(item.price * quantity).toFixed(2)}</Text>
          </View>
        </View>

        {/* Allergen notice */}
        {item.allergens.length > 0 && (
          <View style={styles.allergenBox}>
            <Text style={styles.allergenTitle}>⚠️ Contains: {item.allergens.join(', ')}</Text>
          </View>
        )}

        {/* Order summary */}
        <View style={styles.summaryCard}>
          <Text style={styles.summaryTitle}>Order Summary</Text>
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>{item.name} × {quantity}</Text>
            <Text style={styles.summaryValue}>${(item.price * quantity).toFixed(2)}</Text>
          </View>
          <View style={[styles.summaryRow, styles.summaryTotal]}>
            <Text style={styles.totalLabel}>Total</Text>
            <Text style={styles.totalValue}>${totalPrice.toFixed(2)}</Text>
          </View>
        </View>
      </ScrollView>

      <View style={styles.footer}>
        <TouchableOpacity style={styles.checkoutBtn} onPress={handleCheckout}>
          <Text style={styles.checkoutBtnText}>Proceed to Checkout · ${totalPrice.toFixed(2)}</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingVertical: 16, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.card },
  backBtn: { width: 60 },
  backText: { color: colors.primary, fontSize: 16, fontWeight: '600' },
  title: { fontSize: 18, fontWeight: '800', color: colors.text },
  content: { padding: 20, gap: 16, paddingBottom: 120 },
  itemCard: { backgroundColor: colors.card, borderRadius: 16, padding: 20, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 8, shadowOffset: { width: 0, height: 2 }, elevation: 2 },
  itemInfo: { marginBottom: 16 },
  itemName: { fontSize: 20, fontWeight: '800', color: colors.text, marginBottom: 4 },
  itemStation: { fontSize: 14, color: colors.textSecondary },
  nutritionRow: { flexDirection: 'row', gap: 12, marginTop: 12 },
  nutritionPill: { alignItems: 'center' },
  nutritionValue: { fontSize: 16, fontWeight: '700', color: colors.text },
  nutritionLabel: { fontSize: 11, color: colors.textLight, marginTop: 2 },
  qtyRow: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  qtyBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.background, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center' },
  qtyBtnText: { fontSize: 22, color: colors.text, fontWeight: '600', lineHeight: 28 },
  qtyValue: { fontSize: 20, fontWeight: '700', color: colors.text, minWidth: 28, textAlign: 'center' },
  itemPrice: { marginLeft: 'auto', fontSize: 20, fontWeight: '800', color: colors.text },
  allergenBox: { backgroundColor: '#FEF3C7', borderRadius: 12, padding: 14, borderWidth: 1, borderColor: '#F59E0B' },
  allergenTitle: { fontSize: 14, color: '#92400E', fontWeight: '600' },
  summaryCard: { backgroundColor: colors.card, borderRadius: 16, padding: 20 },
  summaryTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 14 },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10 },
  summaryLabel: { fontSize: 15, color: colors.textSecondary },
  summaryValue: { fontSize: 15, color: colors.text, fontWeight: '600' },
  summaryTotal: { borderTopWidth: 1, borderTopColor: colors.border, marginTop: 8, paddingTop: 12, marginBottom: 0 },
  totalLabel: { fontSize: 17, fontWeight: '800', color: colors.text },
  totalValue: { fontSize: 17, fontWeight: '800', color: colors.primary },
  footer: { position: 'absolute', bottom: 0, left: 0, right: 0, padding: 20, paddingBottom: 36, backgroundColor: colors.background, borderTopWidth: 1, borderTopColor: colors.border },
  checkoutBtn: { backgroundColor: colors.accent, borderRadius: 14, paddingVertical: 18, alignItems: 'center' },
  checkoutBtnText: { color: '#fff', fontSize: 17, fontWeight: '800' },
});
