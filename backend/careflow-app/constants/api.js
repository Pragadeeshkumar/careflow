import { Platform } from 'react-native';

// Use your machine's local IP address for physical device testing
export const API_BASE_URL = 'http://192.168.0.105:5000';
export const SOCKET_BASE_URL = API_BASE_URL;

/* 
Note: 
- 127.0.0.1/localhost only works for Web/iOS Simulator
- 10.0.2.2 only works for Android Emulator
- Physical devices MUST use the computer's actual network IP (192.168.x.x)
*/
