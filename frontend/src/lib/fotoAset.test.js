import { patchHapusFoto, sumberFotoItem } from "./fotoAset";

test("foto tersimpan tetap memakai indeks sumber setelah draf diurut/hapus; foto baru memakai bytes penuh", () => {
  const src = sumberFotoItem({ type: "existing", originalIndex: 4, thumbnail: "/thumb-kecil" }, "aset-a", 7);
  expect(src).toContain("/assets/aset-a/photos/4?v=7");
  expect(src).not.toContain("thumb=");
  expect(sumberFotoItem({ type: "new", newData: "data:image/jpeg;base64,FULL", thumbnail: "SMALL" })).toBe("data:image/jpeg;base64,FULL");
});

test.each([
  [0, [1, 2, 3], 1, 2], [2, [0, 1, 3], 0, null], [3, [0, 1, 2], 2, 2],
])("hapus posisi %s menjaga foto lain, sampul, stiker dan versi", (index, keep, cover, sticker) => {
  const asset = { photo_count: 4, version: 12, thumbnail_index: 2, stiker_photo_index: index === 0 ? 3 : 2 };
  const snapshot = { ...asset };
  expect(patchHapusFoto(asset, index)).toEqual({ photo_ops: { keep, add: [], thumbnail_index: cover, base_version: 12 }, stiker_photo_index: sticker });
  expect(asset).toEqual(snapshot);
});

test("foto terakhir dapat dihapus, metadata yang belum diketahui tidak menebak indeks", () => {
  expect(patchHapusFoto({ photo_count: 1, version: 2 }, 0)).toEqual({ photo_ops: { keep: [], add: [], thumbnail_index: 0, base_version: 2 }, stiker_photo_index: null });
  for (const index of [-1, 3, 1.5]) expect(() => patchHapusFoto({ photo_count: 3, version: 1 }, index)).toThrow();
  expect(() => patchHapusFoto({ photo_count: 3 }, 1)).toThrow();
});
