// Matematika proyeksi untuk unggah citra — MURNI (tanpa DOM/Leaflet), teruji.
//
// Citra drone umumnya diekspor dalam UTM (mis. EPSG:32750 = UTM 50S untuk
// kawasan IKN), sedangkan peta web memakai ubin Web Mercator berkoordinat
// WGS84. Modul ini menerjemahkan keduanya tanpa pustaka proyeksi tambahan:
// rumus UTM Snyder (USGS PP 1395) cukup presisi (sub-milimeter dalam zona).

const A = 6378137;                       // sumbu panjang WGS84
const F = 1 / 298.257223563;
const E2 = F * (2 - F);
const EP2 = E2 / (1 - E2);
const K0 = 0.9996;
const RAD = Math.PI / 180;
export const UBIN_PX = 256;
export const ZOOM_MAKS_CITRA = 21;
export const UBIN_MAKS = 60000;          // sama dengan batas server

// ── Sistem koordinat ────────────────────────────────────────────────────────

/**
 * Kenali CRS dari geo key GeoTIFF. Kembalikan {jenis:"geo"|"merc"|"utm", zona,
 * selatan, label} atau {galat}. Hanya yang pasti benar yang diterima — CRS
 * yang ditebak salah menaruh citra di tempat keliru tanpa terlihat aneh.
 */
export function crsDariGeoKeys(k) {
  const gk = k || {};
  const proj = Number(gk.ProjectedCSTypeGeoKey);
  const geo = Number(gk.GeographicTypeGeoKey);
  const model = Number(gk.GTModelTypeGeoKey);
  if (proj >= 32601 && proj <= 32660) return { jenis: "utm", zona: proj - 32600, selatan: false, label: `EPSG:${proj}` };
  if (proj >= 32701 && proj <= 32760) return { jenis: "utm", zona: proj - 32700, selatan: true, label: `EPSG:${proj}` };
  if (proj === 3857 || proj === 900913 || proj === 3785) return { jenis: "merc", label: "EPSG:3857" };
  if (!proj && (model === 2 || geo) && (!geo || geo === 4326)) return { jenis: "geo", label: "EPSG:4326" };
  const kode = proj || geo;
  return { galat: kode
    ? `Sistem koordinat EPSG:${kode} belum didukung. Ekspor ulang citra ke WGS84 (EPSG:4326) atau UTM WGS84 (mis. EPSG:32750).`
    : "Berkas ini tidak memuat informasi lokasi (bukan GeoTIFF)." };
}

// ── UTM ─────────────────────────────────────────────────────────────────────

