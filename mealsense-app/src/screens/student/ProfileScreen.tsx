import React from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, SafeAreaView, ScrollView, Alert,
} from 'react-native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import { signOut } from 'firebase/auth';
import { auth } from '../../config/firebase';
import { useAuth } from '../../contexts/AuthContext';
import { colors } from '../../constants/colors';
import { ProfileStackParamList } from '../../types';

type Props = { navigation: NativeStackNavigationProp<ProfileStackParamList, 'ProfileMain'> };

const GOAL_LABELS: Record<string, string> = {
  lose_weight: 'Lose Weight',
  maintain: 'Maintain',
  gain_muscle: 'Gain Muscle',
  energy: 'Improve Energy',
  wellness: 'General Wellness',
};

const ACTIVITY_LABELS: Record<string, string> = {
  sedentary: 'Sedentary',
  light: 'Lightly Active',
  moderate: 'Moderately Active',
  very_active: 'Very Active',
};

function ProfileRow({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

function TagList({ label, values }: { label: string; values: string[] }) {
  if (!values.length) return null;
  return (
    <View style={styles.tagSection}>
      <Text style={styles.tagSectionLabel}>{label}</Text>
      <View style={styles.tagRow}>
        {values.map((v) => (
          <View key={v} style={styles.tag}>
            <Text style={styles.tagText}>{v.replace(/_/g, ' ')}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

export default function ProfileScreen({ navigation }: Props) {
  const { profile } = useAuth();

  const handleSignOut = () => {
    Alert.alert('Sign Out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign Out', style: 'destructive', onPress: () => signOut(auth) },
    ]);
  };

  const initials = (profile?.displayName ?? '?')
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.content}>
        {/* Avatar */}
        <View style={styles.avatarSection}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initials}</Text>
          </View>
          <Text style={styles.displayName}>{profile?.displayName ?? '—'}</Text>
          <Text style={styles.email}>{profile?.email ?? '—'}</Text>
          <TouchableOpacity style={styles.editBtn} onPress={() => navigation.navigate('EditProfile')}>
            <Ionicons name="pencil-outline" size={15} color={colors.primary} />
            <Text style={styles.editBtnText}>Edit Profile</Text>
          </TouchableOpacity>
        </View>

        {/* Body stats */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Body Stats</Text>
          <ProfileRow label="Age" value={profile?.age ? `${profile.age} years` : undefined} />
          <ProfileRow label="Sex" value={profile?.sex ? profile.sex.charAt(0).toUpperCase() + profile.sex.slice(1) : undefined} />
          <ProfileRow label="Height" value={profile?.heightCm ? `${profile.heightCm} cm` : undefined} />
          <ProfileRow label="Weight" value={profile?.weightKg ? `${profile.weightKg} kg` : undefined} />
          <ProfileRow label="Activity" value={profile?.activityLevel ? ACTIVITY_LABELS[profile.activityLevel] : undefined} />
          <ProfileRow label="Goal" value={profile?.healthGoal ? GOAL_LABELS[profile.healthGoal] : undefined} />
          {!profile?.age && !profile?.sex && (
            <Text style={styles.emptyNote}>No body stats set yet.</Text>
          )}
        </View>

        {/* Dietary profile */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Dietary Profile</Text>
          <TagList label="Allergies" values={profile?.allergies ?? []} />
          <TagList label="Diet" values={profile?.dietaryIdentity ?? []} />
          <TagList label="Conditions" values={profile?.conditions ?? []} />
          <TagList label="Nutritional focus" values={profile?.nutritionalFocus ?? []} />
          {!profile?.allergies?.length && !profile?.dietaryIdentity?.length && !profile?.conditions?.length && !profile?.nutritionalFocus?.length && (
            <Text style={styles.emptyNote}>No dietary preferences set yet.</Text>
          )}
        </View>

        {/* Sign out */}
        <TouchableOpacity style={styles.signOutBtn} onPress={handleSignOut}>
          <Text style={styles.signOutText}>Sign Out</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, gap: 16, paddingBottom: 40 },
  avatarSection: { alignItems: 'center', paddingVertical: 24 },
  avatar: { width: 80, height: 80, borderRadius: 40, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  avatarText: { fontSize: 28, fontWeight: '800', color: '#fff' },
  displayName: { fontSize: 22, fontWeight: '800', color: colors.text, marginBottom: 4 },
  email: { fontSize: 15, color: colors.textSecondary, marginBottom: 14 },
  editBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 18, paddingVertical: 9, borderRadius: 20, borderWidth: 1.5, borderColor: colors.primary, backgroundColor: colors.primary + '10' },
  editBtnText: { color: colors.primary, fontSize: 14, fontWeight: '700' },
  card: { backgroundColor: colors.card, borderRadius: 16, padding: 20, gap: 4 },
  cardTitle: { fontSize: 16, fontWeight: '700', color: colors.text, marginBottom: 12 },
  row: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.border },
  rowLabel: { fontSize: 15, color: colors.textSecondary },
  rowValue: { fontSize: 15, color: colors.text, fontWeight: '600' },
  tagSection: { marginBottom: 12 },
  tagSectionLabel: { fontSize: 13, fontWeight: '600', color: colors.textSecondary, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tag: { backgroundColor: colors.primaryLight + '25', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 },
  tagText: { fontSize: 13, color: colors.primary, fontWeight: '600', textTransform: 'capitalize' },
  emptyNote: { fontSize: 14, color: colors.textLight, fontStyle: 'italic' },
  signOutBtn: { backgroundColor: colors.error + '15', borderWidth: 1, borderColor: colors.error, borderRadius: 14, paddingVertical: 16, alignItems: 'center', marginTop: 8 },
  signOutText: { color: colors.error, fontSize: 16, fontWeight: '700' },
});
