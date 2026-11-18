import {
  bacaModeInventarisasi, kunciModeInventarisasi, perluSiapOfflineOtomatis, simpanModeInventarisasi,
} from "@/lib/siapOffline";

// F7: data offline disiapkan otomatis di perangkat lapangan, dan pilihan
// Mode Inventarisasi diingat per pengguna + kegiatan.
const env = ({ coarse = false, lebar = 1366, saveData = false, tanpaMatchMedia = false } = {}) => ({
  innerWidth: lebar,
  navigator: { connection: { saveData } },
  ...(tanpaMatchMedia ? {} : { matchMedia: q => ({ matches: q === "(pointer: coarse)" && coarse }) }),
});

describe("perluSiapOfflineOtomatis", () => {
  test("HP/tablet (sentuh kasar atau ≤1023px) → otomatis", () => {
    expect(perluSiapOfflineOtomatis(env({ coarse: true, lebar: 1280 }))).toBe(true);
    expect(perluSiapOfflineOtomatis(env({ lebar: 412 }))).toBe(true);
    expect(perluSiapOfflineOtomatis(env({ lebar: 1023 }))).toBe(true);
  });

  test("desktop kantor tetap manual", () => {
    expect(perluSiapOfflineOtomatis(env({ lebar: 1024 }))).toBe(false);
    expect(perluSiapOfflineOtomatis(env({ lebar: 1920 }))).toBe(false);
  });

  test("mode hemat data (Save-Data) dihormati walau di HP", () => {
    expect(perluSiapOfflineOtomatis(env({ coarse: true, lebar: 412, saveData: true }))).toBe(false);
  });

  test("lingkungan tanpa matchMedia / rusak tidak melempar galat", () => {
    expect(perluSiapOfflineOtomatis(env({ lebar: 600, tanpaMatchMedia: true }))).toBe(true);
    expect(perluSiapOfflineOtomatis({})).toBe(false);
    expect(perluSiapOfflineOtomatis(null)).toBe(false);
    const meledak = { get navigator() { throw new Error("diblokir"); } };
    expect(perluSiapOfflineOtomatis(meledak)).toBe(false);
  });
});

describe("pilihan Mode Inventarisasi tersimpan", () => {
  const simpanan = () => {
    const isi = new Map();
    return {
      isi,
      getItem: k => (isi.has(k) ? isi.get(k) : null),
      setItem: (k, v) => isi.set(k, String(v)),
      removeItem: k => isi.delete(k),
    };
  };

  test("kunci per pengguna + kegiatan; tanpa salah satunya tidak ada kunci", () => {
    expect(kunciModeInventarisasi("u1", "k1")).not.toBe(kunciModeInventarisasi("u2", "k1"));
    expect(kunciModeInventarisasi("u1", "k1")).not.toBe(kunciModeInventarisasi("u1", "k2"));
    expect(kunciModeInventarisasi("", "k1")).toBeNull();
    expect(kunciModeInventarisasi("u1", null)).toBeNull();
  });

  test("simpan aktif → terbaca kembali; mati menghapus kunci", () => {
    const s = simpanan();
    expect(bacaModeInventarisasi("u1", "k1", s)).toBe(false);
    simpanModeInventarisasi("u1", "k1", true, s);
    expect(bacaModeInventarisasi("u1", "k1", s)).toBe(true);
    expect(bacaModeInventarisasi("u2", "k1", s)).toBe(false);   // perangkat bersama
    expect(bacaModeInventarisasi("u1", "k2", s)).toBe(false);
    simpanModeInventarisasi("u1", "k1", false, s);
    expect(bacaModeInventarisasi("u1", "k1", s)).toBe(false);
    expect(s.isi.size).toBe(0);
  });

  test("penyimpanan diblokir tidak melempar galat dan kembali ke bawaan mati", () => {
    const rusak = { getItem() { throw new Error("x"); }, setItem() { throw new Error("x"); }, removeItem() { throw new Error("x"); } };
    expect(() => simpanModeInventarisasi("u1", "k1", true, rusak)).not.toThrow();
    expect(bacaModeInventarisasi("u1", "k1", rusak)).toBe(false);
    expect(bacaModeInventarisasi("u1", "k1", null)).toBe(false);
  });
});
