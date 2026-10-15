import { buatCacheHalamanAset } from "../cacheHalamanAset";
const rows = page => Array.from({ length: 50 }, (_, i) => ({ id: `p${page}-${i}`, version: 1, thumbnail: "a".repeat(4096), notes: "Catatan" }));
test("200 halaman/10k aset mencapai plateau halaman+byte lalu dapat diambil ulang ke arah sebaliknya", () => {
  const c = buatCacheHalamanAset();
  const selection = new Set(["p1-0"]), draft = { assetId: "p1-0", value: "Belum disimpan" };
  for (let page = 1; page <= 200; page++) {
    c.setVisible([`p${Math.max(1, page - 1)}-25`]); c.put(page, rows(page));
    expect(c.metrics().pages).toBeLessThanOrEqual(6); expect(c.metrics().bytes).toBeLessThanOrEqual(8 * 1024 * 1024);
  }
  expect(c.rows()).toHaveLength(300); expect(c.range()).toEqual({ first: 195, last: 200 });
  expect(selection.has("p1-0")).toBe(true); expect(draft.value).toBe("Belum disimpan");
  for (let page = 194; page >= 1; page--) { c.setVisible([`p${page + 1}-25`]); c.put(page, rows(page)); }
  expect(c.range()).toEqual({ first: 1, last: 6 }); expect(c.rows()[0].id).toBe("p1-0");
  expect(c.metrics().overBudget).toBe(false);
});
test("refresh hanya halaman terlihat+margin; patch/delete tidak dihidupkan kembali oleh append", () => {
  const c = buatCacheHalamanAset();
  for (let p = 1; p <= 6; p++) c.put(p, rows(p));
  c.setVisible(["p4-25"]); expect(c.refreshRange(200)).toEqual({ first: 3, last: 5 });
  c.updateRow({ id: "p4-25", version: 9, notes: "Sudah diperbarui" }); c.removeRow("p3-0"); c.put(7, rows(7));
  expect(c.rows().find(r => r.id === "p4-25")).toMatchObject({ version: 9, notes: "Sudah diperbarui" });
  expect(c.rows().some(r => r.id === "p3-0")).toBe(false);
});
test("byte cap mengurangi halaman lebih awal, keanggotaan absolut tetap kontigu", () => {
  const c = buatCacheHalamanAset({ maxPages: 6, maxBytes: 1000000 });
  for (let p = 1; p <= 20; p++) { c.setVisible([`p${p - 1}-25`]); c.put(p, rows(p)); }
  expect(c.metrics().pages).toBe(2); expect(c.metrics().overBudget).toBe(false); expect(c.range()).toEqual({ first: 19, last: 20 });
});
