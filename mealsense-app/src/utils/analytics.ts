import { addDoc, collection, serverTimestamp } from 'firebase/firestore';
import { db } from '../config/firebase';

/**
 * README §14 / tasks.md 8.2: "time to recommendation from app open" (<5s
 * target). Fire-and-forget — analytics must never block the UI or surface
 * an error to the student just because a background write failed. Kept as
 * one narrow function rather than a generic event-logging system: there's
 * exactly one event type instrumented so far, and a generic abstraction
 * isn't worth building until there's a second one.
 */
export function logRecommendationFetchTiming(studentId: string, durationMs: number): void {
  addDoc(collection(db, 'analytics_events'), {
    type: 'recommendation_fetch',
    studentId,
    durationMs,
    createdAt: serverTimestamp(),
  }).catch(() => {
    // Best-effort only — a logging failure here must never surface to the
    // student, who already has their recommendation on screen.
  });
}
