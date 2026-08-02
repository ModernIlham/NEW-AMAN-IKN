import { labelDilepas, lebarItem, PX_PER_HURUF, PX_LABEL_EKSTRA } from "./labelRingkas";

const daftar = [
  { kunci: "kartu", lebarIkon: 32, label: "Cetak Kartu (1150)" },
  { kunci: "hapus", lebarIkon: 32, label: "Hapus Semua" },
  { kunci: "stiker", lebarIkon: 32, label: "Stiker" },
  { kunci: "import", lebarIkon: 32, label: "Import" },
  { kunci: "export", lebarIkon: 32, label: "Export" },
];

describe("lebarItem", () => {
  it("menjumlahkan ikon + panjang label", () => {
    expect(lebarItem({ lebarIkon: 32, label: "Stiker" })).toBeCloseTo(
      32 + 6 * PX_PER_HURUF + PX_LABEL_EKSTRA,
    );
  });

  it("tanpa label = lebar ikon saja (tanpa padding label)", () => {
    expect(lebarItem({ lebarIkon: 32 })).toBe(32);
    expect(lebarItem({ lebarIkon: 32, label: "" })).toBe(32);
  });

  it("lebarPenuh eksplisit menang atas taksiran panjang label", () => {
    // Select menyempit alih-alih kehilangan teks — lebarnya disebut langsung.
    expect(lebarItem({ lebarIkon: 88, lebarPenuh: 160, label: "diabaikan" })).toBe(160);
  });
});

describe("labelDilepas", () => {
  it("ruang berlimpah = tak satu pun label dilepas", () => {
    expect(labelDilepas(4000, daftar).size).toBe(0);
  });

  it("melepas label SATU PER SATU mengikuti urutan daftar", () => {
    // Sempitkan bertahap: himpunan yang dilepas harus tumbuh dari kiri daftar,
    // bukan meloncat. Inilah "jadikan iconnya saja satu persatu".
    const urut = [];
    for (let w = 700; w >= 150; w -= 10) {
      const lepas = labelDilepas(w, daftar);
      const kunci = daftar.filter((d) => lepas.has(d.kunci)).map((d) => d.kunci);
      if (kunci.length !== urut.length) urut.push(kunci.join(","));
    }
    expect(urut).toEqual([
      "kartu",
      "kartu,hapus",
      "kartu,hapus,stiker",
      "kartu,hapus,stiker,import",
      "kartu,hapus,stiker,import,export",
    ]);
  });

  it("berhenti melepas begitu barisnya muat", () => {
    // Cukup melepas label terpanjang saja → sisanya tetap berlabel.
    const lepas = labelDilepas(
      lebarItem(daftar[0]) === 0 ? 0 : 340,
      daftar,
    );
    expect(lepas.has("kartu")).toBe(true);
    expect(lepas.has("export")).toBe(false);
  });

  it("hasil monoton: makin sempit tak pernah MENGEMBALIKAN label", () => {
    let sebelum = -1;
    for (let w = 800; w >= 100; w -= 7) {
      const n = labelDilepas(w, daftar).size;
      if (sebelum >= 0) expect(n).toBeGreaterThanOrEqual(sebelum);
      sebelum = n;
    }
  });

  it("lebarTetap ikut diperhitungkan (judul/indikator yang tak melipat)", () => {
    const lebar = 700;
    expect(labelDilepas(lebar, daftar).size).toBe(0);
    expect(labelDilepas(lebar, daftar, { lebarTetap: 400 }).size).toBeGreaterThan(0);
  });

  it("lebar belum terukur = paling ringkas, bukan paling lebar", () => {
    // Render pertama sebelum ResizeObserver menyala. Menebak 'lebar' di sini
    // akan menampilkan baris meluber ber-scrollbar selama satu frame.
    for (const w of [0, -5, NaN, undefined, null]) {
      expect(labelDilepas(w, daftar).size).toBe(daftar.length);
    }
  });

  it("daftar kosong tidak meledak", () => {
    expect(labelDilepas(500, []).size).toBe(0);
    expect(labelDilepas(500, null).size).toBe(0);
  });

  it("tak pernah melepas lebih dari isi daftar walau ruangnya mustahil", () => {
    expect(labelDilepas(1, daftar).size).toBe(daftar.length);
  });
});
