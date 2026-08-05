/**
 * Penjaga: dialog yang MENJANJIKAN berbagi lewat WhatsApp/email harus benar-
 * benar menyediakan tombolnya.
 *
 * Dialog tautan TTD LPB (Persediaan & Pengadaan) berbunyi "Bagikan lewat
 * WhatsApp/email bila pengiriman otomatis tak aktif", tetapi selama berbulan-
 * bulan satu-satunya tombol di sana adalah "Salin". Operator yang membacanya
 * mencari tombol yang tak pernah ada — dan tak ada galat apa pun yang bisa
 * menandainya, karena tak ada yang rusak: yang salah justru JANJINYA.
 *
 * Uji ini membaca sumbernya, bukan me-render halamannya (repo belum punya uji
 * render komponen), jadi ia menangkap kelas kesalahan itu saja: teks berjanji
 * tanpa pemanggilan `bagikanWa`/`bagikanEmail` di berkas yang sama.
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..");

/** Semua .jsx di bawah src/ (rekursif). */
function berkasJsx(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return berkasJsx(p);
    return e.isFile() && e.name.endsWith(".jsx") ? [p] : [];
  });
}

// Kalimat janji: menyebut WhatsApp DAN email dalam satu baris teks UI.
const JANJI = /Bagikan\s+lewat\s+WhatsApp\s*\/\s*email/i;

const semua = berkasJsx(SRC).map((f) => ({
  nama: path.relative(SRC, f),
  isi: fs.readFileSync(f, "utf8"),
}));

describe("janji berbagi WhatsApp/email selalu punya tombolnya", () => {
  const berjanji = semua.filter((f) => JANJI.test(f.isi));

  test("penjaga ini tidak kosong — kalimat janjinya memang ada di kode", () => {
    // Tanpa ini, mengubah bunyi kalimatnya akan membuat penjaga lolos dengan
    // nol berkas diperiksa: hijau yang tak memeriksa apa pun.
    expect(berjanji.length).toBeGreaterThanOrEqual(2);
  });

  test.each(["pages/PersediaanPage.jsx", "pages/PengadaanPage.jsx"])(
    "%s termasuk yang diperiksa", (nama) => {
      expect(berjanji.map((f) => f.nama)).toContain(nama);
    });

  test("tiap berkas yang berjanji memanggil bagikanWa & bagikanEmail", () => {
    const bolong = berjanji
      .filter((f) => !(f.isi.includes("bagikanWa(") && f.isi.includes("bagikanEmail(")))
      .map((f) => f.nama);
    expect(bolong).toEqual([]);
  });

  test("keterangan pesannya tak dibuang — dialognya memakai hasilTtd", () => {
    // Menyusun {nomor, links} dengan tangan membuang `ringkas`, sehingga pesan
    // WA menyusut jadi perihal + tautan (akar keluhan pada Riwayat BAST dulu).
    const bolong = berjanji
      .filter((f) => f.isi.includes("setTautanTtd(") && !f.isi.includes("hasilTtd("))
      .map((f) => f.nama);
    expect(bolong).toEqual([]);
  });
});
