'use strict';

// Firestore security rules tests, run against the local emulator.
//
//   npm run test:rules
//
// This spins up the Firestore emulator (via `firebase emulators:exec`) and
// runs this file with Node's built-in test runner against it — no Jest
// needed. See mealsense-app/firestore.rules for the rules under test.

const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');
const {
  initializeTestEnvironment,
  assertSucceeds,
  assertFails,
} = require('@firebase/rules-unit-testing');
const { doc, getDoc, setDoc, updateDoc, deleteDoc } = require('firebase/firestore');

const STUDENT_A = 'student-a';
const STUDENT_B = 'student-b';
const KITCHEN = 'kitchen-1';
const KITCHEN_OTHER_LOCATION = 'kitchen-2';
const LOCATION_MAIN = 'main';
const LOCATION_OTHER = 'other-hall';

let testEnv;

test.before(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: 'mealsense-rules-test',
    firestore: {
      rules: fs.readFileSync(path.resolve(__dirname, '../firestore.rules'), 'utf8'),
      host: '127.0.0.1',
      port: 8080,
    },
  });
});

test.after(async () => {
  await testEnv.cleanup();
});

test.beforeEach(async () => {
  await testEnv.clearFirestore();
});

async function seedStudentProfile(uid) {
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), 'users', uid), {
      uid,
      email: `${uid}@example.com`,
      displayName: uid,
      role: 'student',
      allergies: [],
      dietaryIdentity: [],
      conditions: [],
      nutritionalFocus: [],
      onboardingComplete: true,
      createdAt: new Date().toISOString(),
    });
  });
}

async function seedKitchenAccount(uid, locationId = LOCATION_MAIN) {
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), 'users', uid), {
      uid,
      email: `${uid}@example.com`,
      displayName: uid,
      role: 'kitchen',
      locationId,
      allergies: [],
      dietaryIdentity: [],
      conditions: [],
      nutritionalFocus: [],
      onboardingComplete: true,
      createdAt: new Date().toISOString(),
    });
  });
}

async function seedOrder(orderId, studentId, status, extra = {}) {
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), 'orders', orderId), {
      studentId,
      items: [{ menuItemId: 'l001', name: 'Grilled Chicken Bowl', quantity: 1, price: 9.5 }],
      totalPrice: 9.5,
      status,
      placedAt: new Date().toISOString(),
      paymentStatus: 'placeholder',
      locationId: LOCATION_MAIN,
      ...extra,
    });
  });
}

// ── users/{uid} ──────────────────────────────────────────────────────────

test('a signed-in user can create their own profile as role=student', async () => {
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertSucceeds(
    setDoc(doc(db, 'users', STUDENT_A), {
      uid: STUDENT_A,
      email: 'a@example.com',
      displayName: 'A',
      role: 'student',
      allergies: [],
      dietaryIdentity: [],
      conditions: [],
      nutritionalFocus: [],
      onboardingComplete: false,
      createdAt: new Date().toISOString(),
    }),
  );
});

test('self-registering as role=kitchen is rejected (the bug this phase closes)', async () => {
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertFails(
    setDoc(doc(db, 'users', STUDENT_A), {
      uid: STUDENT_A,
      email: 'a@example.com',
      displayName: 'A',
      role: 'kitchen',
      allergies: [],
      dietaryIdentity: [],
      conditions: [],
      nutritionalFocus: [],
      onboardingComplete: true,
      createdAt: new Date().toISOString(),
    }),
  );
});

test('a student cannot read another student\'s profile', async () => {
  await seedStudentProfile(STUDENT_A);
  const db = testEnv.authenticatedContext(STUDENT_B).firestore();
  await assertFails(getDoc(doc(db, 'users', STUDENT_A)));
});

test('a student can read their own profile', async () => {
  await seedStudentProfile(STUDENT_A);
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertSucceeds(getDoc(doc(db, 'users', STUDENT_A)));
});

test('a student cannot escalate their own role to kitchen via update', async () => {
  await seedStudentProfile(STUDENT_A);
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertFails(updateDoc(doc(db, 'users', STUDENT_A), { role: 'kitchen' }));
});

