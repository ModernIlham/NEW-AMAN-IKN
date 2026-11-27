import {
  batasWgs84, crsDariGeoKeys, jumlahUbin, latKeUbinY, lonKeUbinX, lonLatKeMerc, lonLatKeUtm,
  mercKeLonLat, rencanaZoom, rentangUbin, tanggalDariTiff, transformUbin, ubinXKeLon, ubinYKeLat,
  utmKeLonLat, UBIN_MAKS,
} from "../proyeksiCitra";

// Nilai acuan dari pustaka Python `utm` (dipakai backend) — cek silang dua implementasi.
const ACUAN = [
  [-0.96, 116.70, 466622.012, 9893889.592, 50, true],
  [-0.9, 117.4, 544504.895, 9900520.436, 50, true],
  [3.6, 98.67, 463351.036, 397920.047, 47, false],
  [-6.2, 106.8, 699163.391, 9314348.962, 48, true],
  [45.0, 7.5, 381777.034, 4984044.799, 32, false],
];

describe("UTM", () => {
  test.each(ACUAN)("maju %p,%p", (lat, lon, e, n, zona, selatan) => {
    const [x, y] = lonLatKeUtm(lon, lat, zona, selatan);
    expect(Math.abs(x - e)).toBeLessThan(0.01);
    expect(Math.abs(y - n)).toBeLessThan(0.01);
  });
  test.each(ACUAN)("balik %p,%p", (lat, lon, e, n, zona, selatan) => {
    const [lo, la] = utmKeLonLat(e, n, zona, selatan);
    expect(Math.abs(lo - lon)).toBeLessThan(1e-7);
    expect(Math.abs(la - lat)).toBeLessThan(1e-7);
  });
});

test("Web Mercator bolak-balik", () => {
  const [x, y] = lonLatKeMerc(116.7, -0.96);
  const [lon, lat] = mercKeLonLat(x, y);
  expect(lon).toBeCloseTo(116.7, 9);
  expect(lat).toBeCloseTo(-0.96, 9);
});

describe("CRS dari geo key", () => {
  test("UTM selatan/utara, Mercator, WGS84", () => {
    expect(crsDariGeoKeys({ ProjectedCSTypeGeoKey: 32750 })).toMatchObject({ jenis: "utm", zona: 50, selatan: true });
    expect(crsDariGeoKeys({ ProjectedCSTypeGeoKey: 32647 })).toMatchObject({ jenis: "utm", zona: 47, selatan: false });
    expect(crsDariGeoKeys({ ProjectedCSTypeGeoKey: 3857 })).toMatchObject({ jenis: "merc" });
    expect(crsDariGeoKeys({ GTModelTypeGeoKey: 2, GeographicTypeGeoKey: 4326 })).toMatchObject({ jenis: "geo" });
  });
  test("CRS asing & tanpa georeferensi ditolak dengan pesan jelas", () => {
    expect(crsDariGeoKeys({ ProjectedCSTypeGeoKey: 23890 }).galat).toMatch(/EPSG:23890 belum didukung/);
    expect(crsDariGeoKeys(null).galat).toMatch(/bukan GeoTIFF/);
  });
});

describe("ubin XYZ", () => {
  test("konversi dasar", () => {
    expect([lonKeUbinX(0, 1), latKeUbinY(0, 1)]).toEqual([1, 1]);
    expect(ubinXKeLon(1, 1)).toBe(0);
    expect(ubinYKeLat(1, 1)).toBeCloseTo(0, 9);
  });
  test("rentang & jumlah", () => {
    const b = { barat: 116.695, selatan: -0.975, timur: 116.715, utara: -0.955 };
    const r = rentangUbin(b, 15);
    expect(r.x1).toBeGreaterThanOrEqual(r.x0);
    expect(jumlahUbin(b, 15, 15)).toBe((r.x1 - r.x0 + 1) * (r.y1 - r.y0 + 1));
  });
});

test("batas WGS84 dari kotak UTM melingkupi semua sudutnya", () => {
  const crs = { jenis: "utm", zona: 50, selatan: true };
  const b = batasWgs84([466000, 9893000, 468000, 9895000], crs);
  for (const [x, y] of [[466000, 9893000], [468000, 9895000], [466000, 9895000], [468000, 9893000]]) {
    const [lon, lat] = utmKeLonLat(x, y, 50, true);
    expect(lon).toBeGreaterThanOrEqual(b.barat - 1e-12);
    expect(lon).toBeLessThanOrEqual(b.timur + 1e-12);
    expect(lat).toBeGreaterThanOrEqual(b.selatan - 1e-12);
    expect(lat).toBeLessThanOrEqual(b.utara + 1e-12);
  }
});

describe("rencana zoom", () => {
  const b5km = { barat: 116.68, selatan: -0.98, timur: 116.725, utara: -0.935 };
  test("drone 5 cm untuk 5×5 km diturunkan agar tetap di bawah batas ubin", () => {
    const r = rencanaZoom(b5km, 0.05);
    expect(r.jumlah).toBeLessThanOrEqual(UBIN_MAKS);
    expect(r.zmaks).toBe(20);
    expect(r.zmin).toBeLessThan(r.zmaks);
  });
  test("citra kasar tak dibuat ubin berlebihan", () => {
    expect(rencanaZoom(b5km, 1).zmaks).toBe(18);   // 1 m/px ≈ zoom 17,3 → 18
  });
});

test("transform ubin memetakan sudut sumber ke sudut ubin", () => {
  // Ubin memetakan ke kotak piksel sumber [100,612]×[50,562] (skala 2×).
  const sudut = [[100, 50], [612, 50], [100, 562]];
  const jendela = { c0: 100, r0: 50, c1: 612, r1: 562 };
  const [a, b, c, d, e, f] = transformUbin(sudut, jendela, 256, 256);
  const peta = (x, y) => [a * x + c * y + e, b * x + d * y + f];
  expect(peta(0, 0)).toEqual([0, 0]);
  const [x1, y1] = peta(256, 256);
  expect(x1).toBeCloseTo(256, 9);
  expect(y1).toBeCloseTo(256, 9);
});

test("tanggal dari tag TIFF", () => {
  expect(tanggalDariTiff("2026:10:15 09:12:00")).toBe("2026-10-15");
  expect(tanggalDariTiff(undefined)).toBe("");
});
