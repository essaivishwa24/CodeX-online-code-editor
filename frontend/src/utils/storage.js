export function readStorage(key, fallback) {
  try {
    const stored = window.localStorage.getItem(key);
    return stored === null ? fallback : stored;
  } catch {
    return fallback;
  }
}

export function writeStorage(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // The editor remains usable when storage is disabled or full.
  }
}
