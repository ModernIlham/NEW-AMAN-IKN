// Potong GeoTIFF jadi ubin XYZ DI PERAMBAN admin, lalu kirim ke server.
//
// Kenapa di peramban: server produksi 2 vCPU tanpa GDAL; memotong citra drone
// berukuran gigabyte di sana akan memakan CPU yang melayani semua pengguna.
// Peramban membaca berkas sedikit demi sedikit (File.slice — tidak dimuat
// utuh ke memori) lewat geotiff.js yang dimuat LAZY hanya di sini.
//
// Strategi piramida: hanya ubin zoom tertinggi yang dibaca dari citra; ubin
// zoom di bawahnya disusun dari 4 ubin anaknya (penelusuran depth-first,
// memori tetap kecil). Membaca citra utuh untuk ubin zoom rendah — bagian
// terberat — tak pernah terjadi.
import {
  crsDariGeoKeys, batasWgs84, keSumber, rencanaZoom, resolusiMeter, rentangUbin,
  tanggalDariTiff, transformUbin, ubinMenyentuh, ubinXKeLon, ubinYKeLat, UBIN_PX,
} from "./proyeksiCitra";

const KUALITAS = 0.82;

/** Format ubin yang benar-benar bisa disandikan peramban ini. */
export async function pilihFormatUbin() {
  try {
    const c = document.createElement("canvas");
    c.width = 2; c.height = 2;
    const b = await new Promise((r) => c.toBlob(r, "image/webp", KUALITAS));
    if (b && b.type === "image/webp") return "webp";
  } catch { /* abaikan */ }
  return "png";
}

/** Buka GeoTIFF: metadata, batas WGS84, rencana zoom. Lempar Error berpesan jelas. */
export async function bukaGeoTiff(file) {
  const { fromBlob, Pool } = await import("geotiff");
  let tiff;
  try {
    tiff = await fromBlob(file);
  } catch {
    throw new Error("Berkas tidak bisa dibaca sebagai GeoTIFF.");
  }
  const utama = await tiff.getImage(0);
  const crs = crsDariGeoKeys(utama.getGeoKeys());
  if (crs.galat) throw new Error(crs.galat);
  const W = utama.getWidth(); const H = utama.getHeight();
  const [x0, y0] = utama.getOrigin();
  const [rx, ry] = utama.getResolution();
  const kotak = [Math.min(x0, x0 + W * rx), Math.min(y0, y0 + H * ry),
    Math.max(x0, x0 + W * rx), Math.max(y0, y0 + H * ry)];
  const batas = batasWgs84(kotak, crs);
  const latTengah = (batas.utara + batas.selatan) / 2;
  const mpp = resolusiMeter(rx, crs, latTengah);
  const rencana = rencanaZoom(batas, mpp);

  // Overview internal (COG/GDAL): sub-berkas beresolusi lebih rendah. Hanya
  // untuk ubin yang zoom-nya jauh di bawah resolusi asli (citra terlalu besar).
  const tingkat = [{ img: utama, f: 1 }];
  const n = await tiff.getImageCount();
  for (let i = 1; i < n; i += 1) {
    const img = await tiff.getImage(i);
    const jenis = Number(img.fileDirectory.getValue("NewSubfileType") || 0);
    if ((jenis & 1) && !(jenis & 4) && img.getWidth() < W) tingkat.push({ img, f: W / img.getWidth() });
  }
  tingkat.sort((a, b) => a.f - b.f);

  let tanggal = "";
  try { tanggal = tanggalDariTiff(await utama.fileDirectory.loadValue("DateTime")); } catch { /* opsional */ }
  let pool = null;
  try { pool = new Pool(); } catch { pool = null; }

  return {
    namaBerkas: file.name, crs, lebar: W, tinggi: H, asal: [x0, y0], res: [rx, ry],
    batas, meterPerPiksel: mpp, rencana, tingkat, tanggal, pool,
    samples: utama.getSamplesPerPixel(), noData: utama.getGDALNoData(),
    tutup() { try { pool?.destroy(); } catch { /* abaikan */ } },
  };
}

