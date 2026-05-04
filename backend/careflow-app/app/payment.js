import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, ScrollView, Pressable, ActivityIndicator, Alert, StatusBar, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import { useRouter } from 'expo-router';
import { API_BASE_URL } from '../constants/api';
import { CreditCard, ArrowLeft } from 'lucide-react-native';

export default function PaymentScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [payments, setPayments] = useState([]);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState(null);
  const [checkoutOrder, setCheckoutOrder] = useState(null);
  const [showCheckout, setShowCheckout] = useState(false);

  const fetchPayments = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/payment/history`, {
        headers: { Authorization: `Bearer ${global.authToken}` },
      });
      const data = await res.json();
      if (res.ok) {
        setPayments(data.payments || []);
      } else {
        setError(data.error || 'Unable to load payments');
      }
    } catch (_err) {
      setError('Cannot connect to server.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPayments();
  }, []);

  const verifyPayment = async (payload) => {
    setActionLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/payment/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${global.authToken}`,
        },
        body: JSON.stringify({
          razorpay_order_id: payload.razorpay_order_id,
          razorpay_payment_id: payload.razorpay_payment_id,
          razorpay_signature: payload.razorpay_signature,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        Alert.alert('Payment successful', 'Your payment is now confirmed.');
        setShowCheckout(false);
        setCheckoutOrder(null);
        fetchPayments();
      } else {
        Alert.alert('Verification failed', data.error || 'Payment could not be verified.');
      }
    } catch (_err) {
      Alert.alert('Error', 'Unable to verify payment at this time.');
    } finally {
      setActionLoading(false);
    }
  };

  const createOrder = async (appointmentId) => {
    if (!appointmentId) {
      Alert.alert('Error', 'Missing appointment ID for payment');
      return;
    }

    setActionLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/payment/create-order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${global.authToken}`,
        },
        body: JSON.stringify({ appointment_id: appointmentId }),
      });
      const data = await res.json();
      if (!res.ok) {
        Alert.alert('Payment Error', data.error || 'Unable to create payment order.');
      } else {
        setCheckoutOrder(data);
        setShowCheckout(true);
      }
    } catch (_err) {
      Alert.alert('Error', 'Cannot connect to server during payment creation.');
    } finally {
      setActionLoading(false);
    }
  };

  const checkoutHtml = useMemo(() => {
    if (!checkoutOrder) return null;

    const options = {
      key: checkoutOrder.key_id,
      amount: Math.round(checkoutOrder.amount * 100),
      currency: checkoutOrder.currency,
      name: 'CareFlow',
      description: 'Appointment payment',
      order_id: checkoutOrder.order_id,
      modal: {
        ondismiss: function () {
          window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'dismiss' }));
        },
      },
      theme: {
        color: '#2563EB',
      },
    };

    return `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>CareFlow Payment</title>
    <style>body{margin:0;background:#0f172a;color:#fff;font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh}</style>
  </head>
  <body>
    <div>
      <h1 style="font-size:20px;margin-bottom:8px;">Opening secure payment...</h1>
      <p style="color:#94a3b8;margin:0;">If the checkout does not appear, please try again.</p>
    </div>
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <script>
      const options = ${JSON.stringify(options)};
      options.handler = function (response) {
        window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'success', payload: response }));
      };
      const rzp = new Razorpay(options);
      rzp.on('payment.failed', function (response) {
        window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'failed', payload: response.error }));
      });
      setTimeout(function () {
        rzp.open();
      }, 300);
    </script>
  </body>
