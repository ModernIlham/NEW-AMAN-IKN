import { fiturKeGeometri, payloadSimpan, pusatAwal, tutupCincin } from "./denahEditor";

const cincinTerbuka = [[116.7, -1.4], [116.71, -1.4], [116.71, -1.39]];
const cincinTertutup = [...cincinTerbuka, [116.7, -1.4]];

describe("tutupCincin", () => {
  test("cincin terbuka DITUTUP — geoman tak menutup cincin pada toGeoJSON", () => {
    const hasil = tutupCincin(cincinTerbuka);
    expect(hasil).toHaveLength(4);
    expect(hasil[0]).toEqual(hasil[3]);
  });
  test("cincin yang sudah tertutup tidak digandakan titik akhirnya", () => {
    expect(tutupCincin(cincinTertutup)).toHaveLength(4);
  });
  test("titik rusak dibuang; kurang dari 3 titik sah → null", () => {
    expect(tutupCincin([[116.7, -1.4], ["x", "y"], [116.71, -1.4]])).toBeNull();
    expect(tutupCincin([])).toBeNull();
    expect(tutupCincin(null)).toBeNull();
  });
});

describe("fiturKeGeometri", () => {
  const fitur = (geom) => ({ type: "Feature", geometry: geom, properties: {} });

  test("satu poligon → Polygon", () => {
    const { geometry } = fiturKeGeometri([fitur({ type: "Polygon", coordinates: [cincinTerbuka] })]);
    expect(geometry.type).toBe("Polygon");
    // cincin ikut ditutup dalam perjalanan
    expect(geometry.coordinates[0][0]).toEqual(geometry.coordinates[0][3]);
  });
  test("dua goresan terpisah → MultiPolygon (kampus dua tapak itu nyata)", () => {
    const lain = [[117.0, -1.2], [117.01, -1.2], [117.01, -1.19]];
    const { geometry } = fiturKeGeometri([
      fitur({ type: "Polygon", coordinates: [cincinTerbuka] }),
      fitur({ type: "Polygon", coordinates: [lain] }),
    ]);
    expect(geometry.type).toBe("MultiPolygon");
    expect(geometry.coordinates).toHaveLength(2);
  });
  test("MultiPolygon masukan dipecah lalu digabung ulang", () => {
    const lain = [[117.0, -1.2], [117.01, -1.2], [117.01, -1.19]];
    const { geometry } = fiturKeGeometri([
      fitur({ type: "MultiPolygon", coordinates: [[cincinTertutup], [tutupCincin(lain)]] }),
    ]);
    expect(geometry.type).toBe("MultiPolygon");
    expect(geometry.coordinates).toHaveLength(2);
  });
  test("poligon berlubang mempertahankan lubangnya", () => {
    const lubang = [[116.702, -1.398], [116.704, -1.398], [116.704, -1.396]];
    const { geometry } = fiturKeGeometri([
      fitur({ type: "Polygon", coordinates: [cincinTerbuka, lubang] }),
    ]);
    expect(geometry.type).toBe("Polygon");
    expect(geometry.coordinates).toHaveLength(2);
  });
  test("fitur non-poligon dibuang; nol poligon → geometry null (hapus bentuk)", () => {
    expect(fiturKeGeometri([fitur({ type: "Point", coordinates: [116.7, -1.4] })]).geometry).toBeNull();
    expect(fiturKeGeometri([]).geometry).toBeNull();
    expect(fiturKeGeometri(undefined).geometry).toBeNull();
  });
});

describe("payloadSimpan", () => {
  const node = {
    tipe: "GEDUNG", nama: "Gedung A", kode: "GA", parent_id: "tp-1",
    nama_alias: ["A"], lantai: null, zona_kode: "", subzona_kode: "",
    fungsi_kawasan: "", properties: { catatan: "x" }, status: "aktif", prioritas: 2,
  };

  test("SEMUA field NodeIn ikut — PUT mengganti seluruh dokumen", () => {
    const p = payloadSimpan(node, { type: "Polygon", coordinates: [cincinTertutup] });
    expect(p.nama).toBe("Gedung A");
    expect(p.kode).toBe("GA");
    expect(p.parent_id).toBe("tp-1");
    expect(p.properties).toEqual({ catatan: "x" });
    expect(p.prioritas).toBe(2);
    expect(p.geometry.type).toBe("Polygon");
  });
  test("geometry null → {} (kontrak server: {} = kosongkan, null = tak diubah)", () => {
    expect(payloadSimpan(node, null).geometry).toEqual({});
  });
  test("node tipe LANTAI membawa objek lantai apa adanya", () => {
    const lt = { ...node, tipe: "LANTAI", lantai: { ordinal: -1, label: "B1" } };
    expect(payloadSimpan(lt, null).lantai).toEqual({ ordinal: -1, label: "B1" });
  });
});

describe("pusatAwal", () => {
  test("bbox node sendiri menang", () => {
    const p = pusatAwal({ bbox: [116.7, -1.4, 116.8, -1.3] }, { bbox: [110, -7, 111, -6] });
    expect(p.lat).toBeCloseTo(-1.35, 6);
    expect(p.lng).toBeCloseTo(116.75, 6);
  });
  test("tanpa bbox node → bbox induk → fallback IKN", () => {
    const p = pusatAwal({}, { bbox: [110, -7, 111, -6] });
    expect(p.lng).toBeCloseTo(110.5, 6);
    const f = pusatAwal({}, null);
    expect(f.lat).toBeCloseTo(-1.4, 6);
    expect(f.lng).toBeCloseTo(116.7, 6);
  });
  test("bbox rusak tidak meledak", () => {
    expect(pusatAwal({ bbox: ["a", 1, 2] }, null).lng).toBeCloseTo(116.7, 6);
  });
});
