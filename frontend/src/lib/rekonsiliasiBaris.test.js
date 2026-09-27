import { gabungVersiBaris, rekonsiliasiBaris, rekonsiliasiDaftar, versiBaris } from "./rekonsiliasiBaris";

const lama = { id: "a", version: 7, asset_name: "Terbaru", doc_total: 2 };
const pending = [{ isEdit: true, editId: "a", baseVersion: 7, payload: { asset_name: "Edit lokal" } }];

test("versi tertinggi menang meski urutan respons terbalik", () => {
  expect(gabungVersiBaris(lama, { id: "a", version: 6, asset_name: "Usang" })).toBe(lama);
  expect(gabungVersiBaris(lama, { id: "a", version: 8, asset_name: "Baru" }))
    .toEqual({ ...lama, version: 8, asset_name: "Baru" });
});
test("potongan versi sama dan baris era lama tetap dapat digabung", () => {
  expect(gabungVersiBaris(lama, { id: "a", version: 7, condition: "Baik" })).toEqual({ ...lama, condition: "Baik" });
  expect(gabungVersiBaris(lama, { id: "a", version: null, condition: "Baik" }).version).toBe(7);
  expect(gabungVersiBaris({ id: "a" }, { id: "a", asset_name: "Baru" }).asset_name).toBe("Baru");
});
test.each([null, undefined, "", "x", false, -1, 0, 1.5, Infinity])("versi tidak sah %s bukan angka OCC", version => {
  expect(versiBaris({ version })).toBeNull();
});
test("versi numerik dari server lama tetap terbaca", () => {
  expect(versiBaris({ version: "8" })).toBe(8);
});
test("simpan berikutnya/failed tetap terlindungi, versi rekan tidak melewati OCC", () => {
  const lokal = { ...lama, asset_name: "Edit kedua" };
  expect(rekonsiliasiBaris(lokal, { id: "a", version: 9, asset_name: "Rekan" }, pending)).toBe(lokal);
  expect(pending[0].baseVersion).toBe(7);
});
test("konflik menampilkan pemenang server tetapi payload tetap tersedia untuk ditinjau", () => {
  const konflik = [{ ...pending[0], hadConflict: true }];
  expect(rekonsiliasiBaris(lama, { id: "a", version: 8, asset_name: "Rekan" }, konflik).asset_name).toBe("Rekan");
  expect(konflik[0].payload.asset_name).toBe("Edit lokal");
});
test("muat ulang halaman mempertahankan muatan antrean tanpa menaikkan dasar OCC", () => {
  expect(rekonsiliasiBaris(null, { id: "a", version: 9, condition: "Baik" }, pending))
    .toMatchObject({ id: "a", version: 7, asset_name: "Edit lokal", condition: "Baik" });
});
test("filter dan sort server tetap menentukan keanggotaan/urutan, bukan daftar lama", () => {
  const rows = [{ id: "b", version: 1 }, { id: "a", version: 6 }];
  expect(rekonsiliasiDaftar([lama, { id: "tersaring" }], rows)).toEqual([rows[0], lama]);
});
