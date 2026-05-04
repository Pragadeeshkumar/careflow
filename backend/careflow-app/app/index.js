import React, { useState } from 'react';
import { View, Text, ScrollView, TextInput, Pressable, Alert, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Activity, Lock, Mail, ArrowRight, Sun } from 'lucide-react-native';
import { useRouter } from 'expo-router';
import { API_BASE_URL } from '../constants/api';
import { registerPush } from './_layout'; // adjust path if needed

export default function LoginScreen() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert('Error', 'Please fill in all fields');
      return;
    }

    setLoading(true);
    console.log("API URL USED:", API_BASE_URL);

    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();
      setLoading(false);

      if (!res.ok) {
        Alert.alert('Login Failed', data.error || 'Invalid email or password');
        return;
      }

      global.authToken = data.access_token;

      await registerPush();
      router.replace('/dashboard');
    } catch (error) {
  setLoading(false);

  console.log("FULL ERROR:", error);

  Alert.alert(
    "Error",
    error.message || "Network request failed"
  );
}
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#0f172a' }}>
      <StatusBar barStyle="light-content" />
      <ScrollView contentContainerStyle={{ flexGrow: 1, padding: 24 }} keyboardShouldPersistTaps="handled">
        
        {/* Top Header */}
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 40 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
            <Activity color="#3b82f6" size={32} />
            <Text style={{ fontSize: 28, fontWeight: 'bold', color: '#ffffff' }}>CareFlow</Text>
          </View>
          <Pressable>
            <Sun color="#ffffff" size={24} />
          </Pressable>
        </View>

        {/* Welcome Section */}
        <View style={{ marginBottom: 40 }}>
          <Text style={{ fontSize: 36, fontWeight: 'bold', color: '#ffffff', marginBottom: 8 }}>Welcome Back</Text>
          <Text style={{ fontSize: 16, color: '#94a3b8' }}>Sign in to access your healthcare services</Text>
        </View>

        {/* Form Fields */}
        <View style={{ gap: 24 }}>
          <View>
            <Text style={{ fontSize: 14, fontWeight: '600', color: '#ffffff', marginBottom: 8 }}>Email Address</Text>
            <View style={{ 
              flexDirection: 'row', 
              alignItems: 'center', 
              backgroundColor: '#1e293b', 
              borderRadius: 16, 
              paddingHorizontal: 16, 
              height: 64, 
              borderWidth: 1, 
              borderColor: '#334155' 
            }}>
              <Mail color="#94a3b8" size={20} />
              <TextInput
                style={{ flex: 1, color: '#ffffff', fontSize: 16, marginLeft: 12 }}
                placeholder="Enter your email"
                placeholderTextColor="#64748b"
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
              />
            </View>
          </View>

          <View>
            <Text style={{ fontSize: 14, fontWeight: '600', color: '#ffffff', marginBottom: 8 }}>Password</Text>
            <View style={{ 
              flexDirection: 'row', 
              alignItems: 'center', 
              backgroundColor: '#1e293b', 
              borderRadius: 16, 
              paddingHorizontal: 16, 
              height: 64, 
              borderWidth: 1, 
              borderColor: '#334155' 
            }}>
              <Lock color="#94a3b8" size={20} />
              <TextInput
                style={{ flex: 1, color: '#ffffff', fontSize: 16, marginLeft: 12 }}
                placeholder="Enter your password"
                placeholderTextColor="#64748b"
                value={password}
                onChangeText={setPassword}
                secureTextEntry
              />
            </View>
          </View>

          <View style={{ alignItems: 'flex-end' }}>
            <Pressable>
              <Text style={{ color: '#3b82f6', fontSize: 14, fontWeight: '600' }}>Forgot Password?</Text>
            </Pressable>
          </View>

          <Pressable
            onPress={handleLogin}
            disabled={loading}
            style={{ 
              backgroundColor: '#3b82f6', 
              borderRadius: 16, 
              height: 64, 
              alignItems: 'center', 
              justifyContent: 'center', 
              flexDirection: 'row', 
              gap: 8,
              marginTop: 16,
              opacity: loading ? 0.7 : 1
            }}
          >
            <Text style={{ color: '#ffffff', fontSize: 18, fontWeight: '700' }}>{loading ? 'Signing in...' : 'Sign In'}</Text>
            {!loading && <ArrowRight color="#ffffff" size={22} />}
          </Pressable>

          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16, marginVertical: 32 }}>
            <View style={{ flex: 1, height: 1, backgroundColor: '#334155' }} />
            <Text style={{ color: '#94a3b8', fontSize: 14 }}>or</Text>
            <View style={{ flex: 1, height: 1, backgroundColor: '#334155' }} />
          </View>

          <View style={{ alignItems: 'center' }}>
            <Text style={{ color: '#94a3b8', fontSize: 16 }}>Don&apos;t have an account?</Text>
            <Pressable onPress={() => router.push('/register')} style={{ marginTop: 4 }}>
              <Text style={{ color: '#3b82f6', fontSize: 16, fontWeight: '700' }}>Create Account</Text>
            </Pressable>
          </View>
        </View>

        <View style={{ marginTop: 'auto', paddingTop: 40 }}>
          <Text style={{ textAlign: 'center', color: '#94a3b8', fontSize: 12 }}>
            By signing in, you agree to our Terms of Service and Privacy Policy
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
