/**
 * KADENSI PENDAMPING PELACAKAN + jam hidup layar Pelacakan.
 *
 * Keluhan pemilik (verbatim): *"tidak akurat menampilkan real-time mengambil
 * posisi lat lng secara langsung … dan mengirimkan koordinat gpsnya terus
 * menerus."*
 *
 * Penelusuran menemukan bahwa sebagian besar keterlambatan itu BUKAN batas
 * peramban, melainkan angka yang kita pilih sendiri: `/lacak` merekam paling
 * cepat sekali per menit, menganggap pergeseran di bawah 25 m sebagai "diam"
 * lalu melambat ke 15 menit, dan menahan antrean 2 menit sebelum mengirim.
 * Untuk perjalanan dinas yang sedang diawasi, tiga angka itu menjumlah menjadi
 * jeda tampil yang terasa seperti kerusakan.
 *
 * Modul ini menjadikan ketiganya PILIHAN, bukan konstanta tersembunyi — dan
 * memisahkannya dari komponen supaya bisa diuji tanpa DOM, GPS, atau jam.
 *
 * Angka `hemat` SENGAJA sama persis dengan yang berlaku sebelum berkas ini
 * ada (60 dtk / 15 mnt / ambang 25 m / kirim 2 mnt, docs/ARSITEKTUR-SPASIAL-IOT
 * §8.4 #20): mode bawaan tidak boleh diam-diam memboroskan kuota data dan
 * baterai perangkat lapangan hanya karena kami menambahkan sebuah menu.
 */

/**
 * Tiga kadensi. `jeda_kirim` terpendek (15 dtk) = 4 permintaan/menit, jauh di
 * bawah plafon `@limiter.limit("60/minute")` pada `POST /iot/observasi` —
 * mode tercepat pun tak boleh membuat perangkat sendiri kena rate-limit.
 */
export const KADENSI = {
  hemat: {
    kunci: "hemat",
    label: "Hemat baterai",
    ringkas: "1 menit saat bergerak · 15 menit saat diam",
    jeda_bergerak: 60_000,
    jeda_diam: 900_000,
    ambang_diam: 25,
    jeda_kirim: 120_000,
    boros: false,
  },
  sedang: {
    kunci: "sedang",
    label: "Sedang",
    ringkas: "30 detik saat bergerak · 5 menit saat diam",
    jeda_bergerak: 30_000,
    jeda_diam: 300_000,
    ambang_diam: 15,
    jeda_kirim: 60_000,
    boros: false,
  },
  aktif: {
    kunci: "aktif",
    label: "Pemantauan aktif",
    ringkas: "10 detik saat bergerak · 1 menit saat diam",
    jeda_bergerak: 10_000,
    jeda_diam: 60_000,
    ambang_diam: 8,
    jeda_kirim: 15_000,
    boros: true,
  },
};

export const KADENSI_BAWAAN = "hemat";
export const KUNCI_KADENSI = "aman_lacak_kadensi";

/** Profil bernama, atau profil BAWAAN bila namanya tak dikenal.
 *
 * Gagal ke `hemat` (bukan ke yang tercepat) meniru `profil_privasi` di server:
 * nilai rusak — localStorage yang diedit tangan, sisa versi lama — harus
 * mendarat di pilihan yang paling tak merugikan pemegang perangkat. */
export function profilKadensi(nama) {
  return KADENSI[String(nama || "").trim()] || KADENSI[KADENSI_BAWAAN];
}

export function bacaKadensi(simpanan) {
  try {
    return profilKadensi(simpanan?.getItem(KUNCI_KADENSI)).kunci;
  } catch {
    return KADENSI_BAWAAN;               // mode privat/kuota penuh
  }
}

export function simpanKadensi(simpanan, kunci) {
  try {
    simpanan?.setItem(KUNCI_KADENSI, profilKadensi(kunci).kunci);
  } catch { /* penyimpanan ditolak — pilihan tetap berlaku untuk sesi ini */ }
}

/**
 * Usia dalam kalimat sependek mungkin: "12 dtk", "5 mnt", "3 jam", "2 hari".
 *
 * `null`/negatif → "—". Perangkat yang belum pernah mengirim TIDAK boleh
 * tampil "0 dtk lalu"; itu kebalikan dari kenyataannya.
 */
export function usiaSingkat(detik) {
  if (detik === null || detik === undefined) return "—";
  const d = Math.floor(Number(detik));
  if (!Number.isFinite(d) || d < 0) return "—";
  if (d < 60) return `${d} dtk`;
  if (d < 3600) return `${Math.floor(d / 60)} mnt`;
  if (d < 86_400) return `${Math.floor(d / 3600)} jam`;
  return `${Math.floor(d / 86_400)} hari`;
}

/** Ambang "masih terdengar" (detik). Dipilih 2× jeda kirim mode teraktif +
 * kelonggaran jaringan, jadi perangkat yang sehat di mode mana pun tak
 * berkedip merah hanya karena satu batch tertunda. */
export const AMBANG_HIDUP_DETIK = 90;

export function masihHidup(detik) {
  return typeof detik === "number" && detik >= 0 && detik <= AMBANG_HIDUP_DETIK;
}

/**
 * Apakah SEKARANG berada di luar jam aktif profil privasi perangkat?
 *
 * Ini menjawab pertanyaan yang paling sering disalahartikan sebagai kerusakan:
 * perangkat berprofil `personal` yang mengirim di luar 07:00–18:00 WITA atau
 * di akhir pekan memang TIDAK menyimpan apa-apa — `saring_observasi` membuang
 * observasinya di jalur tulis, dengan sengaja. Layar yang tak mengatakannya
 * membiarkan operator menyimpulkan pelacakannya rusak.
 *
 * Perhitungan memakai `zona_offset_jam` yang DIKIRIM SERVER, bukan zona
 * peramban: operator yang membuka layar ini dari WIB tak boleh melihat
 * gerbang jam yang berbeda dari yang benar-benar ditegakkan di server.
 *
 * Mengembalikan `null` bila profilnya tanpa gerbang jam atau datanya belum
 * lengkap — "tidak tahu" bukan "sedang aktif".
 */
export function diLuarJamAktif(profil, sekarang) {
  const mulai = profil?.jam_mulai;
  const selesai = profil?.jam_selesai;
  if (typeof mulai !== "number" || typeof selesai !== "number") return null;
  const kini = sekarang instanceof Date ? sekarang : new Date(sekarang);
  if (Number.isNaN(kini.getTime())) return null;
  const offset = typeof profil.zona_offset_jam === "number"
    ? profil.zona_offset_jam : 8;
  // Digeser lalu dibaca lewat getter UTC — satu-satunya cara membaca jam
  // dinding zona lain tanpa menyentuh zona peramban yang menjalankannya.
  const geser = new Date(kini.getTime() + offset * 3_600_000);
  if (profil.hari_kerja_saja) {
    const hari = geser.getUTCDay();                 // 0 = Minggu, 6 = Sabtu
    if (hari === 0 || hari === 6) return true;
  }
  const jam = geser.getUTCHours();
  return !(jam >= mulai && jam < selesai);
}
