import {
  ringkasPerubahan, teksPerubahan, sidikForm, bangunRekamanDraf,
  pulihkanDrafEdit, pulihkanDrafBaru, kunciDraf, drafBasi, DRAF_TTL_MS, ID_BARU,
} from "./drafAset";
import { emptyAssetForm } from "./assetFormData";

const asli = () => ({ ...emptyAssetForm("k1"), asset_code: "301", asset_name: "Meja", condition: "Baik", _photoCount: 2, thumbnail_index: 0, stiker_photo_index: null });
const ada = (n) => Array.from({ length: n }, (_, i) => ({ type: "existing", originalIndex: i, thumbnail: `t${i}` }));

test("kunci draf per pengguna + kegiatan + aset; aset baru memakai penanda khusus", () => {
  expect(kunciDraf("u1", "k1", "a1")).toBe("u1|k1|a1");
  expect(kunciDraf("u1", "k1", null)).toBe(`u1|k1|${ID_BARU}`);
  expect(kunciDraf("", null, "a1")).toBe("anon|-|a1");
});

test("form edit yang tak disentuh TIDAK dirty — dialog tak boleh muncul", () => {
  const o = asli();
  expect(ringkasPerubahan({ isEditing: true, formData: { ...o }, original: o, photoItems: ada(2), mediaLoaded: true }).dirty).toBe(false);
  // data belum termuat → tidak dirty
  expect(ringkasPerubahan({ isEditing: true, formData: o, original: null }).dirty).toBe(false);
});

test("isian otomatis (GPS pinjaman, garansi riwayat) tidak memicu dirty", () => {
  const o = asli();
  const f = { ...o, koordinat_latitude: "-1.2", koordinat_longitude: "116.8", garansi_hingga: "2027-01-01" };
  expect(ringkasPerubahan({ isEditing: true, formData: f, original: o, abaikan: ["garansi_hingga"] }).dirty).toBe(false);
});

test("aset baru: kategori dummy + NUP otomatis tidak dirty, foto & nama dirty", () => {
  const e = emptyAssetForm("k1");
  const dummy = { ...e, category: "Dummy", asset_code: "999", NUP: "7" };
  expect(ringkasPerubahan({ isEditing: false, formData: dummy, emptyForm: e }).dirty).toBe(false);
  const r = ringkasPerubahan({ isEditing: false, formData: { ...dummy, photos: ["data:a"] }, emptyForm: e });
  expect(r).toMatchObject({ dirty: true, fotoBaru: 1 });
  expect(ringkasPerubahan({ isEditing: false, formData: { ...e, asset_name: "Kursi" }, emptyForm: e }).fields).toEqual(["asset_name"]);
});

test("ringkasan edit: field, foto baru, foto dihapus, checklist", () => {
  const o = asli();
  const items = [ada(2)[1], { type: "new", newData: "data:x", thumbnail: "data:x" }];
  const r = ringkasPerubahan({ isEditing: true, formData: { ...o, asset_name: "Meja Rapat", condition: "Rusak Ringan" },
    original: o, photoItems: items, photosModified: true, mediaLoaded: true, checklistModified: true });
  expect(r).toEqual({ dirty: true, fields: ["asset_name", "condition"], fotoBaru: 1, fotoDihapus: 1, checklist: true });
  expect(teksPerubahan(r)).toBe("Nama Aset, Kondisi, 1 foto baru, 1 foto dihapus, kelengkapan dokumen");
});

test("luring (media belum dimuat): foto lama tak dihitung terhapus", () => {
  const o = asli();
  const r = ringkasPerubahan({ isEditing: true, formData: o, original: o,
    photoItems: [{ type: "new", newData: "d" }], photosModified: true, mediaLoaded: false });
  expect(r).toMatchObject({ dirty: true, fotoBaru: 1, fotoDihapus: 0 });
});

