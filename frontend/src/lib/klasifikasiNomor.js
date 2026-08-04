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
 *   2. ATURAN OTOMATIS (modul / jenis naskah → kode) di pengaturan penomoran,
 *   3. KODE BAWAAN pengaturan sebagai jaring terakhir.
 *
 * Sebuah kode yang cuma didaftarkan di katalog tak menyentuh satu pun dari
 * ketiganya. Sebelumnya layar tak pernah mengatakan itu, jadi kode yang
 * menganggur tampak persis sama dengan kode yang bekerja. Helper di sini
 * menerjemahkan penanda dari server menjadi kalimat yang menyebut keadaan
 * sebenarnya — beserta langkah berikutnya.
 */

/** Label sumber kode pada pratinjau nomor (`sumber_klasifikasi` dari server). */
export function teksSumberKlasifikasi(pratinjau) {
  if (!pratinjau) return "";
  const kode = String(pratinjau.kode_klasifikasi || "").trim();
  const sumber = String(pratinjau.sumber_klasifikasi || "").trim();
  const asal = sumber === "eksplisit" ? "diisi manual"
    : sumber === "pemetaan" ? "otomatis dari aturan pemetaan"
      : sumber === "bawaan" ? "kode bawaan pengaturan"
        : "belum ada aturan maupun kode bawaan";
  return `${kode || "(kosong)"} · ${asal}`;
}

/**
 * Status sebuah entri master: apakah kode ini BENAR-BENAR memengaruhi nomor?
 * `item` = entri dari GET /persuratan/klasifikasi ({dipakai_aturan, bawaan}).
 * @returns {{teks: string, warna: string, aktif: boolean}}
 */
export function statusKodeKlasifikasi(item) {
  const n = Number(item?.dipakai_aturan || 0);
  if (item?.bawaan && n > 0) {
    return {
      teks: `kode bawaan + ${n} aturan`, aktif: true,
      warna: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
    };
  }
  if (item?.bawaan) {
    return {
      teks: "kode bawaan", aktif: true,
      warna: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
    };
  }
  if (n > 0) {
    return {
      teks: n === 1 ? "1 aturan" : `${n} aturan`, aktif: true,
      warna: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
    };
  }
  // Inilah keadaan yang membuat pemilik mengira fiturnya rusak.
  return {
    teks: "belum dipakai", aktif: false,
    warna: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  };
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
