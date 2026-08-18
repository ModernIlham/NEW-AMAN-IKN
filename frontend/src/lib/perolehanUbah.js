/**
 * Bentuk data form "Ubah Perolehan" — dipisah dari halaman supaya dua
 * keputusan yang paling gampang salah bisa diuji tanpa merender halaman.
 *
 * Keduanya bukan soal tampilan, melainkan soal data yang terkirim:
 *
 * 1. **`barang: null` saat daftarnya terkunci.** Server memahami null sebagai
 *    "jangan sentuh". Mengirim salinan daftar terkunci akan ditolak 409 — dan
 *    kalau suatu saat penjaganya longgar, salinan itu menulis ulang baris yang
 *    sudah menjadi stok/aset.
 * 2. **Tanpa `penganggaran_id`/`ppk_pejabat_id`.** Keduanya menulis SNAPSHOT
 *    BEKU lewat endpoint-nya sendiri. Ikut mengirimnya dari form ubah membuat
 *    setiap perbaikan salah ketik diam-diam menimpa PPK yang sudah ditetapkan
 *    dengan isi select yang kebetulan sedang tampil (sering: kosong).
 */

/** Isi awal form dari satu baris register. */
export function formDariPerolehan(p) {
  return {
    mode: "ubah",
    id: p.id,
    // Server lama yang belum mengirim `ubah` dianggap terbuka — server tetap
    // yang memutuskan di akhir, klien hanya menghemat ketikan sia-sia.
    kunci: p.ubah || { identitas: true, barang: true, alasan: "" },
    data: {
      jenis: p.jenis || "pembelian",
      pihak: p.pihak || "",
      nomor_kontrak: p.nomor_kontrak || "",
      nomor_bast: p.nomor_bast || "",
      tanggal_bast: String(p.tanggal_bast || "").slice(0, 10),
      keterangan: p.keterangan || "",
      penganggaran_id: "",
      ppk_pejabat_id: "",
    },
    barang: (p.barang || []).map((b) => ({
      uraian: b.uraian || "",
      kode: b.kode || "",
      jumlah: String(b.jumlah ?? ""),
      harga_satuan: String(b.harga_satuan ?? ""),
    })),
    saving: false,
  };
}

/** Payload PUT /pengadaan/{id} dari isi form. */
export function payloadUbahPerolehan(form) {
  const d = form?.data || {};
  return {
    jenis: d.jenis,
    pihak: d.pihak,
    nomor_kontrak: d.nomor_kontrak,
    nomor_bast: d.nomor_bast,
    tanggal_bast: d.tanggal_bast,
    keterangan: d.keterangan,
    barang: form?.kunci?.barang === false ? null : (form?.barang || []).map((b) => ({
      uraian: b.uraian,
      kode: b.kode,
      jumlah: Number(b.jumlah || 0),
      harga_satuan: Number(b.harga_satuan || 0),
    })),
  };
}
