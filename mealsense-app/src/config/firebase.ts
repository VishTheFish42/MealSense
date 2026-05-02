import { initializeApp, getApps, getApp } from 'firebase/app';
import { initializeAuth, getReactNativePersistence, getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import AsyncStorage from '@react-native-async-storage/async-storage';

const firebaseConfig = {
  apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY,
  authDomain: "myproject-dc745.firebaseapp.com",
  projectId: "myproject-dc745",
  storageBucket: "myproject-dc745.firebasestorage.app",
  messagingSenderId: "101801695589",
  appId: "1:101801695589:web:7dd2b5f4b5129a548e698c",
  measurementId: "G-6RMBG9TSF3"
};

// Guard against duplicate initialization on hot reload
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();

export const auth = (() => {
  try {
    return initializeAuth(app, { persistence: getReactNativePersistence(AsyncStorage) });
  } catch {
    return getAuth(app);
  }
})();

export const db = getFirestore(app);
