import {
  sebutCakupan, statusKodeKlasifikasi, teksSumberKlasifikasi,
} from "./klasifikasiNomor";

describe("teksSumberKlasifikasi", () => {
  test("menyebut dari mana kodenya datang", () => {
    expect(teksSumberKlasifikasi({ kode_klasifikasi: "XX.99", sumber_klasifikasi: "eksplisit" }))
      .toBe("XX.99 · diisi manual");
    expect(teksSumberKlasifikasi({ kode_klasifikasi: "PL.02", sumber_klasifikasi: "pemetaan" }))
      .toBe("PL.02 · otomatis dari aturan pemetaan");
  });

  test("TAK PERNAH menamai kode bawaan sebagai klasifikasi arsip", () => {
    // Kalimat "Klasifikasi: SATKER-D · kode bawaan pengaturan" itulah yang
    // dikeluhkan pemilik: dua hal berbeda dipanggil dengan satu nama.
    for (const sumber of ["bawaan", "", "entah"]) {
      const t = teksSumberKlasifikasi({ kode_klasifikasi: "", sumber_klasifikasi: sumber });
      expect(t).not.toMatch(/kode bawaan/);
    }
  });

  test("kosong dinyatakan terus terang, bukan dibiarkan kosong senyap", () => {
    expect(teksSumberKlasifikasi({ kode_klasifikasi: "", sumber_klasifikasi: "kosong" }))
      .toBe("(kosong) · belum ada aturan otomatis — isi manual bila surat ini perlu kode");
  });

  test("tanpa data → string kosong (pemanggil menyembunyikan barisnya)", () => {
    expect(teksSumberKlasifikasi(null)).toBe("");
  });
});

describe("statusKodeKlasifikasi", () => {
  test("kode yang tak dipasang aturan mana pun mengaku menganggur", () => {
    // Inilah keadaan yang bikin pemilik mengira fiturnya rusak: kode sudah
    // didaftarkan di master, tapi nomor surat tak pernah memakainya.
    const st = statusKodeKlasifikasi({ dipakai_aturan: 0, bawaan: false });
    expect(st.teks).toBe("belum dipakai");
    expect(st.aktif).toBe(false);
    expect(st.warna).toContain("amber");
  });

  test("dipakai aturan → hijau, dengan jumlahnya", () => {
    expect(statusKodeKlasifikasi({ dipakai_aturan: 1 }).teks).toBe("1 aturan");
    expect(statusKodeKlasifikasi({ dipakai_aturan: 3 }).teks).toBe("3 aturan");
    expect(statusKodeKlasifikasi({ dipakai_aturan: 2 }).warna).toContain("emerald");
  });

  test("kode bawaan yang DIMINTA format nomor dihitung terpakai", () => {
    const st = statusKodeKlasifikasi({
      dipakai_aturan: 0, bawaan: true, bawaan_di_nomor: true });
    expect(st.teks).toBe("kode bawaan");
    expect(st.aktif).toBe(true);
    expect(st.warna).toContain("emerald");
  });

  test("kode bawaan yang TAK diminta format nomor mengaku tak di nomor", () => {
    // Sejak kedua kode berdiri sendiri, jadi "kode bawaan" bukan lagi jaminan
    // ikut ke nomor. Badge hijau tanpa syarat akan mengulang persis kesalahan
    // yang melahirkan badge ini: mengatakan sebuah kode bekerja, padahal tidak.
    const st = statusKodeKlasifikasi({
      dipakai_aturan: 0, bawaan: true, bawaan_di_nomor: false });
    expect(st.teks).toBe("kode bawaan (tak di nomor)");
    expect(st.aktif).toBe(false);
    expect(st.warna).toContain("amber");
  });

  test("bawaan + aturan disebut keduanya, dengan catatan bila tak di nomor", () => {
    expect(statusKodeKlasifikasi({
      dipakai_aturan: 2, bawaan: true, bawaan_di_nomor: true }).teks)
      .toBe("kode bawaan + 2 aturan");
    // Aturannya tetap bekerja, jadi statusnya tetap aktif — yang tak bekerja
    // cuma sisi bawaannya, dan itu disebutkan apa adanya.
    const st = statusKodeKlasifikasi({
      dipakai_aturan: 2, bawaan: true, bawaan_di_nomor: false });
    expect(st.teks).toBe("kode bawaan (tak di nomor) + 2 aturan");
    expect(st.aktif).toBe(true);
  });

  test("entri tanpa penanda (server lama) tak meledak", () => {
    expect(statusKodeKlasifikasi({}).aktif).toBe(false);
    expect(statusKodeKlasifikasi(undefined).teks).toBe("belum dipakai");
  });
});

describe("sebutCakupan", () => {
  test("empat bentuk cakupan", () => {
    expect(sebutCakupan("pelaporan", "Laporan")).toBe("modul pelaporan + Laporan");
    expect(sebutCakupan("pelaporan", "")).toBe("modul pelaporan, semua jenis naskah");
    expect(sebutCakupan("", "Berita Acara")).toBe("Berita Acara, semua modul");
    expect(sebutCakupan("", "")).toBe("semua modul & semua jenis naskah");
  });
});
