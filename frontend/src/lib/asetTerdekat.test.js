import {
  arahDerajat, mataAngin, siapkanTitikAset, cariTerdekat, jumlahDalamRadius,
  arahGerakSah, statusPandu, cukupPresisi, urlGoogleMaps, AKURASI_TITIK_M,
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

test("pandu: jarak, arah, tiba bila ≤ max(5 m, akurasi)", () => {
  const tujuan = { lat: P.lat + 0.0003, lng: P.lng }; // ±33 m ke utara
  const jauh = statusPandu({ ...P, accuracy: 6 }, tujuan);
  expect(jauh.tiba).toBe(false);
  expect(Math.round(jauh.arah)).toBe(0);
  expect(statusPandu({ lat: P.lat + 0.00028, lng: P.lng, accuracy: 4 }, tujuan).tiba).toBe(true); // 2 m
  expect(statusPandu({ ...P, accuracy: 40 }, tujuan).tiba).toBe(true); // GPS kasar: tak bisa dibedakan
  expect(statusPandu(null, tujuan)).toBeNull();
});

test("gerbang presisi titik aset = 8 m (sama dengan rana kamera); tautan Google Maps", () => {
  expect(AKURASI_TITIK_M).toBe(8);
  expect(cukupPresisi({ accuracy: 8 })).toBe(true);
  expect(cukupPresisi({ accuracy: 8.1 })).toBe(false);
  expect(cukupPresisi(null)).toBe(false);
  expect(urlGoogleMaps(-1.2, 116.85)).toBe("https://www.google.com/maps/dir/?api=1&destination=-1.200000,116.850000");
});


test("arah gerak hanya sah saat benar-benar bergerak", () => {
  expect(arahGerakSah({ heading: 90, speed: 1.2 })).toBe(true);
  expect(arahGerakSah({ heading: 90, speed: 0.2 })).toBe(false);
  expect(arahGerakSah({ heading: null, speed: 2 })).toBe(false);
  expect(arahGerakSah(null)).toBe(false);
});
