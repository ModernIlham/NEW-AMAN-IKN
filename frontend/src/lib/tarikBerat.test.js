import {
  AMBANG_TARIK,
  MAKS_TAMPAK,
  TAHAP_CAP,
  TAHAP_DAFTAR,
  TAHAP_TERSEMBUNYI,
  arahSah,
  cukupUntukBuka,
  geserTahap,
  kemajuanTarik,
  majuTahap,
  redamTarik,
  tahapSetelahTarik,
} from "./tarikBerat";

describe("redamTarik — gerakan harus terasa BERAT", () => {
  test("tarikan iseng nyaris tak menggerakkan apa pun", () => {
    // Serempetan 8 px: kalau ini sudah menggeser belasan piksel, bilah akan
    // terasa "gampang kebuka" — persis yang diminta untuk dihilangkan.
    expect(redamTarik(8)).toBeLessThan(4);
  });

  test("makin jauh ditarik makin seret (turunan mengecil)", () => {
    const d1 = redamTarik(20) - redamTarik(10);
    const d2 = redamTarik(120) - redamTarik(110);
    expect(d2).toBeLessThan(d1);
  });

  test("tak pernah melewati plafon tampak, sejauh apa pun ditarik", () => {
    expect(redamTarik(10_000)).toBeLessThanOrEqual(MAKS_TAMPAK);
    expect(redamTarik(10_000)).toBeGreaterThan(MAKS_TAMPAK * 0.9);
  });

  test("yang terlihat JAUH lebih pendek dari yang ditarik", () => {
    // Inti "berat": di titik ambang pun layar baru bergerak sedikit.
    expect(redamTarik(AMBANG_TARIK)).toBeLessThan(AMBANG_TARIK / 3);
  });

  test("arah salah dan masukan cacat → diam", () => {
    for (const v of [-50, 0, NaN, undefined, null, "x"]) {
      expect(redamTarik(v)).toBe(0);
    }
  });
});

describe("cukupUntukBuka — ambang dinilai dari tarikan MENTAH", () => {
  test("di bawah ambang tidak membuka, di ambang membuka", () => {
    expect(cukupUntukBuka(AMBANG_TARIK - 1)).toBe(false);
    expect(cukupUntukBuka(AMBANG_TARIK)).toBe(true);
  });

  test("ambangnya benar-benar berat, bukan sekadar ketuk", () => {
    // Ketukan jari lazimnya bergeser < 10 px. Ambang harus jauh di atasnya,
    // kalau tidak "tarik berat" hanya nama.
    expect(AMBANG_TARIK).toBeGreaterThanOrEqual(48);
  });

  test("gerakan teredam TIDAK boleh dipakai menilai ambang", () => {
    // Jebakan halus: memakai redamTarik(x) >= AMBANG_TARIK berarti bilah tak
    // akan pernah terbuka (plafon tampak < ambang). Uji ini mengunci bahwa
    // yang dinilai adalah jarak mentah.
    expect(MAKS_TAMPAK).toBeLessThan(AMBANG_TARIK);
    expect(cukupUntukBuka(redamTarik(1000))).toBe(false);
  });

  test("masukan cacat tidak pernah membuka", () => {
    for (const v of [NaN, undefined, null, "x", -100]) {
      expect(cukupUntukBuka(v)).toBe(false);
    }
  });
});

describe("kemajuanTarik — umpan balik tanpa membuat ringan", () => {
  test("0 di awal, 1 tepat di ambang, tak lebih dari 1", () => {
    expect(kemajuanTarik(0)).toBe(0);
    expect(kemajuanTarik(AMBANG_TARIK)).toBe(1);
    expect(kemajuanTarik(AMBANG_TARIK * 5)).toBe(1);
  });

  test("naik mulus di antaranya", () => {
    expect(kemajuanTarik(AMBANG_TARIK / 2)).toBeCloseTo(0.5, 5);
  });
});

describe("arahSah — tirai punya ujung di kedua sisi", () => {
  test("tersembunyi: hanya ke bawah yang punya tujuan", () => {
    expect(arahSah(TAHAP_TERSEMBUNYI, 80)).toBe(true);
    expect(arahSah(TAHAP_TERSEMBUNYI, -80)).toBe(false);
  });

  test("daftar (tahap terakhir): hanya ke atas yang punya tujuan", () => {
    expect(arahSah(TAHAP_DAFTAR, -80)).toBe(true);
    expect(arahSah(TAHAP_DAFTAR, 80)).toBe(false);
  });

  test("tahap tengah: kedua arah sah", () => {
    expect(arahSah(TAHAP_CAP, 80)).toBe(true);
    expect(arahSah(TAHAP_CAP, -80)).toBe(true);
  });

  test("diam (dy 0) bukan arah, dan masukan cacat ditolak", () => {
    expect(arahSah(TAHAP_CAP, 0)).toBe(false);
    expect(arahSah(TAHAP_CAP, NaN)).toBe(false);
    expect(arahSah(TAHAP_CAP, undefined)).toBe(false);
  });
});

