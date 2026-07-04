/**
 * Backend reachability check.
 *
 * `navigator.onLine` only reports whether the device has a network interface
 * up — it says nothing about whether the backend is actually reachable
 * (captive portals, dead Wi-Fi, server down). Before declaring "online" or
 * auto-flushing queued saves, verify with a real request against the
 * lightweight, unauthenticated GET /api/health endpoint.
 */

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Retry delay suggested to callers when the server is unreachable while the
// browser still reports navigator.onLine === true.
export const REACHABILITY_RETRY_MS = 10000;

/**
 * Returns true only if the backend answers /api/health within `timeoutMs`.
 * Never throws — any failure (timeout, DNS, non-2xx) resolves to false.
 * @param {number} timeoutMs - Abort the probe after this many ms (default 3s).
 */
export async function checkReachable(timeoutMs = 3000) {
  if (typeof navigator !== "undefined" && !navigator.onLine) return false;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API}/health`, {
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
    });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}
