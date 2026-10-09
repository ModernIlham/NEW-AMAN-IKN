// Aturan produk laporan pengamatan; bukan perubahan data induk/akuntansi.
// Sesuaikan dengan LaporanIn.validasi_catatan pada server. Jangan mengisi
// narasi otomatis: teks pemegang dan payload retry harus tetap utuh.
const teks = value => typeof value === "string" ? value.trim() : "";

// Narasi/foto boleh kosong pada pemeriksaan normal; isian kondisi, keadaan,
// lokasi dan waktu tetap merupakan pengamatan yang tidak boleh dibuang diam-diam.
export function laporanPemegangBerubah(form) {
  if (!form) return false;
  return Boolean(teks(form.catatan) || form.bukti?.length || teks(form.lokasi_laporan)
    || form.diambil_pada || teks(form.laporan_sebelumnya_id)
    || (form.kondisi ?? "Tidak diketahui") !== "Tidak diketahui"
    || (form.status_operasional ?? "tidak_diketahui") !== "tidak_diketahui"
    || (form.jenis ?? "berkala") !== "berkala");
}

export function aturanCatatanLaporan(form = {}) {
  if (teks(form.laporan_sebelumnya_id)) return {
    wajib: true, label: "Tanggapan klarifikasi",
    panduan: "Jelaskan perbaikan atau jawaban atas catatan petugas pada laporan sebelumnya (minimal 5 karakter).",
  };
  if (form.jenis === "berkala") {
    const normal = form.kondisi === "Baik" && ["digunakan", "tidak_digunakan"].includes(form.status_operasional);
    return normal ? {
      wajib: false, label: "Catatan tambahan",
      panduan: "Opsional untuk pemeriksaan berkala dengan kondisi baik dan keadaan operasional yang jelas.",
    } : {
      wajib: true, label: "Hasil pemeriksaan / alasan",
      panduan: "Jelaskan kondisi yang ditemukan, proses perbaikan, atau alasan keadaan barang belum diketahui (minimal 5 karakter).",
    };
  }
  const aturan = {
    kerusakan: { label: "Kronologi kerusakan", panduan: "Jelaskan gejala kerusakan, kapan diketahui, dan tindakan awal yang sudah dilakukan (minimal 5 karakter)." },
    kehilangan: { label: "Kronologi kehilangan", panduan: "Jelaskan kapan dan di mana barang terakhir diketahui, penelusuran, serta tindakan yang sudah dilakukan (minimal 5 karakter). Foto dan GPS tidak wajib untuk melaporkan kehilangan." },
    perbaikan: { label: "Proses / hasil perbaikan", panduan: "Jelaskan proses atau hasil perbaikan dan keadaan barang saat ini (minimal 5 karakter)." },
    pengembalian: { label: "Alasan pengembalian", panduan: "Jelaskan alasan pengembalian dan kesiapan barang untuk diperiksa atau diserahterimakan (minimal 5 karakter)." },
  };
  return { wajib: true, ...(aturan[form.jenis] || { label: "Hasil pemeriksaan / kronologi", panduan: "Jelaskan keadaan dan tindakan yang sudah dilakukan (minimal 5 karakter)." }) };
}

export function kesalahanCatatanLaporan(form = {}) {
  if (!["berkala", "kerusakan", "kehilangan", "perbaikan", "pengembalian"].includes(form.jenis)) return "Pilih jenis laporan yang tersedia.";
  const { wajib, label } = aturanCatatanLaporan(form);
  const panjang = Array.from(teks(form.catatan)).length;
  if (wajib && panjang < 5) return `Tuliskan ${label.toLowerCase()} minimal 5 karakter.`;
  if (panjang > 5000) return "Catatan laporan maksimal 5000 karakter.";
  return "";
}
