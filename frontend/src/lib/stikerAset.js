/**
 * Keterangan STIKER satu aset — SATU sumber untuk semua tampilan baris.
 *
 * Ada tiga tempat yang menampilkan status stiker (baris HP, tabel desktop,
 * kartu galeri) dan sebelumnya ketiganya menyusun teksnya sendiri-sendiri:
 * baris HP menulis "Belum Stiker", tabel menulis "Ya"/"-", galeri menulis
 * "Belum dipasang". Tiga kalimat untuk satu keadaan yang sama — dan ukuran
 * stikernya hilang di ketiganya.
 *
 * ── Kenapa ukuran ikut ditampilkan meski belum terpasang ────────────────
 * Permintaan pemilik. Dan itu memang keadaan NORMAL di tengah alur kerja:
 * ukuran dipilih DULU (itulah gunanya mode cetak "sesuai pilihan tiap
 * aset"), stikernya dicetak, baru ditempel. Sepanjang jeda itu, tampilan
 * lama membuang satu-satunya keterangan yang sedang dibutuhkan petugas.
 */

/**
 * Ukuran → huruf ringkas. Kunci disimpan huruf kecil dan pencocokannya
 * tak peka besar-kecil: nilai lama di basis data pernah tersimpan sebagai
 * "Kecil" maupun "kecil".
 */
export const HURUF_UKURAN_STIKER = { kecil: "S", sedang: "M", besar: "L" };

/** Huruf ringkas ukuran stiker ("S"/"M"/"L"), atau "" bila tak dikenali. */
export function hurufUkuranStiker(nilai) {
  return HURUF_UKURAN_STIKER[String(nilai ?? "").trim().toLowerCase()] || "";
}

/**
 * Keterangan stiker siap tampil.
 *
 * `huruf` kosong bukan berarti ukurannya kosong: kolom ini pernah berupa
 * isian bebas ("5x3cm") sebelum menjadi tiga pilihan, jadi nilai lama tak
 * punya huruf ringkas. Yang begitu tak ditampilkan sebagai huruf tetapi
 * TETAP disebut utuh di tooltip — lebih baik daripada memaksakannya menjadi
 * satu huruf yang salah.
 */
export function keteranganStiker(asset) {
  const a = asset || {};
  const terpasang = a.stiker_status === "Sudah Terpasang";
  const ukuran = String(a.stiker_ukuran ?? "").trim();
  return {
    terpasang,
    ukuran,
    huruf: hurufUkuranStiker(ukuran),
    // Warna sudah membedakan status, jadi teksnya boleh sependek mungkin —
    // ruang di baris HP diperebutkan eselon, harga, dan status inventarisasi.
    label: terpasang ? "Stiker" : "Belum Stiker",
    status: a.stiker_status || "Belum Terpasang",
  };
}
