import React, { useState } from 'react';
import { View, Text, ScrollView, TextInput, Pressable, Alert, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowLeft, Mail, Lock, User } from 'lucide-react-native';
import { useRouter } from 'expo-router';
import { API_BASE_URL } from '../constants/api';

export default function RegisterScreen() {
  const router = useRouter();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleRegister = async () => {
    if (!fullName || !email || !password) {
      Alert.alert('Error', 'Please fill in all required fields');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: fullName, email, password, role: 'patient' }),
      });
      const data = await res.json();
      setLoading(false);
      if (!res.ok) {
        Alert.alert('Registration Failed', data.error || 'Unable to create account');
        return;
      }
      global.authToken = data.access_token;
      router.replace('/dashboard');
    } catch (error) {
      setLoading(false);
      Alert.alert('Error', 'Cannot connect to server.');
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#0f172a' }}>
      <StatusBar barStyle="light-content" />
      <ScrollView contentContainerStyle={{ flexGrow: 1, padding: 24 }} keyboardShouldPersistTaps="handled">
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16, marginBottom: 40 }}>
          <Pressable onPress={() => router.back()} style={{ backgroundColor: '#1e293b', p: 12, borderRadius: 12, borderWidth: 1, borderColor: '#334155' }}>
            <ArrowLeft color="#3b82f6" size={24} />
          </Pressable>
          <Text style={{ fontSize: 28, fontWeight: 'bold', color: '#ffffff' }}>Create Account</Text>
        </View>

        <View style={{ gap: 24 }}>
          <View>
            <Text style={{ fontSize: 14, fontWeight: '600', color: '#ffffff', marginBottom: 8 }}>Full Name</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#1e293b', borderRadius: 16, px: 16, height: 64, borderWidth: 1, borderColor: '#334155' }}>
              <User color="#94a3b8" size={20} style={{ marginLeft: 16 }} />
              <TextInput style={{ flex: 1, color: '#ffffff', fontSize: 16, marginLeft: 12 }} placeholder="Enter your full name" placeholderTextColor="#64748b" value={fullName} onChangeText={setFullName} />
            </View>
          </View>
          <View>
            <Text style={{ fontSize: 14, fontWeight: '600', color: '#ffffff', marginBottom: 8 }}>Email Address</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#1e293b', borderRadius: 16, px: 16, height: 64, borderWidth: 1, borderColor: '#334155' }}>
              <Mail color="#94a3b8" size={20} style={{ marginLeft: 16 }} />
              <TextInput style={{ flex: 1, color: '#ffffff', fontSize: 16, marginLeft: 12 }} placeholder="Enter your email" placeholderTextColor="#64748b" value={email} onChangeText={setEmail} autoCapitalize="none" />
            </View>
          </View>
          <View>
            <Text style={{ fontSize: 14, fontWeight: '600', color: '#ffffff', marginBottom: 8 }}>Password</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#1e293b', borderRadius: 16, px: 16, height: 64, borderWidth: 1, borderColor: '#334155' }}>
              <Lock color="#94a3b8" size={20} style={{ marginLeft: 16 }} />
              <TextInput style={{ flex: 1, color: '#ffffff', fontSize: 16, marginLeft: 12 }} placeholder="Create a password" placeholderTextColor="#64748b" value={password} onChangeText={setPassword} secureTextEntry />
            </View>
          </View>
          <Pressable onPress={handleRegister} disabled={loading} style={{ backgroundColor: '#3b82f6', borderRadius: 16, height: 64, alignItems: 'center', justifyContent: 'center', marginTop: 16 }}>
            <Text style={{ color: '#ffffff', fontSize: 18, fontWeight: '700' }}>{loading ? 'Creating account...' : 'Create Account'}</Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
