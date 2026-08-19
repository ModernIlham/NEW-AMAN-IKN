/**
 * Kejelasan kode klasifikasi arsip pada nomor surat.
 *
 * KELUHAN YANG DIJAWAB BERKAS INI: "Master Kode Klasifikasi Arsip di setting
 * penomoran ketika sudah diisi ditambahkan, efeknya tidak menghasilkan apa
 * apa pada bagian dari penomoran."
 *
 * Memang begitu — dan itu memang rancangannya: master klasifikasi adalah
 * KATALOG kode. Yang benar-benar mengubah nomor ada tiga, berurutan:
 *
 *   1. kode yang DIISI MANUAL di form booking (selalu menang),
 *   2. ATURAN OTOMATIS (modul / jenis naskah → kode) di pengaturan penomoran.
 *
 * Dulu ada yang ketiga — KODE BAWAAN sebagai jaring terakhir — dan itu justru
 * melahirkan keluhan berikutnya: *"tolong bedakan Kode Klasifikasi Bawaan
 * (fallback) berdiri sendiri dan Kode Klasifikasi Arsip berdiri sendiri,
 * independent masing masing"*. Selama ia jadi jaring, kode bawaan menempati
 * slot klasifikasi arsip pada nomor, dan layar menyebutnya "klasifikasi arsip
 * surat ini". Sekarang kode bawaan punya slotnya sendiri, `{kode_bawaan}`,
 * dan hanya masuk nomor bila format memang memintanya.
 *
 * Sebuah kode yang cuma didaftarkan di katalog tak menyentuh satu pun dari
 * keduanya. Sebelumnya layar tak pernah mengatakan itu, jadi kode yang
 * menganggur tampak persis sama dengan kode yang bekerja. Helper di sini
 * menerjemahkan penanda dari server menjadi kalimat yang menyebut keadaan
 * sebenarnya — beserta langkah berikutnya.
 */

/** Label sumber kode pada pratinjau nomor (`sumber_klasifikasi` dari server). */
export function teksSumberKlasifikasi(pratinjau) {
  if (!pratinjau) return "";
  const kode = String(pratinjau.kode_klasifikasi || "").trim();
  const sumber = String(pratinjau.sumber_klasifikasi || "").trim();
  // Tak ada lagi cabang "bawaan" — dan itu inti perbaikannya. Kalimat lama
  // "Klasifikasi: SATKER-D · kode bawaan pengaturan" menamai kode bawaan
  // sebagai klasifikasi arsip surat ini; dua hal berbeda, satu nama.
  const asal = sumber === "eksplisit" ? "diisi manual"
    : sumber === "pemetaan" ? "otomatis dari aturan pemetaan"
      : "belum ada aturan otomatis — isi manual bila surat ini perlu kode";
  return `${kode || "(kosong)"} · ${asal}`;
}

const HIJAU = "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400";
const KUNING = "bg-amber-500/10 text-amber-700 dark:text-amber-400";

/**
 * Status sebuah entri master: apakah kode ini BENAR-BENAR memengaruhi nomor?
 * `item` = entri dari GET /persuratan/klasifikasi
 * ({dipakai_aturan, bawaan, bawaan_di_nomor}).
 *
 * `bawaan_di_nomor` menjawab pertanyaan yang dulu tak perlu ditanyakan: sejak
 * Kode Klasifikasi Bawaan berdiri sendiri, menjadi kode bawaan TIDAK otomatis
 * berarti ikut ke nomor — ia ikut hanya bila format memuat `{kode_bawaan}`.
 * Badge yang tetap menghijau tanpa syarat akan mengulang persis kesalahan yang
 * melahirkannya: memberi tahu bahwa sebuah kode bekerja, padahal tidak.
 * @returns {{teks: string, warna: string, aktif: boolean}}
 */
export function statusKodeKlasifikasi(item) {
  const n = Number(item?.dipakai_aturan || 0);
  const bawaan = !!item?.bawaan;
  const bawaanBekerja = bawaan && !!item?.bawaan_di_nomor;
  if (bawaan && n > 0) {
    return {
      teks: bawaanBekerja ? `kode bawaan + ${n} aturan`
        : `kode bawaan (tak di nomor) + ${n} aturan`,
      aktif: true, warna: HIJAU,
    };
  }
  if (bawaan) {
    return bawaanBekerja
      ? { teks: "kode bawaan", aktif: true, warna: HIJAU }
      // Kode bawaan yang formatnya tak pernah meminta = kode menganggur.
      : { teks: "kode bawaan (tak di nomor)", aktif: false, warna: KUNING };
  }
  if (n > 0) {
    return { teks: n === 1 ? "1 aturan" : `${n} aturan`, aktif: true,
      warna: HIJAU };
  }
  // Inilah keadaan yang membuat pemilik mengira fiturnya rusak.
  return { teks: "belum dipakai", aktif: false, warna: KUNING };
}

/** Cakupan aturan dalam bahasa manusia — kembar dengan `sebut_cakupan` backend. */
export function sebutCakupan(modul, jenisNaskah) {
  const m = String(modul || "").trim();
  const j = String(jenisNaskah || "").trim();
  if (m && j) return `modul ${m} + ${j}`;
  if (m) return `modul ${m}, semua jenis naskah`;
  if (j) return `${j}, semua modul`;
  return "semua modul & semua jenis naskah";
}
