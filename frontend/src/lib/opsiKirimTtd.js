/**
 * Pilihan saat melempar dokumen ke e-sign — CERMIN server, bukan penggantinya.
 *
 * Permintaan pemilik: *"di saat mengklik 'kirim ttd' juga dapat memilih jenis
 * urutan tanda tangan apakah ingin paralel atau berurutan, dan berikan juga
 * opsi pemilihan sifat urgensi suratnya."*
 *
 * Nilainya HARUS sama dengan yang divalidasi server (`routes/ttd.py` dan
 * `persuratan_utils.SIFAT_URGENSI`); yang disalin ke sini hanya label untuk
 * layar. Server tetap gerbangnya — daftar yang menyimpang akan ditolak 400,
 * bukan diam-diam tersimpan salah.
 */

export const MODE_TTD = [
  {
    nilai: "paralel",
    label: "Paralel — semua bisa meneken bersamaan",
    arti: "Semua penanda tangan menerima tautan sekaligus. Paling cepat.",
  },
  {
    nilai: "berurutan",
    label: "Berurutan — menunggu giliran",
    arti: ("Tautan berikutnya baru aktif setelah yang sebelumnya meneken. "
           + "Dipakai bila atasan harus melihat tanda tangan bawahannya dulu."),
  },
];

export const SIFAT_URGENSI = [
  { nilai: "biasa", label: "Biasa" },
  { nilai: "segera", label: "Segera" },
  { nilai: "sangat_segera", label: "Sangat Segera" },
];

export const PILIHAN_BAWAAN = { mode: "paralel", sifat_urgensi: "biasa" };

/** Pilihan yang aman dikirim: nilai asing jatuh ke bawaannya, bukan diteruskan. */
export function bersihkanPilihan(p) {
  const mode = MODE_TTD.some((m) => m.nilai === p?.mode)
    ? p.mode : PILIHAN_BAWAAN.mode;
  const urg = SIFAT_URGENSI.some((u) => u.nilai === p?.sifat_urgensi)
    ? p.sifat_urgensi : PILIHAN_BAWAAN.sifat_urgensi;
  return { mode, sifat_urgensi: urg };
}

/** Label urgensi untuk ditampilkan; "" bila biasa (tak perlu diumumkan). */
export function labelUrgensi(nilai) {
  const u = SIFAT_URGENSI.find((x) => x.nilai === nilai);
  return !u || u.nilai === "biasa" ? "" : u.label;
}
