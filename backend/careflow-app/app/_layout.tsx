import { Stack } from 'expo-router';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { useEffect } from 'react';
import { API_BASE_URL } from '../constants/api'; // ✅ ADD THIS

// 🔥 Show notification even when app is open
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export default function RootLayout() {

  useEffect(() => {
    if (global.authToken) {
      registerPush();
    }
  }, []);

  return (
    <Stack
      screenOptions={{
        headerShown: false
      }}
    />
  );
}
export async function registerPush() {
  if (!Device.isDevice) {
    console.log("❌ Not a physical device");
    return;
  }

  const { status } = await Notifications.requestPermissionsAsync();
  if (status !== 'granted') {
    console.log("❌ Permission denied");
    return;
  }

  const token = (
  await Notifications.getExpoPushTokenAsync({
    projectId: "5a366249-e63c-41e5-976f-f552b35ddee5",
  })
).data;

  console.log("🔥 EXPO TOKEN:", token);

  try {
    await fetch(`${API_BASE_URL}/api/patient/notifications/token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${global.authToken}`
      },
      body: JSON.stringify({ fcm_token: token })
    });

    console.log("✅ Token sent to backend");

  } catch (err) {
    console.log("❌ Failed to send token:", err);
  }
}