// ── orders/{orderId} ─────────────────────────────────────────────────────

test('a student can create an order for themselves', async () => {
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertSucceeds(
    setDoc(doc(db, 'orders', 'order-1'), {
      studentId: STUDENT_A,
      items: [{ menuItemId: 'l001', name: 'Grilled Chicken Bowl', quantity: 1, price: 9.5 }],
      totalPrice: 9.5,
      status: 'placed',
      placedAt: new Date().toISOString(),
      paymentStatus: 'placeholder',
      locationId: LOCATION_MAIN,
    }),
  );
});

test('a student cannot create an order under someone else\'s studentId', async () => {
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertFails(
    setDoc(doc(db, 'orders', 'order-1'), {
      studentId: STUDENT_B,
      items: [],
      totalPrice: 9.5,
      status: 'placed',
      placedAt: new Date().toISOString(),
      paymentStatus: 'placeholder',
      locationId: LOCATION_MAIN,
    }),
  );
});

// ── orders/{orderId}: locationId (tasks.md 4.5) ─────────────────────────

test('a student cannot create an order with no locationId', async () => {
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertFails(
    setDoc(doc(db, 'orders', 'order-1'), {
      studentId: STUDENT_A,
      items: [{ menuItemId: 'l001', name: 'Grilled Chicken Bowl', quantity: 1, price: 9.5 }],
      totalPrice: 9.5,
      status: 'placed',
      placedAt: new Date().toISOString(),
      paymentStatus: 'placeholder',
    }),
  );
});

test('a student cannot create an order with an empty-string locationId', async () => {
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertFails(
    setDoc(doc(db, 'orders', 'order-1'), {
      studentId: STUDENT_A,
      items: [{ menuItemId: 'l001', name: 'Grilled Chicken Bowl', quantity: 1, price: 9.5 }],
      totalPrice: 9.5,
      status: 'placed',
      placedAt: new Date().toISOString(),
      paymentStatus: 'placeholder',
      locationId: '',
    }),
  );
});

test('a kitchen account cannot read an order at a different location', async () => {
  await seedOrder('order-1', STUDENT_A, 'placed'); // locationId: LOCATION_MAIN
  await seedKitchenAccount(KITCHEN_OTHER_LOCATION, LOCATION_OTHER);
  const db = testEnv.authenticatedContext(KITCHEN_OTHER_LOCATION).firestore();
  await assertFails(getDoc(doc(db, 'orders', 'order-1')));
});

test('a kitchen account cannot advance an order at a different location', async () => {
  await seedOrder('order-1', STUDENT_A, 'placed'); // locationId: LOCATION_MAIN
  await seedKitchenAccount(KITCHEN_OTHER_LOCATION, LOCATION_OTHER);
  const db = testEnv.authenticatedContext(KITCHEN_OTHER_LOCATION).firestore();
  await assertFails(
    updateDoc(doc(db, 'orders', 'order-1'), { status: 'ready', readyAt: new Date().toISOString() }),
  );
});

test('a kitchen account with no locationId set cannot read any order (fails closed)', async () => {
  await seedOrder('order-1', STUDENT_A, 'placed');
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), 'users', KITCHEN), {
      uid: KITCHEN, email: `${KITCHEN}@example.com`, displayName: KITCHEN, role: 'kitchen',
      // no locationId
      allergies: [], dietaryIdentity: [], conditions: [], nutritionalFocus: [],
      onboardingComplete: true, createdAt: new Date().toISOString(),
    });
  });
  const db = testEnv.authenticatedContext(KITCHEN).firestore();
  await assertFails(getDoc(doc(db, 'orders', 'order-1')));
});

test('a student cannot read another student\'s order', async () => {
  await seedOrder('order-1', STUDENT_A, 'placed');
  const db = testEnv.authenticatedContext(STUDENT_B).firestore();
  await assertFails(getDoc(doc(db, 'orders', 'order-1')));
});

