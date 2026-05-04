import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, TextInput, Pressable, Alert, ActivityIndicator, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { ArrowRight, Calendar, Clock, User, ChevronDown } from 'lucide-react-native';
import { API_BASE_URL } from '../constants/api';

export default function BookScreen() {
  const router = useRouter();
  const [doctors, setDoctors] = useState([]);
  const [selectedDoctor, setSelectedDoctor] = useState(null);
  const [scheduledDate, setScheduledDate] = useState('');
  const [scheduledTime, setScheduledTime] = useState('');
  const [symptoms, setSymptoms] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingDoctors, setLoadingDoctors] = useState(true);

  const fetchDoctors = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/doctor/list`);
      const data = await res.json();
      if (res.ok) {
        setDoctors(data);
      } else {
        Alert.alert('Error', data.error || 'Unable to load doctors');
      }
    } catch (error) {
      Alert.alert('Error', 'Cannot connect to server while loading doctors');
    } finally {
      setLoadingDoctors(false);
    }
  };

  useEffect(() => {
    fetchDoctors();
  }, []);

  const handleBooking = async () => {
    if (!selectedDoctor || !scheduledDate || !scheduledTime) {
      Alert.alert('Missing Fields', 'Please select a doctor and enter date/time');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/patient/book`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${global.authToken}`,
        },
        body: JSON.stringify({
          doctor_id: selectedDoctor.id,
          scheduled_date: scheduledDate,
          scheduled_time: scheduledTime,
          symptoms,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        Alert.alert('Booking Failed', data.error || 'Could not create appointment');
      } else {
        Alert.alert('Booked', 'Appointment created successfully. Proceed to payment.');
        router.push('/payment');
      }
    } catch (error) {
      Alert.alert('Error', 'Cannot connect to server during booking');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#0f172a' }}>
      <StatusBar barStyle="light-content" />
      <ScrollView contentContainerStyle={{ padding: 24 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
          <View>
            <Text style={{ color: '#94a3b8', fontSize: 14 }}>Secure appointment</Text>
            <Text style={{ color: '#ffffff', fontSize: 28, fontWeight: 'bold' }}>Book a Doctor</Text>
          </View>
          <Pressable onPress={() => router.push('/dashboard')} style={{ padding: 10, backgroundColor: '#1e293b', borderRadius: 12, borderWidth: 1, borderColor: '#334155' }}>
            <Text style={{ color: '#3b82f6' }}>Back</Text>
          </Pressable>
        </View>

        <View style={{ backgroundColor: '#1e293b', borderRadius: 24, padding: 24, borderWidth: 1, borderColor: '#334155', marginBottom: 24 }}>
          <Text style={{ color: '#ffffff', fontSize: 16, fontWeight: '700', marginBottom: 16 }}>Choose a doctor</Text>
          {loadingDoctors ? (
            <View style={{ paddingVertical: 24, alignItems: 'center' }}>
              <ActivityIndicator color="#3b82f6" size="large" />
            </View>
          ) : (
            doctors.map((doctor) => (
              <Pressable
                key={doctor.id}
                onPress={() => setSelectedDoctor(doctor)}
                style={{
                  backgroundColor: selectedDoctor?.id === doctor.id ? '#111827' : '#0f172a',
                  padding: 16,
                  borderRadius: 18,
                  borderWidth: 1,
                  borderColor: selectedDoctor?.id === doctor.id ? '#3b82f6' : '#334155',
                  marginBottom: 12,
                }}
              >
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <View>
                    <Text style={{ color: '#ffffff', fontSize: 16, fontWeight: '700' }}>{doctor.name}</Text>
                    <Text style={{ color: '#94a3b8', marginTop: 4 }}>{doctor.specialisation || 'General'}</Text>
                  </View>
                  <ChevronDown color="#94a3b8" size={20} />
                </View>
              </Pressable>
            ))
          )}
        </View>

        <View style={{ backgroundColor: '#1e293b', borderRadius: 24, padding: 24, borderWidth: 1, borderColor: '#334155', marginBottom: 24 }}>
          <Text style={{ color: '#ffffff', fontSize: 16, fontWeight: '700', marginBottom: 16 }}>Appointment details</Text>
          <View style={{ marginBottom: 16 }}>
            <Text style={{ color: '#94a3b8', marginBottom: 8 }}>Date</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#111827', borderRadius: 16, paddingHorizontal: 16, height: 60, borderWidth: 1, borderColor: '#334155' }}>
              <Calendar color="#3b82f6" size={20} />
              <TextInput
                style={{ flex: 1, color: '#ffffff', marginLeft: 12, fontSize: 16 }}
                placeholder="YYYY-MM-DD"
                placeholderTextColor="#64748b"
                value={scheduledDate}
                onChangeText={setScheduledDate}
                autoCapitalize="none"
              />
            </View>
          </View>

          <View style={{ marginBottom: 16 }}>
            <Text style={{ color: '#94a3b8', marginBottom: 8 }}>Time</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#111827', borderRadius: 16, paddingHorizontal: 16, height: 60, borderWidth: 1, borderColor: '#334155' }}>
              <Clock color="#3b82f6" size={20} />
              <TextInput
                style={{ flex: 1, color: '#ffffff', marginLeft: 12, fontSize: 16 }}
                placeholder="HH:MM"
                placeholderTextColor="#64748b"
                value={scheduledTime}
                onChangeText={setScheduledTime}
                autoCapitalize="none"
              />
            </View>
          </View>

          <View>
            <Text style={{ color: '#94a3b8', marginBottom: 8 }}>Symptoms</Text>
            <View style={{ backgroundColor: '#111827', borderRadius: 16, borderWidth: 1, borderColor: '#334155', padding: 16 }}>
              <TextInput
                style={{ minHeight: 100, color: '#ffffff', fontSize: 16, textAlignVertical: 'top' }}
                placeholder="Describe your symptoms"
                placeholderTextColor="#64748b"
                value={symptoms}
                onChangeText={setSymptoms}
                multiline
              />
            </View>
          </View>
        </View>

        <Pressable
          onPress={handleBooking}
          disabled={loading}
          style={{ backgroundColor: '#3b82f6', borderRadius: 18, height: 64, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', opacity: loading ? 0.7 : 1 }}
        >
          <Text style={{ color: '#ffffff', fontSize: 18, fontWeight: '700', marginRight: 10 }}>{loading ? 'Booking...' : 'Confirm Appointment'}</Text>
          {!loading && <ArrowRight color="#ffffff" size={22} />}
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}
