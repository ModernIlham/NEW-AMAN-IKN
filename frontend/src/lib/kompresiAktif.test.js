/**
 * Indikator kuota harus menunjuk layanan yang BENAR-BENAR melayani.
 *
 * Cacat aslinya (dilaporkan dari lapangan): chip toolbar menampilkan **0/500**
 * padahal Compresto masih menyisakan 474. Pemilihannya dulu berbunyi
 *
 *     quotas.find(q => q.available && q.limit > 0 && q.remaining > 0) || quotas[0]
 *
 * dan `available` berarti *"percobaan TERAKHIR terbukti berhasil"* — catatan
 * diagnostik di memori server yang hangus tiap kali proses restart. Setelah
 * satu deploy, layanan sehat pun kembali `available: false`, tak ada satu pun
 * yang lolos saringan, dan `|| quotas[0]` menjatuhkannya ke Tinify yang
 * kuotanya nol.
 */
import { URUTAN, entriAktif, layakPakai, ringkasAktif, sisaKuota } from "./kompresiAktif";

const entri = (service, x = {}) => ({
  service, name: service, terpasang: true, limit: 500, used: 0, remaining: 500, ...x,
});
const pillow = (x = {}) => entri("pillow", { name: "Lokal (Pillow)", limit: -1, remaining: -1, ...x });

// Data persis seperti pada layar pemilik.
const LAPANGAN = [
  entri("tinify", { name: "Tinify (TinyPNG)", used: 500, remaining: 0, available: true }),
  entri("compresto", { name: "Compresto", used: 26, remaining: 474, available: false }),
  entri("uploadcare", { name: "Uploadcare", terpasang: false, limit: 1000, remaining: 1000, available: false }),
  pillow(),
];

describe("keadaan lapangan — 0/500 padahal Compresto masih 474", () => {
  test("cara LAMA memang memilih Tinify yang kosong", () => {
    // Merekam cacatnya supaya perbaikannya terbukti bukan kebetulan.
    const lama = LAPANGAN.find((q) => q.available && q.limit > 0 && q.remaining > 0) || LAPANGAN[0];
    expect(lama.service).toBe("tinify");
    expect(lama.remaining).toBe(0);
  });

  test("kini beralih ke Compresto", () => {
    expect(entriAktif(LAPANGAN).service).toBe("compresto");
  });

  test("angka yang tampil ikut layanan aktif, bukan Tinify", () => {
    expect(ringkasAktif(LAPANGAN).teks).toBe("474");
  });

  test("nama layanan aktif ikut dibawa untuk label", () => {
    expect(ringkasAktif(LAPANGAN).nama).toBe("Compresto");
  });

  test("available palsu tidak menggugurkan giliran", () => {
    expect(LAPANGAN[1].available).toBe(false);
    expect(layakPakai(LAPANGAN[1])).toBe(true);
  });
});

describe("berjenjang Tinify → Compresto → Uploadcare → Pillow", () => {
  const rantai = (habis = []) => [
    entri("tinify", habis.includes("tinify") ? { used: 500, remaining: 0 } : {}),
    entri("compresto", habis.includes("compresto") ? { used: 500, remaining: 0 } : {}),
    entri("uploadcare", { limit: 1000, remaining: habis.includes("uploadcare") ? 0 : 1000,
                          used: habis.includes("uploadcare") ? 1000 : 0 }),
    pillow(),
  ];

  test.each([
    [[], "tinify"],
    [["tinify"], "compresto"],
    [["tinify", "compresto"], "uploadcare"],
    [["tinify", "compresto", "uploadcare"], "pillow"],
  ])("habis %p → aktif %s", (habis, harap) => {
    expect(entriAktif(rantai(habis)).service).toBe(harap);
  });

  test("semua kuota habis TIDAK berarti gagal — Pillow mengambil alih", () => {
    const r = ringkasAktif(rantai(["tinify", "compresto", "uploadcare"]));
    expect(r.entri.service).toBe("pillow");
    expect(r.takTerbatas).toBe(true);
    expect(r.teks).toBe("∞");
    // Persen 0 → chip tak dicat merah. Merah di sini berbohong: kompresi tetap
    // berjalan, hanya lokal.
    expect(r.persen).toBe(0);
  });

  test("urutan daftar masukan tidak menentukan", () => {
    expect(entriAktif(rantai().slice().reverse()).service).toBe("tinify");
  });

  test("URUTAN sama persis dengan rantai server", () => {
    expect(URUTAN).toEqual(["tinify", "compresto", "uploadcare", "pillow"]);
  });
});

describe("jawaban server diutamakan", () => {
  test("memakai `aktif` dari payload", () => {
    expect(entriAktif(LAPANGAN, "uploadcare").service).toBe("uploadcare");
  });

  test("`aktif` yang menunjuk layanan tak dikenal diabaikan", () => {
    expect(entriAktif(LAPANGAN, "layanan_hantu").service).toBe("compresto");
  });

  test("`aktif` kosong → hitung sendiri", () => {
    expect(entriAktif(LAPANGAN, "").service).toBe("compresto");
  });
});

describe("syarat giliran", () => {
  test("kunci belum dipasang → dilewati", () => {
    expect(layakPakai(entri("compresto", { terpasang: false }))).toBe(false);
  });

  test("kuota habis → dilewati", () => {
    expect(layakPakai(entri("tinify", { remaining: 0 }))).toBe(false);
  });

  test("tak terbatas → selalu layak", () => {
    expect(layakPakai(pillow())).toBe(true);
  });

  test("`terpasang` hilang (payload lama) dianggap belum siap", () => {
    expect(layakPakai({ service: "tinify", limit: 500, remaining: 500 })).toBe(false);
  });
});

describe("sisaKuota", () => {
  test("memakai remaining bila ada", () => {
    expect(sisaKuota({ limit: 500, used: 10, remaining: 474 })).toBe(474);
  });

  test("dihitung dari limit - used bila remaining hilang", () => {
    expect(sisaKuota({ limit: 500, used: 480 })).toBe(20);
  });

  test("limit negatif = tak terbatas", () => {
    expect(sisaKuota({ limit: -1 })).toBe(-1);
  });

  test("remaining 0 tetap 0, bukan jatuh ke perhitungan cadangan", () => {
    // `remaining || limit - used` akan membuat layanan yang HABIS tampak
    // masih punya sisa — persis jenis kekeliruan yang dijaga di sini.
    expect(sisaKuota({ limit: 500, used: 500, remaining: 0 })).toBe(0);
  });

  test("nilai kacau → 0 (bukan NaN yang lolos perbandingan)", () => {
    expect(sisaKuota({ limit: "banyak", remaining: "entah" })).toBe(0);
    expect(layakPakai({ terpasang: true, limit: "banyak", remaining: "entah" })).toBe(false);
  });
});

describe("tepian", () => {
  test("daftar kosong tidak meledak", () => {
    expect(entriAktif([])).toBeNull();
    expect(entriAktif(null)).toBeNull();
    expect(ringkasAktif(null).teks).toBe("—");
  });

  test("entri null di dalam daftar diabaikan", () => {
    expect(entriAktif([null, entri("compresto")]).service).toBe("compresto");
  });

  test("persen dihitung dari layanan aktif, bukan gabungan semua", () => {
    // Gabungan: (500+26+0)/(500+500+1000) ≈ 26% → hijau, padahal tangki yang
    // dipakai (Compresto) baru 5% terpakai. Angka gabungan tak berarti apa-apa.
    expect(Math.round(ringkasAktif(LAPANGAN).persen)).toBe(5);
  });
});