function busurMeridian(phi) {
  const e4 = E2 * E2; const e6 = e4 * E2;
  return A * ((1 - E2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi
    - (3 * E2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * Math.sin(2 * phi)
    + (15 * e4 / 256 + 45 * e6 / 1024) * Math.sin(4 * phi)
    - (35 * e6 / 3072) * Math.sin(6 * phi));
}

export function lonLatKeUtm(lon, lat, zona, selatan) {
  const phi = lat * RAD;
  const lam = (lon - ((zona - 1) * 6 - 180 + 3)) * RAD;
  const s = Math.sin(phi); const c = Math.cos(phi); const t = Math.tan(phi);
  const N = A / Math.sqrt(1 - E2 * s * s);
  const T = t * t; const C = EP2 * c * c; const Ak = c * lam;
  const M = busurMeridian(phi);
  const x = K0 * N * (Ak + (1 - T + C) * Ak ** 3 / 6
    + (5 - 18 * T + T * T + 72 * C - 58 * EP2) * Ak ** 5 / 120) + 500000;
  let y = K0 * (M + N * t * (Ak * Ak / 2 + (5 - T + 9 * C + 4 * C * C) * Ak ** 4 / 24
    + (61 - 58 * T + T * T + 600 * C - 330 * EP2) * Ak ** 6 / 720));
  if (selatan) y += 10000000;
  return [x, y];
}

export function utmKeLonLat(x, y, zona, selatan) {
  const e4 = E2 * E2; const e6 = e4 * E2;
  const xx = x - 500000; const yy = selatan ? y - 10000000 : y;
  const mu = (yy / K0) / (A * (1 - E2 / 4 - 3 * e4 / 64 - 5 * e6 / 256));
  const e1 = (1 - Math.sqrt(1 - E2)) / (1 + Math.sqrt(1 - E2));
  const phi1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * Math.sin(2 * mu)
    + (21 * e1 * e1 / 16 - 55 * e1 ** 4 / 32) * Math.sin(4 * mu)
    + (151 * e1 ** 3 / 96) * Math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * Math.sin(8 * mu);
  const s = Math.sin(phi1); const c = Math.cos(phi1); const t = Math.tan(phi1);
  const N1 = A / Math.sqrt(1 - E2 * s * s);
  const T1 = t * t; const C1 = EP2 * c * c;
  const R1 = A * (1 - E2) / (1 - E2 * s * s) ** 1.5;
  const D = xx / (N1 * K0);
  const phi = phi1 - (N1 * t / R1) * (D * D / 2
    - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * EP2) * D ** 4 / 24
    + (61 + 90 * T1 + 298 * C1 + 45 * T1 * T1 - 252 * EP2 - 3 * C1 * C1) * D ** 6 / 720);
  const lam = (D - (1 + 2 * T1 + C1) * D ** 3 / 6
    + (5 - 2 * C1 + 28 * T1 - 3 * C1 * C1 + 8 * EP2 + 24 * T1 * T1) * D ** 5 / 120) / c;
  return [((zona - 1) * 6 - 180 + 3) + lam / RAD, phi / RAD];
}

// ── Web Mercator ────────────────────────────────────────────────────────────

export function lonLatKeMerc(lon, lat) {
  const la = Math.max(-85.0511, Math.min(85.0511, lat));
  return [A * lon * RAD, A * Math.log(Math.tan(Math.PI / 4 + la * RAD / 2))];
}
export function mercKeLonLat(x, y) {
  return [x / A / RAD, (2 * Math.atan(Math.exp(y / A)) - Math.PI / 2) / RAD];
}

/** lon/lat → koordinat sistem sumber. */
export function keSumber(lon, lat, crs) {
  if (crs.jenis === "utm") return lonLatKeUtm(lon, lat, crs.zona, crs.selatan);
  if (crs.jenis === "merc") return lonLatKeMerc(lon, lat);
  return [lon, lat];
}
/** Koordinat sistem sumber → lon/lat. */
export function dariSumber(x, y, crs) {
  if (crs.jenis === "utm") return utmKeLonLat(x, y, crs.zona, crs.selatan);
  if (crs.jenis === "merc") return mercKeLonLat(x, y);
  return [x, y];
}

// ── Ubin XYZ ────────────────────────────────────────────────────────────────

export function lonKeUbinX(lon, z) {
  const n = 2 ** z;
  return Math.min(n - 1, Math.max(0, Math.floor((lon + 180) / 360 * n)));
}
export function latKeUbinY(lat, z) {
  const n = 2 ** z;
  const r = Math.max(-85.0511, Math.min(85.0511, lat)) * RAD;
  return Math.min(n - 1, Math.max(0, Math.floor((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n)));
}
export function ubinXKeLon(x, z) { return x / 2 ** z * 360 - 180; }
export function ubinYKeLat(y, z) {
  const n = Math.PI - 2 * Math.PI * y / 2 ** z;
  return Math.atan(Math.sinh(n)) / RAD;
}

/** Rentang ubin {x0,x1,y0,y1} yang menyentuh batas pada zoom z. */
export function rentangUbin(b, z) {
  return { x0: lonKeUbinX(b.barat, z), x1: lonKeUbinX(b.timur, z),
    y0: latKeUbinY(b.utara, z), y1: latKeUbinY(b.selatan, z) };
}
export function jumlahUbin(b, zmin, zmaks) {
  let n = 0;
  for (let z = zmin; z <= zmaks; z += 1) {
    const r = rentangUbin(b, z);
    n += (r.x1 - r.x0 + 1) * (r.y1 - r.y0 + 1);
  }
  return n;
}
export function ubinMenyentuh(b, z, x, y) {
  const r = rentangUbin(b, z);
  return x >= r.x0 && x <= r.x1 && y >= r.y0 && y <= r.y1;
}

// ── Batas & zoom citra ──────────────────────────────────────────────────────

/**
 * Batas WGS84 dari kotak sumber [xmin, ymin, xmax, ymax]. Tepi kotak UTM
 * melengkung di lon/lat, jadi tepinya disampel, bukan hanya sudutnya.
 */
export function batasWgs84(kotak, crs) {
  const [x0, y0, x1, y1] = kotak;
  let barat = Infinity; let timur = -Infinity; let selatan = Infinity; let utara = -Infinity;
  const N = 16;
  for (let i = 0; i <= N; i += 1) {
    const u = x0 + (x1 - x0) * i / N; const v = y0 + (y1 - y0) * i / N;
    for (const [x, y] of [[u, y0], [u, y1], [x0, v], [x1, v]]) {
      const [lon, lat] = dariSumber(x, y, crs);
      barat = Math.min(barat, lon); timur = Math.max(timur, lon);
      selatan = Math.min(selatan, lat); utara = Math.max(utara, lat);
    }
  }
  return { barat, selatan, timur, utara };
}

/** Ukuran piksel di lapangan (meter). */
export function resolusiMeter(resX, crs, latTengah) {
  const r = Math.abs(resX);
  if (crs.jenis === "geo") return r * 111320 * Math.cos(latTengah * RAD);
  if (crs.jenis === "merc") return r * Math.cos(latTengah * RAD);
  return r;
}

/**
 * Rentang zoom: maksimum = level yang tak lebih kasar dari citra aslinya
 * (dibatasi 21), minimum = level saat seluruh citra muat ±satu ubin. Bila
 * jumlah ubin melebihi batas, zoom maksimum diturunkan (resolusi dikorbankan,
 * bukan wilayahnya).
 */
export function rencanaZoom(batas, meterPerPiksel, batasUbin = UBIN_MAKS) {
  const lat = (batas.utara + batas.selatan) / 2;
  const mpp0 = 156543.03392 * Math.cos(lat * RAD);
  let zmaks = Math.min(ZOOM_MAKS_CITRA, Math.max(0, Math.ceil(Math.log2(mpp0 / Math.max(meterPerPiksel, 0.01)))));
  const span = Math.max(batas.timur - batas.barat, 1e-9);
  const zmin = Math.max(0, Math.min(zmaks, Math.floor(Math.log2(360 / span))));
  while (zmaks > zmin && jumlahUbin(batas, zmin, zmaks) > batasUbin) zmaks -= 1;
  return { zmin, zmaks, jumlah: jumlahUbin(batas, zmin, zmaks) };
}

/**
 * Transform kanvas: gambar sementara (hasil baca jendela sumber berukuran
 * lebarBaca×tinggiBaca yang mewakili piksel sumber [c0,c1]×[r0,r1]) → piksel
 * ubin 256×256. `sudut` = posisi piksel sumber dari sudut kiri-atas, kanan-atas,
 * dan kiri-bawah ubin. Di satu ubin zoom tinggi, pemetaan UTM→Mercator praktis
 * afin, jadi tiga sudut cukup. Kembalikan [a, b, c, d, e, f] untuk setTransform.
 */
export function transformUbin(sudut, jendela, lebarBaca, tinggiBaca) {
  const [[cTL, rTL], [cTR, rTR], [cBL, rBL]] = sudut;
  // M: piksel ubin (u,v) → piksel sumber (c,r)
  const m11 = (cTR - cTL) / UBIN_PX; const m12 = (cBL - cTL) / UBIN_PX;
  const m21 = (rTR - rTL) / UBIN_PX; const m22 = (rBL - rTL) / UBIN_PX;
  const det = m11 * m22 - m12 * m21;
  const i11 = m22 / det; const i12 = -m12 / det; const i21 = -m21 / det; const i22 = m11 / det;
  const { c0, r0, c1, r1 } = jendela;
  const sx = (c1 - c0) / lebarBaca; const sy = (r1 - r0) / tinggiBaca;
  const ox = c0 - cTL; const oy = r0 - rTL;
  return [i11 * sx, i21 * sx, i12 * sy, i22 * sy, i11 * ox + i12 * oy, i21 * ox + i22 * oy];
}

/** "2026:10:15 09:12:00" (tag DateTime TIFF) → "2026-10-15"; selain itu "". */
export function tanggalDariTiff(s) {
  const m = /^(\d{4}):(\d{2}):(\d{2})/.exec(String(s || ""));
  return m ? `${m[1]}-${m[2]}-${m[3]}` : "";
}
