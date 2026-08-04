import {
  sebutCakupan, statusKodeKlasifikasi, teksSumberKlasifikasi,
} from "./klasifikasiNomor";

describe("teksSumberKlasifikasi", () => {
  test("menyebut dari mana kodenya datang", () => {
    expect(teksSumberKlasifikasi({ kode_klasifikasi: "XX.99", sumber_klasifikasi: "eksplisit" }))
      .toBe("XX.99 · diisi manual");
    expect(teksSumberKlasifikasi({ kode_klasifikasi: "PL.02", sumber_klasifikasi: "pemetaan" }))
      .toBe("PL.02 · otomatis dari aturan pemetaan");
    expect(teksSumberKlasifikasi({ kode_klasifikasi: "UM.01", sumber_klasifikasi: "bawaan" }))
      .toBe("UM.01 · kode bawaan pengaturan");
  });

  test("kosong dinyatakan terus terang, bukan dibiarkan kosong senyap", () => {
    expect(teksSumberKlasifikasi({ kode_klasifikasi: "", sumber_klasifikasi: "kosong" }))
      .toBe("(kosong) · belum ada aturan maupun kode bawaan");
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

  test("kode bawaan dihitung terpakai walau tanpa aturan", () => {
    // Bawaan memengaruhi SETIAP nomor yang tak kena aturan — menyebutnya
    // "belum dipakai" akan menyesatkan ke arah sebaliknya.
    const st = statusKodeKlasifikasi({ dipakai_aturan: 0, bawaan: true });
    expect(st.teks).toBe("kode bawaan");
    expect(st.aktif).toBe(true);
  });

  test("bawaan + aturan disebut keduanya", () => {
    expect(statusKodeKlasifikasi({ dipakai_aturan: 2, bawaan: true }).teks)
      .toBe("kode bawaan + 2 aturan");
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
