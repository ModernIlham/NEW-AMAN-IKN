import {
  AMBANG_TARIK,
  MAKS_TAMPAK,
  cukupUntukBuka,
  kemajuanTarik,
  majuTarik,
  redamTarik,
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

describe("majuTarik — hanya arah yang sah yang dihitung", () => {
  test("saat TERTUTUP hanya tarikan ke bawah yang maju", () => {
    expect(majuTarik(80, false)).toBe(80);      // ke bawah → membuka
    expect(majuTarik(-80, false)).toBe(-80);    // ke atas → mundur
    expect(cukupUntukBuka(majuTarik(-80, false))).toBe(false);
  });

  test("saat TERBUKA hanya tarikan ke atas yang maju", () => {
    expect(majuTarik(-80, true)).toBe(80);      // ke atas → menutup
    expect(cukupUntukBuka(majuTarik(80, true))).toBe(false);
  });

  test("masukan cacat → 0", () => {
    expect(majuTarik(NaN, false)).toBe(0);
    expect(majuTarik(undefined, true)).toBe(0);
  });
});
