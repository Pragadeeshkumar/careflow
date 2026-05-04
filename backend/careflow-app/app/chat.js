import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TextInput, Pressable, ActivityIndicator, Alert, StatusBar, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { ArrowLeft, Send, Bot } from 'lucide-react-native';
import { API_BASE_URL } from '../constants/api';

export default function ChatScreen() {
  const router = useRouter();
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);

  const loadHistory = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/chat/history`, {
        headers: { Authorization: `Bearer ${global.authToken}` },
      });
      const data = await res.json();
      if (res.ok) {
        setMessages(data.messages || []);
      }
    } catch (_err) {
      Alert.alert('Error', 'Cannot connect to chat service.');
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const sendMessage = async () => {
    const message = text.trim();
    if (!message || loading) return;

    setText('');
    setLoading(true);
    setMessages((current) => [...current, { role: 'user', content: message }]);

    try {
      const res = await fetch(`${API_BASE_URL}/api/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${global.authToken}`,
        },
        body: JSON.stringify({ message, stream: false }),
      });
      const data = await res.json();
      if (res.ok) {
        setMessages((current) => [...current, { role: 'assistant', content: data.response || data.message }]);
      } else {
        Alert.alert('Chat error', data.error || 'Unable to get response');
      }
    } catch (_err) {
      Alert.alert('Error', 'Cannot connect to chat service.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <View style={styles.botIcon}>
              <Bot color="#3b82f6" size={24} />
            </View>
            <View>
              <Text style={styles.eyebrow}>CareFlow AI</Text>
              <Text style={styles.title}>Chat</Text>
            </View>
          </View>
          <Pressable onPress={() => router.push('/dashboard')} style={styles.iconButton}>
            <ArrowLeft color="#3b82f6" size={22} />
          </Pressable>
        </View>

        <ScrollView contentContainerStyle={styles.messages}>
          {historyLoading ? (
            <View style={styles.center}>
              <ActivityIndicator color="#3b82f6" size="large" />
            </View>
          ) : messages.length === 0 ? (
            <View style={styles.emptyCard}>
              <Text style={styles.emptyTitle}>Start a symptom intake</Text>
            </View>
          ) : (
            messages.map((message, index) => {
              const isUser = message.role === 'user';
              return (
                <View key={`${message.role}-${index}`} style={[styles.bubble, isUser ? styles.userBubble : styles.aiBubble]}>
                  <Text style={[styles.bubbleText, isUser ? styles.userText : styles.aiText]}>{message.content}</Text>
                </View>
              );
            })
          )}
          {loading ? (
            <View style={[styles.bubble, styles.aiBubble]}>
              <ActivityIndicator color="#3b82f6" />
            </View>
          ) : null}
        </ScrollView>

        <View style={styles.composer}>
          <TextInput
            style={styles.input}
            placeholder="Describe symptoms or ask a question"
            placeholderTextColor="#64748b"
            value={text}
            onChangeText={setText}
            multiline
          />
          <Pressable onPress={sendMessage} disabled={loading || !text.trim()} style={styles.sendButton}>
            <Send color="#ffffff" size={20} />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  header: { padding: 24, paddingBottom: 12, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  headerLeft: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  botIcon: { width: 48, height: 48, borderRadius: 16, backgroundColor: '#3b82f620', alignItems: 'center', justifyContent: 'center' },
  eyebrow: { color: '#94a3b8', fontSize: 14 },
  title: { color: '#ffffff', fontSize: 28, fontWeight: 'bold' },
  iconButton: { padding: 10, backgroundColor: '#1e293b', borderRadius: 12, borderWidth: 1, borderColor: '#334155' },
  messages: { padding: 24, paddingTop: 12 },
  center: { paddingVertical: 32, alignItems: 'center' },
  emptyCard: { backgroundColor: '#1e293b', borderRadius: 24, padding: 24, alignItems: 'center', borderWidth: 1, borderColor: '#334155' },
  emptyTitle: { color: '#ffffff', fontSize: 18, fontWeight: '800' },
  bubble: { maxWidth: '86%', borderRadius: 18, padding: 14, marginBottom: 12 },
  userBubble: { alignSelf: 'flex-end', backgroundColor: '#3b82f6' },
  aiBubble: { alignSelf: 'flex-start', backgroundColor: '#1e293b', borderWidth: 1, borderColor: '#334155' },
  bubbleText: { fontSize: 15, lineHeight: 21 },
  userText: { color: '#ffffff' },
  aiText: { color: '#e2e8f0' },
  composer: { padding: 16, borderTopWidth: 1, borderTopColor: '#1e293b', flexDirection: 'row', gap: 12, alignItems: 'flex-end' },
  input: { flex: 1, maxHeight: 120, minHeight: 52, color: '#ffffff', backgroundColor: '#1e293b', borderRadius: 16, borderWidth: 1, borderColor: '#334155', paddingHorizontal: 16, paddingVertical: 14, fontSize: 16 },
  sendButton: { width: 52, height: 52, borderRadius: 16, backgroundColor: '#3b82f6', alignItems: 'center', justifyContent: 'center' },
});
