const fs = require("fs");
const crypto = require("crypto");
const PENANDA = "/* AMAN_LIGHTBOX_PRECACHE */ []";
const RELEASE_MARKER = "/* AMAN_RELEASE_MANIFEST */ null";
const staticFile = file => /^static\/(js|css|media)\/[a-zA-Z0-9_.-]+\.[a-zA-Z0-9]+$/.test(file) && !/\.(map|txt)$/.test(file);
function groupFiles(compilation, name) {
  const files = [...new Set(compilation.namedChunkGroups.get(name)?.getFiles() || [])]
    .filter(file => /^static\/(js|css)\/[a-zA-Z0-9_.-]+\.(js|css)$/.test(file)).sort();
  if (!files.some(file => file.endsWith(".js"))) throw new Error(`Chunk ${name} tidak ditemukan; jaminan luring belum terpenuhi.`);
  if (files.some(file => !compilation.getAsset(file))) throw new Error(`Berkas precache ${name} tidak tersedia dalam hasil build.`);
  return files.map(file => `/${file}`);
}
function berkasLightbox(compilation) { return groupFiles(compilation, "photo-lightbox"); }
function manifestRilis(compilation) {
  const assets = compilation.getAssets().map(asset => asset.name).filter(staticFile).sort().map(file => `/${file}`);
  const entry = (compilation.entrypoints.get("main")?.getFiles() || []).filter(staticFile).map(file => `/${file}`);
  const main = entry.find(file => /\/main\.[A-Za-z0-9]+\.js$/.test(file));
  if (!main) throw new Error("Entrypoint main untuk rilis luring tidak ditemukan.");
  const critical = [...new Set([...entry, ...groupFiles(compilation, "asset-dashboard"), ...groupFiles(compilation, "module-home"), ...berkasLightbox(compilation)])].sort();
  if (assets.length > 500 || critical.some(file => !assets.includes(file))) throw new Error("Manifest rilis tidak lengkap atau melebihi 500 berkas.");
  // Hash final assets, bukan waktu build: build identik memakai identitas identik.
  const integrity = Object.fromEntries(assets.map(file => {
    const asset = compilation.getAsset(file.slice(1));
    const bytes = asset?.source?.source();
    if (bytes === undefined) throw new Error(`Konten aset rilis tidak tersedia: ${file}`);
    return [file, `sha256-${crypto.createHash("sha256").update(bytes).digest("base64")}`];
  }));
  const id = crypto.createHash("sha256").update(JSON.stringify({ assets, critical, main, integrity })).digest("hex").slice(0, 16);
  return { id, main, assets, critical, integrity, source_sha: /^[a-f0-9]{40}$/i.test(process.env.REACT_APP_RELEASE_SHA || "") ? process.env.REACT_APP_RELEASE_SHA.toLowerCase() : null };
}
class LightboxPrecachePlugin {
  constructor(template) { this.template = template; }
  apply(compiler) {
    compiler.hooks.thisCompilation.tap("LightboxPrecachePlugin", compilation => {
      compilation.hooks.processAssets.tap({ name: "LightboxPrecachePlugin", stage: compiler.webpack.Compilation.PROCESS_ASSETS_STAGE_REPORT }, () => {
        const source = fs.readFileSync(this.template, "utf8");
        if (!source.includes(PENANDA) || !source.includes(RELEASE_MARKER)) throw new Error("Penanda precache/rilis hilang.");
        const release = manifestRilis(compilation);
        const output = source.replace(PENANDA, JSON.stringify(berkasLightbox(compilation))).replace(RELEASE_MARKER, JSON.stringify(release));
        compilation.emitAsset("service-worker.js", new compiler.webpack.sources.RawSource(output));
        compilation.emitAsset("aman-release.json", new compiler.webpack.sources.RawSource(JSON.stringify(release)));
      });
    });
  }
}
module.exports = { LightboxPrecachePlugin, berkasLightbox, manifestRilis };
