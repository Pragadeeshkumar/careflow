import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, Pressable, ActivityIndicator, Switch, StatusBar, StyleSheet, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { ArrowLeft, Bell, MapPin, CreditCard, Clock, Megaphone } from 'lucide-react-native';
import { API_BASE_URL } from '../constants/api';

const preferenceLabels = {
  countdown: 'Queue countdown',
  called: 'Token called',
  geofence: 'Geofence warnings',
  payment: 'Payment alerts',
  reminder: 'Appointment reminders',
};

const typeIcons = {
  countdown: Clock,
  called: Megaphone,
  geofence: MapPin,
  payment: CreditCard,
  reminder: Bell,
};

export default function NotificationsScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [preferences, setPreferences] = useState({});
  const [notifications, setNotifications] = useState([]);

  const loadNotifications = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/patient/notifications/history`, {
        headers: { Authorization: `Bearer ${global.authToken}` },
      });
      const data = await res.json();
      if (res.ok) {
        setNotifications(data.notifications || []);
        setPreferences(data.preferences || {});
      } else {
        Alert.alert('Notification error', data.error || 'Unable to load notifications');
      }
    } catch (_err) {
      Alert.alert('Error', 'Cannot connect to server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNotifications();
  }, []);

  const togglePreference = async (key) => {
    const next = { ...preferences, [key]: !preferences[key] };
    setPreferences(next);
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/patient/notifications/preferences`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${global.authToken}`,
        },
        body: JSON.stringify({ preferences: next }),
      });
      const data = await res.json();
      if (res.ok) {
        setPreferences(data.preferences || next);
      } else {
        Alert.alert('Save failed', data.error || 'Unable to update preferences');
      }
    } catch (_err) {
      Alert.alert('Error', 'Cannot connect to server.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View>
            <Text style={styles.eyebrow}>Alerts</Text>
            <Text style={styles.title}>Notifications</Text>
          </View>
          <Pressable onPress={() => router.push('/dashboard')} style={styles.iconButton}>
            <ArrowLeft color="#3b82f6" size={22} />
          </Pressable>
        </View>

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator color="#3b82f6" size="large" />
          </View>
        ) : (
          <>
            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Preferences</Text>
              {Object.keys(preferenceLabels).map((key) => (
                <View key={key} style={styles.preferenceRow}>
                  <Text style={styles.preferenceText}>{preferenceLabels[key]}</Text>
                  <Switch
                    value={!!preferences[key]}
                    onValueChange={() => togglePreference(key)}
                    disabled={saving}
                    trackColor={{ false: '#334155', true: '#1d4ed8' }}
                    thumbColor={preferences[key] ? '#93c5fd' : '#94a3b8'}
                  />
                </View>
              ))}
            </View>

            <Text style={styles.listTitle}>Recent</Text>
            {notifications.length === 0 ? (
              <View style={styles.emptyCard}>
                <Bell color="#3b82f6" size={30} />
                <Text style={styles.emptyTitle}>No notifications yet</Text>
              </View>
            ) : (
              notifications.map((item, index) => {
                const Icon = typeIcons[item.type] || Bell;
                return (
                  <View key={`${item.created_at}-${index}`} style={styles.notificationCard}>
                    <View style={styles.notificationIcon}>
                      <Icon color="#3b82f6" size={22} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.notificationTitle}>{item.title}</Text>
                      <Text style={styles.notificationBody}>{item.body}</Text>
                      <Text style={styles.notificationTime}>{item.created_at}</Text>
                    </View>
                  </View>
                );
              })
            )}
          </>
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
  card: { backgroundColor: '#1e293b', borderRadius: 24, padding: 20, borderWidth: 1, borderColor: '#334155', marginBottom: 26 },
  sectionTitle: { color: '#ffffff', fontSize: 18, fontWeight: '800', marginBottom: 12 },
  preferenceRow: { minHeight: 54, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', borderTopWidth: 1, borderTopColor: '#334155' },
  preferenceText: { color: '#e2e8f0', fontSize: 15, fontWeight: '700' },
  listTitle: { color: '#ffffff', fontSize: 20, fontWeight: '800', marginBottom: 16 },
  emptyCard: { backgroundColor: '#1e293b', borderRadius: 24, padding: 24, alignItems: 'center', borderWidth: 1, borderColor: '#334155' },
  emptyTitle: { color: '#ffffff', fontSize: 18, fontWeight: '800', marginTop: 12 },
  notificationCard: { backgroundColor: '#1e293b', borderRadius: 20, borderWidth: 1, borderColor: '#334155', padding: 16, marginBottom: 14, flexDirection: 'row', gap: 14 },
  notificationIcon: { width: 44, height: 44, borderRadius: 14, backgroundColor: '#3b82f620', alignItems: 'center', justifyContent: 'center' },
  notificationTitle: { color: '#ffffff', fontSize: 16, fontWeight: '800' },
  notificationBody: { color: '#cbd5e1', marginTop: 5, lineHeight: 20 },
  notificationTime: { color: '#64748b', marginTop: 8, fontSize: 12 },
});
