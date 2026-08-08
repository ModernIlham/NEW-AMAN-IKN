/**
 * Penjaga: kepala Wasdal & Perencanaan jadi SATU MENU di HP.
 *
 * Permintaan pemilik (verbatim):
 *   *"Kepala halaman Wasdal & Perencanaan lebur menjadi satu menu saja pada
 *   mode tampilan HP."*
 *
 * Dua halaman ini adalah sisa terakhir yang belum memakai `MenuKepala`.
 * Keduanya membawa TIGA tombol aksi; diukur pada 360 px, tiga tombol + blok
 * judul ber-lantai 9rem (`LANTAI_JUDUL`) tak muat sebaris, sehingga baris
 * kepala membungkus — keluhan yang sama persis seperti Pengadaan dulu.
 *
 * Bentuk yang dipakai adalah CANGKANG GANDA, bukan penghapusan tombol:
 *   - `sm:hidden`      → satu <MenuKepala> berisi semua aksi (HP)
 *   - `hidden sm:flex` → tombol-tombol seperti semula (≥640 px, ruang cukup)
 *
 * Yang mudah rusak diam-diam dan karena itu dikunci di sini:
 *
 *   1. Daftar unduhan ditulis SEKALI (`const UNDUHAN`) lalu dipakai kedua
 *      cangkang. Menyalinnya dua kali berarti suatu hari salah satunya
 *      ketinggalan saat laporan baru ditambahkan — dan yang ketinggalan hampir
 *      pasti cangkang yang jarang dibuka pengembangnya.
 *   2. Tak ada aksi yang HILANG saat dipindahkan; ia cuma berpindah tempat.
 *   3. Tombol tanggalan Perencanaan disembunyikan di HP, TAPI komponennya
 *      tetap terpasang — `<input type="date">` miliknyalah yang dipanggil
 *      butir menu. Menyembunyikan seluruh komponen membuat butir menu itu
 *      jadi tombol mati (jebakan yang serumpun dengan jebakan Radix pada
 *      BookingNomorButton).
 *   4. Tanggal acuan tetap TERBACA tanpa membuka menu — ia menentukan TA
 *      seluruh angka di halaman itu.
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..");
const baca = (rel) => fs.readFileSync(path.join(SRC, rel), "utf8");

const WASDAL = "pages/WasdalPage.jsx";
const PERENCANAAN = "pages/PerencanaanPage.jsx";
const TANGGALAN = "components/ui/TanggalanButton.jsx";

function tanpaKomentar(kode) {
  return kode.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

/** Blok <header>…</header> pertama sebuah halaman. */
function kepala(kode) {
  const m = kode.match(/<header[\s\S]*?<\/header>/);
  return m ? m[0] : "";
}

