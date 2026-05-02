import type { Persistence } from 'firebase/auth';

// firebase/auth types resolve the browser build, which omits getReactNativePersistence.
// Metro resolves the react-native build at runtime, so the function exists — this
// augmentation just makes TypeScript aware of it.
declare module 'firebase/auth' {
  export function getReactNativePersistence(storage: {
    getItem(key: string): Promise<string | null>;
    setItem(key: string, value: string): Promise<void>;
    removeItem(key: string): Promise<void>;
  }): Persistence;
}
