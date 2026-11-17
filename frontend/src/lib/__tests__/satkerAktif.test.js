import { isSuperAdminPusat } from "@/lib/satkerAktif";

// Dulu respons login tidak membawa `kode_satker`, sehingga `!kode_satker`
// bernilai benar untuk SETIAP admin dan admin satker diperlakukan sebagai
// super-admin pusat (tab Sistem, Satker Aktif, setelan universal → 403).
describe("isSuperAdminPusat", () => {
  test("admin dengan kode_satker kosong = super-admin pusat", () => {
    expect(isSuperAdminPusat({ role: "admin", kode_satker: "" })).toBe(true);
    expect(isSuperAdminPusat({ role: "super_admin", kode_satker: "  " })).toBe(true);
  });

  test("admin terikat satker BUKAN super-admin", () => {
    expect(isSuperAdminPusat({ role: "admin", kode_satker: "990000" })).toBe(false);
  });

  test("kode_satker belum diketahui (sesi lama) → bukan super-admin", () => {
    expect(isSuperAdminPusat({ role: "admin" })).toBe(false);
    expect(isSuperAdminPusat({ role: "admin", kode_satker: undefined })).toBe(false);
  });

  test("peran non-admin dan user kosong bukan super-admin", () => {
    expect(isSuperAdminPusat({ role: "viewer", kode_satker: "" })).toBe(false);
    expect(isSuperAdminPusat({ role: "operator", kode_satker: "" })).toBe(false);
    expect(isSuperAdminPusat(null)).toBe(false);
    expect(isSuperAdminPusat(undefined)).toBe(false);
  });
});