describe.each([
  ["Wasdal", WASDAL, "wasdal"],
  ["Perencanaan", PERENCANAAN, "perencanaan"],
])("%s: kepala jadi satu menu di HP", (_nama, berkas, modul) => {
  const kode = baca(berkas);
  const h = tanpaKomentar(kepala(kode));

  test("cangkang HP hanya berisi MenuKepala", () => {
    const m = h.match(/<div className="sm:hidden[^"]*"[\s\S]*?<\/div>/);
    expect(m).not.toBeNull();
    expect(m[0]).toMatch(/<MenuKepala/);
    expect(m[0]).toMatch(new RegExp(`modul="${modul}"`));
    // Persis SATU pemicu di cangkang HP — itulah arti "satu menu saja".
    expect((m[0].match(/<MenuKepala/g) || []).length).toBe(1);
    expect(m[0]).not.toMatch(/<BookingNomorButton/);
    expect(m[0]).not.toMatch(/<TanggalanButton/);
  });

  test("tombol lama tetap ada, tapi hanya dari sm ke atas", () => {
    // Kepala HP yang bersih tak boleh dibayar dengan desktop yang jadi miskin.
    expect(h).toMatch(/hidden sm:(flex|inline-flex)/);
  });

  test("daftar unduhan ditulis sekali & dipakai dua kali", () => {
    expect(kode).toMatch(/const UNDUHAN = \[/);
    // Sekali untuk menu HP (prop ekspor), sekali untuk menu desktop (map).
    expect(h).toMatch(/ekspor=\{UNDUHAN\}/);
    expect(h).toMatch(/UNDUHAN\.map\(/);
  });

  test("tak ada aksi yang hilang — hanya berpindah tempat", () => {
    // Booking nomor tetap terjangkau di kedua ukuran.
    expect(h).toMatch(/booking=\{\{ jenisNaskah:/);
    expect(h).toMatch(/<BookingNomorButton/);
    // Kedua unduhan tetap tercantum di UNDUHAN, bukan tercecer.
    const daftar = kode.slice(kode.indexOf("const UNDUHAN = ["));
    expect((daftar.match(/testid: "/g) || []).length).toBeGreaterThanOrEqual(2);
  });
});

describe("Wasdal — muat ulang tak boleh raib", () => {
  const kode = baca(WASDAL);
  const h = tanpaKomentar(kepala(kode));

  test("muat ulang hadir sebagai butir menu DAN tombol desktop", () => {
    expect(h).toMatch(/id: "reload", label: "Muat ulang"/);
    expect(h).toMatch(/data-testid="wasdal-reload"/);
  });

  test("muat dipanggil TANPA argumen — bukan onClick={muat}", () => {
    // `onClick={muat}` menyerahkan objek event sebagai argumen pertama.
    // Kalau suatu saat muat() menerima parameter (mis. `senyap`), event yang
    // truthy itu diam-diam mengubah perilakunya. Jebakan yang sama pernah
    // menggigit di halaman Pelacakan.
    expect(h).not.toMatch(/onClick=\{muat\}/);
    expect(h).not.toMatch(/onSelect: muat\b/);
    expect(h).toMatch(/onClick=\{\(\) => muat\(\)\}/);
    expect(h).toMatch(/onSelect: \(\) => muat\(\)/);
  });
});

describe("Perencanaan — tanggal acuan tetap hidup di HP", () => {
  const kode = baca(PERENCANAAN);
  const h = tanpaKomentar(kepala(kode));

  test("yang disembunyikan hanya TOMBOLNYA, bukan komponennya", () => {
    // `<TanggalanButton>` tetap dirender; hanya tombolnya yang hilang di HP.
    // Kalau seluruh komponen dibungkus `hidden sm:flex`, input tanggalnya ikut
    // masuk subpohon display:none dan butir menu jadi tombol mati.
    expect(h).toMatch(/<TanggalanButton\s+ref=\{tanggalanRef\}\s+kelasTombol="hidden sm:flex"/);
    expect(h).not.toMatch(/<div className="hidden sm:[a-z-]+">\s*<TanggalanButton/);
  });

  test("butir menu memanggil pemilih tanggal lewat ref, ditunda satu frame", () => {
    // Radix mengembalikan fokus ke pemicu SETELAH menu tertutup; membuka
    // pemilih tanggal pada detik yang sama berarti ia bisa langsung terusir.
    expect(h).toMatch(
      /onSelect: \(\) => requestAnimationFrame\(\(\) => tanggalanRef\.current\?\.buka\(\)\)/);
    expect(kode).toMatch(/const tanggalanRef = useRef\(null\)/);
  });

  test("tanggal acuan terbaca tanpa membuka menu", () => {
    // Ia menentukan TA seluruh angka halaman ini; menyembunyikannya di balik
    // satu ketukan berarti pengguna tak tahu tahun berapa yang dibacanya.
    expect(h).toMatch(/acuan \{tanggalAcuan\}/);
    expect(h).toMatch(/TA \{tahun\}/);
  });
});

describe("TanggalanButton — pintu ref-nya benar-benar ada", () => {
  const t = tanpaKomentar(baca(TANGGALAN));

  test("mengekspos buka() lewat ref, tanpa membuka state internal", () => {
    expect(t).toMatch(/useImperativeHandle\(refLuar, \(\) => \(\{ buka \}\)\)/);
    expect(t).toMatch(/export default React\.forwardRef\(TanggalanButton\)/);
  });

  test("punya jalan mundur bila showPicker gagal", () => {
    // `showPicker()` tak ada di peramban lama dan bisa melempar; tanpa
    // fallback, butir menu di HP akan tampak berfungsi lalu diam saja.
    expect(t).toMatch(/typeof el\.showPicker === "function"/);
    expect(t).toMatch(/catch \{\s*el\.click\(\);/);
  });

  test("kelasTombol hanya menyentuh tombol, bukan input tanggalnya", () => {
    const iInput = t.indexOf('type="date"');
    expect(iInput).toBeGreaterThan(-1);
    expect(t.slice(iInput)).not.toMatch(/kelasTombol/);
  });
});
