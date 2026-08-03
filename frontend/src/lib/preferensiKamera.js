/**
 * PREFERENSI KAMERA LAPANGAN — orientasi stempel, resolusi, & kualitas foto.
 *
 * Setelan MELEKAT PADA AKUN, bukan pada perangkat: petugas yang berganti HP
 * (atau memakai HP pinjaman) tetap memotret dengan setelan yang sama, dan
 * hasil foto satu satker tetap seragam di laporan & stiker. Server menyimpan
 * nilainya di dokumen user; salinan lokal hanya cadangan agar kamera tetap
 * memakai setelan yang benar SAAT LURING — fitur ini dipakai di lapangan yang
 * sinyalnya sering hilang.
 *
 * Modul ini sengaja MURNI (tanpa React/axios) supaya aturannya dapat diuji apa
 * adanya: normalisasi nilai + perhitungan bidang gambar.
 */

export const ORIENTASI = ["auto", "potret", "lanskap"];

/** Pilihan resolusi = SISI TERPANJANG foto hasil (px). */
export const RESOLUSI_PILIHAN = [1280, 1920, 2560, 3840];

/** Batas aman: di bawah ini foto tak terbaca, di atasnya boros tanpa guna. */
export const RESOLUSI_MIN = 640;
export const RESOLUSI_MAX = 4096;
export const KUALITAS_MIN = 50;
export const KUALITAS_MAX = 100;

export const PREFERENSI_BAWAAN = Object.freeze({
  orientasi: "auto",
  resolusi: 1920,      // setara pipeline kompresi form sebelum fitur ini ada
  kualitas: 85,        // persen (JPEG q0.85)
});

const jepit = (n, min, max) => Math.min(max, Math.max(min, n));

/** Angka yang masuk akal, atau null. `boolean` DITOLAK meski `Number(true)`
 *  bernilai 1: tanpa penjagaan ini `{resolusi: true}` diam-diam jadi 640 px. */
function angka(v) {
  if (typeof v === "boolean" || v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/**
 * Bersihkan nilai apa pun menjadi preferensi yang sah.
 * Nilai tak dikenal JATUH KE BAWAAN, bukan ditolak: setelan kamera tak boleh
 * menggagalkan pemotretan hanya karena satu field rusak/usang.
 */
export function normalkanPreferensi(raw) {
  const p = raw && typeof raw === "object" ? raw : {};
  const orientasi = ORIENTASI.includes(p.orientasi) ? p.orientasi : PREFERENSI_BAWAAN.orientasi;
  const res = angka(p.resolusi);
  const kual = angka(p.kualitas);
  return {
    orientasi,
    resolusi: res == null ? PREFERENSI_BAWAAN.resolusi
      : Math.round(jepit(res, RESOLUSI_MIN, RESOLUSI_MAX)),
    kualitas: kual == null ? PREFERENSI_BAWAAN.kualitas
      : Math.round(jepit(kual, KUALITAS_MIN, KUALITAS_MAX)),
  };
}

/**
 * Resolusi yang BENAR-BENAR didukung kamera ini.
 * `maksSisi` diambil dari MediaStreamTrack.getCapabilities(); bila kamera tak
 * memberitahukannya, seluruh pilihan ditawarkan (biar pengguna yang menilai)
 * — lebih baik daripada menyembunyikan pilihan yang sebenarnya bisa.
 */
export function resolusiTersedia(maksSisi) {
  const maks = Number(maksSisi);
  if (!Number.isFinite(maks) || maks <= 0) return [...RESOLUSI_PILIHAN];
  const muat = RESOLUSI_PILIHAN.filter((r) => r <= maks);
  // Kamera yang maksimalnya di bawah pilihan terkecil tetap dapat satu pilihan
  // (kemampuan aslinya), supaya panel setelan tak pernah kosong.
  return muat.length ? muat : [Math.round(jepit(maks, RESOLUSI_MIN, RESOLUSI_MAX))];
}

// Rasio target orientasi paksa. 3:4 & 4:3 dipilih karena memangkas paling
// sedikit dari bingkai kamera yang lazim (4:3 atau 16:9) — memaksa 9:16 akan
// membuang lebih dari sepertiga lebar bingkai 16:9.
const RASIO = { potret: 3 / 4, lanskap: 4 / 3 };

/**
 * Bidang sumber yang dipotong + ukuran kanvas hasil.
 *
 * `auto` memakai bingkai apa adanya. `potret`/`lanskap` memotong dari TENGAH
 * bingkai ke rasio target — bukan memutar gambar, karena memutar akan membuat
 * pemandangannya rebah. Hasil akhir diperkecil sampai sisi terpanjangnya
 * `resolusi`; foto tak pernah diperBESAR dari bingkai aslinya (memperbesar
 * hanya menambah berkas tanpa menambah detail).
 */
export function hitungBidang(vw, vh, orientasi, resolusi) {
  const w = Math.max(1, Math.round(Number(vw) || 0));
  const h = Math.max(1, Math.round(Number(vh) || 0));
  const rasio = RASIO[orientasi];

  let sw = w, sh = h;
  if (rasio) {
    if (w / h > rasio) sw = Math.round(h * rasio);   // bingkai terlalu lebar
    else sh = Math.round(w / rasio);                  // bingkai terlalu tinggi
  }
  const sx = Math.round((w - sw) / 2);
  const sy = Math.round((h - sh) / 2);

  const maks = jepit(Number(resolusi) || PREFERENSI_BAWAAN.resolusi, RESOLUSI_MIN, RESOLUSI_MAX);
  const skala = Math.min(1, maks / Math.max(sw, sh));
  return {
    sx, sy, sw, sh,
    lebar: Math.max(1, Math.round(sw * skala)),
    tinggi: Math.max(1, Math.round(sh * skala)),
  };
}

/** Label ramah untuk panel setelan. */
export function labelOrientasi(o) {
  return { auto: "Auto", potret: "Potret", lanskap: "Lanskap" }[o] || "Auto";
}
