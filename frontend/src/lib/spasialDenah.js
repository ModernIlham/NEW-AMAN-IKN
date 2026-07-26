// Denah spasial berlapis di peta — logika MURNI (tanpa Leaflet, tanpa DOM)
// agar bisa diuji unit. Sisi Leaflet-nya ada di hooks/useDenahSpasial.js.
//
// Ordinal level mengikuti registry backend (spasial_utils.LEVEL_SPASIAL):
// 10 Wilayah · 20 Kawasan · 30 Zona(WP) · 40 Distrik(SWP) · 50 Blok ·
// 55 Sub-Blok · 60 Persil · 70 Tapak · 80 Gedung · 90 Lantai · 95 Sayap ·
// 100 Ruangan · 110 Titik. Makin besar ordinal = makin kecil & detail.

export const ORDINAL_GEDUNG = 80;
export const ORDINAL_RUANGAN = 100;

// Warna per tingkat. Tingkat perencanaan (≤55) bernuansa dingin, tingkat fisik
// (≥60) bernuansa hangat — sehingga sekali lihat terbaca mana batas administratif
// dan mana bangunan nyata.
const WARNA_LEVEL = {
  10: "#64748b",  // Wilayah
  20: "#0f766e",  // Kawasan
  30: "#0891b2",  // Zona (WP)
  40: "#2563eb",  // Distrik (SWP)
  50: "#7c3aed",  // Blok
  55: "#a855f7",  // Sub-Blok
  60: "#db2777",  // Persil
  70: "#ea580c",  // Tapak
  80: "#dc2626",  // Gedung
  90: "#d97706",  // Lantai
  95: "#ca8a04",  // Sayap
  100: "#16a34a", // Ruangan
  110: "#0d9488", // Titik
};
const WARNA_CADANGAN = "#475569";

export function warnaLevel(ordinal) {
  return WARNA_LEVEL[Number(ordinal)] || WARNA_CADANGAN;
}

// Batas administratif digambar PUTUS-PUTUS, batas fisik UTUH. Perbedaan ini
// penting di lapangan: garis blok RDTR itu kesepakatan tata ruang, sedangkan
// dinding gedung bisa diukur.
const ORDINAL_FISIK_MIN = 60;

export function gayaFitur(ordinal, { terpilih = false, redup = false } = {}) {
  const o = Number(ordinal) || 0;
  const warna = warnaLevel(o);
  const fisik = o >= ORDINAL_FISIK_MIN;
  // Poligon besar nyaris transparan supaya tak menutupi ubin peta & pin aset;
  // makin detail makin pekat karena luasnya makin kecil.
  const isi = redup ? 0.03 : Math.min(0.2, 0.04 + (o / 100) * 0.12);
  return {
    color: warna,
    weight: terpilih ? 4 : fisik ? 2 : 1.4,
    opacity: redup ? 0.45 : 1,
    fillColor: warna,
    fillOpacity: terpilih ? Math.min(0.34, isi + 0.16) : isi,
    dashArray: fisik ? null : "5,4",
    // WAJIB true (bawaan Leaflet). Denah adalah LATAR: event mouse harus tetap
    // menembus ke peta. Dengan false, klik-kanan/tekan-lama yang mendarat di
    // atas poligon TIDAK pernah sampai ke handler `contextmenu` peta, sehingga
    // "Tambah aset di sini" mati justru di dalam gedung — tempat yang paling
    // sering dipakai. Tooltip nama & klik pilih-gedung tetap jalan.
    bubblingMouseEvents: true,
  };
}

// ── LOD (level of detail) ───────────────────────────────────────────────────
// Merender ruangan saat seluruh kawasan terlihat itu sia-sia: ribuan poligon
// berukuran sub-piksel. Tangga ini memetakan zoom → ordinal terdalam yang
// masih layak diminta dari server.
export const TANGGA_LOD = [
  { zoom_min: 17, level_maks: 80 },  // gedung terlihat jelas
  { zoom_min: 15, level_maks: 70 },  // tapak/kompleks
  { zoom_min: 13, level_maks: 60 },  // persil
  { zoom_min: 11, level_maks: 50 },  // blok
  { zoom_min: 0, level_maks: 30 },   // kawasan & zona saja
];

// Ruangan (100) & lantai (90) TIDAK pernah ikut LOD viewport — semua lantai
// berbagi jejak 2D yang sama sehingga akan bertumpuk. Mereka dimuat terpisah
// lewat parameter `induk` setelah pengguna memilih satu lantai.
export function levelMaksUntukZoom(zoom) {
  const z = Number(zoom);
  if (!Number.isFinite(z)) return 30;
  for (const t of TANGGA_LOD) {
    if (z >= t.zoom_min) return t.level_maks;
  }
  return 30;
}

// ── bbox viewport ───────────────────────────────────────────────────────────
// Dipadding agar geser sedikit tidak langsung menembak request baru.
export const PADDING_BBOX = 0.35;
const LAT_MAKS = 85;   // batas web-mercator

function jepit(nilai, min, maks) {
  return Math.min(maks, Math.max(min, nilai));
}

