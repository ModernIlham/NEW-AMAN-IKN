export function isKontrak(jenis) {
  return jenis === "Kontrak" || jenis === "Kontrak BLU";
}

export function isNonKontrak(jenis) {
  return jenis === "Non Kontrak/Penerimaan Barang" || jenis === "Non Kontrak BLU";
}
