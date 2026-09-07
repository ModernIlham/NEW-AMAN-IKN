import { HURUF_UKURAN_STIKER, hurufUkuranStiker, keteranganStiker } from "./stikerAset";

describe("hurufUkuranStiker", () => {
  it("memetakan ketiga ukuran ke S/M/L", () => {
    expect(hurufUkuranStiker("Kecil")).toBe("S");
    expect(hurufUkuranStiker("Sedang")).toBe("M");
    expect(hurufUkuranStiker("Besar")).toBe("L");
  });

  it("tak peka besar-kecil huruf maupun spasi", () => {
    // Nilai lama di basis data pernah tersimpan huruf kecil semua.
    expect(hurufUkuranStiker("  besar ")).toBe("L");
    expect(hurufUkuranStiker("SEDANG")).toBe("M");
  });

  it("nilai kosong/tak dikenal tidak dipaksakan jadi huruf", () => {
    // Kolom ini pernah berupa isian bebas; memaksa "5x3cm" menjadi satu
    // huruf berarti menampilkan ukuran yang SALAH, bukan sekadar tak lengkap.
    for (const v of ["", "   ", null, undefined, "5x3cm", "XL", 0]) {
      expect(hurufUkuranStiker(v)).toBe("");
    }
  });

  it("ketiga kuncinya huruf kecil semua", () => {
    // Pencocokan memakai toLowerCase(); kunci ber-huruf besar takkan pernah
    // cocok dan huruf ringkasnya diam-diam hilang.
    for (const k of Object.keys(HURUF_UKURAN_STIKER)) {
      expect(k).toBe(k.toLowerCase());
    }
  });
});

describe("keteranganStiker", () => {
  it("hanya 'Sudah Terpasang' yang dianggap terpasang", () => {
    expect(keteranganStiker({ stiker_status: "Sudah Terpasang" }).terpasang).toBe(true);
    expect(keteranganStiker({ stiker_status: "Belum Terpasang" }).terpasang).toBe(false);
    expect(keteranganStiker({ stiker_status: "sudah terpasang" }).terpasang).toBe(false);
  });

  it("ukuran tetap terbawa meski stiker BELUM terpasang", () => {
    // Inti permintaan pemilik: ukuran dipilih sebelum stiker dicetak, jadi
    // keadaan "belum terpasang + sudah berukuran" adalah keadaan normal.
    const k = keteranganStiker({
      stiker_status: "Belum Terpasang", stiker_ukuran: "Sedang",
    });
    expect(k.terpasang).toBe(false);
    expect(k.huruf).toBe("M");
    expect(k.ukuran).toBe("Sedang");
  });

  it("ukuran tak dikenal: huruf kosong tetapi nilainya tetap disimpan", () => {
    const k = keteranganStiker({ stiker_ukuran: "5x3cm" });
    expect(k.huruf).toBe("");
    expect(k.ukuran).toBe("5x3cm");   // tetap dapat disebut di tooltip
  });

  it("aset kosong/null tidak meledak", () => {
    for (const a of [null, undefined, {}]) {
      const k = keteranganStiker(a);
      expect(k.terpasang).toBe(false);
      expect(k.huruf).toBe("");
      expect(k.status).toBe("Belum Terpasang");
    }
  });
});
