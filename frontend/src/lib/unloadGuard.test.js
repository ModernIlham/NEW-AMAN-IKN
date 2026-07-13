/* eslint-env jest */
import { hasUnsyncedWork } from "./unloadGuard";

// Penentu apakah reload/keluar perlu ditahan demi keamanan data offline.
describe("hasUnsyncedWork", () => {
  test("tidak ada apa-apa → false (boleh reload)", () => {
    expect(hasUnsyncedWork({ pendingCount: 0, actionCount: 0 })).toBe(false);
    expect(hasUnsyncedWork({})).toBe(false);
    expect(hasUnsyncedWork()).toBe(false);
  });

  test("ada pending (queued/saving/gagal jaringan) → true", () => {
    expect(hasUnsyncedWork({ pendingCount: 1, actionCount: 0 })).toBe(true);
    expect(hasUnsyncedWork({ pendingCount: 5 })).toBe(true);
  });

  test("ada item macet (konflik/terkunci) → true", () => {
    expect(hasUnsyncedWork({ pendingCount: 0, actionCount: 2 })).toBe(true);
    expect(hasUnsyncedWork({ actionCount: 1 })).toBe(true);
  });

  test("keduanya ada → true", () => {
    expect(hasUnsyncedWork({ pendingCount: 3, actionCount: 2 })).toBe(true);
  });

  test("nilai non-numerik/NaN diperlakukan 0 (aman)", () => {
    expect(hasUnsyncedWork({ pendingCount: undefined, actionCount: null })).toBe(false);
    expect(hasUnsyncedWork({ pendingCount: "abc" })).toBe(false);
    expect(hasUnsyncedWork({ pendingCount: "2" })).toBe(true); // string angka tetap terbaca
  });
});
