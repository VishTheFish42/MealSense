/**
 * Firestore's JS SDK throws on any field value of `undefined` (it isn't
 * configured with `ignoreUndefinedProperties`). Screens build update objects
 * with `value || undefined` for optional fields, so any field left blank
 * must be dropped before the object reaches setDoc/updateDoc.
 */
export function stripUndefined<T extends object>(obj: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== undefined),
  ) as Partial<T>;
}
