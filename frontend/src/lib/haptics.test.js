/* eslint-env jest */
import { resolveHapticPattern, HAPTIC_PATTERNS } from "./haptics";

// Pemetaan nama kejadian → pola getar. Pola tiap kejadian harus BEDA agar
// pengguna bisa membedakan tanpa melihat layar.
describe("resolveHapticPattern", () => {
  test("nama dikenal → pola-nya masing-masing", () => {
    expect(resolveHapticPattern("gpsLock")).toEqual([18, 40, 70]);
    expect(resolveHapticPattern("save")).toEqual([45]);
    expect(resolveHapticPattern("navNext")).toEqual([14]);
    expect(resolveHapticPattern("navPrev")).toEqual([14, 34, 14]);
  });

  test("nama tak dikenal → fallback 'shutter' (tik ringan, tak undefined)", () => {
    expect(resolveHapticPattern("entah")).toEqual(HAPTIC_PATTERNS.shutter);
    expect(resolveHapticPattern(undefined)).toEqual(HAPTIC_PATTERNS.shutter);
  });

  test("save vs navNext vs navPrev BEDA (bisa dibedakan)", () => {
    const s = JSON.stringify(resolveHapticPattern("save"));
    const n = JSON.stringify(resolveHapticPattern("navNext"));
    const p = JSON.stringify(resolveHapticPattern("navPrev"));
    expect(new Set([s, n, p]).size).toBe(3);
  });

  test("semua pola = array angka positif", () => {
    Object.values(HAPTIC_PATTERNS).forEach((pat) => {
      expect(Array.isArray(pat)).toBe(true);
      expect(pat.length).toBeGreaterThan(0);
      pat.forEach((ms) => expect(typeof ms === "number" && ms > 0).toBe(true));
    });
  });
});
