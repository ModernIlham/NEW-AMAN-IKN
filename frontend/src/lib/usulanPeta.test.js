import {
  bisaDisetujui, judulUsulan, kalimatYakinSemua, rekapUsulan,
  ringkasHasilImpor, statusUsulan,
} from "./usulanPeta";

const titik = (id, st) => ({ id, jenis: "titik", nama_titik: `T-${id}`, status_usulan: st });
const komentarAset = (id) => ({ id, jenis: "komentar", target_jenis: "aset", target_id: "a-1", teks: "x" });
const komentarTitik = (id, target) => ({ id, jenis: "komentar", target_jenis: "titik", target_id: target, teks: "x" });

describe("statusUsulan", () => {
  test("dokumen era-lama tanpa field dianggap BELUM ditinjau", () => {
    // Kalau dianggap selesai, kontribusi lapangan yang sudah terlanjur masuk
    // tak akan pernah muncul di layar peninjauan — hilang tanpa terlihat.
    expect(statusUsulan({})).toBe("terbuka");
    expect(statusUsulan({ status_usulan: "ngawur" })).toBe("terbuka");
    expect(statusUsulan({ status_usulan: "disetujui" })).toBe("disetujui");
  });
});

describe("bisaDisetujui", () => {
  test("titik selalu bisa disetujui", () => {
    expect(bisaDisetujui(titik("t1")).bisa).toBe(true);
  });

  test("komentar pada aset nyata bisa langsung", () => {
    expect(bisaDisetujui(komentarAset("k1")).bisa).toBe(true);
  });

  test("komentar pada titik yang BELUM disetujui ditahan, dengan sebab", () => {
    // Tanpa ini layar menawarkan tombol yang server pasti tolak 409.
    const semua = [titik("t1"), komentarTitik("k1", "t1")];
    const r = bisaDisetujui(semua[1], semua);
    expect(r.bisa).toBe(false);
    expect(r.alasan).toMatch(/titik/i);
  });

  test("komentar pada titik yang SUDAH disetujui jadi bisa", () => {
    const semua = [titik("t1", "disetujui"), komentarTitik("k1", "t1")];
    expect(bisaDisetujui(semua[1], semua).bisa).toBe(true);
  });

  test("yang sudah diimpor tak ditawarkan lagi", () => {
    const r = bisaDisetujui(titik("t1", "disetujui"));
    expect(r.bisa).toBe(false);
    expect(r.alasan).toMatch(/sudah/i);
  });

  test("komentar pada titik yang hilang tak meledak", () => {
    expect(bisaDisetujui(komentarTitik("k1", "entah"), []).bisa).toBe(false);
  });
});

describe("rekap & kalimat konfirmasi", () => {
  test("memisahkan titik dan komentar", () => {
    expect(rekapUsulan([titik("t1"), titik("t2"), komentarAset("k1")]))
      .toEqual({ titik: 2, komentar: 1, total: 3 });
  });

  test("kalimat menyebut ANGKA, bukan 'semua data'", () => {
    expect(kalimatYakinSemua([titik("t1"), titik("t2"), komentarAset("k1")]))
      .toBe("Impor 2 titik → aset baru dan 1 komentar ke peta asli sekarang?");
    expect(kalimatYakinSemua([komentarAset("k1")]))
      .toBe("Impor 1 komentar ke peta asli sekarang?");
    expect(kalimatYakinSemua([])).toBe("Tidak ada usulan yang menunggu.");
  });
});

describe("ringkasHasilImpor", () => {
  test("yang dilewati & gagal ikut disebut, bukan ditelan", () => {
    expect(ringkasHasilImpor({ disetujui: 5 })).toBe("5 usulan diimpor");
    expect(ringkasHasilImpor({ disetujui: 5, dilewati: [1], gagal: [1, 2] }))
      .toBe("5 usulan diimpor · 1 dilewati · 2 gagal");
  });

  test("hasil kosong tak jadi 'undefined'", () => {
    expect(ringkasHasilImpor(null)).toBe("0 usulan diimpor");
  });
});

describe("judulUsulan", () => {
  test("titik memakai namanya, komentar memakai teksnya (dipotong)", () => {
    expect(judulUsulan(titik("t1"))).toBe("T-t1");
    expect(judulUsulan({ jenis: "komentar", teks: "a".repeat(100) }))
      .toBe(`${"a".repeat(80)}…`);
    expect(judulUsulan({ jenis: "titik" })).toBe("Titik tanpa nama");
  });
});
