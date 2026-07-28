/**
 * Pemuatan data yang TAHAN jaringan lapangan — tenggat, coba-ulang, dan
 * pembedaan "kosong" dari "gagal".
 *
 * KENAPA ADA. Petugas BMN memakai aplikasi ini di lokasi bersinyal buruk, dan
 * di sana bentuk kegagalan yang paling sering BUKAN "koneksi ditolak" —
 * itu cepat dan tertangkap `catch`. Yang paling sering adalah koneksi
 * MENGGANTUNG: paket keluar, tak ada yang kembali, dan soketnya tak pernah
 * ditutup siapa pun.
 *
 * Tanpa tenggat, `await axios.get(...)` pada keadaan itu TIDAK PERNAH selesai.
 * Akibatnya berantai: `catch` tak pernah jalan, `finally` tak pernah
 * membereskan spinner, dan penjaga yang sudah dipasang pun ikut mandul —
 * pagar "8 kegagalan beruntun" di ImporDenahDialog hanya menghitung permintaan
 * yang SELESAI, jadi permintaan yang menggantung tak pernah menyentuhnya.
 * Operator menatap loading tanpa akhir lalu menyimpulkan "aplikasi gagal".
 *
 * Modul ini murni angka & keputusan (tanpa DOM, tanpa axios) supaya bisa diuji
 * sungguhan — pola yang sama dipakai `tarikBerat`, `zoomPan`, dan `denahEditor`
 * di repo ini.
 */

/** Tenggat baku untuk GET daftar/detail. Cukup longgar untuk 3G lapangan. */
export const TENGGAT_BAKA = 20000;
/** Tenggat untuk permintaan yang memang berat (ekspor, unduh, impor). */
export const TENGGAT_BERAT = 60000;
/** Percobaan TOTAL (bukan tambahan): 1 asli + 2 ulangan. */
export const MAKS_PERCOBAAN = 3;

export const JENIS = {
  JARINGAN: 'jaringan',       // tak ada respons sama sekali (putus/DNS/menggantung)
  TENGGAT: 'tenggat',         // kita sendiri yang memutus karena kelamaan
  SERVER: 'server',           // 5xx — server hidup tapi gagal
  SIBUK: 'sibuk',             // 429 — rate limit
  IZIN: 'izin',               // 401/403
  PERMINTAAN: 'permintaan',   // 4xx lain — salah kita, mengulang tak menolong
  DIBATALKAN: 'dibatalkan',   // kita membatalkannya sendiri (unmount/ganti node)
};

/**
 * Kenali BENTUK kegagalan. Ini fondasi seluruh modul: memperlakukan "putus
 * jaringan" sama dengan "404" adalah sebab kedua terbanyak layar berperilaku
 * aneh — yang satu layak diulang, yang lain tidak akan pernah berhasil.
 */
export function jenisGalat(err) {
  if (!err) return JENIS.JARINGAN;
  const kode = err.code || '';
  const nama = err.name || '';
  if (kode === 'ERR_CANCELED' || nama === 'CanceledError' || nama === 'AbortError'
      || err.__CANCEL__ === true) {
    return JENIS.DIBATALKAN;
  }
  if (kode === 'ECONNABORTED' || kode === 'ETIMEDOUT'
      || /timeout/i.test(err.message || '')) {
    return JENIS.TENGGAT;
  }
  const status = err.response && err.response.status;
  if (!status) return JENIS.JARINGAN;      // tak ada respons = tak sampai server
  if (status === 429) return JENIS.SIBUK;
  if (status === 401 || status === 403) return JENIS.IZIN;
  if (status >= 500) return JENIS.SERVER;
  return JENIS.PERMINTAAN;
}

/**
 * Layak diulang? HANYA kegagalan yang sifatnya sementara.
 *
 * 4xx TIDAK diulang: permintaannya sendiri yang salah, mengulang hanya
 * membuang kuota dan memperlambat pesan galat sampai ke operator. 401/403 juga
 * tidak — sesi berakhir tak akan pulih dengan menunggu, dan mengulanginya
 * menunda logout yang seharusnya terjadi.
 */
