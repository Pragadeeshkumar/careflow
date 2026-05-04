import React, { useEffect, useState, useRef } from 'react';
import { View, Text, ScrollView, Pressable, ActivityIndicator, Alert, StatusBar, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { io } from 'socket.io-client';
import { API_BASE_URL } from '../constants/api';
import { Clock, ClipboardList, ArrowLeft, ChevronRight } from 'lucide-react-native';
import * as Location from 'expo-location';
import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';

export default function QueueScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [queueStatus, setQueueStatus] = useState(null);
  const [error, setError] = useState(null);
  const [locationStatus, setLocationStatus] = useState('Waiting for queue');
  const [geofenceBoundary, setGeofenceBoundary] = useState(null);
  const [pushTokenRegistered, setPushTokenRegistered] = useState(false);
  const socketRef = useRef(null);
  const locationIntervalRef = useRef(null);

  const fetchQueueStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/patient/queue/status`, {
        headers: {
          Authorization: `Bearer ${global.authToken}`,
        },
      });

      const data = await res.json();
      if (res.ok) {
        setQueueStatus(data);
      } else {
        if (data.error) {
          setError(data.error);
        } else {
          setError('Failed to load queue status.');
        }
      }
    } catch (err) {
      setError('Cannot connect to server.');
    } finally {
      setLoading(false);
    }
  };

  const registerForPushNotificationsAsync = async () => {
    try {
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;
      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }

      if (!Constants.isDevice) {
        console.warn('Push notifications are not supported on this device/emulator');
        setPushTokenRegistered(false);
        return null;
      }

      if (finalStatus !== 'granted') {
        setPushTokenRegistered(false);
        return null;
      }

      const token = (
  await Notifications.getExpoPushTokenAsync({
    projectId: "5a366249-e63c-41e5-976f-f552b35ddee5",
  })
).data;
      return token;
    } catch (error) {
      console.warn('Push registration failed', error);
      return null;
    }
  };

  const updatePushToken = async (token) => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/patient/notifications/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${global.authToken}`,
        },
        body: JSON.stringify({ fcm_token: token }),
      });

      if (res.ok) {
        setPushTokenRegistered(true);
      } else {
        setPushTokenRegistered(false);
      }
    } catch (error) {
      console.warn('Failed to register push token', error);
      setPushTokenRegistered(false);
    }
  };

  const sendLocationUpdate = async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setLocationStatus('Location permission denied');
        return;
      }

      const location = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Highest });
      const body = {
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
      };

      const res = await fetch(`${API_BASE_URL}/api/patient/location`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${global.authToken}`,
        },
        body: JSON.stringify(body),
      });

      if (res.ok) {
        setLocationStatus('Location shared');
      } else {
        setLocationStatus('Unable to share location');
      }
    } catch (error) {
      console.warn('Location update failed', error);
      setLocationStatus('Location update failed');
    }
  };

  const startLocationTracking = () => {
    if (locationIntervalRef.current) return;
    sendLocationUpdate();
    locationIntervalRef.current = setInterval(sendLocationUpdate, 20000);
  };

  const stopLocationTracking = () => {
    if (locationIntervalRef.current) {
      clearInterval(locationIntervalRef.current);
      locationIntervalRef.current = null;
    }
  };

  const loadGeofenceBoundary = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/patient/geofence`, {
        headers: {
          Authorization: `Bearer ${global.authToken}`,
        },
      });
      const data = await res.json();
      if (res.ok) {
        setGeofenceBoundary(data.boundary);
        if (data.current_location) {
          setLocationStatus(data.current_location.within_hospital ? 'Within hospital zone' : 'Outside hospital zone');
        }
      }
    } catch (error) {
      console.warn('Failed to load geofence boundary', error);
    }
  };

  useEffect(() => {
    fetchQueueStatus();
    loadGeofenceBoundary();

    const setupPush = async () => {
      const token = await registerForPushNotificationsAsync();
      if (token) {
        await updatePushToken(token);
      }
    };

    setupPush();
  }, []);

  useEffect(() => {
    return () => {
      socketRef.current?.disconnect();
      socketRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (queueStatus?.in_queue) {
      startLocationTracking();
    } else {
      stopLocationTracking();
    }

    return () => stopLocationTracking();
  }, [queueStatus?.in_queue]);

  useEffect(() => {
    const appointmentId = queueStatus?.queue_token?.appointment_id;
    if (!queueStatus?.in_queue || !appointmentId || !global.authToken) {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
      return;
    }

    if (socketRef.current) {
      return;
    }

    const socket = io(API_BASE_URL, {
      auth: { token: global.authToken },
      transports: ['websocket', 'polling'],
      autoConnect: true,
    });

    socket.on('connect', () => {
      socket.emit('subscribe_queue', { appointment_id: appointmentId, role: 'patient' });
    });

    socket.on('queue_position_update', (data) => {
      if (data.appointment_id !== appointmentId) return;
      setQueueStatus((current) =>
        current
          ? {
              ...current,
              position: data.position ?? current.position,
              people_ahead: data.people_ahead ?? current.people_ahead,
            }
          : current
      );
    });

    const handleCalled = (data) => {
      if (data.appointment_id !== appointmentId) return;
      Alert.alert('Doctor Calling', data.message || `Token #${data.token_number} please proceed to the doctor.`);
    };

    const handleTokenIssued = (data) => {
      if (data.appointment_id !== appointmentId) return;
      setQueueStatus((current) =>
        current
          ? {
              ...current,
              token_number: data.token_number ?? current.token_number,
            }
          : current
      );
      Alert.alert('Token Issued', data.message || `Your queue token has been issued.`);
    };

    socket.on('you_are_called', handleCalled);
    socket.on('token_issued_to_you', handleTokenIssued);
    socket.on('token_issued', handleTokenIssued);
    socket.on('geofence_warning', (data) => {
      if (data.appointment_id !== appointmentId) return;
      Alert.alert('Geofence Warning', data.message || 'Please stay within the hospital area so you can keep your queue position.');
    });

    socket.on('connect_error', (err) => {
      console.warn('Socket connection error', err?.message || err);
    });

    socketRef.current = socket;

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [queueStatus?.in_queue, queueStatus?.queue_token?.appointment_id]);

  const renderContent = () => {
    if (loading) {
      return (
        <View style={{ paddingVertical: 24, alignItems: 'center' }}>
          <ActivityIndicator color="#3b82f6" size="large" />
          <Text style={{ color: '#94a3b8', marginTop: 16 }}>Loading queue status...</Text>
        </View>
      );
    }

    if (error) {
      return (
        <View style={{ paddingVertical: 24, alignItems: 'center' }}>
          <Text style={{ color: '#f87171', fontSize: 16, fontWeight: '700', marginBottom: 12 }}>{error}</Text>
          <Pressable onPress={fetchQueueStatus} style={{ backgroundColor: '#3b82f6', paddingVertical: 12, paddingHorizontal: 24, borderRadius: 16 }}>
            <Text style={{ color: '#ffffff', fontWeight: '700' }}>Retry</Text>
          </Pressable>
        </View>
      );
    }

    if (!queueStatus?.in_queue) {
      return (
        <View style={{ padding: 24, backgroundColor: '#1e293b', borderRadius: 24, borderWidth: 1, borderColor: '#334155' }}>
          <Text style={{ color: '#ffffff', fontSize: 20, fontWeight: '700', marginBottom: 10 }}>You&apos;re not in queue</Text>
          <Text style={{ color: '#94a3b8', fontSize: 16, lineHeight: 22 }}>
            No active queue token was found. Book an appointment or check payment to join the queue.
          </Text>
          <Pressable onPress={() => router.push('/book')} style={{ marginTop: 24, backgroundColor: '#3b82f6', borderRadius: 16, height: 56, alignItems: 'center', justifyContent: 'center' }}>
            <Text style={{ color: '#ffffff', fontSize: 16, fontWeight: '700' }}>Book Appointment</Text>
          </Pressable>
        </View>
      );
    }

    return (
      <View style={{ gap: 18 }}>
        <View style={{ backgroundColor: '#1e293b', borderRadius: 24, padding: 24, borderWidth: 1, borderColor: '#334155' }}>
          <Text style={{ color: '#ffffff', fontSize: 20, fontWeight: '700', marginBottom: 12 }}>Current Queue Status</Text>
          <Text style={{ color: '#94a3b8', marginBottom: 24 }}>Track your position and estimated wait time.</Text>

          <View style={{ backgroundColor: '#111827', borderRadius: 18, padding: 18, marginBottom: 14 }}>
            <Text style={{ color: '#94a3b8', fontSize: 14, marginBottom: 6 }}>Token Number</Text>
            <Text style={{ color: '#ffffff', fontSize: 28, fontWeight: '800' }}>{queueStatus.token_number}</Text>
          </View>

          <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 12, marginBottom: 14 }}>
            <View style={{ flex: 1, backgroundColor: '#111827', borderRadius: 18, padding: 18, borderWidth: 1, borderColor: '#334155' }}>
              <Text style={{ color: '#94a3b8', fontSize: 14 }}>Position</Text>
              <Text style={{ color: '#ffffff', fontSize: 26, fontWeight: '800' }}>{queueStatus.position}</Text>
            </View>
            <View style={{ flex: 1, backgroundColor: '#111827', borderRadius: 18, padding: 18, borderWidth: 1, borderColor: '#334155' }}>
              <Text style={{ color: '#94a3b8', fontSize: 14 }}>Ahead</Text>
              <Text style={{ color: '#ffffff', fontSize: 26, fontWeight: '800' }}>{queueStatus.people_ahead ?? '—'}</Text>
            </View>
          </View>

          <View style={{ backgroundColor: '#111827', borderRadius: 18, padding: 18, borderWidth: 1, borderColor: '#334155' }}>
            <Text style={{ color: '#94a3b8', fontSize: 14 }}>Doctor</Text>
            <Text style={{ color: '#ffffff', fontSize: 18, fontWeight: '700', marginTop: 8 }}>{queueStatus.doctor.name}</Text>
            <Text style={{ color: '#94a3b8', marginTop: 2 }}>{queueStatus.doctor.specialisation}</Text>
          </View>

          {geofenceBoundary ? (
            <View style={{ backgroundColor: '#111827', borderRadius: 18, padding: 18, borderWidth: 1, borderColor: '#334155', marginTop: 14 }}>
              <Text style={{ color: '#94a3b8', fontSize: 14 }}>Hospital Geofence</Text>
              <Text style={{ color: '#ffffff', marginTop: 8 }}>
                Radius: {geofenceBoundary.radius_meters}m around {geofenceBoundary.latitude.toFixed(4)}, {geofenceBoundary.longitude.toFixed(4)}
              </Text>
              <Text style={{ color: '#cbd5e1', marginTop: 10 }}>{locationStatus}</Text>
            </View>
          ) : (
            <Text style={{ color: '#94a3b8', marginTop: 10 }}>{locationStatus}</Text>
          )}
        </View>

        <View style={{ backgroundColor: '#1e293b', borderRadius: 24, padding: 24, borderWidth: 1, borderColor: '#334155' }}>
          <Text style={{ color: '#ffffff', fontSize: 18, fontWeight: '700', marginBottom: 12 }}>Quick Actions</Text>
          <Pressable onPress={() => router.push('/payment')} style={{ backgroundColor: '#3b82f6', borderRadius: 16, height: 56, alignItems: 'center', justifyContent: 'center', marginBottom: 14 }}>
            <Text style={{ color: '#ffffff', fontSize: 16, fontWeight: '700' }}>View Payment</Text>
          </Pressable>
          <Pressable onPress={() => router.push('/dashboard')} style={{ backgroundColor: '#111827', borderRadius: 16, height: 56, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: '#334155' }}>
            <Text style={{ color: '#94a3b8', fontSize: 16, fontWeight: '700' }}>Back to Dashboard</Text>
          </Pressable>
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#0f172a' }}>
      <StatusBar barStyle="light-content" />
      <ScrollView contentContainerStyle={{ padding: 24 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
          <View>
            <Text style={{ color: '#94a3b8', fontSize: 14 }}>Queue status</Text>
            <Text style={{ color: '#ffffff', fontSize: 28, fontWeight: 'bold' }}>Your turn</Text>
          </View>
          <Pressable onPress={() => router.push('/dashboard')} style={{ padding: 10, backgroundColor: '#1e293b', borderRadius: 12, borderWidth: 1, borderColor: '#334155' }}>
            <ArrowLeft color="#3b82f6" size={22} />
          </Pressable>
        </View>

        <View style={{ backgroundColor: '#1e293b', borderRadius: 24, padding: 24, borderWidth: 1, borderColor: '#334155', marginBottom: 24 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
            <View style={{ width: 48, height: 48, borderRadius: 16, backgroundColor: '#3b82f620', alignItems: 'center', justifyContent: 'center' }}>
              <Clock color="#3b82f6" size={24} />
            </View>
            <View>
              <Text style={{ color: '#ffffff', fontSize: 18, fontWeight: '700' }}>Real-time queue updates</Text>
              <Text style={{ color: '#94a3b8', marginTop: 4 }}>Powered by your appointment record.</Text>
            </View>
          </View>
        </View>

        {renderContent()}
      </ScrollView>
    </SafeAreaView>
  );
}
