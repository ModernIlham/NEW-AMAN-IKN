/**
 * Kapan baris pengadaan boleh DILEBURKAN ke aset yang sudah tercatat — MURNI.
 *
 * Permintaan pemilik: peleburan menambah NILAI aset tujuan (jurnal 202)
 * sementara kuantitasnya tetap, *"berikan peringatan agar jika yang
 * dikembangkan lebih dari 1 dan sasarannya hanya NUP hanya 1 maka berikan
 * proses harus 1 NUP 1 barang."*
 *
 * Syarat lengkapnya ditegakkan SERVER (`peleburan_aset.validate_leburan`).
 * Yang di sini hanya menentukan apa yang layak DITAWARKAN dan apa yang perlu
 * dikatakan LEBIH DULU — tombol yang pasti ditolak hanyalah undangan untuk
 * mencoba, dan penolakan yang baru muncul setelah aset tujuan dipilih membuat
 * operator mengira sistemnya yang rewel.
 */

/** Baris ini layak ditawari tombol "Leburkan ke NUP"? */
export function bolehLeburkan(baris) {
  const b = baris || {};
  // Sudah di kartu stok, atau sudah tertaut/terlebur → server menolak.
  if (String(b.psd_item_id || "").trim()) return false;
  if (String(b.asset_id || "").trim()) return false;
  return true;
}

/**
 * Peringatan yang harus tampil SEBELUM aset tujuan dipilih, atau "" bila
 * tak ada. Satu NUP untuk satu barang.
 */
export function peringatanJumlahLebur(baris) {
  const jumlah = Number((baris || {}).jumlah ?? 1);
  if (!Number.isFinite(jumlah) || jumlah === 1) return "";
  return (
    `Baris ini berjumlah ${jumlah} unit sedangkan sasarannya satu NUP. `
    + "Peleburan berlaku 1 NUP untuk 1 barang — pecah barisnya menjadi "
    + "beberapa baris ber-jumlah 1, lalu ulangi peleburan untuk masing-masing."
  );
}
