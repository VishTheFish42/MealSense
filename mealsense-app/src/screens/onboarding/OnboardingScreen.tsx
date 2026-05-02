import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, SafeAreaView, Alert, ActivityIndicator,
} from 'react-native';
import { doc, setDoc } from 'firebase/firestore';
import { signOut } from 'firebase/auth';
import { auth, db } from '../../config/firebase';
import { useAuth } from '../../contexts/AuthContext';
import { colors } from '../../constants/colors';
import {
  Sex, ActivityLevel, HealthGoal, StudentProfile,
} from '../../types';

const TOTAL_STEPS = 7;

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
    <TouchableOpacity
      style={[styles.chip, selected && styles.chipSelected]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{label}</Text>
    </TouchableOpacity>
  );
}

function OptionCard({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <TouchableOpacity
      style={[styles.optionCard, selected && styles.optionCardSelected]}
      onPress={onPress}
      activeOpacity={0.7}
    >
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

export default function OnboardingScreen() {
  const { user, refreshProfile } = useAuth();
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);

  // Step 1 — Name & age
  const [name, setName] = useState('');
  const [age, setAge] = useState('');

  // Step 2 — Body stats
  const [sex, setSex] = useState<Sex | ''>('');
  const [height, setHeight] = useState('');
  const [heightUnit, setHeightUnit] = useState<'cm' | 'in'>('cm');
  const [weight, setWeight] = useState('');
  const [weightUnit, setWeightUnit] = useState<'kg' | 'lb'>('kg');

  // Step 3 — Activity & goal
  const [activityLevel, setActivityLevel] = useState<ActivityLevel | ''>('');
  const [healthGoal, setHealthGoal] = useState<HealthGoal | ''>('');

  // Steps 4–7 — Multi-select + other inputs
  const [allergies, setAllergies] = useState<string[]>([]);
  const [allergyOther, setAllergyOther] = useState('');

  const [dietaryIdentity, setDietaryIdentity] = useState<string[]>([]);
  const [dietOther, setDietOther] = useState('');

  const [conditions, setConditions] = useState<string[]>([]);
  const [conditionOther, setConditionOther] = useState('');

  const [nutritionalFocus, setNutritionalFocus] = useState<string[]>([]);
  const [focusOther, setFocusOther] = useState('');

  // Derived custom (user-added) values not in the preset lists
  const customAllergies = allergies.filter((v) => !ALLERGEN_OPTIONS.find((o) => o.value === v));
  const customDiet = dietaryIdentity.filter((v) => v !== 'none' && !DIET_OPTIONS.find((o) => o.value === v));
  const customConditions = conditions.filter((v) => v !== 'none' && !CONDITION_OPTIONS.find((o) => o.value === v));
  const customFocus = nutritionalFocus.filter((v) => v !== 'none' && !FOCUS_OPTIONS.find((o) => o.value === v));

  const toggle = (list: string[], setList: (v: string[]) => void, value: string) => {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  };

  // For lists that have a "None" option — selecting None clears others, selecting others clears None
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
      if (!isNaN(num)) {
        setHeight(newUnit === 'in' ? (num / 2.54).toFixed(1) : (num * 2.54).toFixed(1));
      }
    }
    setHeightUnit(newUnit as 'cm' | 'in');
  };

  const toggleWeightUnit = (newUnit: string) => {
    if (newUnit === weightUnit) return;
    if (weight) {
      const num = parseFloat(weight);
      if (!isNaN(num)) {
        setWeight(newUnit === 'lb' ? (num / 0.453592).toFixed(1) : (num * 0.453592).toFixed(1));
      }
    }
    setWeightUnit(newUnit as 'kg' | 'lb');
  };

  const canAdvance = () => {
    if (step === 1) return name.trim().length > 0;
    if (step === 2) return sex !== '';
    if (step === 3) return activityLevel !== '' && healthGoal !== '';
    return true;
  };

  const handleNext = () => {
    if (step < TOTAL_STEPS) {
      setStep(step + 1);
    } else {
      handleSave();
    }
  };

  const handleSave = async () => {
    if (!user) return;
    setSaving(true);
    try {
      const heightCm = height
        ? (heightUnit === 'cm' ? parseFloat(height) : parseFloat(height) * 2.54)
        : undefined;
      const weightKg = weight
        ? (weightUnit === 'kg' ? parseFloat(weight) : parseFloat(weight) * 0.453592)
        : undefined;

      const updates: Partial<StudentProfile> = {
        displayName: name.trim() || undefined,
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
        onboardingComplete: true,
      };
      await setDoc(doc(db, 'users', user.uid), updates, { merge: true });
      await refreshProfile();
    } catch (err) {
      console.error('Onboarding save error:', err);
      Alert.alert('Error', 'Could not save your profile. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const progress = step / TOTAL_STEPS;

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.progressTrack}>
        <View style={[styles.progressFill, { width: `${progress * 100}%` }]} />
      </View>
      <View style={styles.stepRow}>
        <Text style={styles.stepIndicator}>Step {step} of {TOTAL_STEPS}</Text>
        <TouchableOpacity style={styles.signOutBtn} onPress={() => signOut(auth)}>
          <Text style={styles.signOutBtnText}>Sign Out</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">

        {step === 1 && (
          <>
            <Text style={styles.stepTitle}>Tell us about yourself</Text>
            <Text style={styles.stepSubtitle}>This helps us personalize your experience.</Text>
            <Text style={styles.label}>First Name *</Text>
            <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="Your name" placeholderTextColor={colors.textLight} />
            <Text style={styles.label}>Age (optional)</Text>
            <TextInput style={styles.input} value={age} onChangeText={setAge} placeholder="e.g. 20" placeholderTextColor={colors.textLight} keyboardType="number-pad" />
          </>
        )}

        {step === 2 && (
          <>
            <Text style={styles.stepTitle}>Your body stats</Text>
            <Text style={styles.stepSubtitle}>Used to calculate your daily calorie target.</Text>
            <Text style={styles.label}>Sex *</Text>
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
              <Text style={styles.labelInline}>Height (optional)</Text>
              <UnitToggle options={['cm', 'in']} active={heightUnit} onPress={toggleHeightUnit} />
            </View>
            <TextInput
              style={styles.input}
              value={height}
              onChangeText={setHeight}
              placeholder={heightUnit === 'cm' ? 'e.g. 175' : 'e.g. 68.9'}
              placeholderTextColor={colors.textLight}
              keyboardType="decimal-pad"
            />

            <View style={styles.labelRow}>
              <Text style={styles.labelInline}>Weight (optional)</Text>
              <UnitToggle options={['kg', 'lb']} active={weightUnit} onPress={toggleWeightUnit} />
            </View>
            <TextInput
              style={styles.input}
              value={weight}
              onChangeText={setWeight}
              placeholder={weightUnit === 'kg' ? 'e.g. 70' : 'e.g. 154.3'}
              placeholderTextColor={colors.textLight}
              keyboardType="decimal-pad"
            />
          </>
        )}

        {step === 3 && (
          <>
            <Text style={styles.stepTitle}>Activity & goal</Text>
            <Text style={styles.stepSubtitle}>We'll tailor calorie recommendations accordingly.</Text>
            <Text style={styles.label}>Activity level *</Text>
            <View style={styles.columnList}>
              {([
                { value: 'sedentary', label: 'Sedentary — mostly sitting' },
                { value: 'light', label: 'Lightly active — light exercise 1–3×/week' },
                { value: 'moderate', label: 'Moderately active — exercise 3–5×/week' },
                { value: 'very_active', label: 'Very active — hard exercise 6–7×/week' },
              ] as { value: ActivityLevel; label: string }[]).map((opt) => (
                <OptionCard key={opt.value} label={opt.label} selected={activityLevel === opt.value} onPress={() => setActivityLevel(opt.value)} />
              ))}
            </View>
            <Text style={styles.label}>Health goal *</Text>
            <View style={styles.columnList}>
              {([
                { value: 'lose_weight', label: 'Lose weight' },
                { value: 'maintain', label: 'Maintain' },
                { value: 'gain_muscle', label: 'Gain muscle' },
                { value: 'energy', label: 'Improve energy' },
                { value: 'wellness', label: 'General wellness' },
              ] as { value: HealthGoal; label: string }[]).map((opt) => (
                <OptionCard key={opt.value} label={opt.label} selected={healthGoal === opt.value} onPress={() => setHealthGoal(opt.value)} />
              ))}
            </View>
          </>
        )}

        {step === 4 && (
          <>
            <Text style={styles.stepTitle}>Any allergies?</Text>
            <Text style={styles.stepSubtitle}>These are hard filters — we'll never recommend items containing them.</Text>
            <View style={styles.chipWrap}>
              {ALLERGEN_OPTIONS.map((o) => (
                <Chip key={o.value} label={o.label} selected={allergies.includes(o.value)} onPress={() => toggle(allergies, setAllergies, o.value)} />
              ))}
              {customAllergies.map((v) => (
                <Chip key={v} label={v} selected onPress={() => toggle(allergies, setAllergies, v)} />
              ))}
            </View>
            <Text style={styles.otherLabel}>Other</Text>
            <View style={styles.otherRow}>
              <TextInput
                style={[styles.input, styles.otherInput]}
                value={allergyOther}
                onChangeText={setAllergyOther}
                placeholder="e.g. Mustard, Celery"
                placeholderTextColor={colors.textLight}
                returnKeyType="done"
                onSubmitEditing={() => { addOther(allergyOther, allergies, setAllergies); setAllergyOther(''); }}
              />
              <TouchableOpacity style={styles.addBtn} onPress={() => { addOther(allergyOther, allergies, setAllergies); setAllergyOther(''); }}>
                <Text style={styles.addBtnText}>Add</Text>
              </TouchableOpacity>
            </View>
          </>
        )}

        {step === 5 && (
          <>
            <Text style={styles.stepTitle}>Dietary preferences</Text>
            <Text style={styles.stepSubtitle}>We'll only recommend items that match.</Text>
            <View style={styles.chipWrap}>
              <Chip label="None" selected={dietaryIdentity.includes('none')} onPress={() => toggleWithNone(dietaryIdentity, setDietaryIdentity, 'none')} />
              {DIET_OPTIONS.map((o) => (
                <Chip key={o.value} label={o.label} selected={dietaryIdentity.includes(o.value)} onPress={() => toggleWithNone(dietaryIdentity, setDietaryIdentity, o.value)} />
              ))}
              {customDiet.map((v) => (
                <Chip key={v} label={v} selected onPress={() => toggleWithNone(dietaryIdentity, setDietaryIdentity, v)} />
              ))}
            </View>
            <Text style={styles.otherLabel}>Other</Text>
            <View style={styles.otherRow}>
              <TextInput
                style={[styles.input, styles.otherInput]}
                value={dietOther}
                onChangeText={setDietOther}
                placeholder="e.g. Jain, Raw food"
                placeholderTextColor={colors.textLight}
                returnKeyType="done"
                onSubmitEditing={() => { addOther(dietOther, dietaryIdentity, setDietaryIdentity); setDietOther(''); }}
              />
              <TouchableOpacity style={styles.addBtn} onPress={() => { addOther(dietOther, dietaryIdentity, setDietaryIdentity); setDietOther(''); }}>
                <Text style={styles.addBtnText}>Add</Text>
              </TouchableOpacity>
            </View>
          </>
        )}

        {step === 6 && (
          <>
            <Text style={styles.stepTitle}>Any health conditions?</Text>
            <Text style={styles.stepSubtitle}>These adjust the scoring weights — they never block items.</Text>
            <View style={styles.columnList}>
              <OptionCard label="None" selected={conditions.includes('none')} onPress={() => toggleWithNone(conditions, setConditions, 'none')} />
              {CONDITION_OPTIONS.map((o) => (
                <OptionCard key={o.value} label={o.label} selected={conditions.includes(o.value)} onPress={() => toggleWithNone(conditions, setConditions, o.value)} />
              ))}
            </View>
            {customConditions.length > 0 && (
              <View style={[styles.chipWrap, { marginTop: 12 }]}>
                {customConditions.map((v) => (
                  <Chip key={v} label={v} selected onPress={() => toggleWithNone(conditions, setConditions, v)} />
                ))}
              </View>
            )}
            <Text style={styles.otherLabel}>Other</Text>
            <View style={styles.otherRow}>
              <TextInput
                style={[styles.input, styles.otherInput]}
                value={conditionOther}
                onChangeText={setConditionOther}
                placeholder="e.g. Celiac disease, Crohn's"
                placeholderTextColor={colors.textLight}
                returnKeyType="done"
                onSubmitEditing={() => { addOther(conditionOther, conditions, setConditions); setConditionOther(''); }}
              />
              <TouchableOpacity style={styles.addBtn} onPress={() => { addOther(conditionOther, conditions, setConditions); setConditionOther(''); }}>
                <Text style={styles.addBtnText}>Add</Text>
              </TouchableOpacity>
            </View>
          </>
        )}

        {step === 7 && (
          <>
            <Text style={styles.stepTitle}>Nutritional focus</Text>
            <Text style={styles.stepSubtitle}>Select anything you want to prioritize.</Text>
            <View style={styles.chipWrap}>
              <Chip label="None" selected={nutritionalFocus.includes('none')} onPress={() => toggleWithNone(nutritionalFocus, setNutritionalFocus, 'none')} />
              {FOCUS_OPTIONS.map((o) => (
                <Chip key={o.value} label={o.label} selected={nutritionalFocus.includes(o.value)} onPress={() => toggleWithNone(nutritionalFocus, setNutritionalFocus, o.value)} />
              ))}
              {customFocus.map((v) => (
                <Chip key={v} label={v} selected onPress={() => toggleWithNone(nutritionalFocus, setNutritionalFocus, v)} />
              ))}
            </View>
            <Text style={styles.otherLabel}>Other</Text>
            <View style={styles.otherRow}>
              <TextInput
                style={[styles.input, styles.otherInput]}
                value={focusOther}
                onChangeText={setFocusOther}
                placeholder="e.g. Omega-3, Anti-inflammatory"
                placeholderTextColor={colors.textLight}
                returnKeyType="done"
                onSubmitEditing={() => { addOther(focusOther, nutritionalFocus, setNutritionalFocus); setFocusOther(''); }}
              />
              <TouchableOpacity style={styles.addBtn} onPress={() => { addOther(focusOther, nutritionalFocus, setNutritionalFocus); setFocusOther(''); }}>
                <Text style={styles.addBtnText}>Add</Text>
              </TouchableOpacity>
            </View>
          </>
        )}

      </ScrollView>

      <View style={styles.footer}>
        {step > 1 && (
          <TouchableOpacity style={styles.backBtn} onPress={() => setStep(step - 1)}>
            <Text style={styles.backBtnText}>← Back</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity
          style={[styles.nextBtn, !canAdvance() && styles.nextBtnDisabled]}
          onPress={handleNext}
          disabled={!canAdvance() || saving}
        >
          {saving ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.nextBtnText}>{step === TOTAL_STEPS ? 'Finish Setup' : 'Next →'}</Text>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  progressTrack: { height: 4, backgroundColor: colors.border },
  progressFill: { height: 4, backgroundColor: colors.primary },
  stepRow: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', marginTop: 10, paddingHorizontal: 20 },
  stepIndicator: { flex: 1, textAlign: 'center', color: colors.textSecondary, fontSize: 13 },
  signOutBtn: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 10, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card },
  signOutBtnText: { color: colors.textSecondary, fontSize: 13, fontWeight: '600' },
  content: { padding: 24, paddingBottom: 120 },
  stepTitle: { fontSize: 26, fontWeight: '800', color: colors.text, marginBottom: 8, marginTop: 16 },
  stepSubtitle: { fontSize: 15, color: colors.textSecondary, marginBottom: 24, lineHeight: 22 },
  label: { fontSize: 14, fontWeight: '600', color: colors.text, marginBottom: 10, marginTop: 16 },
  labelInline: { fontSize: 14, fontWeight: '600', color: colors.text },
  labelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 16,
    marginBottom: 10,
  },
  input: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    color: colors.text,
  },
  // Unit toggle
  unitToggle: {
    flexDirection: 'row',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  unitOption: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    backgroundColor: colors.card,
  },
  unitOptionActive: { backgroundColor: colors.primary },
  unitOptionText: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
  unitOptionTextActive: { color: '#fff' },
  // Chips
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  chip: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 24,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.card,
  },
  chipSelected: { borderColor: colors.primary, backgroundColor: '#EDF7F2' },
  chipText: { fontSize: 15, color: colors.textSecondary, fontWeight: '500' },
  chipTextSelected: { color: colors.primary, fontWeight: '700' },
  // Option cards (always full-width in columnList)
  columnList: { gap: 10 },
  optionCard: {
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.card,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  optionCardSelected: { borderColor: colors.primary, backgroundColor: '#EDF7F2' },
  optionCardText: { fontSize: 15, color: colors.textSecondary, fontWeight: '500', flexShrink: 1 },
  optionCardTextSelected: { color: colors.primary, fontWeight: '700' },
  checkmark: { color: colors.primary, fontSize: 16, fontWeight: '700', marginLeft: 8 },
  // Other input
  otherLabel: { fontSize: 14, fontWeight: '600', color: colors.text, marginTop: 20, marginBottom: 8 },
  otherRow: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  otherInput: { flex: 1 },
  addBtn: {
    backgroundColor: colors.primary,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  addBtnText: { color: '#fff', fontWeight: '700', fontSize: 15 },
  // Footer
  footer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: 'row',
    padding: 20,
    paddingBottom: 36,
    backgroundColor: colors.background,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: 12,
  },
  backBtn: {
    flex: 1,
    paddingVertical: 16,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: 'center',
    backgroundColor: colors.card,
  },
  backBtnText: { fontSize: 16, fontWeight: '600', color: colors.text },
  nextBtn: {
    flex: 2,
    backgroundColor: colors.primary,
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
  },
  nextBtnDisabled: { backgroundColor: colors.disabled },
  nextBtnText: { color: '#fff', fontSize: 17, fontWeight: '700' },
});