</html>`;
  }, [checkoutOrder]);

  const handleCheckoutMessage = async (event) => {
    try {
      const message = JSON.parse(event.nativeEvent.data);
      if (message.type === 'success') {
        const payload = message.payload;
        await verifyPayment({
          razorpay_order_id: payload.razorpay_order_id,
          razorpay_payment_id: payload.razorpay_payment_id,
          razorpay_signature: payload.razorpay_signature,
        });
      } else if (message.type === 'failed') {
        Alert.alert('Payment failed', message.payload.description || 'The payment was not completed.');
        setShowCheckout(false);
        setCheckoutOrder(null);
      } else if (message.type === 'dismiss') {
        setShowCheckout(false);
        setCheckoutOrder(null);
      }
    } catch (_err) {
      Alert.alert('Payment error', 'Unexpected payment response.');
      setShowCheckout(false);
      setCheckoutOrder(null);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />
      <ScrollView contentContainerStyle={{ padding: 24 }}>
        <View style={styles.headerRow}>
          <View>
            <Text style={styles.subTitle}>Payment center</Text>
            <Text style={styles.title}>Your bills</Text>
          </View>
          <Pressable onPress={() => router.push('/dashboard')} style={styles.iconButton}>
            <ArrowLeft color="#3b82f6" size={22} />
          </Pressable>
        </View>

        <View style={styles.card}> 
          <View style={styles.cardTop}>
            <View style={styles.iconWrapper}>
              <CreditCard color="#3b82f6" size={24} />
            </View>
            <View style={{ marginLeft: 14 }}>
              <Text style={styles.cardTitle}>Manage your payments</Text>
              <Text style={styles.cardDescription}>View history and complete pending bills.</Text>
            </View>
          </View>
          <Text style={styles.cardFooter}>Payments are protected and processed securely via your backend service.</Text>
        </View>

        {loading ? (
          <View style={styles.statusRow}>
            <ActivityIndicator color="#3b82f6" size="large" />
            <Text style={styles.statusText}>Loading payment history...</Text>
          </View>
        ) : error ? (
          <View style={styles.statusRow}>
            <Text style={styles.errorText}>{error}</Text>
            <Pressable onPress={fetchPayments} style={styles.retryButton}>
              <Text style={styles.retryText}>Retry</Text>
            </Pressable>
          </View>
        ) : payments.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyTitle}>No payments yet</Text>
            <Text style={styles.emptyText}>Once you book an appointment, your pending payment will show up here.</Text>
          </View>
        ) : (
          payments.map((payment) => (
            <View key={payment.id} style={styles.paymentCard}>
              <View style={styles.paymentRow}>
                <View>
                  <Text style={styles.paymentAmount}>{payment.currency} {payment.amount}</Text>
                  <Text style={styles.paymentStatusText}>{payment.status}</Text>
                </View>
                <View style={[styles.statusBadge, payment.status === 'paid' ? styles.paidBadge : styles.pendingBadge]}>
                  <Text style={[styles.statusBadgeText, payment.status === 'paid' ? styles.paidBadgeText : styles.pendingBadgeText]}>{payment.status}</Text>
                </View>
              </View>
              <View style={styles.paymentDetails}>
                <Text style={styles.detailLabel}>Appointment</Text>
                <Text style={styles.detailValue}>{payment.appointment_id || 'N/A'}</Text>
                {payment.appointment && (
                  <Text style={styles.detailNote}>Doctor: {payment.appointment.doctor_id || 'N/A'}</Text>
                )}
              </View>
              {payment.status !== 'paid' ? (
                <Pressable onPress={() => createOrder(payment.appointment_id)} disabled={actionLoading} style={styles.payButton}>
                  <Text style={styles.payButtonText}>{actionLoading ? 'Processing...' : 'Pay now'}</Text>
                </Pressable>
              ) : null}
            </View>
          ))
        )}
      </ScrollView>

      {showCheckout && checkoutHtml ? (
        <View style={styles.checkoutOverlay}>
          <WebView
            source={{ html: checkoutHtml }}
            originWhitelist={['*']}
            onMessage={handleCheckoutMessage}
            javaScriptEnabled
            style={styles.webview}
          />
          <View style={styles.checkoutFooter}>
            <Pressable onPress={() => { setShowCheckout(false); setCheckoutOrder(null); }} style={styles.checkoutCancel}>
              <Text style={styles.checkoutCancelText}>Cancel payment</Text>
            </Pressable>
          </View>
        </View>
      ) : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 },
  subTitle: { color: '#94a3b8', fontSize: 14 },
  title: { color: '#ffffff', fontSize: 28, fontWeight: 'bold' },
  iconButton: { padding: 10, backgroundColor: '#1e293b', borderRadius: 12, borderWidth: 1, borderColor: '#334155' },
  card: { backgroundColor: '#1e293b', borderRadius: 24, padding: 24, borderWidth: 1, borderColor: '#334155', marginBottom: 24 },
  cardTop: { flexDirection: 'row', alignItems: 'center', marginBottom: 16 },
  iconWrapper: { width: 48, height: 48, borderRadius: 16, backgroundColor: '#3b82f620', alignItems: 'center', justifyContent: 'center' },
  cardTitle: { color: '#ffffff', fontSize: 18, fontWeight: '700' },
  cardDescription: { color: '#94a3b8', marginTop: 4 },
  cardFooter: { color: '#94a3b8', fontSize: 14 },
  statusRow: { paddingVertical: 24, alignItems: 'center' },
  statusText: { color: '#94a3b8', marginTop: 16 },
  errorText: { color: '#f87171', fontSize: 16, fontWeight: '700', marginBottom: 12 },
  retryButton: { backgroundColor: '#3b82f6', paddingVertical: 12, paddingHorizontal: 24, borderRadius: 16 },
  retryText: { color: '#ffffff', fontWeight: '700' },
  emptyState: { padding: 24, backgroundColor: '#1e293b', borderRadius: 24, borderWidth: 1, borderColor: '#334155', alignItems: 'center' },
  emptyTitle: { color: '#ffffff', fontSize: 18, fontWeight: '700', marginBottom: 8 },
  emptyText: { color: '#94a3b8', textAlign: 'center', lineHeight: 22 },
  paymentCard: { backgroundColor: '#1e293b', borderRadius: 24, borderWidth: 1, borderColor: '#334155', padding: 20, marginBottom: 16 },
  paymentRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  paymentAmount: { color: '#ffffff', fontSize: 16, fontWeight: '700' },
  paymentStatusText: { color: '#94a3b8', marginTop: 4 },
  statusBadge: { paddingVertical: 6, paddingHorizontal: 10, borderRadius: 999 },
  paidBadge: { backgroundColor: '#10b98120' },
  pendingBadge: { backgroundColor: '#f59e0b20' },
  statusBadgeText: { fontWeight: '700' },
  paidBadgeText: { color: '#10b981' },
  pendingBadgeText: { color: '#f59e0b' },
  paymentDetails: { borderTopWidth: 1, borderTopColor: '#334155', paddingTop: 14 },
  detailLabel: { color: '#94a3b8', marginBottom: 6 },
  detailValue: { color: '#ffffff', fontSize: 15, fontWeight: '600' },
  detailNote: { color: '#94a3b8', marginTop: 6 },
  payButton: { marginTop: 18, backgroundColor: '#3b82f6', borderRadius: 16, height: 52, alignItems: 'center', justifyContent: 'center' },
  payButtonText: { color: '#ffffff', fontSize: 16, fontWeight: '700' },
  checkoutOverlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: '#000000dd', },
  webview: { flex: 1 },
  checkoutFooter: { position: 'absolute', bottom: 24, left: 24, right: 24, alignItems: 'center' },
  checkoutCancel: { backgroundColor: '#1e293b', paddingVertical: 12, paddingHorizontal: 20, borderRadius: 16, borderWidth: 1, borderColor: '#334155' },
  checkoutCancelText: { color: '#ffffff', fontWeight: '700' },
});
