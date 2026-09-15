// tasks.md 7.2: environment-based API URL, not a hardcoded LAN IP that
// goes stale every time the dev Mac switches networks. Defaults to the
// real deployed backend (Cloud Run, tasks.md Phase 7) so a production
// build works with zero configuration; override EXPO_PUBLIC_API_BASE_URL
// in mealsense-app/.env for local development against
// `cd mealsense-api && venv/bin/uvicorn main:app --host 0.0.0.0 --reload`
// running on your own machine instead.
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL || 'https://mealsense-api-983327527722.us-west1.run.app';
