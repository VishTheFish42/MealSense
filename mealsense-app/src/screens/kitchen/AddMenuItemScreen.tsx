import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, SafeAreaView, Alert, ActivityIndicator,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useAuth } from '../../contexts/AuthContext';
import { colors } from '../../constants/colors';
import { API_BASE_URL } from '../../config/api';
import { KitchenStackParamList, MealPeriod } from '../../types';

type Props = { navigation: NativeStackNavigationProp<KitchenStackParamList, 'AddMenuItem'> };

type Option = { label: string; value: string };

const MEAL_PERIOD_OPTIONS: { label: string; value: MealPeriod }[] = [
  { label: 'Breakfast', value: 'breakfast' },
  { label: 'Lunch', value: 'lunch' },
  { label: 'Dinner', value: 'dinner' },
  { label: 'All Day', value: 'all_day' },
];

// README.md §6.2's allergen list — kept in sync manually with
// EditPreferencesScreen.tsx's student-facing ALLERGEN_OPTIONS.
const ALLERGEN_OPTIONS: Option[] = [
  { label: 'Nuts', value: 'nuts' },
  { label: 'Dairy', value: 'dairy' },
  { label: 'Gluten', value: 'gluten' },
  { label: 'Eggs', value: 'eggs' },
  { label: 'Soy', value: 'soy' },
  { label: 'Shellfish', value: 'shellfish' },
  { label: 'Fish', value: 'fish' },
  { label: 'Sesame', value: 'sesame' },
];

const DIET_TAG_OPTIONS: Option[] = [
  { label: 'Vegetarian', value: 'vegetarian' },
  { label: 'Vegan', value: 'vegan' },
  { label: 'Halal', value: 'halal' },
  { label: 'Kosher', value: 'kosher' },
];

const NUMERIC_FIELDS: { key: string; label: string; placeholder: string }[] = [
  { key: 'calories', label: 'Calories', placeholder: 'e.g. 450' },
  { key: 'protein_g', label: 'Protein (g)', placeholder: 'e.g. 38' },
  { key: 'carbs_g', label: 'Carbs (g)', placeholder: 'e.g. 20' },
  { key: 'fat_g', label: 'Fat (g)', placeholder: 'e.g. 12' },
  { key: 'fiber_g', label: 'Fiber (g)', placeholder: 'e.g. 3' },
  { key: 'sodium_mg', label: 'Sodium (mg)', placeholder: 'e.g. 410' },
  { key: 'sugar_g', label: 'Sugar (g)', placeholder: 'e.g. 2' },
  { key: 'price', label: 'Price ($)', placeholder: 'e.g. 9.50' },
];

