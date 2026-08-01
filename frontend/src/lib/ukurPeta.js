/**
 * Perhitungan JARAK & LUAS di permukaan bumi — bagian murni (tanpa Leaflet).
 *
 * KENAPA GEODESIK, BUKAN PLANAR. Peta ditampilkan dalam proyeksi Web Mercator,
 * dan menghitung luas langsung dari koordinat layar akan MELEBIH-LEBIHKAN hasil
 * makin jauh dari khatulistiwa. Untuk IKN (±1° LS) galatnya kecil, tetapi
 * aplikasi ini juga dipakai satker di lintang lain, dan angka luas di sini
 * dipakai untuk hal yang serius — SBSK, sengketa batas, laporan BMN. Maka
 * jarak memakai haversine dan luas memakai rumus luas bola (spherical excess),
 * keduanya pada jari-jari rata-rata bumi.
 *
 * Modul ini murni angka supaya bisa diuji sungguhan — pola yang sama dipakai
 * `tarikBerat`, `zoomPan`, `spasialDenah`, dan `unduhFoto` di repo ini.
 */

/** Jari-jari rata-rata bumi (IUGG), meter. */
export const JARI_BUMI_M = 6371008.8;

const rad = (d) => (d * Math.PI) / 180;

/**
 * Jarak lingkaran-besar antara dua titik {lat, lng}, dalam METER.
 *
 * Haversine dipilih ketimbang rumus kosinus sederhana karena tetap stabil pada
 * jarak sangat pendek — dan justru itulah kasus yang paling sering di sini
 * (mengukur sisi ruangan, lebar jalan inspeksi).
 */
export function jarakMeter(a, b) {
  if (!a || !b) return 0;
  const lat1 = Number(a.lat), lng1 = Number(a.lng);
  const lat2 = Number(b.lat), lng2 = Number(b.lng);
  if (![lat1, lng1, lat2, lng2].every(Number.isFinite)) return 0;
  const dLat = rad(lat2 - lat1);
  const dLng = rad(lng2 - lng1);
  const s = Math.sin(dLat / 2) ** 2
    + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * JARI_BUMI_M * Math.asin(Math.min(1, Math.sqrt(s)));
}

/** Panjang total sebuah jalur (deret titik), dalam meter. */
export function panjangJalurMeter(titik) {
  if (!Array.isArray(titik) || titik.length < 2) return 0;
  let total = 0;
  for (let i = 1; i < titik.length; i += 1) total += jarakMeter(titik[i - 1], titik[i]);
  return total;
}

/**
 * Luas poligon di permukaan bola, dalam METER PERSEGI.
 *
 * Poligon ditutup sendiri (titik terakhir tak perlu mengulang titik pertama).
 * Nilai mutlak diambil supaya arah putaran (searah/berlawanan jarum jam) tak
 * mengubah hasil — pengguna menggambar ke arah mana pun.
 */
export function luasMeterPersegi(titik) {
  if (!Array.isArray(titik) || titik.length < 3) return 0;
  const n = titik.length;
  let total = 0;
  for (let i = 0; i < n; i += 1) {
    const p1 = titik[i];
    const p2 = titik[(i + 1) % n];
    const lng1 = Number(p1?.lng), lat1 = Number(p1?.lat);
    const lng2 = Number(p2?.lng), lat2 = Number(p2?.lat);
    if (![lng1, lat1, lng2, lat2].every(Number.isFinite)) return 0;
    total += rad(lng2 - lng1) * (2 + Math.sin(rad(lat1)) + Math.sin(rad(lat2)));
  }
  return Math.abs((total * JARI_BUMI_M * JARI_BUMI_M) / 2);
}

/**
 * Format jarak untuk operator Indonesia.
 *
 * Di bawah 1 km ditulis meter dengan satu desimal — mengukur sisi ruangan
 * butuh ketelitian itu; di atasnya kilometer dengan dua desimal.
 */
export function formatJarak(meter) {
  const m = Number(meter);
  if (!Number.isFinite(m) || m <= 0) return "0 m";   // belum ada yang diukur — bukan "0,00 m"
  // `minimumFractionDigits` DIPAKSA, bukan lewat `toFixed` lalu `Number(...)`:
  // pembulatan-lalu-dikembalikan-ke-angka membuang nol di belakang, sehingga
  // "5,20 m" tampil "5,2 m" sementara "5,23 m" tetap dua desimal. Angka ini
  // masuk berita acara dan laporan — presisinya harus terlihat KONSISTEN.
  if (m < 1000) {
    const desimal = m < 10 ? 2 : 1;
    return `${m.toLocaleString("id-ID", { minimumFractionDigits: desimal, maximumFractionDigits: desimal })} m`;
  }
  return `${(m / 1000).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} km`;
}

/**
 * Format luas, dengan HEKTAR sebagai satuan tambahan.
 *
 * Hektar bukan hiasan: dokumen pertanahan & BMN untuk tanah memakainya, jadi
 * angka yang tampil bisa langsung dibandingkan dengan sertifikat tanpa
 * dihitung ulang.
 */
export function formatLuas(meterPersegi) {
  const m2 = Number(meterPersegi);
  if (!Number.isFinite(m2) || m2 <= 0) return "0 m²";  // belum ada bidang — bukan "0,00 m²"
  if (m2 < 10000) {
    const desimal = m2 < 100 ? 2 : 1;
    return `${m2.toLocaleString("id-ID", { minimumFractionDigits: desimal, maximumFractionDigits: desimal })} m²`;
  }
  const ha = m2 / 10000;
  const km2 = m2 / 1000000;
  const utama = `${ha.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ha`;
  if (km2 >= 1) {
    return `${utama} (${km2.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} km²)`;
  }
  return utama;
}

/**
 * Ringkasan pengukuran yang siap ditampilkan.
 *
 * `luas` hanya diisi bila titiknya ≥3 — dua titik itu garis, dan melaporkan
 * "luas 0 m²" untuk sebuah garis membingungkan, bukan informatif.
 */
export function ringkasUkur(titik) {
  const n = Array.isArray(titik) ? titik.length : 0;
  const panjang = panjangJalurMeter(titik);
  const luas = n >= 3 ? luasMeterPersegi(titik) : null;
  return {
    jumlahTitik: n,
    panjangMeter: panjang,
    luasMeterPersegi: luas,
    teksPanjang: formatJarak(panjang),
    teksLuas: luas == null ? null : formatLuas(luas),
    // Keliling hanya bermakna untuk bidang tertutup.
    kelilingMeter: n >= 3 ? panjang + jarakMeter(titik[n - 1], titik[0]) : null,
  };
}
