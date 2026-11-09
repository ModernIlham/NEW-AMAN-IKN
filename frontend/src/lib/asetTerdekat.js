// Perhitungan murni untuk fitur "Lokasi Anda" di peta: aset terdekat, arah
// mata angin, dan jejak perjalanan. Tanpa DOM/Leaflet agar teruji unit.
import { jarakMeter } from "./ukurPeta";
import { parseKoordinat } from "./koordinatAset";

const rad = (d) => (d * Math.PI) / 180;

/** Arah awal (azimut, 0° = utara, searah jarum jam) dari a ke b, derajat 0–360. */
export function arahDerajat(a, b) {
  const φ1 = rad(a.lat), φ2 = rad(b.lat), Δλ = rad(b.lng - a.lng);
  const y = Math.sin(Δλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

const MATA_ANGIN = ["Utara", "Timur Laut", "Timur", "Tenggara", "Selatan", "Barat Daya", "Barat", "Barat Laut"];
/** 8 mata angin berbahasa Indonesia. */
export function mataAngin(derajat) {
  if (!Number.isFinite(derajat)) return "";
  return MATA_ANGIN[Math.round((((derajat % 360) + 360) % 360) / 45) % 8];
}

/** Ubah baris aset jadi titik siap hitung (sekali per perubahan data). */
export function siapkanTitikAset(rows) {
  const hasil = [];
  for (const row of rows || []) {
    const lat = parseKoordinat(row?.koordinat_latitude);
    const lng = parseKoordinat(row?.koordinat_longitude);
    if (lat === null || lng === null || Math.abs(lat) > 90) continue;
    hasil.push({ row, lat, lng });
  }
  return hasil;
}

/**
 * N aset terdekat dari posisi. O(jumlah titik) per panggilan — ±10.000 aset
 * tetap di bawah beberapa milidetik, cukup untuk dipanggil sekali per fix.
 *
 * @param opsi.hanyaBelum  hanya aset yang statusnya masih "Belum Diinventarisasi"
 * @param opsi.maksMeter   abaikan aset lebih jauh dari ini (default 5 km)
 * → [{ row, lat, lng, jarak, arah }] terurut dari yang paling dekat.
 */
export function cariTerdekat(titik, posisi, { n = 5, hanyaBelum = false, maksMeter = 5000 } = {}) {
  if (!posisi || !Number.isFinite(posisi.lat) || !Number.isFinite(posisi.lng)) return [];
  const terbaik = [];
  for (const t of titik || []) {
    if (hanyaBelum && (t.row.inventory_status || "Belum Diinventarisasi") !== "Belum Diinventarisasi") continue;
    const jarak = jarakMeter(posisi, t);
    if (jarak > maksMeter) continue;
    if (terbaik.length === n && jarak >= terbaik[n - 1].jarak) continue;
    // Sisip terurut ke daftar kecil (n ≤ ~10): lebih murah dari sort penuh.
    let i = terbaik.length;
    while (i > 0 && terbaik[i - 1].jarak > jarak) i -= 1;
    terbaik.splice(i, 0, { ...t, jarak });
    if (terbaik.length > n) terbaik.pop();
  }
  return terbaik.map((t) => ({ ...t, arah: arahDerajat(posisi, t) }));
}

/** Jumlah aset dalam radius tertentu (untuk ringkasan "N dalam 50 m"). */
export function jumlahDalamRadius(titik, posisi, meter, { hanyaBelum = false } = {}) {
  if (!posisi) return 0;
  let n = 0;
  for (const t of titik || []) {
    if (hanyaBelum && (t.row.inventory_status || "Belum Diinventarisasi") !== "Belum Diinventarisasi") continue;
    if (jarakMeter(posisi, t) <= meter) n += 1;
  }
  return n;
}

// ── Jejak perjalanan (hanya di memori tab) ──
export const JEJAK_MAKS_TITIK = 3000;
export const JEJAK_AKURASI_MAKS = 50; // fix lebih kasar dari ini tak masuk jejak

/**
 * Apakah fix ini layak menambah titik jejak? Menyaring jitter GPS saat diam:
 * titik baru hanya bila bergeser ≥ max(5 m, setengah akurasi) dari titik
 * jejak terakhir, dan akurasinya cukup baik.
 * → jarak tambahan (meter) bila layak; null bila tidak.
 */
export function langkahJejak(titikTerakhir, fix) {
  if (!fix || !Number.isFinite(fix.accuracy) || fix.accuracy > JEJAK_AKURASI_MAKS) return null;
  if (!titikTerakhir) return 0;
  const jarak = jarakMeter(titikTerakhir, fix);
  return jarak >= Math.max(5, fix.accuracy / 2) ? jarak : null;
}

/** Arah gerak layak ditampilkan? (GPS memberi heading acak saat diam.) */
export function arahGerakSah(fix) {
  return !!fix && Number.isFinite(fix.heading) && Number.isFinite(fix.speed) && fix.speed >= 0.7;
}
