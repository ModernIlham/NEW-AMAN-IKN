/**
 * Ambil koordinat GPS yang SEGAR & AKURAT.
 *
 * Masalah lama: `getCurrentPosition({ enableHighAccuracy:true })` sering
 * mengembalikan fix yang MASIH TER-CACHE, sehingga menekan "Ambil GPS"
 * berulang kali memberi koordinat yang sama (tidak berubah) dan belum tentu
 * akurat.
 *
 * Solusi: pakai `watchPosition` dengan `maximumAge: 0` (paksa fix baru), lalu
 * kumpulkan pembacaan selama beberapa detik dan pilih akurasi TERBAIK. Setiap
 * perbaikan dilaporkan lewat `onUpdate` sehingga UI bisa memperbarui koordinat
 * secara realtime saat sinyal mengerucut. Berhenti lebih awal begitu akurasi
 * yang diinginkan tercapai, atau setelah `maxWait`.
 *
 * @param {Object} [opts]
 * @param {(fix:{lat:string,lng:string,accuracy:number}) => void} [opts.onUpdate]
 *        Dipanggil tiap kali ada fix baru yang lebih akurat (untuk tampilan realtime).
 * @param {number} [opts.desiredAccuracy=15] meter — selesai lebih awal bila tercapai.
 * @param {number} [opts.maxWait=8000] ms — durasi maksimum mengumpulkan fix.
 * @param {number} [opts.timeout=15000] ms — timeout per pembacaan geolokasi.
 * @returns {Promise<{lat:string,lng:string,accuracy:number}>}
 */
export function acquireAccuratePosition({
  onUpdate,
  desiredAccuracy = 15,
  maxWait = 8000,
  timeout = 15000,
} = {}) {
  return new Promise((resolve, reject) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      reject(new Error("GPS tidak didukung di browser ini"));
      return;
    }

    let best = null;
    let watchId = null;
    let settled = false;
    let maxTimer = null;

    const cleanup = () => {
      if (watchId != null) { navigator.geolocation.clearWatch(watchId); watchId = null; }
      if (maxTimer) { clearTimeout(maxTimer); maxTimer = null; }
    };

    const finish = () => {
      if (settled) return;
      settled = true;
      cleanup();
      if (best) resolve(best);
      else reject(new Error("Gagal mendapatkan lokasi GPS"));
    };

    watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const acc = Number.isFinite(pos.coords.accuracy) ? pos.coords.accuracy : Infinity;
        const fix = {
          lat: pos.coords.latitude.toFixed(6),
          lng: pos.coords.longitude.toFixed(6),
          accuracy: acc,
        };
        // Simpan hanya bila lebih akurat (atau fix pertama) — hindari mundur.
        if (!best || acc <= best.accuracy) {
          best = fix;
          try { onUpdate?.(fix); } catch { /* pembaruan UI tidak boleh menggagalkan fix */ }
        }
        // Sudah cukup akurat → selesai lebih awal.
        if (acc <= desiredAccuracy) finish();
      },
      (err) => {
        // Izin ditolak = kesalahan permanen: hentikan dan teruskan errornya.
        if (err && err.code === 1 /* PERMISSION_DENIED */) {
          if (settled) return;
          settled = true;
          cleanup();
          reject(err);
          return;
        }
        // TIMEOUT / POSITION_UNAVAILABLE sementara: biarkan watch lanjut sampai
        // maxWait; kalau sudah ada `best`, itu yang dipakai.
      },
      { enableHighAccuracy: true, maximumAge: 0, timeout }
    );

    // Batas waktu total: pakai fix terbaik yang terkumpul sejauh ini.
    maxTimer = setTimeout(finish, maxWait);
  });
}

export default acquireAccuratePosition;
