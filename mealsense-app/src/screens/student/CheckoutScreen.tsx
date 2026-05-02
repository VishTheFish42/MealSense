import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  SafeAreaView, ScrollView, ActivityIndicator, Alert, KeyboardAvoidingView, Platform,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RouteProp } from '@react-navigation/native';
import { addDoc, collection, serverTimestamp } from 'firebase/firestore';
import { db } from '../../config/firebase';
import { useAuth } from '../../contexts/AuthContext';
import { colors } from '../../constants/colors';
import { HomeStackParamList, Order } from '../../types';

type Props = {
  navigation: NativeStackNavigationProp<HomeStackParamList, 'Checkout'>;
  route: RouteProp<HomeStackParamList, 'Checkout'>;
};

export default function CheckoutScreen({ navigation, route }: Props) {
  const { items, totalPrice } = route.params;
  const { user, profile } = useAuth();

  // Fake payment fields (pre-filled, no real processing)
  const [cardNumber, setCardNumber] = useState('4242 4242 4242 4242');
  const [expiry, setExpiry] = useState('12/28');
  const [cvv, setCvv] = useState('123');
  const [nameOnCard, setNameOnCard] = useState(profile?.displayName ?? '');
  const [notes, setNotes] = useState('');
  const [placing, setPlacing] = useState(false);

  const handlePlaceOrder = async () => {
    if (!user) return;
    setPlacing(true);
    try {
      const orderData: Omit<Order, 'id'> = {
        studentId: user.uid,
        items,
        totalPrice,
        status: 'placed',
        placedAt: new Date().toISOString(),
        paymentStatus: 'placeholder',
        notes: notes.trim(),
      };
      const docRef = await addDoc(collection(db, 'orders'), {
        ...orderData,
        placedAt: serverTimestamp(),
      });
      navigation.replace('OrderStatus', { orderId: docRef.id });
    } catch {
      Alert.alert('Error', 'Could not place your order. Please try again.');
    } finally {
      setPlacing(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Text style={styles.backText}>← Back</Text>
          </TouchableOpacity>
          <Text style={styles.title}>Checkout</Text>
          <View style={{ width: 60 }} />
        </View>

        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          {/* Order summary */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Order Summary</Text>
            {items.map((item) => (
              <View key={item.menuItemId} style={styles.summaryRow}>
                <Text style={styles.summaryItem}>{item.name} × {item.quantity}</Text>
                <Text style={styles.summaryPrice}>${(item.price * item.quantity).toFixed(2)}</Text>
              </View>
            ))}
            <View style={[styles.summaryRow, styles.totalRow]}>
              <Text style={styles.totalLabel}>Total</Text>
              <Text style={styles.totalValue}>${totalPrice.toFixed(2)}</Text>
            </View>
          </View>

          {/* Notes */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Special Instructions</Text>
            <TextInput
              style={[styles.input, styles.notesInput]}
              value={notes}
              onChangeText={setNotes}
              placeholder="Any requests or allergies to flag…"
              placeholderTextColor={colors.textLight}
              multiline
              numberOfLines={3}
            />
          </View>

          {/* Payment (fake) */}
          <View style={styles.section}>
            <View style={styles.sectionTitleRow}>
              <Text style={styles.sectionTitle}>Payment</Text>
              <View style={styles.demoTag}>
                <Text style={styles.demoTagText}>Demo — no charge</Text>
              </View>
            </View>
            <Text style={styles.fieldLabel}>Name on Card</Text>
            <TextInput style={styles.input} value={nameOnCard} onChangeText={setNameOnCard} placeholderTextColor={colors.textLight} />
            <Text style={styles.fieldLabel}>Card Number</Text>
            <TextInput style={styles.input} value={cardNumber} onChangeText={setCardNumber} keyboardType="number-pad" placeholderTextColor={colors.textLight} />
            <View style={styles.cardRow}>
              <View style={styles.cardRowField}>
                <Text style={styles.fieldLabel}>Expiry</Text>
                <TextInput style={styles.input} value={expiry} onChangeText={setExpiry} placeholder="MM/YY" placeholderTextColor={colors.textLight} keyboardType="number-pad" />
              </View>
              <View style={styles.cardRowField}>
                <Text style={styles.fieldLabel}>CVV</Text>
                <TextInput style={styles.input} value={cvv} onChangeText={setCvv} placeholder="123" placeholderTextColor={colors.textLight} keyboardType="number-pad" secureTextEntry />
              </View>
            </View>
            <Text style={styles.disclaimer}>🔒 Payment processing is coming soon. Your card will not be charged.</Text>
          </View>
        </ScrollView>

        <View style={styles.footer}>
          <TouchableOpacity style={styles.placeBtn} onPress={handlePlaceOrder} disabled={placing}>
            {placing ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.placeBtnText}>Place Order · ${totalPrice.toFixed(2)}</Text>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingVertical: 16, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.card },
  backBtn: { width: 60 },
  backText: { color: colors.primary, fontSize: 16, fontWeight: '600' },
  title: { fontSize: 18, fontWeight: '800', color: colors.text },
  content: { padding: 20, gap: 20, paddingBottom: 120 },
  section: { backgroundColor: colors.card, borderRadius: 16, padding: 20 },
  sectionTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 16 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 14 },
  demoTag: { backgroundColor: '#FEF3C7', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  demoTagText: { fontSize: 12, color: '#92400E', fontWeight: '600' },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  summaryItem: { fontSize: 15, color: colors.textSecondary },
  summaryPrice: { fontSize: 15, color: colors.text, fontWeight: '600' },
  totalRow: { borderTopWidth: 1, borderTopColor: colors.border, marginTop: 8, paddingTop: 12, marginBottom: 0 },
  totalLabel: { fontSize: 17, fontWeight: '800', color: colors.text },
  totalValue: { fontSize: 17, fontWeight: '800', color: colors.primary },
  fieldLabel: { fontSize: 13, fontWeight: '600', color: colors.textSecondary, marginBottom: 6, marginTop: 12 },
  input: { backgroundColor: colors.background, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, color: colors.text },
  notesInput: { minHeight: 80, textAlignVertical: 'top' },
  cardRow: { flexDirection: 'row', gap: 12 },
  cardRowField: { flex: 1 },
  disclaimer: { fontSize: 12, color: colors.textLight, marginTop: 14, lineHeight: 18 },
  footer: { position: 'absolute', bottom: 0, left: 0, right: 0, padding: 20, paddingBottom: 36, backgroundColor: colors.background, borderTopWidth: 1, borderTopColor: colors.border },
  placeBtn: { backgroundColor: colors.primary, borderRadius: 14, paddingVertical: 18, alignItems: 'center' },
  placeBtnText: { color: '#fff', fontSize: 17, fontWeight: '800' },
});
