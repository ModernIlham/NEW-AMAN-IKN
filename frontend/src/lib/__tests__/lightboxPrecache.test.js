import fs from "fs";
import path from "path";
import vm from "vm";
const { berkasLightbox, LightboxPrecachePlugin } = require("../../../plugins/lightbox-precache-plugin.cjs");
const templatePath = path.resolve(__dirname, "../../../public/service-worker.js");
const template = fs.readFileSync(templatePath, "utf8");
const files = ["static/js/penampil.123.chunk.js", "static/js/bersama.456.chunk.js", "static/css/penampil.123.css"];
function kompilasi(list = files) {
  return { namedChunkGroups: new Map([["photo-lightbox", { getFiles: () => list }]]), getAsset: jest.fn(() => ({})) };
}
test("precache memuat semua dependensi grup, mengabaikan map dan menolak URL non-statis", () => {
  expect(berkasLightbox(kompilasi([...files, ...files, "static/js/penampil.js.map", "/api/foto.jpg", "https://lain/foto.js"])))
    .toEqual([...files].sort().map(f => `/${f}`));
});
test("build gagal jika grup hilang atau berkas hash tidak tersedia", () => {
  expect(() => berkasLightbox(kompilasi([]))).toThrow(/tidak ditemukan/);
  const c = kompilasi(); c.getAsset.mockReturnValue(undefined);
  expect(() => berkasLightbox(c)).toThrow(/tidak tersedia/);
});
test("plugin menghasilkan worker dengan URL hash final, bukan berkas manifest yang dapat berubah", () => {
  const c = kompilasi(); c.emitAsset = jest.fn();
  c.hooks = { processAssets: { tap: (options, cb) => { expect(options.stage).toBe(5000); cb(); } } };
  const compiler = { hooks: { thisCompilation: { tap: (_name, cb) => cb(c) } },
    webpack: { Compilation: { PROCESS_ASSETS_STAGE_REPORT: 5000 }, sources: { RawSource: class { constructor(source) { this.source = source; } } } } };
  new LightboxPrecachePlugin(templatePath).apply(compiler);
  expect(c.emitAsset.mock.calls[0][0]).toBe("service-worker.js");
  const source = c.emitAsset.mock.calls[0][1].source;
  expect(source).not.toContain("/* AMAN_LIGHTBOX_PRECACHE */ []");
  for (const file of files) expect(source).toContain(`/${file}`);
});
function worker(gagal = false) {
  const handlers = {};
  const cache = { addAll: jest.fn(() => gagal ? Promise.reject(new Error("404 chunk")) : Promise.resolve()) };
  const caches = { open: jest.fn(async () => cache), delete: jest.fn() };
  const self = { addEventListener: (type, handler) => { handlers[type] = handler; }, skipWaiting: jest.fn(async () => {}), clients: { claim: jest.fn() } };
  vm.runInNewContext(template.replace("/* AMAN_LIGHTBOX_PRECACHE */ []", JSON.stringify(files.map(f => `/${f}`))), { self, caches, URL, console });
  let selesai;
  handlers.install({ waitUntil: p => { selesai = p; } });
  return { cache, caches, self, selesai, handlers };
}
test("worker baru aktif hanya setelah semua chunk siap", async () => {
  const w = worker(); await w.selesai;
  expect(w.cache.addAll).toHaveBeenCalledWith(["/", "/index.html", "/manifest.json", ...files.map(f => `/${f}`)]);
  expect(w.self.skipWaiting).toHaveBeenCalledTimes(1);
});
test("precache gagal tidak mengaktifkan worker baru atau menghapus cache lama", async () => {
  const w = worker(true); await expect(w.selesai).rejects.toThrow("404 chunk");
  expect(w.self.skipWaiting).not.toHaveBeenCalled();
  expect(w.caches.delete).not.toHaveBeenCalled();
});
test("API privat termasuk foto tidak masuk strategi cache statis", () => {
  const w = worker();
  const respondWith = jest.fn();
  w.handlers.fetch({ request: { method: "GET", url: "https://aman.test/api/assets/a/photos/0.jpg" }, respondWith });
  expect(respondWith).not.toHaveBeenCalled();
});
test("ketiga pintu masuk memakai loader bersama, tidak mengimpor penampil langsung", () => {
  for (const file of ["components/assets/AssetGalleryView.jsx", "components/assets/AssetMapFullView.jsx", "pages/DashboardPage.jsx"]) {
    const source = fs.readFileSync(path.resolve(__dirname, "../..", file), "utf8");
    expect(source).toContain("PhotoLightboxLoader");
    expect(source).not.toMatch(/(?:from|import\()\s*["'][^"']*\/PhotoLightbox["']/);
  }
});
