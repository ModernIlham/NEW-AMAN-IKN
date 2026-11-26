import fs from "fs";
import path from "path";
const { berkasLightbox, manifestRilis, LightboxPrecachePlugin } = require("../../../plugins/lightbox-precache-plugin.cjs");
const templatePath = path.resolve(__dirname, "../../../public/service-worker.js");
const template = fs.readFileSync(templatePath, "utf8");
const files = ["static/js/penampil.123.chunk.js", "static/js/bersama.456.chunk.js", "static/css/penampil.123.css"];
function kompilasi(list = files) {
  return { namedChunkGroups: new Map([["photo-lightbox", { getFiles: () => list }], ["asset-dashboard", { getFiles: () => ["static/js/asset-dashboard.789.chunk.js"] }], ["module-home", { getFiles: () => ["static/js/module-home.abc.chunk.js"] }]]),
    entrypoints: new Map([["main", { getFiles: () => ["static/js/main.abc.js"] }]]),
    getAssets: () => [...files, "static/js/asset-dashboard.789.chunk.js", "static/js/module-home.abc.chunk.js", "static/js/main.abc.js"].map(name => ({ name })), getAsset: jest.fn(() => ({ source: { source: () => "compiled bytes" } })) };
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
test("manifest memuat bootstrap dan grup editor luring, hash stabil serta source SHA terpisah", () => {
  const manifest = manifestRilis(kompilasi());
  expect(manifest.main).toBe("/static/js/main.abc.js");
  expect(manifest.critical).toEqual(expect.arrayContaining([manifest.main, "/static/js/asset-dashboard.789.chunk.js", "/static/js/module-home.abc.chunk.js", ...files.map(f => `/${f}`)]));
  expect(manifest.id).toMatch(/^[a-f0-9]{16}$/);
  const previous = process.env.AMAN_RELEASE_SHA;
  try { process.env.AMAN_RELEASE_SHA = "a".repeat(40); const tagged = manifestRilis(kompilasi()); expect(tagged.id).toBe(manifest.id); expect(tagged.source_sha).toBe("a".repeat(40)); }
  finally { if (previous === undefined) delete process.env.AMAN_RELEASE_SHA; else process.env.AMAN_RELEASE_SHA = previous; }
});
test("ketiga pintu masuk memakai loader bersama, tidak mengimpor penampil langsung", () => {
  for (const file of ["components/assets/AssetGalleryView.jsx", "components/assets/AssetMapFullView.jsx", "pages/DashboardPage.jsx"]) {
    const source = fs.readFileSync(path.resolve(__dirname, "../..", file), "utf8");
    expect(source).toContain("PhotoLightboxLoader");
    expect(source).not.toMatch(/(?:from|import\()\s*["'][^"']*\/PhotoLightbox["']/);
  }
});

test("SHA sumber hanya di aman-release.json; worker identik antar-deploy yang hanya beda SHA", () => {
  const bangun = sha => {
    const previous = process.env.AMAN_RELEASE_SHA;
    try {
      process.env.AMAN_RELEASE_SHA = sha;
      const c = kompilasi(); c.emitAsset = jest.fn();
      c.hooks = { processAssets: { tap: (_o, cb) => cb() } };
      const compiler = { hooks: { thisCompilation: { tap: (_n, cb) => cb(c) } },
        webpack: { Compilation: { PROCESS_ASSETS_STAGE_REPORT: 5000 }, sources: { RawSource: class { constructor(source) { this.source = source; } } } } };
      new LightboxPrecachePlugin(templatePath).apply(compiler);
      return Object.fromEntries(c.emitAsset.mock.calls.map(([nama, src]) => [nama, src.source]));
    } finally { if (previous === undefined) delete process.env.AMAN_RELEASE_SHA; else process.env.AMAN_RELEASE_SHA = previous; }
  };
  const a = bangun("a".repeat(40)), b = bangun("b".repeat(40));
  expect(a["service-worker.js"]).toBe(b["service-worker.js"]);
  expect(a["service-worker.js"]).not.toContain("source_sha");
  expect(JSON.parse(a["aman-release.json"]).source_sha).toBe("a".repeat(40));
  expect(JSON.parse(b["aman-release.json"]).source_sha).toBe("b".repeat(40));
});

test("REACT_APP_RELEASE_SHA lama tetap diterima sebagai cadangan; AMAN_RELEASE_SHA diutamakan", () => {
  const simpan = { a: process.env.AMAN_RELEASE_SHA, r: process.env.REACT_APP_RELEASE_SHA };
  try {
    delete process.env.AMAN_RELEASE_SHA; process.env.REACT_APP_RELEASE_SHA = "c".repeat(40);
    expect(manifestRilis(kompilasi()).source_sha).toBe("c".repeat(40));
    process.env.AMAN_RELEASE_SHA = "d".repeat(40);
    expect(manifestRilis(kompilasi()).source_sha).toBe("d".repeat(40));
  } finally {
    for (const [k, v] of [["AMAN_RELEASE_SHA", simpan.a], ["REACT_APP_RELEASE_SHA", simpan.r]]) {
      if (v === undefined) delete process.env[k]; else process.env[k] = v;
    }
  }
});

test("deploy & CI tak lagi mengoper SHA lewat REACT_APP_ (tersemat ke bundel → hash berubah tiap deploy)", () => {
  const akar = path.resolve(__dirname, "../../../..");
  const deploy = fs.readFileSync(path.join(akar, "scripts/deploy_vps.sh"), "utf8");
  const ci = fs.readFileSync(path.join(akar, ".github/workflows/ci.yml"), "utf8");
  expect(deploy).toMatch(/AMAN_RELEASE_SHA="\$DEPLOY_SHA" yarn build/);
  expect(deploy).not.toMatch(/REACT_APP_RELEASE_SHA=/);
  expect(ci).not.toMatch(/REACT_APP_RELEASE_SHA:/);
});
