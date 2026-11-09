import "../uji/indexedDB";
import { openDB, deleteDB } from "idb";
import { simpanDraf, muatDraf, hapusDraf } from "./drafAset";
beforeEach(async () => { await deleteDB("aman_draf_aset"); });
const record = { key: "u|k|a", assetId: "a", userId: "u", updatedAt: Date.now(), fotoBaru: [{ newData: "foto lama" }], formData: { asset_name: "A" } };
test("format deployed tanpa revision dipulihkan, disimpan dan dibaca ulang beserta foto", async () => {
  const db = await openDB("aman_draf_aset", 1, { upgrade(db) { db.createObjectStore("draf", { keyPath: "key" }); } });
  await db.put("draf", record); db.close();
  expect((await muatDraf(record.key)).fotoBaru).toEqual(record.fotoBaru);
  await simpanDraf({ ...record, formData: { asset_name: "Baru" } });
  expect(await muatDraf(record.key)).toMatchObject({ revision: 1, fotoBaru: record.fotoBaru, formData: { asset_name: "Baru" } });
});
test("perubahan tab lain menolak tulis dan hapus usang tanpa menghilangkan foto", async () => {
  await muatDraf(record.key); await simpanDraf(record);
  const db = await openDB("aman_draf_aset", 1);
  await db.put("draf", { ...record, revision: 2, fotoBaru: [{ newData: "foto tab lain" }] });
  await expect(simpanDraf(record)).rejects.toThrow("tab lain");
  await expect(hapusDraf(record.key)).rejects.toThrow("tab lain");
  expect((await db.get("draf", record.key)).fotoBaru[0].newData).toBe("foto tab lain"); db.close();
});
test("dua autosave satu tab berurutan dan hapus menunggu commit terakhir", async () => {
  await muatDraf(record.key);
  await Promise.all([simpanDraf(record), simpanDraf({ ...record, label: "terakhir" })]);
  expect(await muatDraf(record.key)).toMatchObject({ revision: 2, label: "terakhir" });
  await hapusDraf(record.key); expect(await muatDraf(record.key)).toBeNull();
});
