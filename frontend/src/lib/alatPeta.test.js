import {
  ALAT_PETA, daftarAlatPeta, perluLaciAlat, ringkasAlatAktif,
} from "./alatPeta";

describe("daftarAlatPeta", () => {
  test("operator punya usulan, seleksi, dan alat ukur", () => {
    expect(daftarAlatPeta({ bolehModerasi: true }))
      .toEqual([ALAT_PETA.USULAN, ALAT_PETA.SELEKSI, ALAT_PETA.UKUR]);
  });

  test("tamu HANYA punya alat ukur — usulan & seleksi milik operator", () => {
    // Ini bukan soal tata letak: kalau tamu ikut kebagian tombol moderasi,
    // pemegang tautan mana pun bisa menghapus titik kolaborasi.
    expect(daftarAlatPeta({ bolehModerasi: false })).toEqual([ALAT_PETA.UKUR]);
    expect(daftarAlatPeta(undefined)).toEqual([ALAT_PETA.UKUR]);
  });
});

describe("perluLaciAlat", () => {
  test("operator: dilipat — tiga tombol jadi satu menghemat ruang nyata", () => {
    expect(perluLaciAlat({ bolehModerasi: true })).toBe(true);
  });

  test("tamu: TIDAK dilipat — melipat satu tombol cuma menambah ketukan", () => {
    expect(perluLaciAlat({ bolehModerasi: false })).toBe(false);
  });
});

describe("ringkasAlatAktif", () => {
  test("tanpa saklar menyala, labelnya menyebut isi lacinya", () => {
    const r = ringkasAlatAktif({ moderasi: false, ukur: false });
    expect(r.adaAktif).toBe(false);
    expect(r.daftar).toEqual([]);
    expect(r.label).toMatch(/usulan/i);
    expect(r.label).toMatch(/ukur/i);
  });

  test("alat ukur menyala harus TERBACA dari luar laci", () => {
    // Inti penjagaan: saklar yang tersembunyi di dalam laci tetap memakan
    // ketukan di peta. Kalau labelnya tak menyebutkannya, pemakainya menaruh
    // titik ukur tanpa tahu kenapa.
    const r = ringkasAlatAktif({ moderasi: false, ukur: true });
    expect(r.adaAktif).toBe(true);
    expect(r.daftar).toEqual(["Alat ukur"]);
    expect(r.label).toMatch(/aktif/i);
    expect(r.label).toMatch(/ukur/i);
  });

  test("mode seleksi menyala juga terbaca", () => {
    const r = ringkasAlatAktif({ moderasi: true, ukur: false });
    expect(r.daftar).toEqual(["Seleksi"]);
    expect(r.label).toMatch(/seleksi/i);
    expect(r.label).toMatch(/aktif/i);
  });

  test("dua-duanya menyala disebut dua-duanya, bukan salah satu", () => {
    const r = ringkasAlatAktif({ moderasi: true, ukur: true });
    expect(r.daftar).toEqual(["Seleksi", "Alat ukur"]);
    expect(r.label).toMatch(/Seleksi/);
    expect(r.label).toMatch(/Alat ukur/);
  });

  test("status kosong/undefined tak melempar & tak mengaku aktif", () => {
    expect(ringkasAlatAktif(undefined).adaAktif).toBe(false);
    expect(ringkasAlatAktif({}).adaAktif).toBe(false);
  });
});
