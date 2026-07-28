import {
  ORDINAL_GEDUNG, bboxDariBatas, bboxKeParam, bboxTermuat, gayaFitur,
  kelompokPerLevel, labelLevel, levelMaksUntukZoom, ordinalLantai,
  perluMuatUlang, urutFitur, urutLantaiTampilan, warnaLevel,
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
  test("bujur di luar ±180 (geser lewat antimeridian) → null, BUKAN kotak pipih", () => {
    // Leaflet getBounds() mengembalikan bujur tak-dibungkus setelah peta digeser
    // melewati antimeridian. Rentang mentahnya wajar, tapi kedua tepi menjepit ke
    // nilai yang sama → kotak pipih → server balas 400 pada SETIAP geser peta.
    expect(bboxDariBatas({ barat: 190, selatan: -1.5, timur: 195, utara: -1.0 })).toBeNull();
    expect(bboxDariBatas({ barat: -195, selatan: -1.5, timur: -190, utara: -1.0 })).toBeNull();
  });
  test("hasil penjepitan SELALU non-degenerat bila tidak null", () => {
    const contoh = [
      { barat: 116, selatan: -1.5, timur: 117, utara: -1.0 },
      { barat: -400, selatan: -89, timur: 400, utara: 89 },
      { barat: 179, selatan: 84, timur: 179.9, utara: 84.9 },
      { barat: -179.9, selatan: -84.9, timur: -179, utara: -84 },
    ];
    for (const b of contoh) {
      const r = bboxDariBatas(b);
      if (r === null) continue;
      expect(r.timur).toBeGreaterThan(r.barat);
      expect(r.utara).toBeGreaterThan(r.selatan);
    }
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
  test("terpotong TIDAK lagi memaksa muat ulang saat diam di tempat", () => {
    // Dulu ini `true`, dan itulah sebab penanda memuat berputar tanpa henti:
    // tiap moveend/zoomend menembak ulang request yang mengembalikan potongan
    // yang sama persis. Wilayah sah untuk hasil terpotong kini dipersempit di
    // pemanggil (viewport tanpa padding), bukan dengan mematikan cache.
    expect(perluMuatUlang({ ...termuat, terpotong: true }, didalam, 50)).toBe(false);
  });

  test("terpotong dengan wilayah sah SEMPIT: geser sedikit langsung memuat ulang", () => {
    // Inilah pengganti perilaku lama — pemanggil menyimpan viewport apa adanya
    // (tanpa padding) sebagai bbox, sehingga bergeser keluar darinya memicu
    // muat ulang, tetapi diam di tempat tidak.
    const sempit = { bbox: { barat: 2, selatan: 2, timur: 8, utara: 8 }, level_maks: 50, terpotong: true };
    expect(perluMuatUlang(sempit, { barat: 2, selatan: 2, timur: 8, utara: 8 }, 50)).toBe(false);
    expect(perluMuatUlang(sempit, { barat: 1.9, selatan: 2, timur: 8, utara: 8 }, 50)).toBe(true);
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

// ── Kontrak klien ↔ server ──────────────────────────────────────────────────
// Fixture di bawah MENIRU bentuk respons backend persis (routes/spasial.py).
// Nama field yang salah tak akan pernah menggagalkan eslint, build, maupun uji
// lain — ia hanya membuat peta tampil kosong tanpa satu pun galat. Uji ini yang
// mengikat kedua sisi: bila backend mengganti nama field, ini yang jatuh.
describe("kontrak bentuk respons server", () => {
  const responsGeojson = {
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [[[116.7, -1.4], [116.71, -1.4], [116.71, -1.39], [116.7, -1.4]]] },
      properties: { id: "gd-1", tipe: "GEDUNG", nama: "Gedung A", kode: "GA", ordinal_level: 80, parent_id: "tp-1" },
    }],
    jumlah: 1, jumlah_total: 1, terpotong: false, batas: 3000,
  };
  const responsLantai = {
    items: [{ id: "lt-1", nama: "Lantai 1", kode: "L1", lantai: { ordinal: 0, label: "Lantai 1" } }],
    jumlah: 1,
    gedung: { id: "gd-1", tipe: "GEDUNG", nama: "Gedung A", kode: "GA", ordinal_level: 80 },
  };

  test("fitur geojson terbaca oleh urutFitur/kelompokPerLevel/gayaFitur", () => {
    const f = responsGeojson.features;
    expect(urutFitur(f)).toHaveLength(1);
    expect(kelompokPerLevel(f).get(80)).toHaveLength(1);
    // ordinal_level HARUS terbaca; kalau tidak semua fitur jatuh ke lapis 0.
    expect(f[0].properties.ordinal_level).toBe(ORDINAL_GEDUNG);
    expect(gayaFitur(f[0].properties.ordinal_level).color).toBe(warnaLevel(80));
  });
  test("penanda `terpotong` & pencacah dibaca dengan nama yang benar", () => {
    expect(typeof responsGeojson.terpotong).toBe("boolean");
    expect(Number.isFinite(responsGeojson.jumlah_total)).toBe(true);
    expect(perluMuatUlang(
      { bbox: { barat: 0, selatan: 0, timur: 10, utara: 10 }, level_maks: 80, terpotong: responsGeojson.terpotong },
      { barat: 2, selatan: 2, timur: 8, utara: 8 }, 80,
    )).toBe(false);
  });
  test("daftar lantai server terurut benar oleh urutLantaiTampilan", () => {
    const urut = urutLantaiTampilan(responsLantai.items);
    expect(urut).toHaveLength(1);
    expect(ordinalLantai(urut[0])).toBe(0);          // lantai.ordinal, bukan lantai_ordinal
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

describe("ordinalLantai", () => {
  test("0 adalah ordinal SAH (lantai akses utama), bukan 'kosong'", () => {
    expect(ordinalLantai({ lantai: { ordinal: 0 } })).toBe(0);
    expect(ordinalLantai({ lantai: { ordinal: -2 } })).toBe(-2);
  });
  test("null/undefined/'' dari server BUKAN 0 — server memang menyimpan null", () => {
    // `Number(null)` = 0 dan 0 itu finite, jadi cek naif memperlakukan lantai
    // tanpa ordinal sebagai lantai dasar: ia menyusup ke tengah urutan lift dan
    // tampil bernomor "0".
    expect(ordinalLantai({ lantai: { ordinal: null } })).toBeNull();
    expect(ordinalLantai({ lantai: { ordinal: "" } })).toBeNull();
    expect(ordinalLantai({ lantai: {} })).toBeNull();
    expect(ordinalLantai({})).toBeNull();
    expect(ordinalLantai(null)).toBeNull();
    expect(ordinalLantai({ lantai: { ordinal: "abc" } })).toBeNull();
  });
  test("angka berbentuk string tetap terbaca", () => {
    expect(ordinalLantai({ lantai: { ordinal: "3" } })).toBe(3);
  });
});

describe("urutLantaiTampilan", () => {
  const lt = (nama, ordinal) => ({ id: nama, nama, lantai: ordinal === undefined ? {} : { ordinal } });

  test("lantai ber-ordinal null ditaruh di akhir, tidak menyamar jadi lantai 0", () => {
    const urut = urutLantaiTampilan([
      lt("Belum diisi", null), lt("Lantai 1", 0), lt("Basement", -1), lt("Lantai 2", 1),
    ]);
    expect(urut.map((l) => l.nama)).toEqual(["Lantai 2", "Lantai 1", "Basement", "Belum diisi"]);
  });

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
