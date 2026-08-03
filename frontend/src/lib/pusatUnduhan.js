// PUSAT UNDUHAN (klien) — daftarkan unduhan berat sebagai job latar server.
//
// Dipakai dua arah:
//  1. downloadFileWithProgress men-fallback OTOMATIS ke sini saat unduhan
//     langsung kehabisan waktu (server masih menyusun file — jangan dibuang);
//  2. tombol unduhan yang SUDAH diketahui berat memanggil langsung.
//
// Panel <PusatUnduhan /> (di-mount global di App.js) mendengarkan event
// `aman:unduhan-baru` untuk membuka diri + memantau progres + auto-unduh
// saat selesai. Hasil tersimpan 30 hari di server — bisa diunduh ulang
// kapan saja tanpa generate ulang.
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const EVENT_UNDUHAN_BARU = "aman:unduhan-baru";

/** Path internal (relatif /api) dari URL absolut `${API}/...`; null bila
 *  bukan URL API kita. */
export function pathDariUrl(url) {
  if (typeof url !== "string") return null;
  const idx = url.indexOf("/api/");
  if (idx < 0) return null;
  const path = url.slice(idx + 4);          // sisakan "/..." setelah "/api"
  return path.startsWith("/") ? path : null;
}

/**
 * Daftarkan unduhan ke Pusat Unduhan.
 * @param {{path: string, namaFile: string, label?: string}} arg
 * @returns {Promise<string>} unduhan_id
 */
export async function mulaiUnduhanPusat({ path, namaFile, label }) {
  const r = await axios.post(`${API}/unduhan/mulai`, {
    path, nama_file: namaFile, label: label || namaFile,
  });
  const id = r.data?.unduhan_id;
  if (!id) throw new Error("unduhan_id tidak diterima");
  try {
    window.dispatchEvent(new CustomEvent(EVENT_UNDUHAN_BARU, { detail: { id } }));
  } catch { /* lingkungan tanpa CustomEvent */ }
  return id;
}
