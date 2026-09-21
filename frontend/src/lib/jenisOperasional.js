// Satu referensi untuk form lengkap, lembar cepat, kamera, dan ubah massal.
export const OPERASIONAL_JENIS_OPTIONS = ["Unit/Tempat/Tugas", "Ruangan"];

export function normalisasiJenisOperasional(nilai) {
  const teks = String(nilai ?? "").trim();
  const kunci = teks.replace(/\s+/g, "").toLowerCase();
  if (["kegiatan/acara/kebutuhan", "unit/tempat/tugas"].includes(kunci)) {
    return OPERASIONAL_JENIS_OPTIONS[0];
  }
  if (kunci === "ruangan") return OPERASIONAL_JENIS_OPTIONS[1];
  // Nilai kustom/era lama lain tidak boleh hilang saat form dibuka.
  return teks;
}
