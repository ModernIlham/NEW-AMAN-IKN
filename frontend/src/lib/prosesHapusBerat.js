/**
 * Penanganan permintaan HAPUS berat (hapus kegiatan, hapus semua aset).
 *
 * Kenapa perlu: tenggat axios global 20 dtk (App.js) dan nginx `/api/`
 * memotong di 120 dtk, sedangkan menghapus ratusan aset beserta foto &
 * dokumennya bisa lebih lama. Saat itu browser menerima galat (timeout/504)
 * padahal server MASIH menghapus di latar — pengguna mengira perintahnya
 * gagal/tak direspons dan daftar lama masih tampil.
 *
 * Pola: kirim dengan tenggat panjang; bila koneksi terputus tanpa jawaban
 * server yang pasti (timeout, 502/503/504, jaringan), JANGAN laporkan gagal —
 * pantau (`cekSelesai`) sampai data benar-benar hilang atau batas tunggu habis.
 */

export const TENGGAT_HAPUS_BERAT = 130 * 1000;   // sedikit di atas proxy 120 dtk
const JEDA_PANTAU = 3000;
const BATAS_PANTAU = 10 * 60 * 1000;

/** True bila galat berarti "jawaban tak sampai", bukan penolakan server. */
export function jawabanTerputus(err) {
  if (!err) return false;
  if (err.code === "ECONNABORTED" || err.code === "ETIMEDOUT" || err.code === "ERR_NETWORK") return true;
  const st = err.response?.status;
  if (!err.response) return true;
  return st === 502 || st === 503 || st === 504;
}

const tidur = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Jalankan `kirim()`; bila jawabannya terputus, pantau `cekSelesai()`.
 * Hasil: { status: "selesai", data } | { status: "selesai_latar" }
 *        | { status: "belum_pasti" }. Galat penolakan server (4xx/500) dilempar.
 */
export async function jalankanHapusBerat(kirim, cekSelesai, { jeda = JEDA_PANTAU, batas = BATAS_PANTAU } = {}) {
  try {
    const r = await kirim();
    return { status: "selesai", data: r?.data };
  } catch (err) {
    if (!jawabanTerputus(err)) throw err;
  }
  const akhir = Date.now() + batas;
  while (Date.now() < akhir) {
    await tidur(jeda);
    try {
      if (await cekSelesai()) return { status: "selesai_latar" };
    } catch { /* jaringan sesaat putus — coba lagi */ }
  }
  return { status: "belum_pasti" };
}
