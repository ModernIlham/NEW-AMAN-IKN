/* eslint-env jest */
import { resolveBaseVersion } from "./occ";

// Inti perbaikan "toast konflik berulang / terus minta sinkron" pada edit
// berantai satu pengguna: If-Match harus memakai versi TERTINGGI yang diketahui.
describe("resolveBaseVersion", () => {
  test("edit berantai: pakai lastSaved yang lebih baru (cegah self-409)", () => {
    // form dimuat di v5, simpanan sebelumnya sudah konfirmasi v6 → kirim 6
    expect(resolveBaseVersion(5, 6)).toBe(6);
  });

  test("tak menurunkan versi: base lebih baru dari lastSaved basi", () => {
    // daftar sudah dimuat ulang ke v8 (mis. edit orang lain), lastSaved kita 6
    // → tetap 8 agar bentrok sah tetap terdeteksi (bukan ditutupi)
    expect(resolveBaseVersion(8, 6)).toBe(8);
  });

  test("lastSaved null → pakai base", () => {
    expect(resolveBaseVersion(5, null)).toBe(5);
    expect(resolveBaseVersion(5, undefined)).toBe(5);
  });

  test("base null → pakai lastSaved", () => {
    expect(resolveBaseVersion(null, 6)).toBe(6);
    expect(resolveBaseVersion(undefined, 6)).toBe(6);
  });

  test("keduanya null → null (CREATE / belum ada versi)", () => {
    expect(resolveBaseVersion(null, null)).toBe(null);
    expect(resolveBaseVersion(undefined, undefined)).toBe(null);
  });

  test("sama → nilai itu", () => {
    expect(resolveBaseVersion(7, 7)).toBe(7);
  });

  test("nilai non-angka diabaikan (aman)", () => {
    expect(resolveBaseVersion("bukan-angka", 6)).toBe(6);
    expect(resolveBaseVersion(5, NaN)).toBe(5);
  });
});
