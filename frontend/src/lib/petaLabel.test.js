/**
 * Penataan label nama aset di peta.
 *
 * Permintaan pemilik: *"tambahkan fitur label yang menampilkan nama-nama
 * asetnya … pastikan rapi mengingat ada cluster dan berdekatan satu dengan
 * lainnya."*
 *
 * Yang diuji di sini sifat penataannya, bukan rupanya: label yang bertindih
 * tak menghilang dengan sendirinya — ia menjadi coretan hitam-putih di atas
 * peta, dan tak satu pun galat memberi tahu.
 */
import {
  JARAK_DARI_MARKER, LEBAR_MAKS, MAKS_BARIS, MAKS_LABEL, SISIPAN_X,
  SISIPAN_Y, TINGGI_BARIS, kotakLabel, pilihLabelTampil, ukurLabel,
} from "./petaLabel";

const kotak = (kiri, atas, kanan, bawah) => ({ kiri, atas, kanan, bawah });

describe("ukurLabel", () => {
  test("teks kosong tak berukuran sama sekali", () => {
    expect(ukurLabel("").lebar).toBe(0);
    expect(ukurLabel(null).tinggi).toBe(0);
    expect(ukurLabel("   ").baris).toBe(0);
  });

  test("nama panjang MEMBUNGKUS, tidak melebar tanpa batas", () => {
    // Label selebar layar menutupi petanya sendiri; yang dibatasi lebarnya,
    // bukan teksnya — tak ada nama yang dipotong.
    const panjang = ukurLabel("Alat Laboratorium Pendidikan Kedokteran Lainnya");
    expect(panjang.lebar).toBeLessThanOrEqual(LEBAR_MAKS + SISIPAN_X * 2);
    expect(panjang.baris).toBeGreaterThan(1);
  });

  test("makin panjang namanya makin tinggi kotaknya", () => {
    const pendek = ukurLabel("Meja");
    const panjang = ukurLabel("Meja Kerja Kayu Jati Ukuran Besar Ruang Rapat Lantai Dua");
    expect(panjang.tinggi).toBeGreaterThan(pendek.tinggi);
  });

  test("nama pendek TIDAK dipaksa selebar maksimum", () => {
    // Kotak yang ditaksir terlalu lebar membuat label bertetangga dinilai
    // bertabrakan padahal keduanya muat berdampingan.
    expect(ukurLabel("Meja").lebar).toBeLessThan(LEBAR_MAKS);
  });
});

describe("kotakLabel", () => {
  test("label duduk di BAWAH marker dan rata tengah terhadapnya", () => {
    // Titik jangkar kedua gaya marker (pin 22×22 dan marker foto 46×54)
    // sama-sama di TENGAH-BAWAH ikonnya, jadi satu penempatan "bawah"
    // membuat label rapi di tengah pada keduanya — permintaan pemilik.
    const k = kotakLabel(100, 200, "Meja");
    expect((k.kiri + k.kanan) / 2).toBeCloseTo(100, 5);
    expect(k.atas).toBe(200 + JARAK_DARI_MARKER);
    expect(k.bawah).toBeGreaterThan(k.atas);
  });

  test("kotak SEJALAN dengan yang tergambar, bukan di kanan marker", () => {
    /* PENJAGA REGRESI. Kotak dulu dihitung di KANAN marker karena tooltipnya
       memang `direction: "right"`. Setelah label pindah ke bawah, kotak yang
       tertinggal di kanan membuat penata anti-tindih menyembunyikan label yang
       sebenarnya lega dan meloloskan label yang sebenarnya bertindih —
       tabrakan yang dihitungnya bukan tabrakan yang terjadi. */
    const k = kotakLabel(100, 200, "Meja");
    expect(k.kiri).toBeLessThan(100);      // membentang ke KIRI titik marker
    expect(k.atas).toBeGreaterThan(200);   // seluruhnya di BAWAH titik marker
  });

  test("label paling banyak DUA baris", () => {
    // Label yang mengalir lebih panjang menutupi marker tetangganya — dan
    // justru marker itulah yang sedang dicari mata. Sisanya dipotong
    // ber-elipsis oleh CSS; angka di sini harus sama dengan di index.css.
    const panjang = "MERTANI Sensor Kualitas Udara (Sensor Kebisingan) GT-2.EF1";
    expect(ukurLabel(panjang).baris).toBe(MAKS_BARIS);
    expect(ukurLabel("A".repeat(400)).baris).toBe(MAKS_BARIS);
    expect(ukurLabel("Meja").baris).toBe(1);
  });

  test("tinggi kotak ikut terbatas dua baris", () => {
    const panjang = "A".repeat(400);
    const pendek = "Meja";
    expect(ukurLabel(panjang).tinggi)
      .toBe(MAKS_BARIS * TINGGI_BARIS + SISIPAN_Y * 2);
    expect(ukurLabel(panjang).tinggi)
      .toBeGreaterThan(ukurLabel(pendek).tinggi);
  });
});

