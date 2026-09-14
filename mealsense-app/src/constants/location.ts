/**
 * Location-scoped kitchen isolation (design-spec.md §2.3, tasks.md 4.5).
 *
 * There is no per-location selection anywhere in the student app yet —
 * every order placed today is implicitly for the one pilot dining
 * location this deployment serves. DEFAULT_LOCATION_ID exists so that
 * real per-location Firestore rule enforcement (see firestore.rules) can
 * be turned on now, correctly, rather than retrofitted later once a
 * second location actually exists. When that happens, this constant goes
 * away in favor of a real location-selection flow; the rules themselves
 * don't change.
 */
export const DEFAULT_LOCATION_ID = 'main';
