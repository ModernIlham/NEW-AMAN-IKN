/**
 * Agregat kartu ringkasan — dihitung dari baris yang SUDAH tersaring.
 *
 * Dipakai jalur LURING. Saat daftar disajikan dari snapshot lokal, angka
 * kartunya dulu tetap angka daring terakhir: filter diubah, daftar menyusut,
 * kartu diam. Persis keluhan yang sama dengan jalur daring, hanya lebih sulit
 * disadari karena orang cenderung memaafkan layar yang sedang offline.
 *
 * Rumusnya sengaja mencerminkan agregasi server (routes/assets.py,
 * `get_assets_stats`): `purchase_price` boleh berupa angka, teks, kosong, atau
 * tidak ada sama sekali — semuanya dihitung sebagai 0, bukan NaN. Satu NaN
 * membuat seluruh Total Nilai berubah jadi "NaN" di layar.
 */

/** Angka dari nilai apa pun; teks tak terbaca / kosong / null → 0. */
export function angkaAman(v) {
  const n = typeof v === "number" ? v : parseFloat(v);
  return Number.isFinite(n) ? n : 0;
}

/**
 * @param {Array} rows baris aset yang sudah tersaring
 * @returns {{totalAssets:number,totalValue:number,activeCount:number,maintenanceCount:number}}
 */
export function hitungStatistikBaris(rows) {
  const daftar = Array.isArray(rows) ? rows : [];
  let totalValue = 0;
  let activeCount = 0;
  let maintenanceCount = 0;
  for (const r of daftar) {
    totalValue += angkaAman(r?.purchase_price);
    // Perbandingan PERSIS, sama dengan `$eq` di server. Menggunakan
    // pencocokan longgar (mis. huruf kecil) akan membuat angka luring
    // berbeda dari angka daring untuk data yang sama.
    if (r?.status === "Aktif") activeCount += 1;
    else if (r?.status === "Maintenance") maintenanceCount += 1;
  }
  return { totalAssets: daftar.length, totalValue, activeCount, maintenanceCount };
}

/** Bentuk siap-tampil (Total Nilai sudah diformat gaya Indonesia). */
export function statistikUntukKartu(rows) {
  const s = hitungStatistikBaris(rows);
  return {
    totalAssets: s.totalAssets,
    totalValue: s.totalValue.toLocaleString("id-ID"),
    activeCount: s.activeCount,
    maintenanceCount: s.maintenanceCount,
  };
}
