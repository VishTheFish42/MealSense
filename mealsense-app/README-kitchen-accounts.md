# Provisioning kitchen staff accounts

`firestore.rules` deliberately rejects any client-created `users/{uid}` document with
`role != "student"` (see the rules file for why — it closes a self-service
privilege-escalation path that used to exist in `RegisterScreen.tsx`). That means
kitchen accounts cannot be created through the app's normal registration flow.
Both operations below are Admin SDK / console operations, which bypass Firestore
security rules entirely — that's expected and is how the rules are meant to be
used.

## To create a kitchen account today (manual, console)

1. Have the staff member register normally through the app (creates an Auth user +
   a `role: "student"` profile doc).
2. In the Firebase console → Firestore → `users/{their uid}`, edit the document and
   change `role` to `"kitchen"`, and set `onboardingComplete: true`.
3. They'll be routed to the Kitchen Dashboard on next app launch (`RootNavigator.tsx`
   checks `profile.role === 'kitchen'`).

This is fine for the current handful of test/demo accounts. It does not scale past a
small pilot — see `tasks.md` Phase 4 (Admin Dashboard), which is where a real
staff-provisioning flow (e.g. an admin-only screen backed by the Firebase Admin SDK,
or Firebase custom claims) belongs.