function kanvas(w = UBIN_PX, h = UBIN_PX) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  return c;
}

function kosong(ctx) {
  const d = ctx.getImageData(0, 0, UBIN_PX, UBIN_PX).data;
  for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) return false;
  return true;
}

/** Baca jendela sumber jadi RGBA Uint8ClampedArray. */
async function bacaRgba(sumber, lvl, jendelaLvl, w, h) {
  const { img } = lvl;
  const opsi = { window: jendelaLvl, width: w, height: h, interleave: true,
    resampleMethod: "bilinear", pool: sumber.pool };
  let data; let kanal;
  if (sumber.samples >= 4) {
    // RGB + band ke-4: perlakukan sebagai alfa (keluaran drone/QGIS lazim),
    // walau tag ExtraSamples-nya "unspecified".
    data = await img.readRasters({ ...opsi, samples: [0, 1, 2, 3] });
    kanal = 4;
  } else {
    data = await img.readRGB({ ...opsi, enableAlpha: true });
    kanal = data.length === w * h * 4 ? 4 : 3;
  }
  const geser = data instanceof Uint16Array ? 8 : 0;   // 16-bit → 8-bit
  const out = new Uint8ClampedArray(w * h * 4);
  const nd = sumber.noData;
  for (let p = 0, q = 0; p < w * h; p += 1, q += kanal) {
    const r = data[q] >> geser; const g = data[q + 1] >> geser; const b = data[q + 2] >> geser;
    out[p * 4] = r; out[p * 4 + 1] = g; out[p * 4 + 2] = b;
    let a = kanal === 4 ? data[q + 3] >> geser : 255;
    if (nd !== null && nd !== undefined && data[q] === nd && data[q + 1] === nd && data[q + 2] === nd) a = 0;
    out[p * 4 + 3] = a;
  }
  return out;
}

/** Render satu ubin zoom tertinggi langsung dari citra. Kembalikan kanvas atau null (kosong). */
async function ubinDariSumber(sumber, z, x, y) {
  const { crs, asal: [x0, y0], res: [rx, ry], lebar: W, tinggi: H } = sumber;
  const lon0 = ubinXKeLon(x, z); const lon1 = ubinXKeLon(x + 1, z);
  const lat0 = ubinYKeLat(y, z); const lat1 = ubinYKeLat(y + 1, z);
  const px = (lon, lat) => {
    const [sx, sy] = keSumber(lon, lat, crs);
    return [(sx - x0) / rx, (sy - y0) / ry];
  };
  const sudut = [px(lon0, lat0), px(lon1, lat0), px(lon0, lat1)];
  const br = px(lon1, lat1);
  const cs = [...sudut.map((s) => s[0]), br[0]]; const rs = [...sudut.map((s) => s[1]), br[1]];
  const c0 = Math.max(0, Math.floor(Math.min(...cs)) - 1); const c1 = Math.min(W, Math.ceil(Math.max(...cs)) + 1);
  const r0 = Math.max(0, Math.floor(Math.min(...rs)) - 1); const r1 = Math.min(H, Math.ceil(Math.max(...rs)) + 1);
  if (c1 <= c0 || r1 <= r0) return null;

  const pxPerUbin = Math.hypot(sudut[1][0] - sudut[0][0], sudut[1][1] - sudut[0][1]) / UBIN_PX;
  const lvl = [...sumber.tingkat].reverse().find((t) => t.f <= Math.max(1, pxPerUbin)) || sumber.tingkat[0];
  const jendelaLvl = [Math.floor(c0 / lvl.f), Math.floor(r0 / lvl.f),
    Math.max(Math.floor(c0 / lvl.f) + 1, Math.ceil(c1 / lvl.f)), Math.max(Math.floor(r0 / lvl.f) + 1, Math.ceil(r1 / lvl.f))];
  const skala = Math.max(1, pxPerUbin / lvl.f);
  const w = Math.max(1, Math.min(1024, Math.round((jendelaLvl[2] - jendelaLvl[0]) / skala)));
  const h = Math.max(1, Math.min(1024, Math.round((jendelaLvl[3] - jendelaLvl[1]) / skala)));
  const rgba = await bacaRgba(sumber, lvl, jendelaLvl, w, h);

  const tmp = kanvas(w, h);
  tmp.getContext("2d").putImageData(new ImageData(rgba, w, h), 0, 0);
  const c = kanvas();
  const ctx = c.getContext("2d", { willReadFrequently: true });
  ctx.imageSmoothingQuality = "high";
  const jendelaPenuh = { c0: jendelaLvl[0] * lvl.f, r0: jendelaLvl[1] * lvl.f, c1: jendelaLvl[2] * lvl.f, r1: jendelaLvl[3] * lvl.f };
  ctx.setTransform(...transformUbin(sudut, jendelaPenuh, w, h));
  ctx.drawImage(tmp, 0, 0);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  return kosong(ctx) ? null : c;
}

