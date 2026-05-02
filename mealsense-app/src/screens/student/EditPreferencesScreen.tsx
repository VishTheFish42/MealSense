import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, SafeAreaView, Alert, ActivityIndicator,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { doc, setDoc } from 'firebase/firestore';
import { db } from '../../config/firebase';
import { useAuth } from '../../contexts/AuthContext';
import { colors } from '../../constants/colors';
import { ProfileStackParamList, Sex, ActivityLevel, HealthGoal, StudentProfile } from '../../types';

type Props = { navigation: NativeStackNavigationProp<ProfileStackParamList, 'EditProfile'> };

type MultiSelectOption = { label: string; value: string };

const ALLERGEN_OPTIONS: MultiSelectOption[] = [
  { label: 'Nuts', value: 'nuts' },
  { label: 'Dairy', value: 'dairy' },
  { label: 'Gluten', value: 'gluten' },
  { label: 'Eggs', value: 'eggs' },
  { label: 'Soy', value: 'soy' },
  { label: 'Shellfish', value: 'shellfish' },
  { label: 'Fish', value: 'fish' },
];

const DIET_OPTIONS: MultiSelectOption[] = [
  { label: 'Vegetarian', value: 'vegetarian' },
  { label: 'Vegan', value: 'vegan' },
  { label: 'Halal', value: 'halal' },
  { label: 'Kosher', value: 'kosher' },
];

const CONDITION_OPTIONS: MultiSelectOption[] = [
  { label: 'Diabetes / Pre-diabetes', value: 'diabetes' },
  { label: 'High blood pressure', value: 'hypertension' },
  { label: 'High cholesterol', value: 'high_cholesterol' },
  { label: 'IBS / Digestive sensitivity', value: 'ibs' },
  { label: 'Lactose intolerance', value: 'lactose_intolerance' },
  { label: 'Iron deficiency', value: 'iron_deficiency' },
];

const FOCUS_OPTIONS: MultiSelectOption[] = [
  { label: 'High protein', value: 'high_protein' },
  { label: 'Low carb', value: 'low_carb' },
  { label: 'Low sodium', value: 'low_sodium' },
  { label: 'High fiber', value: 'high_fiber' },
  { label: 'Low sugar', value: 'low_sugar' },
];

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

