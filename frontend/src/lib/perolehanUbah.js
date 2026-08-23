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
/**
 * Kolom dokumen pengadaan — CERMIN `pengadaan_dokumen.py` di server.
 *
 * Daftar ini sengaja pendek dan datar: yang menentukan kolom mana BERLAKU
 * tetap server (`validate_dokumen`), dan menyalin aturannya ke sini hanya
 * akan melahirkan dua aturan yang perlahan berbeda. Yang disalin cuma NAMA
 * kolomnya, supaya payload tak menjatuhkan kolom yang sudah tercatat.
 */
export const KUNCI_DOKUMEN = [
  "no_sp_spk", "jenis_up", "no_spby", "no_spp", "no_spm", "no_bukti",
  "no_dokumen",
];

/** Kolom dokumen dari sebuah form/record, dipangkas spasi tepinya. */
export function bersihkanDokumen(d) {
  const out = {};
  for (const k of KUNCI_DOKUMEN) out[k] = String(d?.[k] || "").trim();
  return out;
}

/**
 * Kolom yang IKUT TERHAPUS saat sifat pengadaan berganti.
 *
 * Dibersihkan di layar, bukan sekadar ditolak server: operator yang mengisi
 * SP/SPK lalu berpindah ke Non-Kontrak akan ditolak menyimpan tanpa tahu
 * kolom mana penyebabnya — kolomnya sendiri sudah tak terlihat lagi.
 */
export function dokumenSetelahGantiSifat(d, sifat) {
  const hapus = sifat === "kontrak" ? ["jenis_up", "no_spby"]
    : sifat === "non_kontrak" ? ["no_sp_spk"]
      : [];
  const out = { ...d, sifat };
  for (const k of hapus) out[k] = "";
  return out;
}


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
      // Dokumen pengadaan — dimuat apa adanya supaya form ubah tak
      // MENGOSONGKAN kolom yang sudah terisi. Register lama tak punya
      // kunci-kunci ini sama sekali; "" adalah keadaan sebenarnya.
      sifat: p.sifat || "",
      no_sp_spk: p.no_sp_spk || "",
      jenis_up: p.jenis_up || "",
      no_spby: p.no_spby || "",
      no_spp: p.no_spp || "",
      no_spm: p.no_spm || "",
      no_bukti: p.no_bukti || "",
      no_dokumen: p.no_dokumen || "",
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
    // Dokumen pengadaan ikut terkirim — tanpa ini, menyimpan perubahan
    // apa pun akan MENGOSONGKAN dokumen yang sudah tercatat, karena server
    // menulis ulang seluruh kolomnya.
    sifat: d.sifat || "",
    ...bersihkanDokumen(d),
    barang: form?.kunci?.barang === false ? null : (form?.barang || []).map((b) => ({
      uraian: b.uraian,
      kode: b.kode,
      jumlah: Number(b.jumlah || 0),
      harga_satuan: Number(b.harga_satuan || 0),
    })),
  };
}
