/**
 * Penjaga: layar pelacakan harus HIDUP, bukan potret saat halaman dibuka.
 *
 * Keluhan pemilik (verbatim): *"tidak akurat menampilkan real-time mengambil
 * posisi lat lng secara langsung … dan mengirimkan koordinat gpsnya terus
 * menerus."*
 *
 * Penelusuran menemukan tiga penyebab yang seluruhnya buatan sendiri, dan
 * ketiganya adalah kelas cacat yang mudah kembali diam-diam saat berkas ini
 * disunting nanti:
 *
 *   1. `/lacak` merekam paling cepat sekali per menit — angka mati di dalam
 *      komponen, tanpa cara mengubahnya.
 *   2. `PelacakanPage` memuat SEKALI lalu diam selamanya; posisi yang sudah
 *      mendarat di server tak pernah muncul sampai seseorang menekan muat
 *      ulang.
 *   3. Usia "terakhir terdengar" hanya dalam MENIT, sehingga perangkat yang
 *      baru saja mengirim dan yang sunyi 59 detik sama-sama tertulis "0 mnt".
 *
 * Uji ini menjaga bentuk kodenya, bukan komentarnya — semua pola di bawah
 * dicocokkan ke ekspresi yang benar-benar dijalankan.
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..");
const baca = (rel) => fs.readFileSync(path.join(SRC, rel), "utf8");

const LACAK = "pages/LacakPage.jsx";
const PELACAKAN = "pages/PelacakanPage.jsx";

/** Buang komentar blok & baris supaya assert tak bisa lolos karena prosa. */
function tanpaKomentar(kode) {
  return kode.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

// ── /lacak: kadensi jadi pilihan yang berlaku HIDUP ─────────────────────────

describe("pendamping /lacak", () => {
  const lacak = tanpaKomentar(baca(LACAK));

  test("angka kadensi datang dari modul bersama, bukan konstanta lokal", () => {
    expect(lacak).toMatch(/from "@\/lib\/kadensiLacak"/);
    // Konstanta lama harus benar-benar HILANG. Menyisakannya berarti ada dua
    // sumber angka, dan yang tak dipakai akan menyesatkan penyunting berikutnya.
    expect(lacak).not.toMatch(/const JEDA_BERGERAK_MS\s*=/);
    expect(lacak).not.toMatch(/const JEDA_DIAM_MS\s*=/);
    expect(lacak).not.toMatch(/const AMBANG_DIAM_M\s*=/);
    expect(lacak).not.toMatch(/const JEDA_KIRIM_MS\s*=/);
  });

  test("callback watchPosition membaca kadensi dari REF, bukan closure state", () => {
    // Inilah yang membuat penggantian mode berlaku SEKETIKA. Membacanya dari
    // state berarti callback yang dipasang saat Mulai memegang nilai lama
    // selamanya — menu yang tampak bekerja tapi tidak.
    expect(lacak).toMatch(/const k = kadensiRef\.current;/);
    expect(lacak).toMatch(/jarakM\(acuanRef\.current, titik\) > k\.ambang_diam/);
    expect(lacak).toMatch(/bergerak \? k\.jeda_bergerak : k\.jeda_diam/);
    // Ref-nya harus benar-benar disegarkan saat state berubah.
    expect(lacak).toMatch(/kadensiRef\.current = profilKadensi\(kadensi\)/);
  });

  test("timer pengiriman dipasang ulang saat kadensi berganti", () => {
    // Tanpa `prof.jeda_kirim` di deps, interval lama tetap hidup dan mode
    // aktif tak mempercepat apa pun sampai perekaman dihentikan.
    expect(lacak).toMatch(
      /setInterval\(kirimAntrean, prof\.jeda_kirim\)[\s\S]{0,200}?\[jalan, kirimAntrean, prof\.jeda_kirim\]/);
  });

  test("pemilih kadensi terpasang & pilihannya disimpan", () => {
    expect(lacak).toMatch(/data-testid="lacak-kadensi"/);
    expect(lacak).toMatch(/simpanKadensi\(window\.localStorage, k\.kunci\)/);
    expect(lacak).toMatch(/bacaKadensi\(window\.localStorage\)/);
  });

  test("batas peramban TETAP dinyatakan, tak tertutup fitur baru", () => {
    // Bahaya terbesar dari menu ini adalah ia terbaca sebagai janji bahwa
    // pelacakan kini berjalan di latar belakang. Peringatan lama wajib
    // bertahan, dan wajib menyebut bahwa kadensi tercepat pun tak mengubahnya.
    const utuh = baca(LACAK);
    expect(utuh).toMatch(/Halaman ini harus tetap terbuka/);
    expect(utuh).toMatch(/kerapatan tercepat[\s\S]{0,40}tidak mengubahnya/);
  });

  test("mode boros memberi peringatan baterai", () => {
    expect(lacak).toMatch(/prof\.boros &&/);
    expect(lacak).toMatch(/data-testid="lacak-kadensi-peringatan"/);
  });
});

// ── Layar Pelacakan: menyegarkan diri & berdenyut ───────────────────────────

describe("halaman Pelacakan", () => {
  const pelacakan = tanpaKomentar(baca(PELACAKAN));

  test("daftar menyegarkan diri secara berkala", () => {
    expect(pelacakan).toMatch(/setInterval\(\(\) => muat\(true\), JEDA_SEGAR_MS\)/);
    expect(pelacakan).toMatch(/const JEDA_SEGAR_MS = 20_000;/);
  });

  test("penyegaran berhenti saat tab tersembunyi dan bangun saat kembali", () => {
    // Halaman ini lazim ditinggal terbuka seharian. Tanpa gerbang ini ia
    // menembak permintaan ke VPS selamanya untuk layar yang tak dilihat.
    expect(pelacakan).toMatch(/document\.addEventListener\("visibilitychange"/);
    expect(pelacakan).toMatch(/document\.removeEventListener\("visibilitychange"/);
    expect(pelacakan).toMatch(/if \(document\.hidden\) \{ berhenti\(\); return; \}/);
  });

  test("penyegaran otomatis bisa dimatikan operator", () => {
    expect(pelacakan).toMatch(/data-testid="pelacakan-auto-segar"/);
    expect(pelacakan).toMatch(/if \(!autoSegar\) return undefined;/);
  });

  test("muat senyap tak memutar spinner, dan SEMUA handler membungkus muat", () => {
    expect(pelacakan).toMatch(/async \(senyap = false\)/);
    expect(pelacakan).toMatch(/if \(!senyap\) setMemuat\(true\);/);
    // Jebakan yang membuat parameter `senyap` berbahaya: `onClick={muat}`
    // mengoper objek event React sebagai argumen pertama — objek itu truthy,
    // jadi klik MANUAL justru berjalan senyap dan operator tak melihat tanda
    // apa pun bahwa tombolnya bekerja.
    expect(pelacakan).not.toMatch(/onClick=\{muat\}/);
    expect(pelacakan).not.toMatch(/onUlang=\{muat\}/);
    expect(pelacakan).toMatch(/onClick=\{\(\) => muat\(\)\}/);
    expect(pelacakan).toMatch(/onUlang=\{\(\) => muat\(\)\}/);
  });

  test("usia dihitung dari SELISIH DETIK server, bukan cap waktu ISO-nya", () => {
    // `ts_server` yang naif akan dibaca peramban sebagai waktu LOKAL; operator
    // di WIB akan melihat "terakhir 1 jam lalu" untuk perangkat yang baru saja
    // mengirim. Selisih detik kebal terhadap zona.
    expect(pelacakan).toMatch(
      /detikAwal \+ Math\.max\(0, Math\.round\(\(Date\.now\(\) - dimuatPada\) \/ 1000\)\)/);
    expect(pelacakan).toMatch(/detikAwal=\{d\.kesehatan\?\.diam_detik\}/);
    // Jam hidup berdenyut di komponennya sendiri — timer di halaman akan
    // merender ulang seluruh daftar tiap detik.
    expect(pelacakan).toMatch(/function UsiaHidup\(/);
    expect(pelacakan).toMatch(/setInterval\(\(\) => tik\(\(n\) => n \+ 1\), 1000\)/);
  });

  test("perangkat yang belum pernah mengirim tak tampil sebagai '0 dtk'", () => {
    expect(pelacakan).toMatch(
      /if \(detikAwal === null \|\| detikAwal === undefined\)[\s\S]{0,200}?Belum pernah mengirim/);
  });

  test("dua penjelas kesunyian terpasang di kartu perangkat", () => {
    // Perangkat berprofil `wilayah` di luar jam kerja MEMANG tak menyimpan
    // apa-apa. Tanpa kalimat ini, satu-satunya cara mengetahuinya adalah
    // membaca privasi_utils.saring_observasi.
    expect(pelacakan).toMatch(/petaProfil\[d\.profil_privasi\]\?\.presisi === "wilayah"/);
    expect(pelacakan).toMatch(/diLuarJamAktif\(petaProfil\[d\.profil_privasi\], new Date\(\)\)/);
    expect(pelacakan).toMatch(/data-testid=\{`pelacakan-luar-jam-\$\{d\.id\}`\}/);
  });

  test("helper usia lama tak lagi ada duanya", () => {
    // `lamaDiam` digantikan `usiaSingkat`. Meninggalkannya berarti dua
    // pemformat usia yang bisa menyimpang.
    expect(pelacakan).not.toMatch(/function lamaDiam\(/);
    expect(pelacakan).toMatch(/from "@\/lib\/kadensiLacak"/);
  });
});
