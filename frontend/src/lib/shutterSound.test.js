/* eslint-env jest */
import { shutterSoundEnabled } from "./shutterSound";

// Preferensi bunyi rana (default AKTIF). Hanya bagian MURNI yang diuji —
// pemutaran audio memakai Web Audio API yang tidak ada di jsdom.
describe("shutterSoundEnabled", () => {
  afterEach(() => {
    try { localStorage.removeItem("aman_shutter_sound"); } catch { /* diam */ }
    jest.restoreAllMocks();
  });

  test("default AKTIF (belum pernah diset)", () => {
    expect(shutterSoundEnabled()).toBe(true);
  });

  test('"off" → nonaktif', () => {
    localStorage.setItem("aman_shutter_sound", "off");
    expect(shutterSoundEnabled()).toBe(false);
  });

  test("nilai lain (mis. \"on\") → tetap AKTIF", () => {
    localStorage.setItem("aman_shutter_sound", "on");
    expect(shutterSoundEnabled()).toBe(true);
  });

  test("robust bila localStorage melempar → default AKTIF (tak melempar)", () => {
    jest.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(shutterSoundEnabled()).toBe(true);
  });
});
