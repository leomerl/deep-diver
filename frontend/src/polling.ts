// The API has no job endpoints (DESIGN §1), so progress is polled. A dead-lettered job never produces
// a row, hence the give-up: without it the UI would wait forever.
export const POLL_MS = 3_000;
export const GIVE_UP_MS = 15 * 60 * 1_000;