function todayLocalDate(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function Chip({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <TouchableOpacity style={[styles.chip, selected && styles.chipSelected]} onPress={onPress} activeOpacity={0.7}>
      <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{label}</Text>
    </TouchableOpacity>
  );
}

function OptionCard({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <TouchableOpacity style={[styles.optionCard, selected && styles.optionCardSelected]} onPress={onPress} activeOpacity={0.7}>
      <Text style={[styles.optionCardText, selected && styles.optionCardTextSelected]}>{label}</Text>
      {selected && <Text style={styles.checkmark}>✓</Text>}
    </TouchableOpacity>
  );
}

const emptyNumericState: Record<string, string> = Object.fromEntries(NUMERIC_FIELDS.map((f) => [f.key, '']));

export default function AddMenuItemScreen({ navigation }: Props) {
  const { user } = useAuth();
  const [submitting, setSubmitting] = useState(false);

  const [name, setName] = useState('');
  const [station, setStation] = useState('');
  const [mealPeriod, setMealPeriod] = useState<MealPeriod | ''>('');
  const [availableFrom, setAvailableFrom] = useState('');
  const [availableUntil, setAvailableUntil] = useState('');
  const [numbers, setNumbers] = useState<Record<string, string>>(emptyNumericState);

  // Allergens use an explicit tri-state: nothing selected yet (undecided),
  // 'none' (verified zero allergens), or one-or-more specific allergens.
  // Undecided must block submission — mirrors the ingestion layer's
  // fail-closed rule (design-spec.md §7.0a): a missing allergens field is
  // never treated as safe, so staff can't accidentally skip this.
  const [allergens, setAllergens] = useState<string[]>([]);
  const [dietaryTags, setDietaryTags] = useState<string[]>([]);
  const [ingredients, setIngredients] = useState('');
  const [description, setDescription] = useState('');

  const toggleAllergenNone = () => {
    setAllergens((prev) => (prev.includes('none') ? [] : ['none']));
  };
  const toggleAllergen = (value: string) => {
    setAllergens((prev) => {
      const withoutNone = prev.filter((v) => v !== 'none');
      return withoutNone.includes(value) ? withoutNone.filter((v) => v !== value) : [...withoutNone, value];
    });
  };
  const toggleDietTag = (value: string) => {
    setDietaryTags((prev) => (prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]));
  };
  const setNumberField = (key: string, value: string) => {
    setNumbers((prev) => ({ ...prev, [key]: value }));
  };

  const resetForm = () => {
    setName('');
    setStation('');
    setMealPeriod('');
    setAvailableFrom('');
    setAvailableUntil('');
    setNumbers(emptyNumericState);
    setAllergens([]);
    setDietaryTags([]);
    setIngredients('');
    setDescription('');
  };

  const validate = (): string | null => {
    if (!name.trim()) return 'Item name is required.';
    if (!mealPeriod) return 'Select a meal period.';
    for (const f of NUMERIC_FIELDS) {
      const raw = numbers[f.key].trim();
      if (!raw) return `${f.label} is required.`;
      if (isNaN(Number(raw))) return `${f.label} must be a number.`;
    }
    if (allergens.length === 0) {
      return 'Allergens must be set — tap "None (verified)" if this item truly has none. Leaving it blank is treated as unknown and will be rejected.';
    }
    return null;
  };

  const handleSubmit = async () => {
    const error = validate();
    if (error) {
      Alert.alert('Check the form', error);
      return;
    }
    if (!user) {
      Alert.alert('Not signed in', 'Please sign in again.');
      return;
    }

    setSubmitting(true);
    try {
      const idToken = await user.getIdToken();
      const payload = [{
        name: name.trim(),
        station: station.trim() || undefined,
        meal_period: mealPeriod,
        available_from: availableFrom.trim() || undefined,
        available_until: availableUntil.trim() || undefined,
        calories: Number(numbers.calories),
        protein_g: Number(numbers.protein_g),
        carbs_g: Number(numbers.carbs_g),
        fat_g: Number(numbers.fat_g),
        fiber_g: Number(numbers.fiber_g),
        sodium_mg: Number(numbers.sodium_mg),
        sugar_g: Number(numbers.sugar_g),
        price: Number(numbers.price),
        allergens: allergens.includes('none') ? 'none' : allergens.join(', '),
        dietary_tags: dietaryTags.join(', '),
        ingredients: ingredients.trim(),
        description: description.trim() || undefined,
      }];

      const servedOn = todayLocalDate();
      const resp = await fetch(
        `${API_BASE_URL}/admin/menu/upload?format=messy_json&served_on=${servedOn}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${idToken}`,
          },
          body: JSON.stringify(payload),
        },
      );

      if (!resp.ok) {
        const text = await resp.text().catch(() => '');
        throw new Error(`Upload failed (${resp.status}): ${text}`);
      }

      const body = await resp.json();
      if (body.rejected && body.rejected.length > 0) {
        Alert.alert('Item rejected', body.rejected[0].reason ?? 'Unknown reason.');
        return;
      }

      Alert.alert('Added to today’s menu', `${name.trim()} is now live for ${servedOn}.`, [
        { text: 'Add another', onPress: resetForm },
        { text: 'Done', onPress: () => navigation.goBack() },
      ]);
    } catch (err: any) {
      console.error('Add menu item error:', err);
      Alert.alert('Could not add item', err?.message ?? 'Please check the API server is running and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Add Menu Item</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.sectionHeader}>Basics</Text>
        <View style={styles.card}>
          <Text style={styles.label}>Name</Text>
          <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="e.g. Grilled Chicken Bowl" placeholderTextColor={colors.textLight} />
          <Text style={styles.label}>Station (optional)</Text>
          <TextInput style={styles.input} value={station} onChangeText={setStation} placeholder="e.g. Hot Entrees" placeholderTextColor={colors.textLight} />
        </View>

        <Text style={styles.sectionHeader}>Meal Period</Text>
        <View style={styles.card}>
          <View style={styles.columnList}>
            {MEAL_PERIOD_OPTIONS.map((opt) => (
              <OptionCard key={opt.value} label={opt.label} selected={mealPeriod === opt.value} onPress={() => setMealPeriod(opt.value)} />
            ))}
          </View>
          <Text style={[styles.label, { marginTop: 12 }]}>Available From (optional, HH:MM)</Text>
          <TextInput style={styles.input} value={availableFrom} onChangeText={setAvailableFrom} placeholder="e.g. 11:00" placeholderTextColor={colors.textLight} />
          <Text style={styles.label}>Available Until (optional, HH:MM)</Text>
          <TextInput style={styles.input} value={availableUntil} onChangeText={setAvailableUntil} placeholder="e.g. 15:00" placeholderTextColor={colors.textLight} />
          <Text style={styles.hint}>Leave blank to use the standard hours for this meal period.</Text>
        </View>

        <Text style={styles.sectionHeader}>Nutrition & Price</Text>
        <View style={styles.card}>
          {NUMERIC_FIELDS.map((f) => (
            <View key={f.key}>
              <Text style={styles.label}>{f.label}</Text>
              <TextInput
                style={styles.input}
                value={numbers[f.key]}
                onChangeText={(v) => setNumberField(f.key, v)}
                placeholder={f.placeholder}
                placeholderTextColor={colors.textLight}
                keyboardType="decimal-pad"
              />
            </View>
          ))}
        </View>

        <Text style={styles.sectionHeader}>Allergens (required)</Text>
        <View style={styles.card}>
          <Text style={styles.hint}>This is a safety-critical field — an item with no allergen data is never shown to students. Select every allergen present, or confirm there are none.</Text>
          <View style={styles.chipWrap}>
            <Chip label="None (verified)" selected={allergens.includes('none')} onPress={toggleAllergenNone} />
            {ALLERGEN_OPTIONS.map((opt) => (
              <Chip key={opt.value} label={opt.label} selected={allergens.includes(opt.value)} onPress={() => toggleAllergen(opt.value)} />
            ))}
          </View>
        </View>

        <Text style={styles.sectionHeader}>Dietary Tags (optional)</Text>
        <View style={styles.card}>
          <View style={styles.chipWrap}>
            {DIET_TAG_OPTIONS.map((opt) => (
              <Chip key={opt.value} label={opt.label} selected={dietaryTags.includes(opt.value)} onPress={() => toggleDietTag(opt.value)} />
            ))}
          </View>
        </View>

        <Text style={styles.sectionHeader}>Ingredients & Description (optional)</Text>
        <View style={styles.card}>
          <Text style={styles.label}>Ingredients (comma-separated)</Text>
          <TextInput style={styles.input} value={ingredients} onChangeText={setIngredients} placeholder="e.g. chicken, olive oil, garlic" placeholderTextColor={colors.textLight} />
          <Text style={styles.label}>Description</Text>
          <TextInput style={styles.input} value={description} onChangeText={setDescription} placeholder="e.g. Herb-marinated grilled chicken over rice." placeholderTextColor={colors.textLight} multiline />
        </View>

        <TouchableOpacity style={styles.saveBtn} onPress={handleSubmit} disabled={submitting}>
          {submitting ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveBtnText}>Add to Today's Menu</Text>}
        </TouchableOpacity>
      </ScrollView>
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
  sectionHeader: { fontSize: 13, fontWeight: '700', color: colors.textLight, letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 12, marginBottom: 4, marginLeft: 4 },
  card: { backgroundColor: colors.card, borderRadius: 16, padding: 18, gap: 10 },
  label: { fontSize: 14, fontWeight: '600', color: colors.text },
  hint: { fontSize: 12, color: colors.textSecondary, lineHeight: 17 },
  input: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: colors.text,
  },
  columnList: { gap: 8 },
  optionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 14,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  optionCardSelected: { borderColor: colors.primary, backgroundColor: colors.primary + '12' },
  optionCardText: { fontSize: 15, color: colors.textSecondary, fontWeight: '500', flexShrink: 1 },
  optionCardTextSelected: { color: colors.primary, fontWeight: '700' },
  checkmark: { color: colors.primary, fontWeight: '700', fontSize: 16 },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  chipSelected: { borderColor: colors.primary, backgroundColor: colors.primary + '15' },
  chipText: { fontSize: 14, color: colors.textSecondary, fontWeight: '500' },
  chipTextSelected: { color: colors.primary, fontWeight: '700' },
  saveBtn: {
    backgroundColor: colors.primary,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 16,
  },
  saveBtnText: { color: '#fff', fontSize: 17, fontWeight: '700' },
});
