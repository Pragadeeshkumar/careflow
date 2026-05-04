import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, Pressable, ActivityIndicator, RefreshControl, StatusBar, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { ArrowLeft, CalendarClock, FileText } from 'lucide-react-native';
import { API_BASE_URL } from '../constants/api';

export default function HistoryScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [appointments, setAppointments] = useState([]);
  const [error, setError] = useState(null);

  const loadHistory = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/patient/history`, {
        headers: { Authorization: `Bearer ${global.authToken}` },
      });
      const data = await res.json();
      if (res.ok) {
        setAppointments(data.appointments || []);
      } else {
        setError(data.error || 'Unable to load history');
      }
    } catch (_err) {
      setError('Cannot connect to server.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    loadHistory();
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#3b82f6" />}
      >
        <View style={styles.header}>
          <View>
            <Text style={styles.eyebrow}>Appointments</Text>
            <Text style={styles.title}>History</Text>
          </View>
          <Pressable onPress={() => router.push('/dashboard')} style={styles.iconButton}>
            <ArrowLeft color="#3b82f6" size={22} />
          </Pressable>
        </View>

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator color="#3b82f6" size="large" />
            <Text style={styles.muted}>Loading appointments...</Text>
          </View>
        ) : error ? (
          <View style={styles.emptyCard}>
            <Text style={styles.error}>{error}</Text>
            <Pressable onPress={loadHistory} style={styles.primaryButton}>
              <Text style={styles.primaryButtonText}>Retry</Text>
            </Pressable>
          </View>
        ) : appointments.length === 0 ? (
          <View style={styles.emptyCard}>
            <CalendarClock color="#3b82f6" size={32} />
            <Text style={styles.emptyTitle}>No appointments yet</Text>
          </View>
        ) : (
          appointments.map((item) => (
            <View key={item.id} style={styles.card}>
              <View style={styles.cardTop}>
                <View style={styles.iconCircle}>
                  <FileText color="#3b82f6" size={22} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.cardTitle}>{item.scheduled_date} at {item.scheduled_time}</Text>
                  <Text style={styles.cardSub}>{item.status}</Text>
                </View>
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>Score {item.triage_score ?? 0}</Text>
                </View>
              </View>
              {item.symptoms ? <Text style={styles.bodyText}>{item.symptoms}</Text> : null}
              {item.notes ? <Text style={styles.noteText}>Notes: {item.notes}</Text> : null}
            </View>
          ))
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
  emptyCard: { backgroundColor: '#1e293b', borderRadius: 24, padding: 24, alignItems: 'center', borderWidth: 1, borderColor: '#334155' },
  emptyTitle: { color: '#ffffff', fontSize: 18, fontWeight: '800', marginTop: 12 },
  error: { color: '#f87171', fontWeight: '700', marginBottom: 16 },
  primaryButton: { backgroundColor: '#3b82f6', borderRadius: 16, paddingVertical: 12, paddingHorizontal: 24 },
  primaryButtonText: { color: '#ffffff', fontWeight: '800' },
  card: { backgroundColor: '#1e293b', borderRadius: 22, padding: 18, borderWidth: 1, borderColor: '#334155', marginBottom: 16 },
  cardTop: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 14 },
  iconCircle: { width: 44, height: 44, borderRadius: 14, backgroundColor: '#3b82f620', alignItems: 'center', justifyContent: 'center' },
  cardTitle: { color: '#ffffff', fontSize: 16, fontWeight: '800' },
  cardSub: { color: '#94a3b8', marginTop: 4, textTransform: 'capitalize' },
  badge: { backgroundColor: '#111827', borderRadius: 12, paddingVertical: 6, paddingHorizontal: 10, borderWidth: 1, borderColor: '#334155' },
  badgeText: { color: '#93c5fd', fontWeight: '800', fontSize: 12 },
  bodyText: { color: '#cbd5e1', lineHeight: 20 },
  noteText: { color: '#94a3b8', marginTop: 10, lineHeight: 20 },
});
