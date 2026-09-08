import { initializeApp, getApps, getApp } from 'firebase/app';
import { initializeAuth, getReactNativePersistence, getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import AsyncStorage from '@react-native-async-storage/async-storage';

const firebaseConfig = {
  apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY,
  authDomain: "mealsense-cb5ab.firebaseapp.com",
  projectId: "mealsense-cb5ab",
  storageBucket: "mealsense-cb5ab.firebasestorage.app",
  messagingSenderId: "983327527722",
  appId: "1:983327527722:web:b49f9f916ab83573758453",
  measurementId: "G-KWQVSEVN21"
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
