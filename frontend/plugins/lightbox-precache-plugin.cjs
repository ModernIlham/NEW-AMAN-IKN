const fs = require("fs");

const PENANDA = "/* AMAN_LIGHTBOX_PRECACHE */ []";

// Nama berkas diambil SETELAH hashing webpack selesai, bukan ditebak dari
// nomor chunk. Termasuk chunk bersama/CSS yang diperlukan grup impor ini.
function berkasLightbox(compilation) {
  const grup = compilation.namedChunkGroups.get("photo-lightbox");
  const files = [...new Set(grup?.getFiles() || [])]
    .filter(file => /^static\/(js|css)\/[a-zA-Z0-9_.-]+\.(js|css)$/.test(file))
    .sort();
  if (!files.some(file => file.endsWith(".js"))) {
    throw new Error("Chunk PhotoLightbox tidak ditemukan; jaminan luring belum terpenuhi.");
  }
  if (files.some(file => !compilation.getAsset(file))) {
    throw new Error("Berkas precache PhotoLightbox tidak tersedia dalam hasil build.");
  }
  return files.map(file => `/${file}`);
}

class LightboxPrecachePlugin {
  constructor(template) { this.template = template; }
  apply(compiler) {
    compiler.hooks.thisCompilation.tap("LightboxPrecachePlugin", compilation => {
      compilation.hooks.processAssets.tap({ name: "LightboxPrecachePlugin",
        stage: compiler.webpack.Compilation.PROCESS_ASSETS_STAGE_REPORT }, () => {
        const source = fs.readFileSync(this.template, "utf8");
        if (!source.includes(PENANDA)) throw new Error("Penanda precache PhotoLightbox hilang.");
        const output = source.replace(PENANDA, JSON.stringify(berkasLightbox(compilation)));
        compilation.emitAsset("service-worker.js", new compiler.webpack.sources.RawSource(output));
      });
    });
  }
}

module.exports = { LightboxPrecachePlugin, berkasLightbox };