/** {barat,selatan,timur,utara} → bbox padded, atau null bila tak masuk akal. */
export function bboxDariBatas(batas, padding = PADDING_BBOX) {
  if (!batas) return null;
  const { barat, selatan, timur, utara } = batas;
  if (![barat, selatan, timur, utara].every((v) => Number.isFinite(v))) return null;
  const lebar = timur - barat;
  const tinggi = utara - selatan;
  if (lebar <= 0 || tinggi <= 0) return null;
  const px = lebar * padding;
  const py = tinggi * padding;
  const hasil = {
    barat: jepit(barat - px, -180, 180),
    selatan: jepit(selatan - py, -LAT_MAKS, LAT_MAKS),
    timur: jepit(timur + px, -180, 180),
    utara: jepit(utara + py, -LAT_MAKS, LAT_MAKS),
  };
  // Cek degenerasi WAJIB diulang SETELAH penjepitan. Leaflet `getBounds()`
  // mengembalikan bujur yang TAK dibungkus setelah peta digeser melewati
  // antimeridian — mis. {barat:190, timur:195}. Rentang mentahnya masuk akal
  // (lebar 5°), tetapi kedua tepi menjepit ke 180 sehingga kotaknya jadi pipih.
  // Kotak pipih ditolak server dengan HTTP 400, dan karena kegagalan membuat
  // cache viewport dikosongkan, SETIAP geser peta menembak request gagal lagi.
  // Kembalikan null → penelepon melewatkan permintaan sama sekali.
  if (hasil.timur <= hasil.barat || hasil.utara <= hasil.selatan) return null;
  return hasil;
}

/** bbox → string parameter server "lon_min,lat_min,lon_maks,lat_maks". */
export function bboxKeParam(bbox) {
  if (!bbox) return "";
  return [bbox.barat, bbox.selatan, bbox.timur, bbox.utara]
    .map((v) => Number(v).toFixed(6)).join(",");
}

/** Apakah `dalam` sepenuhnya berada di dalam `luar`? */
export function bboxTermuat(luar, dalam) {
  if (!luar || !dalam) return false;
  return luar.barat <= dalam.barat && luar.selatan <= dalam.selatan
    && luar.timur >= dalam.timur && luar.utara >= dalam.utara;
}

/**
 * Perlu ambil data baru?
 *
 * Tidak, bila viewport sekarang masih di dalam bbox yang sudah dimuat DAN
 * tingkat detailnya sama. Ini yang membuat geser/zoom kecil terasa instan.
 * Hasil yang TERPOTONG selalu dimuat ulang karena isinya belum lengkap.
 */
export function perluMuatUlang(termuat, viewport, levelMaks) {
  if (!termuat || !termuat.bbox) return true;
  if (termuat.terpotong) return true;
  if (termuat.level_maks !== levelMaks) return true;
  return !bboxTermuat(termuat.bbox, viewport);
}

// ── Fitur ───────────────────────────────────────────────────────────────────
/**
 * Urut fitur agar poligon BESAR digambar lebih dulu (di bawah) dan yang detail
 * di atasnya. Tanpa ini poligon kawasan bisa menutupi ruangan sepenuhnya.
 * Urutan stabil: ordinal menaik, lalu nama.
 */
export function urutFitur(fitur) {
  return [...(fitur || [])].sort((a, b) => {
    const oa = Number(a?.properties?.ordinal_level) || 0;
    const ob = Number(b?.properties?.ordinal_level) || 0;
    if (oa !== ob) return oa - ob;
    return String(a?.properties?.nama || "").localeCompare(String(b?.properties?.nama || ""), "id");
  });
}

/** Kelompokkan fitur per ordinal level → { [ordinal]: Feature[] } untuk toggle per lapis. */
export function kelompokPerLevel(fitur) {
  const peta = new Map();
  for (const f of fitur || []) {
    const o = Number(f?.properties?.ordinal_level) || 0;
    if (!peta.has(o)) peta.set(o, []);
    peta.get(o).push(f);
  }
  return peta;
}

/** Label lapis untuk legenda/toggle (dari registry level backend bila ada). */
export function labelLevel(ordinal, daftarLevel) {
  const o = Number(ordinal);
  const cocok = (daftarLevel || []).find((l) => Number(l.ordinal_level) === o);
  return cocok?.label_ui || cocok?.label_baku || `Tingkat ${o}`;
}

/**
 * Urutan lantai untuk switcher: basement paling BAWAH, rooftop paling ATAS —
 * jadi daftar ditampilkan MENURUN (ordinal besar dulu) seperti panel lift.
 * Lantai tanpa ordinal ditaruh paling akhir agar tak mengacaukan urutan.
 */
/**
 * Ordinal lantai, atau null bila memang belum diisi.
 *
 * `Number(null)` = 0 — dan 0 itu ordinal yang SAH (lantai akses utama). Tanpa
 * pemeriksaan null/"" eksplisit, lantai yang ordinalnya belum diisi menyamar
 * sebagai lantai dasar: ia menyusup ke tengah urutan lift dan tampil bernomor
 * "0". Server memang menyimpan `ordinal: null` bila operator mengosongkannya.
 * Satu sumber kebenaran untuk pengurutan MAUPUN penampilan.
 */
export function ordinalLantai(l) {
  const o = l?.lantai?.ordinal;
  if (o === null || o === undefined || o === "") return null;
  const n = Number(o);
  return Number.isFinite(n) ? n : null;
}

export function urutLantaiTampilan(lantai) {
  const punya = (l) => ordinalLantai(l) !== null;
  const berordinal = (lantai || []).filter(punya)
    .sort((a, b) => ordinalLantai(b) - ordinalLantai(a));
  const tanpa = (lantai || []).filter((l) => !punya(l))
    .sort((a, b) => String(a?.nama || "").localeCompare(String(b?.nama || ""), "id"));
  return [...berordinal, ...tanpa];
}
