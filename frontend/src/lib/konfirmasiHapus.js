// Konfirmasi ketik-nama untuk aksi destruktif yang tidak dapat dibatalkan
// (pola baku: GitHub/AWS/GCP meminta nama sumber daya diketik ulang).
// Murni & teruji — dipakai dialog "Hapus Semua Aset Kegiatan" (F8).

const normal = (t) => String(t ?? "").normalize("NFKC").replace(/\s+/g, " ").trim().toLocaleLowerCase("id-ID");

/** Frasa yang harus diketik: nama kegiatan; "HAPUS" bila nama kosong. */
export function frasaKonfirmasiHapus(namaKegiatan) {
  const nama = String(namaKegiatan ?? "").replace(/\s+/g, " ").trim();
  return nama || "HAPUS";
}

/** Cocok bila sama setelah normalisasi spasi & huruf besar/kecil. */
export function konfirmasiCocok(ketikan, frasa) {
  const f = normal(frasa);
  return f.length > 0 && normal(ketikan) === f;
}