describe("majuTahap — arah buntu tidak menggerakkan apa pun", () => {
  test("jaraknya MUTLAK: berat yang sama untuk membuka & menutup", () => {
    expect(majuTahap(80, TAHAP_CAP)).toBe(80);
    expect(majuTahap(-80, TAHAP_CAP)).toBe(80);
  });

  test("arah buntu → 0, jadi redaman & ambang ikut mati", () => {
    expect(majuTahap(-80, TAHAP_TERSEMBUNYI)).toBe(0);
    expect(majuTahap(80, TAHAP_DAFTAR)).toBe(0);
    expect(redamTarik(majuTahap(80, TAHAP_DAFTAR))).toBe(0);
    expect(cukupUntukBuka(majuTahap(80, TAHAP_DAFTAR))).toBe(false);
  });
});

describe("tahapSetelahTarik — SATU tarikan, SATU tahap", () => {
  test("tarikan panjang tetap naik satu tahap saja", () => {
    // Sapuan 900 px dari tersembunyi TIDAK boleh langsung membuka daftar
    // satker: menggantinya memuat ulang seluruh aplikasi.
    expect(tahapSetelahTarik(TAHAP_TERSEMBUNYI, 900)).toBe(TAHAP_CAP);
    expect(tahapSetelahTarik(TAHAP_CAP, 900)).toBe(TAHAP_DAFTAR);
  });

  test("usaha kurang dari ambang tidak memindahkan apa pun", () => {
    expect(tahapSetelahTarik(TAHAP_CAP, AMBANG_TARIK - 1)).toBe(TAHAP_CAP);
    expect(tahapSetelahTarik(TAHAP_CAP, -(AMBANG_TARIK - 1))).toBe(TAHAP_CAP);
  });

  test("tepat di ambang sudah cukup", () => {
    expect(tahapSetelahTarik(TAHAP_CAP, AMBANG_TARIK)).toBe(TAHAP_DAFTAR);
    expect(tahapSetelahTarik(TAHAP_CAP, -AMBANG_TARIK)).toBe(TAHAP_TERSEMBUNYI);
  });

  test("tak bisa melewati kedua ujung", () => {
    expect(tahapSetelahTarik(TAHAP_TERSEMBUNYI, -900)).toBe(TAHAP_TERSEMBUNYI);
    expect(tahapSetelahTarik(TAHAP_DAFTAR, 900)).toBe(TAHAP_DAFTAR);
  });

  test("tahap di luar rentang dijepit dulu, bukan dipakai apa adanya", () => {
    expect(tahapSetelahTarik(99, 900)).toBe(TAHAP_DAFTAR);
    expect(tahapSetelahTarik(-5, -900)).toBe(TAHAP_TERSEMBUNYI);
  });
});

describe("geserTahap — tanda mengikuti arah, berat mengikuti redaman", () => {
  test("turun positif, naik negatif, besarnya sama", () => {
    const turun = geserTahap(120, TAHAP_CAP);
    const naik = geserTahap(-120, TAHAP_CAP);
    expect(turun).toBeGreaterThan(0);
    expect(naik).toBeLessThan(0);
    expect(Math.abs(naik)).toBeCloseTo(turun, 10);
  });

  test("tak pernah melampaui MAKS_TAMPAK walau ditarik sejauh apa pun", () => {
    expect(Math.abs(geserTahap(100000, TAHAP_CAP))).toBeLessThan(MAKS_TAMPAK);
  });

  test("arah buntu tetap diam di tempat", () => {
    expect(geserTahap(300, TAHAP_DAFTAR)).toBe(0);
    expect(geserTahap(-300, TAHAP_TERSEMBUNYI)).toBe(-0);
  });
});

describe("kemajuanTarik di tirai bertahap", () => {
  test("indikator memakai jarak MUTLAK, jadi menutup pun terlihat berjalan", () => {
    expect(kemajuanTarik(majuTahap(-AMBANG_TARIK / 2, TAHAP_CAP))).toBeCloseTo(0.5, 6);
  });
});
