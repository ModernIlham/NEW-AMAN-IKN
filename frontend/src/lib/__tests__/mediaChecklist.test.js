import { gabungMediaChecklist, indeksItemMedia } from "../mediaChecklist";
import { bangunChecklist, rekomendasiKelengkapan } from "../kelengkapanBmn";

test("rekomendasi yang memindahkan STNK tetap membawa indeks server dan sentinel file asli", () => {
  const stored = [{ id: "stnk-id", name: "STNK", checked: true, photo_count: 2,
    documents: [{ id: "pdf-id", name: "STNK.pdf", idx: 1 }] }];
  const ordered = bangunChecklist(rekomendasiKelengkapan("3020105004"), stored);
  expect(ordered.findIndex(item => item.name === "STNK")).toBeGreaterThan(0);
  const merged = gabungMediaChecklist(ordered, stored), item = merged.find(entry => entry.name === "STNK");
  expect(item).toMatchObject({ id: "stnk-id", _serverItemIndex: 0, photos: ["__existing__:0", "__existing__:1"], documents: [{ id: "pdf-id", name: "STNK.pdf", data: "__existing__:1" }] });
  expect(indeksItemMedia(item, 4)).toBe(0); expect(stored[0]).not.toHaveProperty("_serverItemIndex");
});
test("ID stabil mengikuti rename/reorder; nama legacy ganda tidak menyalin media item terakhir ke semua baris", () => {
  const source = [{ id: "first", name: "Lama", photo_count: 1 }, { id: "second", name: "Lama", photo_count: 2 }];
  const reordered = gabungMediaChecklist([{ id: "second", name: "Baru" }, { id: "first", name: "Lama" }], source);
  expect(reordered.map(item => item._serverItemIndex)).toEqual([1, 0]); expect(reordered.map(item => item.photos.length)).toEqual([2, 1]);
  const legacy = gabungMediaChecklist([{ name: "Lama" }, { name: "Lama" }], source.map(({ id, ...rest }) => rest));
  expect(legacy.map(item => item._serverItemIndex)).toEqual([0, 1]); expect(legacy.map(item => item.photos.length)).toEqual([1, 2]);
  const removed = { id: "deleted", name: "Lama", photos: [] }; expect(gabungMediaChecklist([removed], source)[0]).toBe(removed);
});