test('kitchen staff can read an order at their own location', async () => {
  await seedOrder('order-1', STUDENT_A, 'placed');
  await seedKitchenAccount(KITCHEN);
  const db = testEnv.authenticatedContext(KITCHEN).firestore();
  await assertSucceeds(getDoc(doc(db, 'orders', 'order-1')));
});

test('the order owner can advance their own order placed -> preparing (demo timer path)', async () => {
  await seedOrder('order-1', STUDENT_A, 'placed');
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertSucceeds(
    updateDoc(doc(db, 'orders', 'order-1'), { status: 'preparing', preparingAt: new Date().toISOString() }),
  );
});

test('the order owner cannot skip straight from placed to ready', async () => {
  await seedOrder('order-1', STUDENT_A, 'placed');
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertFails(
    updateDoc(doc(db, 'orders', 'order-1'), { status: 'ready', readyAt: new Date().toISOString() }),
  );
});

test('the order owner cannot change totalPrice while advancing status', async () => {
  await seedOrder('order-1', STUDENT_A, 'placed');
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertFails(
    updateDoc(doc(db, 'orders', 'order-1'), {
      status: 'preparing',
      preparingAt: new Date().toISOString(),
      totalPrice: 0.01,
    }),
  );
});

test('kitchen staff can mark a placed order ready, then completed', async () => {
  await seedOrder('order-1', STUDENT_A, 'placed');
  await seedKitchenAccount(KITCHEN);
  const db = testEnv.authenticatedContext(KITCHEN).firestore();
  await assertSucceeds(
    updateDoc(doc(db, 'orders', 'order-1'), { status: 'ready', readyAt: new Date().toISOString() }),
  );
  await assertSucceeds(
    updateDoc(doc(db, 'orders', 'order-1'), { status: 'completed', completedAt: new Date().toISOString() }),
  );
});

test('a student (non-kitchen) cannot mark an order completed', async () => {
  await seedOrder('order-1', STUDENT_A, 'ready');
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertFails(
    updateDoc(doc(db, 'orders', 'order-1'), { status: 'completed', completedAt: new Date().toISOString() }),
  );
});

test('the order owner can delete their own order (data-deletion flow)', async () => {
  await seedOrder('order-1', STUDENT_A, 'placed');
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertSucceeds(deleteDoc(doc(db, 'orders', 'order-1')));
});

// ── analytics_events/{eventId} ────────────────────────────────────────────

test('a student can create their own analytics event', async () => {
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertSucceeds(
    setDoc(doc(db, 'analytics_events', 'event-1'), {
      type: 'recommendation_fetch',
      studentId: STUDENT_A,
      durationMs: 1200,
    }),
  );
});

test('a student cannot create an analytics event under someone else\'s studentId', async () => {
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertFails(
    setDoc(doc(db, 'analytics_events', 'event-1'), {
      type: 'recommendation_fetch',
      studentId: STUDENT_B,
      durationMs: 1200,
    }),
  );
});

test('a student cannot read back an analytics event, even their own', async () => {
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), 'analytics_events', 'event-1'), {
      type: 'recommendation_fetch',
      studentId: STUDENT_A,
      durationMs: 1200,
    });
  });
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertFails(getDoc(doc(db, 'analytics_events', 'event-1')));
});

test('a student cannot update or delete an analytics event', async () => {
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    await setDoc(doc(ctx.firestore(), 'analytics_events', 'event-1'), {
      type: 'recommendation_fetch',
      studentId: STUDENT_A,
      durationMs: 1200,
    });
  });
  const db = testEnv.authenticatedContext(STUDENT_A).firestore();
  await assertFails(updateDoc(doc(db, 'analytics_events', 'event-1'), { durationMs: 500 }));
  await assertFails(deleteDoc(doc(db, 'analytics_events', 'event-1')));
});

test('an unauthenticated client cannot read or write anything', async () => {
  await seedOrder('order-1', STUDENT_A, 'placed');
  const db = testEnv.unauthenticatedContext().firestore();
  await assertFails(getDoc(doc(db, 'orders', 'order-1')));
  await assertFails(setDoc(doc(db, 'orders', 'order-2'), { studentId: STUDENT_A }));
});
