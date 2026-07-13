/* eslint-env jest */
import { isQuotaExceeded } from "./idbErrors";

// Klasifikasi error kuota IndexedDB (perangkat penuh) — lintas-peramban.
// Dipakai agar sync snapshot offline degradasi anggun (cache sebagian), bukan crash.
describe("isQuotaExceeded", () => {
  test("DOMException QuotaExceededError (Blink/WebKit) → true", () => {
    expect(isQuotaExceeded({ name: "QuotaExceededError" })).toBe(true);
  });

  test("nama Firefox NS_ERROR_DOM_QUOTA_REACHED → true", () => {
    expect(isQuotaExceeded({ name: "NS_ERROR_DOM_QUOTA_REACHED" })).toBe(true);
  });

  test("kode lawas 22 (WebKit/Blink) & 1014 (Firefox) → true", () => {
    expect(isQuotaExceeded({ code: 22 })).toBe(true);
    expect(isQuotaExceeded({ code: 1014 })).toBe(true);
  });

  test("error terbungkus event (err.target.error) → true", () => {
    expect(isQuotaExceeded({ target: { error: { name: "QuotaExceededError" } } })).toBe(true);
  });

  test("error non-kuota → false", () => {
    expect(isQuotaExceeded({ name: "AbortError" })).toBe(false);
    expect(isQuotaExceeded({ name: "NotFoundError", code: 8 })).toBe(false);
    expect(isQuotaExceeded(new Error("boom"))).toBe(false);
  });

  test("null/undefined → false (aman)", () => {
    expect(isQuotaExceeded(null)).toBe(false);
    expect(isQuotaExceeded(undefined)).toBe(false);
  });
});
