/* eslint-env jest */
import {
  STATUS_BELUM, STATUS_SUDAH,
  autoInventarisasiEnabled, statusInventarisasiOtomatis,
} from "./inventoryStatus";

// Semua kondisi terpenuhi (fitur aktif, ada foto, ada koordinat, status default).
const lengkap = { inventory_status: STATUS_BELUM, hasPhoto: true, lat: "-0.912345", lng: "116.123456", enabled: true };

describe("statusInventarisasiOtomatis", () => {
  test("auto-status = 'Ditemukan' (bukan 'Sudah Diinventarisasi' yang yatim)", () => {
    expect(STATUS_SUDAH).toBe("Ditemukan");
  });

  test("naik ke Ditemukan bila foto + koordinat + status default 'Belum'", () => {
    expect(statusInventarisasiOtomatis(lengkap)).toBe(STATUS_SUDAH);
  });

  test("revert manual ke 'Belum' MENETAP saat enabled=false (pengguna memilih sendiri)", () => {
    // AssetForm mematikan `enabled` begitu pengguna memilih status manual —
    // sehingga "Belum Diinventarisasi" tak di-promosi ulang walau foto+koordinat.
    expect(statusInventarisasiOtomatis({ ...lengkap, inventory_status: STATUS_BELUM, enabled: false }))
      .toBe(STATUS_BELUM);
  });

  test("naik ke SUDAH juga bila status kosong ('' / undefined)", () => {
    expect(statusInventarisasiOtomatis({ ...lengkap, inventory_status: "" })).toBe(STATUS_SUDAH);
    expect(statusInventarisasiOtomatis({ ...lengkap, inventory_status: undefined })).toBe(STATUS_SUDAH);
  });

  test("TIDAK naik bila fitur dimatikan", () => {
    expect(statusInventarisasiOtomatis({ ...lengkap, enabled: false })).toBe(STATUS_BELUM);
  });

  test("TIDAK naik bila belum ada foto", () => {
    expect(statusInventarisasiOtomatis({ ...lengkap, hasPhoto: false })).toBe(STATUS_BELUM);
  });

  test("TIDAK naik bila koordinat kosong/null (dianggap belum ada)", () => {
    expect(statusInventarisasiOtomatis({ ...lengkap, lat: "" })).toBe(STATUS_BELUM);
    expect(statusInventarisasiOtomatis({ ...lengkap, lng: null })).toBe(STATUS_BELUM);
    expect(statusInventarisasiOtomatis({ ...lengkap, lat: undefined, lng: undefined })).toBe(STATUS_BELUM);
  });

  test("TIDAK menyentuh status yang sudah diubah manual", () => {
    for (const s of ["Tidak Ditemukan", "Berlebih", "Sengketa", STATUS_SUDAH]) {
      expect(statusInventarisasiOtomatis({ ...lengkap, inventory_status: s })).toBe(s);
    }
  });
});

describe("autoInventarisasiEnabled", () => {
  afterEach(() => {
    try { localStorage.removeItem("aman_auto_inventarisasi"); } catch { /* diam */ }
    jest.restoreAllMocks();
  });

  test("default AKTIF (belum pernah diset)", () => {
    expect(autoInventarisasiEnabled()).toBe(true);
  });

  test('"off" → nonaktif', () => {
    localStorage.setItem("aman_auto_inventarisasi", "off");
    expect(autoInventarisasiEnabled()).toBe(false);
  });

  test("robust bila localStorage melempar → default AKTIF", () => {
    jest.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(autoInventarisasiEnabled()).toBe(true);
  });
});
