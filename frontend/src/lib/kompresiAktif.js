/**
 * Layanan kompresi mana yang SEDANG dipakai — bagian murni indikator kuota.
 *
 * Laporan lapangan: angka di toolbar menunjukkan **0/500** padahal Compresto
 * masih menyisakan 474. Rantainya sendiri sehat — server memang beralih
 * Tinify → Compresto → Uploadcare → Pillow saat kuota habis. Yang keliru
 * indikatornya: ia memilih layanan dengan bendera `available`, dan `available`
 * berarti *"percobaan TERAKHIR terbukti berhasil"* — catatan diagnostik di
 * memori server yang hangus tiap kali proses restart. Setelah satu deploy,
 * layanan yang sehat pun kembali `available: false`, dan indikator jatuh ke
 * `quotas[0]` (Tinify) yang kuotanya nol.
 *
 * Yang benar-benar menentukan giliran hanya dua hal — sama persis dengan yang
 * diperiksa `compress_with_*` di server: **kuncinya terpasang** dan
 * **kuotanya belum habis**.
 *
 * Server kini menghitungnya sendiri dan mengirimnya sebagai `aktif`; fungsi di
 * sini menghormati jawaban itu lalu menghitung ulang bila tak ada (mis. saat
 * peramban masih memegang jawaban lama dari cache).
 */

// Cerminan `backend/kompresi_rantai.URUTAN` dan `URUTAN_PDF`.
export const URUTAN = ["tinify", "compresto", "uploadcare", "pillow"];
export const URUTAN_PDF = ["ilovepdf", "pypdf"];

/**
 * Sebab yang layak DITAMPILKAN pada satu baris layanan — "" bila tak ada.
 *
 * Hanya keadaan yang BISA DITINDAKLANJUTI yang bersuara: layanan gagal, atau
 * kuncinya belum dipasang. Status `belum_dicoba` sengaja DIAM — ia bukan
 * masalah (hilang sendiri setelah satu unggahan), dan menampilkannya membuat
 * panel dipenuhi paragraf tiga baris yang tak menuntut tindakan apa pun.
 * Itulah keluhan "kembalikan ke desain yang simple".
 */
export function sebabTampil(entri) {
  const e = entri || {};
  const perluTindakan = e.status === "gagal" || e.terpasang === false;
  return perluTindakan && e.alasan ? String(e.alasan) : "";
}

/** Sisa kuota satu entri. Negatif = tak terbatas (Pillow lokal). */
export function sisaKuota(entri) {
  const e = entri || {};
  const batas = Number(e.limit);
  if (Number.isFinite(batas) && batas < 0) return -1;
  const sisa = Number(e.remaining);
  if (e.remaining !== null && e.remaining !== undefined && Number.isFinite(sisa)) {
    return sisa;
  }
  if (!Number.isFinite(batas)) return 0;
  const terpakai = Number(e.used);
  return Math.max(0, batas - (Number.isFinite(terpakai) ? terpakai : 0));
}

/** True bila layanan ini benar-benar akan dicoba oleh rantai. */
export function layakPakai(entri) {
  const e = entri || {};
  if (!e.terpasang) return false;
  return sisaKuota(e) !== 0;
}

function prioritas(nama) {
  const i = URUTAN.indexOf(nama);
  return i < 0 ? URUTAN.length : i;   // tak dikenal → paling belakang
}

/**
 * Entri layanan yang melayani permintaan berikutnya.
 *
 * `aktifServer` (dari payload) diutamakan supaya layar dan server tak pernah
 * menjawab berbeda; ia hanya diabaikan bila menunjuk layanan yang tak ada di
 * daftar.
 */
export function entriAktif(kuota, aktifServer) {
  const daftar = Array.isArray(kuota) ? kuota.filter(Boolean) : [];
  if (!daftar.length) return null;

  if (aktifServer) {
    const dariServer = daftar.find((q) => q.service === aktifServer);
    if (dariServer) return dariServer;
  }

  const urut = daftar.slice().sort(
    (a, b) => prioritas(a.service) - prioritas(b.service));
  return urut.find(layakPakai) || null;
}

/**
 * Ringkasan siap-tampil untuk chip toolbar.
 *
 * `habisSemua` sengaja dibedakan dari "tak ada data": bila SELURUH layanan
 * berkuota habis, Pillow tetap mengambil alih — jadi keadaan itu bukan
 * kegagalan dan tak boleh dicat merah seperti alarm.
 */
export function ringkasAktif(kuota, aktifServer) {
  const entri = entriAktif(kuota, aktifServer);
  if (!entri) {
    return { entri: null, nama: "", teks: "—", takTerbatas: false, persen: 0 };
  }
  const sisa = sisaKuota(entri);
  const takTerbatas = sisa < 0;
  const batas = Number(entri.limit);
  const terpakai = Number(entri.used);
  const persen = !takTerbatas && Number.isFinite(batas) && batas > 0
    ? Math.min(100, (Number.isFinite(terpakai) ? terpakai : 0) / batas * 100)
    : 0;
  return {
    entri,
    nama: entri.name || entri.service || "",
    teks: takTerbatas ? "∞" : String(sisa),
    takTerbatas,
    persen,
  };
}
