/**
 * Penjaga KELAS CACAT: `col-span-N` tanpa prefiks `sm:` di dalam grid yang
 * seharusnya SATU KOLOM di HP.
 *
 * Laporan pemilik (dengan tangkapan layar popup "Catat Perolehan"):
 * *"di mode HP sangat berantakan komposisinya."*
 *
 * Penyebabnya satu baris kelas yang tampak benar:
 *
 *     <div className="grid grid-cols-1 sm:grid-cols-2">   ← niatnya 1 kolom di HP
 *       …
 *       <div className="col-span-2">…</div>               ← TAPI ini merusaknya
 *
 * Di CSS Grid, anak yang membentang 2 kolom pada grid 1-kolom membuat browser
 * MENUMBUHKAN kolom implisit kedua. Jadi seluruh dialog diam-diam menjadi dua
 * kolom sempit di HP — label terpotong ("Pembelian (APB…"), tanggal terpotong
 * ("07/08/20…"), dan tinggi antar-kolom tak sejajar. Kelasnya tetap tertulis
 * `grid-cols-1`, jadi membaca kode saja tak memperlihatkan cacatnya.
 *
 * Yang BENAR untuk "penuh di HP, setengah/penuh di desktop":
 *   - penuh di kedua ukuran  → `sm:col-span-2`  (di HP otomatis penuh)
 *   - penuh di HP, ½ desktop → `sm:col-span-1`  (JANGAN tambahkan col-span-2)
 *
 * Uji ini memindai SELURUH berkas .jsx dan menuntut nol pelanggaran. Ia menjaga
 * kelasnya, bukan satu dialog — saat ditulis, cacat yang sama hidup di 70 titik
 * pada 14 berkas, dan hanya satu di antaranya yang sempat dilaporkan pemilik.
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

/**
 * Elemen ber-`grid` terdekat yang MEMBUNGKUS baris ke-i.
 *
 * Dicari lewat indentasi, bukan jendela teks: induk sebuah elemen JSX selalu
 * ber-indentasi lebih kecil. Jendela teks polos akan salah menuduh anak dari
 * grid BERSARANG yang memang 2 kolom di HP (mis. kartu "Daftar barang" pada
 * Catat Perolehan, atau grid tombol pada CetakStikerDialog) — dan tuduhan
 * palsu pada penjaga seperti ini akan membuatnya dimatikan orang, bukan
 * dipatuhi.
 */
function indukGrid(baris, i) {
  const indent = baris[i].length - baris[i].trimStart().length;
  for (let j = i - 1; j >= 0 && j > i - 400; j -= 1) {
    const b = baris[j];
    if (!b.trim()) continue;
    const jd = b.length - b.trimStart().length;
    if (jd >= indent) continue;
    if (b.includes("grid-cols-") || /className="[^"]*\bgrid\b/.test(b)) return b.trim();
  }
  return "";
}

describe("grid satu-kolom di HP tak boleh ditumbuhi kolom implisit", () => {
  test("tak ada col-span-N tanpa sm: di dalam grid-cols-1 sm:grid-cols-2", () => {
    const pelanggaran = [];
    for (const f of berkasJsx(SRC)) {
      const baris = fs.readFileSync(f, "utf8").split("\n");
      baris.forEach((b, i) => {
        // `(?<!:)` menolak `sm:col-span-2` / `lg:col-span-2` — yang bermasalah
        // hanya col-span TANPA breakpoint, karena itulah yang berlaku di HP.
        if (!/(?<!:)\bcol-span-\d\b/.test(b)) return;
        if (/grid-cols-1\s+sm:grid-cols-2/.test(indukGrid(baris, i))) {
          pelanggaran.push(`${path.relative(SRC, f)}:${i + 1}  →  ${b.trim().slice(0, 72)}`);
        }
      });
    }
    expect(pelanggaran).toEqual([]);
  });

  test("penjaganya benar-benar bisa menangkap — bukan regex yang selalu lolos", () => {
    // Tanpa uji ini, sebuah regex yang salah ketik akan lulus selamanya dengan
    // daftar kosong dan memberi rasa aman palsu.
    const contoh = [
      '        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">',
      '          <div>',
      '            <label>Aman</label>',
      '          </div>',
      '          <div className="col-span-2">',
      '            <label>Melanggar</label>',
      '          </div>',
      '        </div>',
    ];
    const kena = contoh
      .map((b, i) => (/(?<!:)\bcol-span-\d\b/.test(b)
        && /grid-cols-1\s+sm:grid-cols-2/.test(indukGrid(contoh, i)) ? i : -1))
      .filter((i) => i >= 0);
    expect(kena).toEqual([4]);
  });

  test("grid yang MEMANG 2 kolom di HP tidak dituduh", () => {
    // `col-span-2` pada grid 2-kolom adalah pemakaian yang sah — penjaga yang
    // menuduhnya akan dimatikan orang, bukan dipatuhi.
    const contoh = [
      '        <div className="grid grid-cols-2 sm:grid-cols-[1fr_5rem_9rem] gap-2">',
      '          <div className="col-span-2 sm:col-span-1">',
      '            <label>Sah</label>',
      '          </div>',
      '        </div>',
    ];
    const kena = contoh
      .map((b, i) => (/(?<!:)\bcol-span-\d\b/.test(b)
        && /grid-cols-1\s+sm:grid-cols-2/.test(indukGrid(contoh, i)) ? i : -1))
      .filter((i) => i >= 0);
    expect(kena).toEqual([]);
  });
});

describe("dialog Catat Perolehan — komposisi yang dilaporkan pemilik", () => {
  const halaman = fs.readFileSync(path.join(SRC, "pages/PengadaanPage.jsx"), "utf8");
  const dialog = halaman.slice(halaman.indexOf("Dialog perolehan baru"));

  test("Tanggal BAST & Keterangan berpasangan — tak menyisakan sel kosong", () => {
    // Sebelumnya keduanya dipisah oleh nota penjelas, sehingga masing-masing
    // meninggalkan satu sel kosong di desktop.
    const iTgl = dialog.indexOf('htmlFor="pgd-tgl"');
    const iKet = dialog.indexOf('htmlFor="pgd-ket"');
    const iNota = dialog.indexOf("BAST ini adalah serah terima dari");
    expect(iTgl).toBeGreaterThan(-1);
    expect(iKet).toBeGreaterThan(iTgl);
    expect(iNota).toBeGreaterThan(iKet);
  });

  test("kartu barang tetap 2 kolom di HP — jumlah & harga berdampingan", () => {
    // Grid DALAM ini sengaja 2 kolom di HP; penyapuan tak boleh ikut mengubahnya.
    expect(dialog).toMatch(/grid grid-cols-2 sm:grid-cols-\[1fr_5rem_9rem\]/);
    expect(dialog).toMatch(/className="col-span-2 sm:col-span-1"/);
  });
});