function UnitToggle({ options, active, onPress }: { options: [string, string]; active: string; onPress: (v: string) => void }) {
  return (
    <View style={styles.unitToggle}>
      {options.map((opt) => (
        <TouchableOpacity
          key={opt}
          style={[styles.unitOption, active === opt && styles.unitOptionActive]}
          onPress={() => onPress(opt)}
          activeOpacity={0.8}
        >
          <Text style={[styles.unitOptionText, active === opt && styles.unitOptionTextActive]}>{opt}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

export default function EditPreferencesScreen({ navigation }: Props) {
  const { user, profile, refreshProfile } = useAuth();
  const [saving, setSaving] = useState(false);

  const [name, setName] = useState(profile?.displayName ?? '');
  const [age, setAge] = useState(profile?.age ? String(profile.age) : '');

  const [sex, setSex] = useState<Sex | ''>(profile?.sex ?? '');
  const [heightUnit, setHeightUnit] = useState<'cm' | 'in'>('cm');
  const [height, setHeight] = useState(profile?.heightCm ? String(Math.round(profile.heightCm * 10) / 10) : '');
  const [weightUnit, setWeightUnit] = useState<'kg' | 'lb'>('kg');
  const [weight, setWeight] = useState(profile?.weightKg ? String(Math.round(profile.weightKg * 10) / 10) : '');

  const [activityLevel, setActivityLevel] = useState<ActivityLevel | ''>(profile?.activityLevel ?? '');
  const [healthGoal, setHealthGoal] = useState<HealthGoal | ''>(profile?.healthGoal ?? '');

  const [allergies, setAllergies] = useState<string[]>(profile?.allergies ?? []);
  const [allergyOther, setAllergyOther] = useState('');
  const [dietaryIdentity, setDietaryIdentity] = useState<string[]>(profile?.dietaryIdentity ?? []);
  const [dietOther, setDietOther] = useState('');
  const [conditions, setConditions] = useState<string[]>(profile?.conditions ?? []);
  const [conditionOther, setConditionOther] = useState('');
  const [nutritionalFocus, setNutritionalFocus] = useState<string[]>(profile?.nutritionalFocus ?? []);
  const [focusOther, setFocusOther] = useState('');

  const customAllergies = allergies.filter((v) => !ALLERGEN_OPTIONS.find((o) => o.value === v));
  const customDiet = dietaryIdentity.filter((v) => v !== 'none' && !DIET_OPTIONS.find((o) => o.value === v));
  const customConditions = conditions.filter((v) => v !== 'none' && !CONDITION_OPTIONS.find((o) => o.value === v));
  const customFocus = nutritionalFocus.filter((v) => v !== 'none' && !FOCUS_OPTIONS.find((o) => o.value === v));

  const toggle = (list: string[], setList: (v: string[]) => void, value: string) => {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  };

  const toggleWithNone = (list: string[], setList: (v: string[]) => void, value: string) => {
    if (value === 'none') {
      setList(list.includes('none') ? [] : ['none']);
    } else {
      const withoutNone = list.filter((v) => v !== 'none');
      setList(withoutNone.includes(value) ? withoutNone.filter((v) => v !== value) : [...withoutNone, value]);
    }
  };

  const addOther = (text: string, list: string[], setList: (v: string[]) => void) => {
    const values = text.split(',').map((v) => v.trim()).filter(Boolean);
    const toAdd = values.filter((v) => !list.includes(v));
    if (toAdd.length > 0) setList([...list.filter((v) => v !== 'none'), ...toAdd]);
  };

  const toggleHeightUnit = (newUnit: string) => {
    if (newUnit === heightUnit) return;
    if (height) {
      const num = parseFloat(height);
      if (!isNaN(num)) setHeight(newUnit === 'in' ? (num / 2.54).toFixed(1) : (num * 2.54).toFixed(1));
    }
    setHeightUnit(newUnit as 'cm' | 'in');
  };

  const toggleWeightUnit = (newUnit: string) => {
    if (newUnit === weightUnit) return;
    if (weight) {
      const num = parseFloat(weight);
      if (!isNaN(num)) setWeight(newUnit === 'lb' ? (num / 0.453592).toFixed(1) : (num * 0.453592).toFixed(1));
    }
    setWeightUnit(newUnit as 'kg' | 'lb');
  };

  const handleSave = async () => {
    if (!user) return;
    if (!name.trim()) {
      Alert.alert('Name required', 'Please enter your name.');
      return;
    }
    setSaving(true);
    try {
      const heightCm = height
        ? (heightUnit === 'cm' ? parseFloat(height) : parseFloat(height) * 2.54)
        : undefined;
      const weightKg = weight
        ? (weightUnit === 'kg' ? parseFloat(weight) : parseFloat(weight) * 0.453592)
        : undefined;

      const updates: Partial<StudentProfile> = {
        displayName: name.trim(),
        age: age ? parseInt(age, 10) : undefined,
        sex: sex || undefined,
        heightCm,
        weightKg,
        activityLevel: activityLevel || undefined,
        healthGoal: healthGoal || undefined,
        allergies: allergies.filter((v) => v !== 'none'),
        dietaryIdentity: dietaryIdentity.filter((v) => v !== 'none'),
        conditions: conditions.filter((v) => v !== 'none'),
        nutritionalFocus: nutritionalFocus.filter((v) => v !== 'none'),
      };
      await setDoc(doc(db, 'users', user.uid), updates, { merge: true });
      await refreshProfile();
      navigation.goBack();
    } catch (err) {
      console.error('Edit profile error:', err);
      Alert.alert('Error', 'Could not save your profile. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Edit Profile</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">

        <Text style={styles.sectionHeader}>Personal Info</Text>
        <View style={styles.card}>
          <Text style={styles.label}>Name</Text>
          <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="Your name" placeholderTextColor={colors.textLight} />
          <Text style={styles.label}>Age (optional)</Text>
          <TextInput style={styles.input} value={age} onChangeText={setAge} placeholder="e.g. 20" placeholderTextColor={colors.textLight} keyboardType="number-pad" />
        </View>

        <Text style={styles.sectionHeader}>Body Stats</Text>
        <View style={styles.card}>
          <Text style={styles.label}>Sex</Text>
          <View style={styles.columnList}>
            {(['male', 'female', 'undisclosed'] as Sex[]).map((s) => (
              <OptionCard
                key={s}
                label={s === 'undisclosed' ? 'Prefer not to say' : s.charAt(0).toUpperCase() + s.slice(1)}
                selected={sex === s}
                onPress={() => setSex(s)}
              />
            ))}
          </View>
          <View style={styles.labelRow}>
            <Text style={styles.label}>Height (optional)</Text>
            <UnitToggle options={['cm', 'in']} active={heightUnit} onPress={toggleHeightUnit} />
          </View>
          <TextInput
            style={styles.input}
            value={height}
            onChangeText={setHeight}
            placeholder={heightUnit === 'cm' ? 'e.g. 170' : 'e.g. 67.0'}
            placeholderTextColor={colors.textLight}
            keyboardType="decimal-pad"
          />
          <View style={styles.labelRow}>
            <Text style={styles.label}>Weight (optional)</Text>
            <UnitToggle options={['kg', 'lb']} active={weightUnit} onPress={toggleWeightUnit} />
          </View>
          <TextInput
            style={styles.input}
            value={weight}
            onChangeText={setWeight}
            placeholder={weightUnit === 'kg' ? 'e.g. 65' : 'e.g. 143.0'}
            placeholderTextColor={colors.textLight}
            keyboardType="decimal-pad"
          />
        </View>

        <Text style={styles.sectionHeader}>Activity & Goals</Text>
        <View style={styles.card}>
          <Text style={styles.label}>Activity Level</Text>
          <View style={styles.columnList}>
            {([
              { value: 'sedentary', label: 'Sedentary' },
              { value: 'light', label: 'Lightly Active' },
              { value: 'moderate', label: 'Moderately Active' },
              { value: 'very_active', label: 'Very Active' },
            ] as { value: ActivityLevel; label: string }[]).map((opt) => (
              <OptionCard key={opt.value} label={opt.label} selected={activityLevel === opt.value} onPress={() => setActivityLevel(opt.value)} />
            ))}
          </View>
          <Text style={[styles.label, { marginTop: 16 }]}>Health Goal</Text>
          <View style={styles.columnList}>
            {([
              { value: 'lose_weight', label: 'Lose Weight' },
              { value: 'maintain', label: 'Maintain Weight' },
              { value: 'gain_muscle', label: 'Gain Muscle' },
              { value: 'energy', label: 'Improve Energy' },
              { value: 'wellness', label: 'General Wellness' },
            ] as { value: HealthGoal; label: string }[]).map((opt) => (
              <OptionCard key={opt.value} label={opt.label} selected={healthGoal === opt.value} onPress={() => setHealthGoal(opt.value)} />
            ))}
          </View>
        </View>

        <Text style={styles.sectionHeader}>Allergies</Text>
        <View style={styles.card}>
          <View style={styles.chipWrap}>
            {ALLERGEN_OPTIONS.map((opt) => (
              <Chip key={opt.value} label={opt.label} selected={allergies.includes(opt.value)} onPress={() => toggle(allergies, setAllergies, opt.value)} />
            ))}
            {customAllergies.map((v) => (
              <Chip key={v} label={v} selected onPress={() => toggle(allergies, setAllergies, v)} />
            ))}
          </View>
          <View style={styles.otherRow}>
            <TextInput
              style={styles.otherInput}
              value={allergyOther}
              onChangeText={setAllergyOther}
              placeholder="Other (comma-separated)"
              placeholderTextColor={colors.textLight}
              returnKeyType="done"
              onSubmitEditing={() => { addOther(allergyOther, allergies, setAllergies); setAllergyOther(''); }}
            />
            <TouchableOpacity style={styles.addBtn} onPress={() => { addOther(allergyOther, allergies, setAllergies); setAllergyOther(''); }}>
              <Text style={styles.addBtnText}>Add</Text>
            </TouchableOpacity>
          </View>
        </View>

        <Text style={styles.sectionHeader}>Dietary Preferences</Text>
        <View style={styles.card}>
          <View style={styles.chipWrap}>
            <Chip label="None" selected={dietaryIdentity.includes('none')} onPress={() => toggleWithNone(dietaryIdentity, setDietaryIdentity, 'none')} />
            {DIET_OPTIONS.map((opt) => (
              <Chip key={opt.value} label={opt.label} selected={dietaryIdentity.includes(opt.value)} onPress={() => toggleWithNone(dietaryIdentity, setDietaryIdentity, opt.value)} />
            ))}
            {customDiet.map((v) => (
              <Chip key={v} label={v} selected onPress={() => toggleWithNone(dietaryIdentity, setDietaryIdentity, v)} />
            ))}
          </View>
          <View style={styles.otherRow}>
            <TextInput
              style={styles.otherInput}
              value={dietOther}
              onChangeText={setDietOther}
              placeholder="Other (comma-separated)"
              placeholderTextColor={colors.textLight}
              returnKeyType="done"
              onSubmitEditing={() => { addOther(dietOther, dietaryIdentity, setDietaryIdentity); setDietOther(''); }}
            />
            <TouchableOpacity style={styles.addBtn} onPress={() => { addOther(dietOther, dietaryIdentity, setDietaryIdentity); setDietOther(''); }}>
              <Text style={styles.addBtnText}>Add</Text>
            </TouchableOpacity>
          </View>
        </View>

        <Text style={styles.sectionHeader}>Health Conditions</Text>
        <View style={styles.card}>
          <View style={styles.chipWrap}>
            <Chip label="None" selected={conditions.includes('none')} onPress={() => toggleWithNone(conditions, setConditions, 'none')} />
            {CONDITION_OPTIONS.map((opt) => (
              <Chip key={opt.value} label={opt.label} selected={conditions.includes(opt.value)} onPress={() => toggleWithNone(conditions, setConditions, opt.value)} />
            ))}
            {customConditions.map((v) => (
              <Chip key={v} label={v} selected onPress={() => toggleWithNone(conditions, setConditions, v)} />
            ))}
          </View>
          <View style={styles.otherRow}>
            <TextInput
              style={styles.otherInput}
              value={conditionOther}
              onChangeText={setConditionOther}
              placeholder="Other (comma-separated)"
              placeholderTextColor={colors.textLight}
              returnKeyType="done"
              onSubmitEditing={() => { addOther(conditionOther, conditions, setConditions); setConditionOther(''); }}
            />
            <TouchableOpacity style={styles.addBtn} onPress={() => { addOther(conditionOther, conditions, setConditions); setConditionOther(''); }}>
              <Text style={styles.addBtnText}>Add</Text>
            </TouchableOpacity>
          </View>
        </View>

        <Text style={styles.sectionHeader}>Nutritional Focus</Text>
        <View style={styles.card}>
          <View style={styles.chipWrap}>
            <Chip label="None" selected={nutritionalFocus.includes('none')} onPress={() => toggleWithNone(nutritionalFocus, setNutritionalFocus, 'none')} />
            {FOCUS_OPTIONS.map((opt) => (
              <Chip key={opt.value} label={opt.label} selected={nutritionalFocus.includes(opt.value)} onPress={() => toggleWithNone(nutritionalFocus, setNutritionalFocus, opt.value)} />
            ))}
            {customFocus.map((v) => (
              <Chip key={v} label={v} selected onPress={() => toggleWithNone(nutritionalFocus, setNutritionalFocus, v)} />
            ))}
          </View>
          <View style={styles.otherRow}>
            <TextInput
              style={styles.otherInput}
              value={focusOther}
              onChangeText={setFocusOther}
              placeholder="Other (comma-separated)"
              placeholderTextColor={colors.textLight}
              returnKeyType="done"
              onSubmitEditing={() => { addOther(focusOther, nutritionalFocus, setNutritionalFocus); setFocusOther(''); }}
            />
            <TouchableOpacity style={styles.addBtn} onPress={() => { addOther(focusOther, nutritionalFocus, setNutritionalFocus); setFocusOther(''); }}>
              <Text style={styles.addBtnText}>Add</Text>
            </TouchableOpacity>
          </View>
        </View>

        <TouchableOpacity style={styles.saveBtn} onPress={handleSave} disabled={saving}>
          {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveBtnText}>Save Changes</Text>}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.border },
  backBtn: { width: 70 },
  backText: { color: colors.primary, fontSize: 16, fontWeight: '600' },
  headerTitle: { flex: 1, textAlign: 'center', fontSize: 17, fontWeight: '700', color: colors.text },
  content: { padding: 20, paddingBottom: 48, gap: 8 },
  sectionHeader: { fontSize: 13, fontWeight: '700', color: colors.textLight, letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 12, marginBottom: 4, marginLeft: 4 },
  card: { backgroundColor: colors.card, borderRadius: 16, padding: 18, gap: 10 },
  label: { fontSize: 14, fontWeight: '600', color: colors.text },
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
  labelRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  unitToggle: { flexDirection: 'row', borderRadius: 8, overflow: 'hidden', borderWidth: 1, borderColor: colors.border },
  unitOption: { paddingHorizontal: 12, paddingVertical: 5, backgroundColor: colors.background },
  unitOptionActive: { backgroundColor: colors.primary },
  unitOptionText: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  unitOptionTextActive: { color: '#fff' },
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
  otherRow: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  otherInput: {
    flex: 1,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: colors.text,
  },
  addBtn: { backgroundColor: colors.primary, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10 },
  addBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  saveBtn: {
    backgroundColor: colors.primary,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 16,
  },
  saveBtnText: { color: '#fff', fontSize: 17, fontWeight: '700' },
});
