/**
 * Usulan GESER marker asli — logika murni untuk peta kolaborasi & peta asli.
 *
 * Mandat pemilik: tamu boleh menggeser marker asli; garis putus-putus
 * menghubungkan posisi asal dengan posisi usulannya; marker usulannya
 * TRANSPARAN; "akan berubah ketika disetujui".
 *
 * KEPUTUSAN YANG DIWUJUDKAN DI SINI: menggeser tidak mengubah data. Server
 * menyimpannya sebagai usulan, dan layar HARUS memperlihatkan itu — marker
 * asli kembali ke tempatnya, yang transparan menandai usulannya. Kalau marker
 * asli dibiarkan di tempat baru, layar berbohong: pemakainya mengira posisinya
 * sudah pindah padahal belum ada yang menyetujui.
 */

/** Mode geser saat gembok terbuka. Tombolnya IKON-SAJA (mandat pemilik). */
export const MODE_GESER = {
  ASLI: "asli",         // usul KOREKSI posisi aset yang sudah ada
  USULAN: "usulan",     // usul TITIK BARU
};

/** Keterangan tiap mode — dipakai title/aria-label tombol ikon. */
export const KETERANGAN_MODE = {
  [MODE_GESER.ASLI]:
    "Geser titik ASLI — mengusulkan koreksi posisi aset yang sudah ada. "
    + "Posisinya baru benar-benar berubah setelah pengelola menyetujui.",
  [MODE_GESER.USULAN]:
    "Titik USULAN — menambahkan titik baru di peta, bukan memindahkan aset "
    + "yang sudah ada.",
};

/** Gaya garis putus-putus penghubung posisi asal → posisi usulan. */
export const GAYA_GARIS_USULAN = {
  color: "#0d9488",
  weight: 2,
  opacity: 0.85,
  dashArray: "6 6",
};

/**
 * true bila pasangan koordinat ini layak digambar.
 *
 * `null`/`undefined`/`""` DITOLAK EKSPLISIT sebelum dikonversi: `Number(null)`
 * dan `Number("")` sama-sama menghasilkan 0, yang finite dan masuk rentang —
 * jadi koordinat KOSONG akan lolos sebagai titik nol dan garis usulan
 * terbentang ke tengah Samudra Atlantik. Sebaliknya, 0 yang MEMANG diisi
 * tetap sah (khatulistiwa/meridian utama), jadi penyaringnya tak boleh
 * sekadar `if (!lat)`.
 */
export function koordinatSah(lat, lng) {
  const kosong = (v) => v === null || v === undefined || v === "";
  if (kosong(lat) || kosong(lng)) return false;
  const a = Number(lat);
  const b = Number(lng);
  return Number.isFinite(a) && Number.isFinite(b)
    && a >= -90 && a <= 90 && b >= -180 && b <= 180;
}

/**
 * Bahan gambar satu usulan geser: garis + posisi marker bayangan.
 * @returns {{garis: [number,number][], bayangan: [number,number]}|null}
 *   null bila salah satu ujungnya tak diketahui — lebih baik tak menggambar
 *   apa pun daripada menarik garis ke titik nol di tengah Samudra Atlantik.
 */
export function bahanGarisUsulan(u) {
  if (!u) return null;
  const { lat, lng, lat_asal: la, lng_asal: lo } = u;
  if (!koordinatSah(lat, lng)) return null;
  const bayangan = [Number(lat), Number(lng)];
  if (!koordinatSah(la, lo)) return { garis: null, bayangan };
  return { garis: [[Number(la), Number(lo)], bayangan], bayangan };
}

/** Ringkasan satu usulan geser untuk popup marker bayangan. */
export function ringkasGeser(u) {
  const nama = String(u?.nama_titik || "Aset").trim();
  const oleh = String(u?.oleh || "Tamu").trim();
  const kode = String(u?.kode || "").trim();
  const nup = String(u?.nup || "").trim();
  const id = kode ? `${kode}${nup ? ` · NUP ${nup}` : ""}` : "";
  return { nama, oleh, identitas: id };
}

/**
 * Jarak perpindahan dalam METER (haversine) — dipakai layar untuk menyebut
 * seberapa jauh usulannya. Angka konkret jauh lebih berguna bagi peninjau
 * daripada sekadar "posisi diusulkan berubah".
 */
export function jarakMeter(lat1, lng1, lat2, lng2) {
  if (!koordinatSah(lat1, lng1) || !koordinatSah(lat2, lng2)) return null;
  const R = 6371000;
  const rad = (d) => (Number(d) * Math.PI) / 180;
  const dLat = rad(lat2) - rad(lat1);
  const dLng = rad(lng2) - rad(lng1);
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLng / 2) ** 2;
  return Math.round(2 * R * Math.asin(Math.min(1, Math.sqrt(a))));
}

/** "12 m" / "1,4 km" / "" bila tak terhitung. */
export function teksJarak(meter) {
  if (meter === null || meter === undefined || !Number.isFinite(Number(meter))) return "";
  const m = Number(meter);
  if (m < 1000) return `${m} m`;
  return `${(m / 1000).toFixed(1).replace(".", ",")} km`;
}