describe("pilihLabelTampil", () => {
  test("label yang TIDAK bertabrakan semuanya tampil", () => {
    const tampil = pilihLabelTampil([
      { id: "a", kotak: kotak(0, 0, 50, 20) },
      { id: "b", kotak: kotak(60, 0, 110, 20) },
      { id: "c", kotak: kotak(0, 30, 50, 50) },
    ]);
    expect([...tampil].sort()).toEqual(["a", "b", "c"]);
  });

  test("dari dua label yang bertindih, HANYA yang lebih diprioritaskan tampil", () => {
    const tampil = pilihLabelTampil([
      { id: "a", kotak: kotak(0, 0, 50, 20) },
      { id: "b", kotak: kotak(10, 5, 60, 25) },
    ]);
    expect([...tampil]).toEqual(["a"]);
  });

  test("label yang bersentuhan TEPI saja tidak dianggap bertabrakan", () => {
    // Tepi yang berimpit masih terbaca; menganggapnya bertabrakan membuang
    // label tanpa alasan pada peta yang tersusun rapi berjajar.
    const tampil = pilihLabelTampil([
      { id: "a", kotak: kotak(0, 0, 50, 20) },
      { id: "b", kotak: kotak(50, 0, 100, 20) },
    ]);
    expect(tampil.size).toBe(2);
  });

  test("urutan kandidat MENENTUKAN siapa yang bertahan", () => {
    const dua = [
      { id: "a", kotak: kotak(0, 0, 50, 20) },
      { id: "b", kotak: kotak(10, 5, 60, 25) },
    ];
    expect([...pilihLabelTampil(dua)]).toEqual(["a"]);
    expect([...pilihLabelTampil([...dua].reverse())]).toEqual(["b"]);
  });

  test("peta yang TERLALU PADAT tak dilabeli sama sekali", () => {
    // Label yang tersisa setelah tabrakan hanya segelintir yang tersebar acak,
    // dan pembaca tak punya cara menebak mengapa justru yang itu yang bernama.
    const banyak = Array.from({ length: MAKS_LABEL + 1 }, (_, i) => ({
      id: `a${i}`, kotak: kotak(i * 200, 0, i * 200 + 50, 20),
    }));
    expect(pilihLabelTampil(banyak).size).toBe(0);
    // …tepat di ambangnya masih dilabeli.
    expect(pilihLabelTampil(banyak.slice(0, MAKS_LABEL)).size).toBe(MAKS_LABEL);
  });

  test("daftar kosong / bukan larik tak melempar galat", () => {
    expect(pilihLabelTampil([]).size).toBe(0);
    expect(pilihLabelTampil(null).size).toBe(0);
    expect(pilihLabelTampil(undefined).size).toBe(0);
  });

  test("kandidat tanpa kotak dilewati, bukan meruntuhkan sapuan", () => {
    const tampil = pilihLabelTampil([
      { id: "a" },
      { id: "b", kotak: kotak(0, 0, 50, 20) },
    ]);
    expect([...tampil]).toEqual(["b"]);
  });

  test("satu label yang sama tak pernah menghalangi dirinya sendiri", () => {
    const tampil = pilihLabelTampil([{ id: "a", kotak: kotak(0, 0, 50, 20) }]);
    expect(tampil.has("a")).toBe(true);
  });
});
