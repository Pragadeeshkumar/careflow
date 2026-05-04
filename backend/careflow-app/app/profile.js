import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TextInput, Pressable, ActivityIndicator, Alert, StatusBar, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { ArrowLeft, Save, User, Phone, Droplet, Calendar } from 'lucide-react-native';
import { API_BASE_URL } from '../constants/api';
export default function ProfileScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ full_name: '', phone: '', blood_group: '', date_of_birth: '' });

  const loadProfile = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/patient/profile`, {
        headers: { Authorization: `Bearer ${global.authToken}` },
      });
      const data = await res.json();
      if (res.ok) {
        setForm({
          full_name: data.full_name || '',
          phone: data.phone || '',
          blood_group: data.blood_group || '',
          date_of_birth: data.date_of_birth || '',
        });
      } else {
        Alert.alert('Profile error', data.error || 'Unable to load profile');
      }
    } catch (_err) {
      Alert.alert('Error', 'Cannot connect to server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const updateField = (name, value) => setForm((current) => ({ ...current, [name]: value }));

  const saveProfile = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/patient/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${global.authToken}`,
        },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (res.ok) {
        Alert.alert('Saved', 'Your profile has been updated.');
      } else {
        Alert.alert('Save failed', data.error || 'Unable to update profile');
      }
    } catch (_err) {
      Alert.alert('Error', 'Cannot connect to server.');
    } finally {
      setSaving(false);
    }
  };

  const fields = [
    { key: 'full_name', label: 'Full Name', icon: User, placeholder: 'Your name' },
    { key: 'phone', label: 'Phone', icon: Phone, placeholder: 'Phone number' },
    { key: 'blood_group', label: 'Blood Group', icon: Droplet, placeholder: 'O+' },
    { key: 'date_of_birth', label: 'Date of Birth', icon: Calendar, placeholder: 'YYYY-MM-DD' },
  ];

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <View>
            <Text style={styles.eyebrow}>Account</Text>
            <Text style={styles.title}>Profile</Text>
          </View>
          <Pressable onPress={() => router.push('/dashboard')} style={styles.iconButton}>
            <ArrowLeft color="#3b82f6" size={22} />
          </Pressable>
        </View>

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator color="#3b82f6" size="large" />
            <Text style={styles.muted}>Loading profile...</Text>
          </View>
        ) : (
          <View style={styles.card}>
            {fields.map((field) => {
              const Icon = field.icon;
              return (
                <View key={field.key} style={styles.fieldBlock}>
                  <Text style={styles.label}>{field.label}</Text>
                  <View style={styles.inputWrap}>
                    <Icon color="#3b82f6" size={20} />
                    <TextInput
                      style={styles.input}
                      placeholder={field.placeholder}
                      placeholderTextColor="#64748b"
                      value={form[field.key]}
                      onChangeText={(text) => updateField(field.key, text)}
                      autoCapitalize="none"
                    />
                  </View>
                </View>
              );
            })}

            <Pressable onPress={saveProfile} disabled={saving} style={[styles.primaryButton, saving && { opacity: 0.7 }]}>
              <Save color="#ffffff" size={20} />
              <Text style={styles.primaryButtonText}>{saving ? 'Saving...' : 'Save Changes'}</Text>
            </Pressable>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  content: { padding: 24 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 },
  eyebrow: { color: '#94a3b8', fontSize: 14 },
  title: { color: '#ffffff', fontSize: 28, fontWeight: 'bold' },
  iconButton: { padding: 10, backgroundColor: '#1e293b', borderRadius: 12, borderWidth: 1, borderColor: '#334155' },
  center: { paddingVertical: 32, alignItems: 'center' },
  muted: { color: '#94a3b8', marginTop: 14 },
  card: { backgroundColor: '#1e293b', borderRadius: 24, padding: 24, borderWidth: 1, borderColor: '#334155' },
  fieldBlock: { marginBottom: 18 },
  label: { color: '#ffffff', fontSize: 14, fontWeight: '700', marginBottom: 8 },
  inputWrap: { height: 58, flexDirection: 'row', alignItems: 'center', backgroundColor: '#111827', borderRadius: 16, paddingHorizontal: 16, borderWidth: 1, borderColor: '#334155' },
  input: { flex: 1, color: '#ffffff', fontSize: 16, marginLeft: 12 },
  primaryButton: { marginTop: 10, height: 56, borderRadius: 16, backgroundColor: '#3b82f6', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10 },
  primaryButtonText: { color: '#ffffff', fontSize: 16, fontWeight: '800' },
});
