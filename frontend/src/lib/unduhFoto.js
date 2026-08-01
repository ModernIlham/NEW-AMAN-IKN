/**
 * Unduh foto ASLI — bagian yang murni (tanpa DOM, tanpa axios) supaya bisa diuji.
 *
 * KENAPA ADA. Laporan lapangan: tombol unduh di popup foto "sering gagal", dan
 * satu-satunya cara yang berhasil adalah membuka layar penuh dulu baru mengunduh.
 * Akarnya bukan di endpoint, melainkan di `axios.defaults.timeout` = 20 detik
 * (lantai tenggat global, lihat App.js). Foto ASLI dari kamera HP berukuran
 * beberapa megabyte; di jaringan lapangan transfernya lewat dari 20 detik, dan
 * axios memutusnya di tengah jalan.
 *
 * Membuka layar penuh "memperbaikinya" karena <img> mengambil URL yang SAMA dan
 * pengambilan gambar oleh peramban TIDAK terikat tenggat axios. Setelah itu
 * berkasnya ada di cache HTTP, sehingga permintaan axios berikutnya selesai
 * seketika — itulah kenapa unduh baru berhasil "setelah fullscreen".
 *
 * Maka tenggat tetap untuk unduhan besar adalah alat yang salah. Yang benar:
 * pantau KEMAJUAN. Koneksi menggantung tetap harus diputus (itu bahaya asli
 * yang dijaga tenggat global), tapi transfer yang lambat-namun-jalan jangan
 * dihukum. `pemantauMacet` di bawah menerapkan itu.
 */

/** Diam berapa lama (tanpa satu byte pun tiba) sebelum unduhan dianggap macet. */
export const AMBANG_MACET_MS = 30000;

/**
 * Ekstensi berkas dari tipe MIME respons.
 *
 * Server menyimpan foto apa adanya (JPEG dari kamera) atau hasil konversi WebP,
 * jadi ekstensi HARUS ikut isi berkas — bukan ditebak dari nama aset. Salah
 * ekstensi membuat berkas tak bisa dibuka di sebagian galeri Android.
 */
export function ekstensiDariMime(mime) {
  const m = String(mime || "").toLowerCase();
  if (m.includes("png")) return "png";
  if (m.includes("webp")) return "webp";
  if (m.includes("avif")) return "avif";
  if (m.includes("heic") || m.includes("heif")) return "heic";
  if (m.includes("gif")) return "gif";
  return "jpg";
}

/**
 * Bersihkan potongan nama berkas.
 *
 * Kode barang BMN memakai titik (`3.05.02.001`) — itu aman dan sengaja
 * DIPERTAHANKAN. Yang dibuang adalah karakter yang ditolak sistem berkas
 * (`/ \ : * ? " < > |`) dan karakter kendali; tanpa ini nama aset yang memuat
 * garis miring menghasilkan unduhan bernama aneh atau gagal tersimpan.
 */
export function bersihkanNamaBerkas(teks) {
  return String(teks == null ? "" : teks)
    .replace(/[/\\:*?"<>|]/g, "-")            // ditolak sistem berkas
    .replace(/[\u0000-\u001f\u007f]/g, "")     // karakter kendali
    .replace(/\s+/g, " ")
    .replace(/^[.\s]+|[.\s]+$/g, "")           // titik/spasi di ujung tak valid di Windows
    .slice(0, 80)
    .trim();
}

/**
 * Nama berkas unduhan: `<kode|NUP|id>_foto-<n>.<ext>`.
 *
 * Urutan sumber sengaja: kode barang paling bermakna bagi petugas BMN, lalu
 * NUP, baru id internal sebagai jaring terakhir. `nup` dan `NUP` sama-sama
 * diperiksa karena kedua ejaan itu beredar di respons daftar & detail.
 */
export function namaBerkasFoto(aset, idx, mime) {
  const a = aset || {};
  const dasar = bersihkanNamaBerkas(a.asset_code) || bersihkanNamaBerkas(a.nup)
    || bersihkanNamaBerkas(a.NUP) || bersihkanNamaBerkas(a.id) || "foto";
  const nomor = Number.isFinite(Number(idx)) ? Number(idx) + 1 : 1;
  return `${dasar}_foto-${nomor}.${ekstensiDariMime(mime)}`;
}

/**
 * Pantau kemajuan unduhan; panggil `padaMacet` bila TIDAK ada byte baru selama
 * `ambangMs`. Mengembalikan `{ maju, hentikan }`.
 *
 * `maju(diterima)` dipanggil dari `onDownloadProgress`. Pemicu hanya berjalan
 * saat benar-benar diam — unduhan 5 menit yang terus mengalir tidak pernah
 * dihentikan, sedangkan soket yang menggantung diputus setelah `ambangMs`.
 *
 * `jadwal`/`batal` disuntikkan agar uji tak perlu menunggu detik sungguhan.
 */
export function pemantauMacet(padaMacet, opsi = {}) {
  const ambangMs = opsi.ambangMs || AMBANG_MACET_MS;
  const jadwal = opsi.jadwal || ((fn, ms) => setTimeout(fn, ms));
  const batal = opsi.batal || ((h) => clearTimeout(h));
  let handle = null;
  let mati = false;

  const pasang = () => {
    if (mati) return;
    handle = jadwal(() => { if (!mati) { mati = true; padaMacet(); } }, ambangMs);
  };
  pasang();

  return {
    /** Ada byte tiba → setel ulang jam pasir. */
    maju() {
      if (mati) return;
      if (handle !== null) batal(handle);
      pasang();
    },
    /** Unduhan selesai/gagal → berhenti memantau. */
    hentikan() {
      mati = true;
      if (handle !== null) { batal(handle); handle = null; }
    },
  };
}

/**
 * Kalimat kegagalan yang menyebut SEBAB, bukan "terjadi kesalahan".
 *
 * `macet` dibedakan dari pembatalan biasa: keduanya sama-sama AbortError di
 * mata axios, tapi artinya berbeda bagi operator — yang satu jaringan mandek,
 * yang lain dia sendiri yang menutup.
 */
export function pesanGagalUnduh(err, macet = false) {
  if (macet) {
    return "Unduhan terhenti — data berhenti mengalir. Periksa sinyal lalu coba lagi; "
      + "atau buka Layar Penuh dulu, lalu unduh.";
  }
  const status = err && err.response && err.response.status;
  if (status === 401 || status === 403) {
    return "Tidak berhak mengunduh foto ini — sesi Anda mungkin sudah berakhir. Muat ulang halaman.";
  }
  if (status === 404) return "Foto ini tidak ditemukan di server (mungkin sudah dihapus atau diputar ulang).";
  if (status === 429) return "Terlalu banyak permintaan sekaligus. Tunggu ±1 menit lalu coba lagi.";
  if (status >= 500) return "Server sedang bermasalah saat menyiapkan foto. Coba lagi beberapa saat lagi.";
  if (!status) return "Gagal mengunduh foto asli — perangkat tidak dapat menghubungi server. Periksa sinyal.";
  return "Gagal mengunduh foto asli.";
}

/** Persentase kemajuan (0–100) atau null bila server tak mengirim panjang isi. */
export function persenUnduh(diterima, total) {
  const t = Number(total);
  const d = Number(diterima);
  if (!Number.isFinite(t) || t <= 0 || !Number.isFinite(d) || d < 0) return null;
  return Math.max(0, Math.min(100, Math.round((d / t) * 100)));
}