export function bolehUlang(err) {
  const j = jenisGalat(err);
  return j === JENIS.JARINGAN || j === JENIS.TENGGAT
      || j === JENIS.SERVER || j === JENIS.SIBUK;
}

/**
 * Jeda sebelum percobaan ke-`percobaan` (1 = ulangan pertama).
 *
 * Backoff eksponensial + JITTER. Jitter itu wajib, bukan hiasan: saat sinyal
 * pulih di satu lokasi, seluruh perangkat regu inventarisasi mencoba ulang
 * pada detik yang sama dan menghantam server berbarengan. Acak kecil
 * memecah gelombang itu.
 */
export function jedaUlang(percobaan, acak = Math.random) {
  const n = Math.max(1, Number(percobaan) || 1);
  const dasar = Math.min(8000, 800 * Math.pow(2, n - 1));
  return Math.round(dasar + acak() * 400);
}

/**
 * Kalimat untuk operator — menyebut APA yang terjadi dan apa yang bisa
 * dilakukan, bukan sekadar "terjadi kesalahan".
 */
export function pesanGalat(err, bawaan = 'Gagal memuat data') {
  switch (jenisGalat(err)) {
    case JENIS.JARINGAN:
      return `${bawaan} — perangkat tidak dapat menghubungi server. Periksa sinyal, lalu coba lagi.`;
    case JENIS.TENGGAT:
      return `${bawaan} — server tidak menjawab tepat waktu. Coba lagi; data Anda tidak hilang.`;
    case JENIS.SERVER:
      return `${bawaan} — server sedang bermasalah. Coba lagi beberapa saat lagi.`;
    case JENIS.SIBUK:
      return `${bawaan} — terlalu banyak permintaan sekaligus. Tunggu ±1 menit lalu coba lagi.`;
    case JENIS.IZIN:
      return `${bawaan} — sesi Anda berakhir atau Anda tidak berhak atas data ini.`;
    default: {
      const d = err && err.response && err.response.data && err.response.data.detail;
      return typeof d === 'string' && d ? d : bawaan;
    }
  }
}

/**
 * Jalankan `kerja` dengan coba-ulang untuk kegagalan yang sementara saja.
 *
 * `kerja(percobaan)` dipanggil 1..MAKS_PERCOBAAN kali. Galat percobaan
 * TERAKHIR dilempar apa adanya supaya pemanggil tetap bisa memeriksa
 * `err.response` seperti biasa.
 *
 * `tidur` disuntikkan agar uji tak perlu benar-benar menunggu detik nyata.
 * `padaUlang` dipakai layar untuk memberi tahu operator bahwa ia sedang
 * mencoba lagi — diam selama 3 percobaan terasa seperti macet.
 */
export async function muatAndal(kerja, opsi = {}) {
  const maks = Math.max(1, opsi.maksPercobaan || MAKS_PERCOBAAN);
  const tidur = opsi.tidur || ((ms) => new Promise((r) => setTimeout(r, ms)));
  const acak = opsi.acak || Math.random;
  let galatTerakhir;
  for (let percobaan = 1; percobaan <= maks; percobaan += 1) {
    try {
      return await kerja(percobaan);
    } catch (err) {
      galatTerakhir = err;
      // Dibatalkan = keputusan KITA (unmount / ganti node). Mengulanginya
      // berarti menghidupkan kembali permintaan yang sengaja dimatikan.
      if (percobaan >= maks || !bolehUlang(err)) throw err;
      if (opsi.padaUlang) opsi.padaUlang(percobaan, err);
      await tidur(jedaUlang(percobaan, acak));
    }
  }
  throw galatTerakhir;                       // tak terjangkau; jaring pengaman
}
