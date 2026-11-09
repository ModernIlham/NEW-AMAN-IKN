// Pemantauan lokasi foreground. Tidak menyimpan/mengirim koordinat ke server.
// Satu watch per peta; callback dari watch lama tidak boleh menghidupkan UI lagi.
const OPSI_GPS = { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 };
const BATAS_SEGAR = 15000;
const BATAS_SENYAP = 30000;
const JEDA_TAMPIL = 1000;

function bacaPosisi(pos) {
  const { latitude: lat, longitude: lng, accuracy } = pos?.coords || {};
  const timestamp = pos?.timestamp;
  if (![lat, lng, accuracy, timestamp].every(Number.isFinite)
      || lat < -90 || lat > 90 || lng < -180 || lng > 180 || accuracy < 0
      || timestamp <= 0 || Date.now() - timestamp > BATAS_SEGAR
      || timestamp - Date.now() > 5000) return null;
  return { lat, lng, accuracy, timestamp };
}

export function buatPemantauLokasi({ onPosition, onStatus }) {
  let aktif = false;
  let dilepas = false;
  let terlihat = true;
  let halamanAktif = true;
  let watchId = null;
  let generasi = 0;
  let retryTimer = null;
  let senyapTimer = null;
  let tampilTimer = null;
  let percobaan = 0;
  let posisi = null;
  let tertunda = null;
  let tampilTerakhir = 0;

  const status = (nilai, message) => onStatus({ status: nilai, active: aktif, position: posisi, message });
  const bolehMemantau = () => aktif && terlihat && halamanAktif
    && document.visibilityState !== "hidden" && !dilepas;

  function bersihkan() {
    generasi += 1;
    if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    watchId = null;
    clearTimeout(retryTimer);
    clearTimeout(senyapTimer);
    clearTimeout(tampilTimer);
    retryTimer = senyapTimer = tampilTimer = null;
    tertunda = null;
  }

  function gagalPermanen(message) {
    bersihkan();
    aktif = false;
    posisi = null;
    status("error", message);
  }

  function tampilkan() {
    tampilTimer = null;
    if (!bolehMemantau() || !tertunda) return;
    const fix = tertunda;
    tertunda = null;
    tampilTerakhir = Date.now();
    onPosition(fix);
    status(fix.accuracy > 100 ? "weak" : "live");
  }

  function ulangi(alasan = "retrying") {
    if (!bolehMemantau() || retryTimer !== null) return;
    bersihkan();
    status(alasan);
    // Sinyal putus tidak boleh menjadi polling GPS rapat tanpa batas.
    const jeda = Math.min(30000, 2000 * (2 ** Math.min(percobaan, 4)));
    percobaan += 1;
    retryTimer = setTimeout(() => {
      retryTimer = null;
      mulaiWatch();
    }, jeda);
  }

  function pasangBatasSenyap() {
    clearTimeout(senyapTimer);
    // Termasuk browser yang berhenti memberi callback tanpa mengirim error.
    senyapTimer = setTimeout(() => ulangi("stale"), BATAS_SENYAP);
  }

  function mulaiWatch() {
    if (!bolehMemantau()) return;
    bersihkan();
    status(posisi ? "retrying" : "searching");
    const sesi = generasi;
    pasangBatasSenyap();
    try {
      const id = navigator.geolocation.watchPosition((hasil) => {
        if (sesi !== generasi || !bolehMemantau()) return;
        const fix = bacaPosisi(hasil);
        if (!fix || (posisi && fix.timestamp <= posisi.timestamp)) return;
        // Saat berjalan, fix terbaru tetap dipakai meski akurasinya menurun.
        // Memilih akurasi terbaik sepanjang sesi akan membekukan titik lama.
        posisi = fix;
        percobaan = 0;
        pasangBatasSenyap();
        tertunda = fix;
        const jeda = JEDA_TAMPIL - (Date.now() - tampilTerakhir);
        if (jeda <= 0) tampilkan();
        else if (tampilTimer === null) tampilTimer = setTimeout(tampilkan, jeda);
      }, (err) => {
        if (sesi !== generasi || !bolehMemantau()) return;
        if (err?.code === 1) {
          gagalPermanen("Izin lokasi ditolak — aktifkan izin lokasi browser untuk fitur ini");
        } else {
          ulangi();
        }
      }, OPSI_GPS);
      // Juga aman untuk penyedia/mock yang memanggil callback sinkron.
      if (sesi === generasi && bolehMemantau()) watchId = id;
      else navigator.geolocation.clearWatch(id);
    } catch (err) {
      if (sesi !== generasi) return;
      if (err?.name === "SecurityError" || err?.name === "NotAllowedError") {
        gagalPermanen("Akses lokasi diblokir — periksa izin lokasi browser");
      } else {
        ulangi();
      }
    }
  }

  function sesuaikanVisibilitas() {
    if (!aktif || dilepas) return;
    if (bolehMemantau()) {
      if (watchId === null && retryTimer === null) mulaiWatch();
    } else {
      bersihkan();
      status("paused");
    }
  }

  const saatKeluar = () => { halamanAktif = false; sesuaikanVisibilitas(); };
  const saatKembali = () => { halamanAktif = true; sesuaikanVisibilitas(); };
  document.addEventListener("visibilitychange", sesuaikanVisibilitas);
  window.addEventListener("pagehide", saatKeluar);
  window.addEventListener("pageshow", saatKembali);

  function stop() {
    bersihkan();
    aktif = false;
    posisi = null;
    percobaan = 0;
    tampilTerakhir = 0;
    status("off");
  }

  return {
    start() {
      if (dilepas || aktif) return;
      if (window.isSecureContext === false) {
        gagalPermanen("Lokasi memerlukan koneksi HTTPS atau localhost");
        return;
      }
      if (!navigator.geolocation) {
        gagalPermanen("Lokasi tidak didukung di browser ini");
        return;
      }
      aktif = true;
      sesuaikanVisibilitas();
    },
    stop,
    setVisible(nilai) {
      terlihat = !!nilai;
      sesuaikanVisibilitas();
    },
    destroy() {
      if (dilepas) return;
      stop();
      dilepas = true;
      document.removeEventListener("visibilitychange", sesuaikanVisibilitas);
      window.removeEventListener("pagehide", saatKeluar);
      window.removeEventListener("pageshow", saatKembali);
    },
  };
}
