import {
  arahDerajat, mataAngin, siapkanTitikAset, cariTerdekat, jumlahDalamRadius,
  langkahJejak, arahGerakSah,
} from "./asetTerdekat";

const P = { lat: -1.0, lng: 116.0 };
// ±1e-4° ≈ 11 m di khatulistiwa.
const row = (id, dLat, dLng, status = "Belum Diinventarisasi") => ({
  id, asset_name: id, inventory_status: status,
  koordinat_latitude: String(P.lat + dLat), koordinat_longitude: String(P.lng + dLng),
});

test("arah awal & mata angin Indonesia", () => {
  expect(Math.round(arahDerajat(P, { lat: -0.99, lng: 116 }))).toBe(0);
  expect(Math.round(arahDerajat(P, { lat: -1, lng: 116.01 }))).toBe(90);
  expect(Math.round(arahDerajat(P, { lat: -1.01, lng: 116 }))).toBe(180);
  expect(mataAngin(0)).toBe("Utara");
  expect(mataAngin(44)).toBe("Timur Laut");
  expect(mataAngin(135)).toBe("Tenggara");
  expect(mataAngin(359)).toBe("Utara");
  expect(mataAngin(-90)).toBe("Barat");
  expect(mataAngin(NaN)).toBe("");
});

test("siapkanTitikAset melewati aset tanpa koordinat sah, menerima koma desimal", () => {
  const t = siapkanTitikAset([
    row("a", 0, 0), { id: "b", koordinat_latitude: "", koordinat_longitude: "116" },
    { id: "c", koordinat_latitude: "-1,5", koordinat_longitude: "116,2" },
    { id: "d", koordinat_latitude: "95", koordinat_longitude: "116" }, null,
  ]);
  expect(t.map((x) => x.row.id)).toEqual(["a", "c"]);
  expect(t[1]).toMatchObject({ lat: -1.5, lng: 116.2 });
});

test("cariTerdekat: urut jarak, dibatasi n, filter belum-didata & radius maks", () => {
  const titik = siapkanTitikAset([
    row("jauh", 0.01, 0), row("dekat", 0.0001, 0), row("tengah", 0, 0.0004, "Ditemukan"),
    row("sedang", 0.0003, 0.0003), row("luar5km", 0.1, 0),
  ]);
  const hasil = cariTerdekat(titik, P, { n: 3 });
  expect(hasil.map((h) => h.row.id)).toEqual(["dekat", "tengah", "sedang"]);
  expect(hasil[0].jarak).toBeGreaterThan(10);
  expect(hasil[0].jarak).toBeLessThan(12);
  expect(Math.round(hasil[0].arah)).toBe(0);
  expect(cariTerdekat(titik, P, { n: 10, hanyaBelum: true }).map((h) => h.row.id)).toEqual(["dekat", "sedang", "jauh"]);
  expect(cariTerdekat(titik, P, { n: 10 }).some((h) => h.row.id === "luar5km")).toBe(false);
  expect(cariTerdekat(titik, null)).toEqual([]);
  expect(jumlahDalamRadius(titik, P, 50)).toBe(3);
  expect(jumlahDalamRadius(titik, P, 50, { hanyaBelum: true })).toBe(2);
});

test("jejak menyaring jitter diam & fix kasar, mencatat langkah nyata", () => {
  expect(langkahJejak(null, { ...P, accuracy: 8 })).toBe(0);
  expect(langkahJejak(null, { ...P, accuracy: 80 })).toBeNull();
  expect(langkahJejak(P, { lat: P.lat + 0.00002, lng: P.lng, accuracy: 8 })).toBeNull(); // ±2 m
  expect(langkahJejak(P, { lat: P.lat + 0.0001, lng: P.lng, accuracy: 30 })).toBeNull(); // 11 m < 15 m
  expect(langkahJejak(P, { lat: P.lat + 0.0001, lng: P.lng, accuracy: 8 })).toBeGreaterThan(10);
});

test("arah gerak hanya sah saat benar-benar bergerak", () => {
  expect(arahGerakSah({ heading: 90, speed: 1.2 })).toBe(true);
  expect(arahGerakSah({ heading: 90, speed: 0.2 })).toBe(false);
  expect(arahGerakSah({ heading: null, speed: 2 })).toBe(false);
  expect(arahGerakSah(null)).toBe(false);
});
