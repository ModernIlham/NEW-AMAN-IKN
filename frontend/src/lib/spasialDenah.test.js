import {
  ORDINAL_GEDUNG, bboxDariBatas, bboxKeParam, bboxTermuat, gayaFitur,
  kelompokPerLevel, labelLevel, levelMaksUntukZoom, perluMuatUlang, urutFitur,
  urutLantaiTampilan, warnaLevel,
} from "./spasialDenah";

const fitur = (ordinal, nama, extra = {}) => ({
  type: "Feature",
  geometry: { type: "Point", coordinates: [116.7, -1.4] },
  properties: { ordinal_level: ordinal, nama, ...extra },
});

describe("warnaLevel", () => {
  test("tiap ordinal registry punya warna sendiri", () => {
    const semua = [10, 20, 30, 40, 50, 55, 60, 70, 80, 90, 95, 100, 110].map(warnaLevel);
    expect(new Set(semua).size).toBe(semua.length);
  });
  test("ordinal tak dikenal jatuh ke warna cadangan (bukan undefined)", () => {
    expect(warnaLevel(999)).toMatch(/^#[0-9a-f]{6}$/i);
    expect(warnaLevel(null)).toMatch(/^#[0-9a-f]{6}$/i);
  });
});

describe("gayaFitur", () => {
  test("batas administratif putus-putus, batas fisik utuh", () => {
    expect(gayaFitur(30).dashArray).toBeTruthy();   // Zona (WP)
    expect(gayaFitur(80).dashArray).toBeNull();     // Gedung
  });
  test("makin detail makin pekat, tapi tak pernah menutupi ubin peta", () => {
    expect(gayaFitur(100).fillOpacity).toBeGreaterThan(gayaFitur(20).fillOpacity);
    for (const o of [10, 30, 60, 80, 100, 110]) {
      expect(gayaFitur(o).fillOpacity).toBeLessThanOrEqual(0.2);
    }
  });
  test("terpilih menebalkan garis & isian, tetap di bawah ambang buram", () => {
    const biasa = gayaFitur(80);
    const pilih = gayaFitur(80, { terpilih: true });
    expect(pilih.weight).toBeGreaterThan(biasa.weight);
    expect(pilih.fillOpacity).toBeGreaterThan(biasa.fillOpacity);
    expect(pilih.fillOpacity).toBeLessThanOrEqual(0.34);
  });
  test("event mouse SELALU menembus ke peta — klik-kanan 'Tambah aset di sini' tak boleh tertelan poligon", () => {
    for (const o of [10, 30, 60, 80, 100]) {
      expect(gayaFitur(o).bubblingMouseEvents).toBe(true);
      expect(gayaFitur(o, { terpilih: true }).bubblingMouseEvents).toBe(true);
    }
  });
});

describe("levelMaksUntukZoom", () => {
  test("zoom jauh hanya kawasan & zona", () => {
    expect(levelMaksUntukZoom(5)).toBe(30);
    expect(levelMaksUntukZoom(10)).toBe(30);
  });
  test("makin dekat makin dalam, monoton tak menurun", () => {
    let sebelum = 0;
    for (let z = 0; z <= 22; z += 1) {
      const kini = levelMaksUntukZoom(z);
      expect(kini).toBeGreaterThanOrEqual(sebelum);
      sebelum = kini;
    }
  });
  test("gedung baru diminta saat zoom rapat", () => {
    expect(levelMaksUntukZoom(16)).toBeLessThan(ORDINAL_GEDUNG);
    expect(levelMaksUntukZoom(18)).toBe(ORDINAL_GEDUNG);
  });
  test("LANTAI & RUANGAN tak pernah ikut viewport (dimuat per lantai terpilih)", () => {
    for (let z = 0; z <= 22; z += 1) {
      expect(levelMaksUntukZoom(z)).toBeLessThanOrEqual(ORDINAL_GEDUNG);
    }
  });
  test("zoom tak valid → tingkat teraman (paling luar)", () => {
    expect(levelMaksUntukZoom(undefined)).toBe(30);
    expect(levelMaksUntukZoom(NaN)).toBe(30);
  });
});

describe("bboxDariBatas", () => {
  const batas = { barat: 116.0, selatan: -1.5, timur: 117.0, utara: -1.0 };

  test("padding melebarkan ke empat arah", () => {
    const b = bboxDariBatas(batas, 0.5);
    expect(b.barat).toBeCloseTo(115.5, 6);
    expect(b.timur).toBeCloseTo(117.5, 6);
    expect(b.selatan).toBeCloseTo(-1.75, 6);
    expect(b.utara).toBeCloseTo(-0.75, 6);
  });
  test("padding 0 mengembalikan viewport apa adanya", () => {
    expect(bboxDariBatas(batas, 0)).toEqual(batas);
  });
  test("dijepit ke rentang bujur/lintang sah — server menolak bbox di luar itu", () => {
    const b = bboxDariBatas({ barat: -179, selatan: -84, timur: 179, utara: 84 }, 1);
    expect(b.barat).toBeGreaterThanOrEqual(-180);
    expect(b.timur).toBeLessThanOrEqual(180);
    expect(b.selatan).toBeGreaterThanOrEqual(-85);
    expect(b.utara).toBeLessThanOrEqual(85);
  });
  test("batas rusak/degenerat → null (jangan kirim request sia-sia)", () => {
    expect(bboxDariBatas(null)).toBeNull();
    expect(bboxDariBatas({ barat: 1, selatan: 1, timur: 1, utara: 2 })).toBeNull(); // lebar 0
    expect(bboxDariBatas({ barat: 1, selatan: 1, timur: 2, utara: NaN })).toBeNull();
  });
});

describe("bboxKeParam", () => {
  test("urutan lon,lat,lon,lat sesuai kontrak server (GeoJSON: bujur dulu)", () => {
    expect(bboxKeParam({ barat: 116.5, selatan: -1.25, timur: 117, utara: -1 }))
      .toBe("116.500000,-1.250000,117.000000,-1.000000");
  });
  test("bbox kosong → string kosong (parameter tak dikirim)", () => {
    expect(bboxKeParam(null)).toBe("");
  });
});

describe("bboxTermuat", () => {
  const luar = { barat: 0, selatan: 0, timur: 10, utara: 10 };
  test("bagian dalam dan yang persis sama dianggap termuat", () => {
    expect(bboxTermuat(luar, { barat: 2, selatan: 2, timur: 8, utara: 8 })).toBe(true);
    expect(bboxTermuat(luar, luar)).toBe(true);
  });
  test("melewati tepi mana pun = tak termuat", () => {
    expect(bboxTermuat(luar, { barat: -1, selatan: 2, timur: 8, utara: 8 })).toBe(false);
    expect(bboxTermuat(luar, { barat: 2, selatan: 2, timur: 11, utara: 8 })).toBe(false);
    expect(bboxTermuat(luar, { barat: 2, selatan: 2, timur: 8, utara: 11 })).toBe(false);
  });
});

describe("perluMuatUlang", () => {
  const termuat = { bbox: { barat: 0, selatan: 0, timur: 10, utara: 10 }, level_maks: 50, terpotong: false };
  const didalam = { barat: 2, selatan: 2, timur: 8, utara: 8 };

  test("belum pernah memuat → harus memuat", () => {
    expect(perluMuatUlang(null, didalam, 50)).toBe(true);
  });
  test("geser kecil di dalam bbox termuat & LOD sama → tidak fetch ulang", () => {
    expect(perluMuatUlang(termuat, didalam, 50)).toBe(false);
  });
  test("ganti tingkat detail selalu memuat ulang", () => {
    expect(perluMuatUlang(termuat, didalam, 70)).toBe(true);
    expect(perluMuatUlang(termuat, didalam, 30)).toBe(true);
  });
  test("keluar dari bbox termuat → memuat ulang", () => {
    expect(perluMuatUlang(termuat, { barat: 9, selatan: 9, timur: 12, utara: 12 }, 50)).toBe(true);
  });
  test("hasil terpotong selalu dimuat ulang — isinya belum lengkap", () => {
    expect(perluMuatUlang({ ...termuat, terpotong: true }, didalam, 50)).toBe(true);
  });
});

describe("urutFitur", () => {
  test("poligon besar lebih dulu agar tergambar di BAWAH yang detail", () => {
    const urut = urutFitur([fitur(100, "Ruang A"), fitur(20, "Kawasan"), fitur(80, "Gedung")]);
    expect(urut.map((f) => f.properties.ordinal_level)).toEqual([20, 80, 100]);
  });
  test("ordinal sama → urut nama, hasil stabil", () => {
    const urut = urutFitur([fitur(80, "Gedung C"), fitur(80, "Gedung A"), fitur(80, "Gedung B")]);
    expect(urut.map((f) => f.properties.nama)).toEqual(["Gedung A", "Gedung B", "Gedung C"]);
  });
  test("tidak memutasi array masukan", () => {
    const asli = [fitur(100, "Z"), fitur(20, "A")];
    urutFitur(asli);
    expect(asli[0].properties.ordinal_level).toBe(100);
  });
  test("masukan kosong/undefined aman", () => {
    expect(urutFitur(undefined)).toEqual([]);
  });
});

describe("kelompokPerLevel", () => {
  test("mengelompokkan per ordinal", () => {
    const peta = kelompokPerLevel([fitur(80, "G1"), fitur(80, "G2"), fitur(20, "K")]);
    expect(peta.get(80)).toHaveLength(2);
    expect(peta.get(20)).toHaveLength(1);
  });
});

describe("labelLevel", () => {
  const registry = [{ ordinal_level: 30, label_ui: "Zona (WP)", label_baku: "Wilayah Perencanaan" }];
  test("memakai label registry backend", () => {
    expect(labelLevel(30, registry)).toBe("Zona (WP)");
  });
  test("tanpa registry tetap ada label terbaca", () => {
    expect(labelLevel(30, [])).toBe("Tingkat 30");
    expect(labelLevel(30, undefined)).toBe("Tingkat 30");
  });
});

describe("urutLantaiTampilan", () => {
  const lt = (nama, ordinal) => ({ id: nama, nama, lantai: ordinal === undefined ? {} : { ordinal } });

  test("seperti panel lift — rooftop di atas, basement di bawah", () => {
    const urut = urutLantaiTampilan([lt("Lantai 1", 0), lt("Basement 2", -2), lt("Rooftop", 8), lt("Basement 1", -1)]);
    expect(urut.map((l) => l.nama)).toEqual(["Rooftop", "Lantai 1", "Basement 1", "Basement 2"]);
  });
  test("lantai tanpa ordinal ditaruh paling akhir, tak mengacaukan urutan", () => {
    const urut = urutLantaiTampilan([lt("Mezanin"), lt("Lantai 1", 0), lt("Basement", -1)]);
    expect(urut.map((l) => l.nama)).toEqual(["Lantai 1", "Basement", "Mezanin"]);
  });
  test("ordinal 0 tetap ikut terurut (bukan dianggap kosong)", () => {
    const urut = urutLantaiTampilan([lt("Lantai 2", 1), lt("Dasar", 0)]);
    expect(urut.map((l) => l.nama)).toEqual(["Lantai 2", "Dasar"]);
  });
  test("daftar kosong aman", () => {
    expect(urutLantaiTampilan([])).toEqual([]);
    expect(urutLantaiTampilan(undefined)).toEqual([]);
  });
});
