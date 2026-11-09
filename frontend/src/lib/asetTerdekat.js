// Perhitungan murni untuk fitur "Lokasi Anda" di peta: aset terdekat, arah
// mata angin, dan jejak perjalanan. Tanpa DOM/Leaflet agar teruji unit.
import { jarakMeter } from "./ukurPeta";
import { parseKoordinat } from "./koordinatAset";

const rad = (d) => (d * Math.PI) / 180;

/** Arah awal (azimut, 0° = utara, searah jarum jam) dari a ke b, derajat 0–360. */
export function arahDerajat(a, b) {
  const lat1 = rad(a.lat), lat2 = rad(b.lat), dLng = rad(b.lng - a.lng);
  const y = Math.sin(dLng) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);
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

// ── Pekerjaan lapangan dari lokasi Anda ──

/**
 * Batas akurasi untuk MENULIS koordinat aset dari GPS — sama dengan gerbang
 * rana Mode Kamera Penuh (≤ 8 m). Titik aset adalah data resmi; fix ±30 m di
 * dalam gedung bisa menaruh aset di ruangan sebelah.
 */
export const AKURASI_TITIK_M = 8;

/** Fix cukup presisi untuk dijadikan titik aset? */
export function cukupPresisi(posisi) {
  return !!posisi && Number.isFinite(posisi.accuracy) && posisi.accuracy <= AKURASI_TITIK_M;
}

/**
 * Status pemandu menuju aset tujuan.
 * `tiba` = jarak ≤ max(5 m, akurasi GPS) — lebih dekat dari itu GPS tak
 * bisa membedakan, jadi menunggu "0 m" hanya membuat petugas berputar-putar.
 */
export function statusPandu(posisi, tujuan) {
  if (!posisi || !tujuan) return null;
  const jarak = jarakMeter(posisi, tujuan);
  const ambang = Math.max(5, Number(posisi.accuracy) || 0);
  return { jarak, arah: arahDerajat(posisi, tujuan), tiba: jarak <= ambang, ambang };
}

/** Tautan navigasi Google Maps (untuk aset jauh: lahan, gedung lain). */
export function urlGoogleMaps(lat, lng) {
  return `https://www.google.com/maps/dir/?api=1&destination=${Number(lat).toFixed(6)},${Number(lng).toFixed(6)}`;
}

/** Arah gerak layak ditampilkan? (GPS memberi heading acak saat diam.) */
export function arahGerakSah(fix) {
  return !!fix && Number.isFinite(fix.heading) && Number.isFinite(fix.speed) && fix.speed >= 0.7;
}
