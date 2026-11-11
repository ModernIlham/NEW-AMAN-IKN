import { KUNCI_IKON, infoIkon, kelompokDari, kunciIkon, sebutTataran } from "../kelompokOrang";

test("empat kunci ikon, masing-masing dengan teks alternatif berbeda", () => {
  expect(KUNCI_IKON).toEqual(["internal", "eksternal_pusat", "eksternal_daerah", "pihak_ketiga"]);
  const alt = KUNCI_IKON.map((k) => infoIkon(k).alt);
  expect(new Set(alt).size).toBe(4);
  expect(infoIkon("tak-dikenal")).toBeNull();
});

test("kunciIkon mencerminkan backend; pusat dan daerah berbeda", () => {
  expect(kunciIkon("eksternal", "daerah")).toBe("eksternal_daerah");
  expect(kunciIkon("eksternal", "")).toBe("eksternal_pusat");
  expect(kunciIkon("pihak_ketiga")).toBe("pihak_ketiga");
  expect(kunciIkon("")).toBe("internal");
  expect(sebutTataran("eksternal_daerah")).toBe("Daerah");
  expect(sebutTataran("internal")).toBe("");
});

test("salinan pada catatan menang atas jawaban server; tanpa keduanya → null", () => {
  expect(kelompokDari({ kelompok: "eksternal", tataran: "daerah" }, "internal")).toBe("eksternal_daerah");
  expect(kelompokDari({ penerima_kelompok: "pihak_ketiga" }, "internal")).toBe("pihak_ketiga");
  expect(kelompokDari({ kunci_ikon: "eksternal_pusat" }, "pihak_ketiga")).toBe("eksternal_pusat");
  expect(kelompokDari({}, "pihak_ketiga")).toBe("pihak_ketiga");
  expect(kelompokDari({}, null)).toBeNull();
  expect(kelompokDari(null, "bukan-kunci")).toBeNull();
});