function keBlob(c, format) {
  const mime = format === "webp" ? "image/webp" : "image/png";
  return new Promise((r) => c.toBlob(r, mime, KUALITAS));
}

/**
 * Proses seluruh citra. `kirim(daftar)` menerima [{nama, blob}] per batch;
 * `onProgres({selesai, total})`. Batalkan lewat `sinyal.batal = true`.
 */
export async function potongCitra(sumber, { zmin, zmaks, format, kirim, onProgres, sinyal = {} }) {
  const { batas } = sumber;
  const total = (() => {
    let n = 0;
    for (let z = zmin; z <= zmaks; z += 1) {
      const r = rentangUbin(batas, z);
      n += (r.x1 - r.x0 + 1) * (r.y1 - r.y0 + 1);
    }
    return n;
  })();
  let selesai = 0; let terkirim = 0;
  let batch = []; let ukuranBatch = 0; let kirimanJalan = Promise.resolve();

  const setor = async (z, x, y, c) => {
    const blob = await keBlob(c, format);
    batch.push({ nama: `${z}-${x}-${y}.${format}`, blob });
    ukuranBatch += blob.size;
    if (batch.length >= 60 || ukuranBatch > 6 * 1024 * 1024) {
      const isi = batch; batch = []; ukuranBatch = 0;
      await kirimanJalan;                 // satu kiriman berjalan sambil memotong berikutnya
      kirimanJalan = kirim(isi).then(() => { terkirim += isi.length; });
    }
  };

  const proses = async (z, x, y) => {
    if (sinyal.batal) throw new Error("Dibatalkan");
    if (!ubinMenyentuh(batas, z, x, y)) return null;
    let c;
    if (z === zmaks) {
      c = await ubinDariSumber(sumber, z, x, y);
    } else {
      const anak = [];
      for (const [dx, dy] of [[0, 0], [1, 0], [0, 1], [1, 1]]) {
        anak.push([dx, dy, await proses(z + 1, x * 2 + dx, y * 2 + dy)]);
      }
      if (anak.every(([, , k]) => !k)) { c = null; } else {
        c = kanvas();
        const ctx = c.getContext("2d");
        ctx.imageSmoothingQuality = "high";
        for (const [dx, dy, k] of anak) if (k) ctx.drawImage(k, dx * 128, dy * 128, 128, 128);
      }
    }
    selesai += 1;
    if (selesai % 8 === 0) onProgres?.({ selesai, total });
    if (c) await setor(z, x, y, c);
    return c;
  };

  const r = rentangUbin(batas, zmin);
  for (let x = r.x0; x <= r.x1; x += 1) {
    for (let y = r.y0; y <= r.y1; y += 1) await proses(zmin, x, y);
  }
  await kirimanJalan;
  if (batch.length) await kirim(batch).then(() => { terkirim += batch.length; });
  onProgres?.({ selesai: total, total });
  return { terkirim };
}
