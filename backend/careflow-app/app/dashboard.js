import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, Pressable, ActivityIndicator, StatusBar, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Activity, Calendar, Clock, CreditCard, LogOut, User, ChevronRight, Bell, MessageCircle, FileText } from 'lucide-react-native';
import { API_BASE_URL } from '../constants/api';
import { Bot } from 'lucide-react-native';

export default function DashboardScreen() {
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchUserData = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/me`, {
        headers: {
          'Authorization': `Bearer ${global.authToken}`
        }
      });
      const data = await res.json();
      if (res.ok) {
        setUser(data.user);
      } else {
        router.replace('/');
      }
    } catch (error) {
      console.error('Failed to fetch user:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchUserData();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    fetchUserData();
  };

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: '#0f172a', justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" color="#3b82f6" />
      </View>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#0f172a' }}>
      <StatusBar barStyle="light-content" />
      <ScrollView
        contentContainerStyle={{ padding: 24 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#3b82f6" />}
      >
        {/* Header */}
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
          <View>
            <Text style={{ color: '#94a3b8', fontSize: 16 }}>Welcome back,</Text>
            <Text style={{ color: '#ffffff', fontSize: 24, fontWeight: 'bold' }}>{user?.full_name || 'User'}</Text>
          </View>
          <View style={{ flexDirection: 'row', gap: 12 }}>
            <Pressable onPress={() => router.push('/notifications')} style={{ backgroundColor: '#1e293b', p: 10, borderRadius: 12, borderWidth: 1, borderColor: '#334155' }}>
              <Bell color="#ffffff" size={22} />
            </Pressable>
            <Pressable
              onPress={() => { global.authToken = null; router.replace('/'); }}
              style={{ backgroundColor: '#1e293b', p: 10, borderRadius: 12, borderWidth: 1, borderColor: '#334155' }}
            >
              <LogOut color="#f87171" size={22} />
            </Pressable>
          </View>
        </View>

        {/* Quick Stats / Status Card */}
        <View style={{ backgroundColor: '#1e293b', borderRadius: 24, padding: 24, marginBottom: 32, borderWidth: 1, borderColor: '#334155' }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <View style={{ backgroundColor: '#3b82f620', p: 8, borderRadius: 8 }}>
              <Activity color="#3b82f6" size={20} />
            </View>
            <Text style={{ color: '#ffffff', fontSize: 18, fontWeight: '600' }}>Health Status</Text>
          </View>
          <Text style={{ color: '#94a3b8', fontSize: 14, lineHeight: 20 }}>
            You have no active appointments for today. Stay healthy!
          </Text>
          <Pressable
            onPress={() => router.push('/book')}
            style={{ backgroundColor: '#3b82f6', borderRadius: 12, height: 48, alignItems: 'center', justifyContent: 'center', marginTop: 20 }}
          >
            <Text style={{ color: '#ffffff', fontWeight: 'bold' }}>Book New Appointment</Text>
          </Pressable>
        </View>

        {/* Services Grid */}
        <Text style={{ color: '#ffffff', fontSize: 20, fontWeight: 'bold', marginBottom: 20 }}>Quick Services</Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 16 }}>
          {[
            { title: 'Appointments', icon: Calendar, color: '#3b82f6', route: '/book' },
            { title: 'Queue Status', icon: Clock, color: '#10b981', route: '/queue' },
            { title: 'Payments', icon: CreditCard, color: '#f59e0b', route: '/payment' },
            { title: 'History', icon: FileText, color: '#06b6d4', route: '/history' },
            { title: 'Profile', icon: User, color: '#8b5cf6', route: '/profile' },
          ].map((item, index) => (
            <Pressable
              key={index}
              onPress={() => router.push(item.route)}
              style={{
                width: '47%',
                backgroundColor: '#1e293b',
                borderRadius: 20,
                padding: 20,
                borderWidth: 1,
                borderColor: '#334155',
                alignItems: 'center',
                gap: 12
              }}
            >
              <View style={{ backgroundColor: `${item.color}20`, p: 12, borderRadius: 16 }}>
                <item.icon color={item.color} size={28} />
              </View>
              <Text style={{ color: '#ffffff', fontWeight: '600' }}>{item.title}</Text>
            </Pressable>
          ))}
        </View>

        {/* Recent Activity */}
        <View style={{ marginTop: 32 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <Text style={{ color: '#ffffff', fontSize: 20, fontWeight: 'bold' }}>Recent Activity</Text>
            <Pressable><Text style={{ color: '#3b82f6' }}>See All</Text></Pressable>
          </View>

          <View style={{ backgroundColor: '#1e293b', borderRadius: 20, borderWidth: 1, borderColor: '#334155' }}>
            <View style={{ padding: 16, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <View style={{ backgroundColor: '#334155', p: 8, borderRadius: 10 }}>
                  <Activity color="#94a3b8" size={20} />
                </View>
                <View>
                  <Text style={{ color: '#ffffff', fontWeight: '600' }}>New User Registration</Text>
                  <Text style={{ color: '#94a3b8', fontSize: 12 }}>Today, 10:00 AM</Text>
                </View>
              </View>
              <ChevronRight color="#334155" size={20} />
            </View>
          </View>
        </View>

      </ScrollView>
      <Pressable
        onPress={() => router.push('/chat')}
        style={{
          position: 'absolute',
          bottom: 24,
          right: 24,
          width: 60,
          height: 60,
          borderRadius: 30,
          backgroundColor: '#3b82f6',
          alignItems: 'center',
          justifyContent: 'center',
          elevation: 10,
          shadowColor: '#3b82f6',
          shadowOpacity: 0.5,
          shadowRadius: 10,
        }}
      >
        <Bot color="#ffffff" size={26} />
      </Pressable>
    </SafeAreaView>
  );
}
