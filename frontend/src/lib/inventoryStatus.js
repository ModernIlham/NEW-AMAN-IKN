// Status inventarisasi OTOMATIS — saat foto DAN koordinat sudah terekam dan
// status masih default "Belum Diinventarisasi", aset otomatis disimpan sebagai
// "Ditemukan". Kerja lapangan berjalan cepat: surveyor cukup memotret + kunci
// GPS tanpa harus mengetuk status. Bisa dimatikan pengguna via localStorage
// `aman_auto_inventarisasi` = "off" (default AKTIF).
//
// Catatan: nilai lama "Sudah Diinventarisasi" TIDAK ada di daftar pilihan resmi
// (Belum Diinventarisasi / Ditemukan / Tidak Ditemukan / Berlebih / Sengketa),
// sehingga status itu "yatim" — tak muncul terseleksi di chip lapangan dan
// gagal validasi impor. Kini auto-status = "Ditemukan" (memang aset ber-foto =
// ditemukan). Data lama yang terlanjur "Sudah Diinventarisasi" dinormalkan ke
// "Ditemukan" oleh migrasi startup di backend (server.py).
//
// Fungsi MURNI (tanpa dependensi DOM) agar mudah diuji unit dan dipakai identik
// di jalur kamera penuh maupun lembar inventarisasi cepat — keduanya menyimpan
// lewat AssetForm.handleSubmit.

export const STATUS_BELUM = "Belum Diinventarisasi";
// Auto-status saat foto+koordinat lengkap. (Nama const dipertahankan demi
// kompatibilitas impor; nilainya kini "Ditemukan", bukan "Sudah Diinventarisasi".)
export const STATUS_SUDAH = "Ditemukan";

// Preferensi pengguna (default AKTIF). Dibungkus try/catch untuk lingkungan
// tanpa localStorage (SSR/uji). Mengikuti pola hapticsEnabled().
export function autoInventarisasiEnabled() {
  try {
    return typeof localStorage === "undefined" || localStorage.getItem("aman_auto_inventarisasi") !== "off";
  } catch {
    return true;
  }
}

// Nilai dianggap ADA bila bukan null/undefined dan bukan string kosong — koordinat
// disimpan sebagai string ("−0.912345"), jadi "" / null → dianggap belum ada.
const ada = (v) => v != null && String(v).trim() !== "";

// Murni: kembalikan status inventarisasi EFEKTIF. Naikkan ke "Ditemukan" HANYA
// bila fitur aktif, ada foto, ada koordinat (lat & lng), dan status masih
// default "Belum Diinventarisasi"/kosong. Status apa pun yang sudah diubah
// manual (mis. "Tidak Ditemukan", "Berlebih", "Sengketa", atau bahkan "Belum
// Diinventarisasi" yang DIPILIH sengaja) TAK PERNAH diubah — kembalikan apa
// adanya. Pemanggil (AssetForm) mematikan `enabled` ketika pengguna memilih
// status secara manual, sehingga pilihan "Belum" dapat di-revert & menetap
// walau aset punya foto+koordinat.
export function statusInventarisasiOtomatis({ inventory_status, hasPhoto, lat, lng, enabled }) {
  const masihDefault = inventory_status === STATUS_BELUM || !inventory_status;
  if (enabled && hasPhoto && ada(lat) && ada(lng) && masihDefault) return STATUS_SUDAH;
  return inventory_status;
}
