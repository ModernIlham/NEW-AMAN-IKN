/**
 * Penjaga: "Perbarui PPK pada BAST" harus benar-benar bisa MEMILIH.
 *
 * Laporan pemilik (verbatim): *"jika ada 2 ppk disaat itu juga ppk yang
 * terpilih malah yang terakhir, harusnya bisa memilih hingga 3 atau lebih ppk
 * sesuai yang terdaftar di tanggal tersebut."*
 *
 * Kelas cacat yang diperbaiki sangat khas dan sangat mudah kembali: daftar
 * pilihan SUDAH disusun di layar ini, lalu dibuang tanpa pernah ditampilkan
 * (`void pilihan`), dan yang dikirim ke server selalu `"auto"`. Endpoint PUT-nya
 * sejak dulu menerima id eksplisit — jadi selama bertahun-bulan fiturnya ada di
 * server tetapi mustahil dijangkau dari layar.
 *
 * Uji ini menjaga bentuk kodenya (bukan komentarnya): dropdown terpasang,
 * nilainya benar-benar dikirim, kandidat diambil per TANGGAL BAST, dan tak ada
 * lagi pengiriman "auto" yang dipaku.
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..");
const baca = (rel) => fs.readFileSync(path.join(SRC, rel), "utf8");

const HALAMAN = "pages/PengadaanPage.jsx";
const DIALOG = "components/ui/TransitionDialog.jsx";

/** Buang komentar blok & baris supaya assert tak lolos karena prosa. */
function tanpaKomentar(kode) {
  return kode.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

describe("dialog bersama: tipe select", () => {
  const dialog = tanpaKomentar(baca(DIALOG));

  test("merender <select> native, bukan portal melayang", () => {
    expect(dialog).toMatch(/f\.type === "select"/);
    expect(dialog).toMatch(/<select id=\{`trx-\$\{f\.key\}`\}/);
    expect(dialog).toMatch(/\(f\.opsi \|\| \[\]\)\.map/);
  });

  test("pilihan bernilai KOSONG tak dianggap 'belum diisi'", () => {
    // "Kosongkan penetapan" bernilai "" dan merupakan aksi yang SAH. Tanpa
    // pengecualian ini, field select yang wajib akan memblokirnya selamanya.
    expect(dialog).toMatch(/f\.wajib && f\.type !== "select"/);
  });
});

describe("Perbarui PPK pada BAST", () => {
  const halaman = tanpaKomentar(baca(HALAMAN));

  test("dropdown PPK benar-benar ditampilkan", () => {
    expect(halaman).toMatch(/type: "select"/);
    expect(halaman).toMatch(/key: "ppk"/);
    expect(halaman).toMatch(/mintaTransisi\(\{/);
    // Dialognya harus dirender — hook tanpa render = dialog tak pernah muncul.
    expect(halaman).toMatch(/\{transitionDialog\}/);
    expect(halaman).toMatch(/useTransitionDialog\(\)/);
  });

  test("yang dikirim ke server adalah PILIHAN operator, bukan 'auto' dipaku", () => {
    expect(halaman).toMatch(/ppk_pejabat_id: nilai\.ppk/);
    expect(halaman).not.toMatch(/ppk_pejabat_id: "auto"/);
  });

  test("daftar pilihan tak lagi disusun lalu dibuang", () => {
    // Inilah bug aslinya, dan bentuknya cukup khas untuk dijaga langsung.
    expect(halaman).not.toMatch(/void pilihan/);
    expect(halaman).not.toMatch(/const pilihan = \[/);
  });

  test("kandidat diambil PER TANGGAL BAST, bukan seluruh PPK sepanjang masa", () => {
    // Menawarkan PPK yang SK-nya sudah berakhir pada tanggal itu mengundang
    // penetapan yang tak bisa dipertanggungjawabkan.
    expect(halaman).toMatch(/params: \{ peran: "ppk", \.\.\.\(tgl \? \{ per_tanggal: tgl \} : \{\}\) \}/);
    expect(halaman).toMatch(/kandidat = r\.data\?\.kandidat \|\| \[\]/);
    expect(halaman).toMatch(/const tgl = String\(p\.tanggal_bast \|\| ""\)\.slice\(0, 10\)/);
  });

  test("ketiga pilihan tetap tersedia: otomatis, tiap kandidat, kosongkan", () => {
    expect(halaman).toMatch(/id: "auto"/);
    expect(halaman).toMatch(/\.\.\.kandidat\.map\(\(pj\) => \(\{/);
    expect(halaman).toMatch(/id: "", label: "Kosongkan penetapan"/);
  });

  test("label 'Otomatis' menyebut siapa yang akan terpilih", () => {
    // Tanpa ini, operator menekan "Otomatis" tanpa tahu hasilnya — dan justru
    // ketidaktahuan itulah yang membuat bug ini terasa seperti kesalahan diam.
    expect(halaman).toMatch(/const otomatis = kandidat\[0\]/);
    expect(halaman).toMatch(/SK terbaru/);
  });

  test("adanya lebih dari satu PPK dikatakan terus terang", () => {
    expect(halaman).toMatch(/kandidat\.length > 1/);
  });

  test("server tak menjawab → tetap menawarkan pilihan, bukan menyerah", () => {
    expect(halaman).toMatch(/kandidat = opsiPpk;/);
  });
});