test("teks ringkas memotong daftar panjang", () => {
  expect(teksPerubahan({ dirty: true, fields: ["asset_name", "brand", "model", "condition", "notes", "location"], fotoBaru: 0, fotoDihapus: 0 }, 2))
    .toBe("Nama Aset, Brand, +4 field lain");
});

test("sidik berubah bila isian / foto berubah", () => {
  const o = asli();
  const a = sidikForm(o, ada(2));
  expect(sidikForm({ ...o }, ada(2))).toBe(a);
  expect(sidikForm({ ...o, notes: "x" }, ada(2))).not.toBe(a);
  expect(sidikForm(o, [...ada(2), { type: "new", newData: "abc" }])).not.toBe(a);
});

test("draf edit pulih di atas data server segar: hanya field yang diubah pengguna yang ditimpa", () => {
  const o = asli();
  const items = [ada(2)[1], { type: "new", newData: "data:baru", thumbnail: "th" }];
  const rec = bangunRekamanDraf({ key: "k", userId: "u", activityId: "k1", assetId: "a1", isEditing: true,
    formData: { ...o, asset_name: "Meja Rapat", thumbnail_index: 1 }, original: o, photoItems: items,
    photosModified: true, baseVersion: 3 });
  expect(rec.fotoBaru).toEqual([{ newData: "data:baru", thumbnail: "th" }]);
  expect(rec.fotoTetap).toEqual([1]);
  // server mengubah field LAIN sejak draf → tetap terbawa
  const segar = { ...o, brand: "Informa" };
  const r = pulihkanDrafEdit({ draf: rec, lightData: segar, existingItems: ada(2), versiKini: 3, mediaLoaded: true });
  expect(r.formData).toMatchObject({ asset_name: "Meja Rapat", brand: "Informa", thumbnail_index: 1 });
  expect(r.diubah).toEqual(["asset_name"]);
  expect(r.items.map(it => it.type === "existing" ? it.originalIndex : it.newData)).toEqual([1, "data:baru"]);
  expect(r).toMatchObject({ versiBerubah: false, fotoDisusun: true, bentrok: [] });
});

test("versi server berubah: penghapusan foto & sampul tidak diterapkan, bentrok dilaporkan", () => {
  const o = asli();
  const rec = bangunRekamanDraf({ key: "k", isEditing: true, assetId: "a1",
    formData: { ...o, asset_name: "Meja Rapat", thumbnail_index: 1 }, original: o,
    photoItems: [ada(2)[1], { type: "new", newData: "n" }], photosModified: true, baseVersion: 3 });
  const r = pulihkanDrafEdit({ draf: rec, lightData: { ...o, asset_name: "Meja Server" }, existingItems: ada(2), versiKini: 4, mediaLoaded: true });
  expect(r.versiBerubah).toBe(true);
  expect(r.bentrok).toEqual(["asset_name"]);
  expect(r.formData.asset_name).toBe("Meja Rapat");
  expect(r.formData.thumbnail_index).toBe(0);
  expect(r.items.map(it => it.originalIndex ?? it.newData)).toEqual([0, 1, "n"]);
});

test("draf aset baru: foto & isian kembali, indeks sampul dijaga", () => {
  const e = emptyAssetForm("k1");
  const rec = bangunRekamanDraf({ key: "k", isEditing: false, formData: { ...e, asset_name: "Kursi", photos: ["p1", "p2"], thumbnail_index: 5 } });
  expect(rec.assetId).toBe(null);
  const f = pulihkanDrafBaru({ draf: rec, emptyForm: e });
  expect(f).toMatchObject({ asset_name: "Kursi", photos: ["p1", "p2"], thumbnail_index: 1, activity_id: "k1" });
});

test("draf basi dibuang setelah TTL", () => {
  const now = Date.now();
  expect(drafBasi({ updatedAt: now - DRAF_TTL_MS - 1 }, now)).toBe(true);
  expect(drafBasi({ updatedAt: now - 1000 }, now)).toBe(false);
  expect(drafBasi(null)).toBe(true);
});
