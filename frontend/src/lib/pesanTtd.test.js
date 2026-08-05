/**
 * Uji penyusun pesan permintaan tanda tangan.
 *
 * Mandat pemilik: pesan lama hanya "judul + tautan", sehingga penanda tangan
 * harus MEMBUKA tautan sekadar untuk tahu dokumen apa itu — dan berbulan-bulan
 * kemudian tak ada jejak yang bisa dicari di riwayat percakapannya.
 */
import { pesanTtd, subjekTtd, barisKeterangan } from "./pesanTtd";

const RINGKAS = {
  nomor: "BAST-77/OIKN/2026",
  perihal: "Mutasi/Alih Pemegang Barang Milik Negara",
  tanggal: "2026-08-04",
  pihak: ["Budi Santoso (Pihak Pertama)", "Ani Lestari (Pihak Kedua)"],
  barang: [
    { kode: "3.05.01.01.001", nup: "12", nama: "Laptop" },
    { kode: "3.05.02.01.003", nup: "4", nama: "Printer" },
  ],
  jumlah_barang: 7,
};

describe("pesanTtd", () => {
  test("memuat nomor, perihal, barang (kode+NUP+nama) dan para pihak", () => {
    const t = pesanTtd("Budi Santoso", "BAST", "https://x/s/K7m2QxV9pT", RINGKAS);
    expect(t).toContain("BAST-77/OIKN/2026");
    expect(t).toContain("Mutasi/Alih Pemegang Barang Milik Negara");
    expect(t).toContain("3.05.01.01.001 / NUP 12 — Laptop");
    expect(t).toContain("3.05.02.01.003 / NUP 4 — Printer");
    expect(t).toContain("Budi Santoso (Pihak Pertama)");
    expect(t).toContain("Ani Lestari (Pihak Kedua)");
    expect(t).toContain("https://x/s/K7m2QxV9pT");
  });

  test("sisa barang diringkas — jumlahnya tetap jujur", () => {
    const t = pesanTtd("Budi", "BAST", "https://x/s/abc", RINGKAS);
    expect(t).toContain("(+5 barang lainnya)");   // 7 total, 2 ditampilkan
  });

  test("tanpa ringkasan, pesan menyusut sendiri tanpa baris kosong", () => {
    const t = pesanTtd("Budi", "Dokumen Unggahan", "https://x/s/abc", null);
    expect(t).toContain("Yth. Budi");
    expect(t).toContain("Dokumen Unggahan");      // judul jadi perihal
    expect(t).toContain("https://x/s/abc");
    expect(t).not.toContain("Nomor");
    expect(t).not.toContain("undefined");
    expect(t).not.toContain("null");
  });

  test("barang tanpa NUP tetap terbaca", () => {
    const b = barisKeterangan("BAST", {
      barang: [{ kode: "3.05.01", nup: "", nama: "Meja" }], jumlah_barang: 1 });
    expect(b.join("\n")).toContain("3.05.01 — Meja");
  });

  test("hanya jumlah barang (tanpa rincian) tetap diberitahukan", () => {
    const b = barisKeterangan("BAST", { barang: [], jumlah_barang: 12 });
    expect(b.join("\n")).toContain("12 unit");
  });

  test("subjek email menyertakan nomor bila ada", () => {
    expect(subjekTtd("BAST", RINGKAS)).toContain("BAST-77/OIKN/2026");
    expect(subjekTtd("Dokumen", {})).toBe(
      "Permintaan Tanda Tangan Elektronik — Dokumen");
  });
});


// ── Bentuk yang selamat di layar penerima ──────────────────────────────────
//
// Keluhan pemilik disertai tangkapan pesan yang sudah diterima: labelnya tak
// sejajar, nilainya terlempar ke baris sendiri, dan baris barang ke-2/ke-3
// menggantung tanpa keterangan.
//
// Akarnya: bentuk lama meratakan label dengan spasi ganjal (`Nomor    : `) dan
// menyambung daftar dengan indentasi 11 spasi. Keduanya mengandaikan monospace
// + spasi yang dipertahankan — WhatsApp tak memenuhi keduanya.
describe("bentuk pesan tahan di WhatsApp maupun email", () => {
  const semuaBaris = (t) => t.split("\n");
  const PESAN = pesanTtd("Budi", "BAST", "https://x/s/abc", RINGKAS);

  test("tak ada baris yang diawali spasi", () => {
    // Indentasi = cara lama menyambung daftar. WhatsApp menciutkannya, dan
    // barisnya kehilangan induk.
    expect(semuaBaris(PESAN).filter((b) => /^\s+/.test(b))).toEqual([]);
  });

  test("tak ada ganjalan spasi ganda untuk meratakan kolom", () => {
    // `Nomor    : ` hanya lurus di font monospace; di WhatsApp tak pernah.
    expect(semuaBaris(PESAN).filter((b) => /\S {2,}/.test(b))).toEqual([]);
  });

  test("tiap butir daftar diawali peluru, bukan spasi", () => {
    const butir = semuaBaris(PESAN).filter((b) => b.includes(" — ")
      || b.includes("(Pihak "));
    expect(butir.length).toBeGreaterThanOrEqual(4);   // 2 barang + 2 pihak
    butir.forEach((b) => expect(b.startsWith("• ")).toBe(true));
  });

  test("jalur EMAIL tetap polos — tanpa penanda yang tercetak mentah", () => {
    // `mailto:` tak mengenal penanda; "*Barang*" terbaca apa adanya di sana.
    expect(PESAN).not.toMatch(/[*_~]/);
  });

  test("daftar punya judulnya sendiri, dipisah baris kosong", () => {
    expect(PESAN).toContain("\n\nBarang (7 unit):\n");
    expect(PESAN).toContain("\n\nPihak:\n");
  });

  test("jumlah total tampil di judul daftar barang", () => {
    // Sebelumnya total hanya tersirat dari "(+N lainnya)" — penerima harus
    // menjumlah sendiri untuk tahu ia meneken berapa unit.
    expect(barisKeterangan("BAST", RINGKAS)).toContain("Barang (7 unit):");
  });

  test("kelompok kosong tak meninggalkan baris kosong menggantung", () => {
    // Judul dikosongkan agar perihal tak terisi darinya — yang diuji di sini
    // pemisah antarkelompok, bukan pengisian perihal.
    const b = barisKeterangan("", { nomor: "X" });
    expect(b).toEqual(["Nomor: X"]);
    expect(b.join("\n")).not.toMatch(/\n\s*\n/);
  });

  test("tanpa identitas, daftar tak diawali baris kosong", () => {
    const b = barisKeterangan("", { barang: [{ kode: "K1", nama: "Meja" }],
                                    jumlah_barang: 1 });
    expect(b[0]).toBe("Barang (1 unit):");
  });

  test("sapaan tak buntung saat nama kosong", () => {
    expect(pesanTtd("", "BAST", "https://x/s/abc", RINGKAS))
      .toContain("Yth. Bapak/Ibu,");
    expect(pesanTtd(null, "BAST", "https://x/s/abc", null))
      .not.toContain("Yth. ,");
  });

  test("tautan tetap berdiri sendiri di barisnya — tak tercampur teks", () => {
    // Baris tautan yang bercampur kata membuat sebagian peramban WA memotong
    // tautannya saat ditekan.
    expect(semuaBaris(PESAN)).toContain("https://x/s/abc");
  });
});


// ── Penanda WhatsApp ───────────────────────────────────────────────────────
//
// Mandat pemilik: label TEBAL (`*Teks*`) dan butir daftar berawalan `* ` supaya
// WhatsApp merapikannya sebagai daftar ber-indentasi.
//
// Penanda ini HANYA untuk WhatsApp. Pesan yang sama juga dikirim lewat
// `mailto:` yang tak mengenal penanda sama sekali — di sana asterisknya
// tercetak apa adanya, jadi jalur email wajib tetap polos.
describe("penanda WhatsApp", () => {
  const WA = pesanTtd("Budi", "BAST", "https://x/s/abc", RINGKAS,
                      { penandaWa: true });
  const barisWa = WA.split("\n");

  test("label ditebalkan", () => {
    expect(WA).toContain("*Nomor:* BAST-77/OIKN/2026");
    expect(WA).toContain("*Tanggal:* 2026-08-04");
    expect(WA).toContain("*Barang (7 unit):*");
    expect(WA).toContain("*Pihak:*");
  });

  test("BINTANG PENUTUP MENEMPEL — tanpa spasi ganjal sebelumnya", () => {
    // Inti kegagalan lama: `*Barang   : *` punya spasi sebelum bintang penutup,
    // dan WhatsApp hanya menebalkan bila penutupnya menempel pada karakter
    // bukan-spasi. Akibatnya bintangnya sendiri yang tampil di layar penerima.
    expect(WA).not.toMatch(/ \*(\s|$)/m);
    barisWa.filter((b) => b.startsWith("*") && !b.startsWith("* "))
      .forEach((b) => expect(b).toMatch(/^\*\S.*\S\*/));
  });

  test("butir daftar berawalan '* ' — perintah daftar WhatsApp", () => {
    const butir = barisWa.filter((b) => b.includes(" — ") || b.includes("(Pihak "));
    expect(butir.length).toBeGreaterThanOrEqual(4);
    butir.forEach((b) => expect(b.startsWith("* ")).toBe(true));
  });

  test("judul daftar TIDAK ikut jadi butir daftar", () => {
    // "*Barang...*" diawali bintang tapi TANPA spasi sesudahnya — WhatsApp
    // membacanya sebagai tebal, bukan butir. Kalau sampai jadi "* Barang",
    // judulnya melebur ke dalam daftar.
    expect(WA).not.toContain("* Barang (");
    expect(WA).not.toContain("* Pihak:");
  });

  test("sapaan, tautan, dan penutup tak ikut ditandai", () => {
    expect(WA).toContain("Yth. Budi,");
    expect(barisWa).toContain("https://x/s/abc");
    expect(WA).toContain("Terima kasih.");
  });

  test("isinya sama dengan jalur polos — hanya penandanya yang beda", () => {
    const polos = pesanTtd("Budi", "BAST", "https://x/s/abc", RINGKAS);
    const bersih = WA.replace(/\*/g, "").replace(/^ /gm, "");
    expect(bersih).toBe(polos.replace(/• /g, ""));
  });

  test("bentuknya tetap rapi: tanpa indentasi & tanpa spasi ganjal", () => {
    expect(barisWa.filter((b) => /^\s+/.test(b))).toEqual([]);
    expect(barisWa.filter((b) => /\S {2,}/.test(b))).toEqual([]);
  });

  test("bawaan pesanTtd TETAP polos — email tak boleh ikut tertandai", () => {
    expect(pesanTtd("Budi", "BAST", "https://x/s/abc", RINGKAS))
      .not.toMatch(/[*_~]/);
  });
});


// ── hasilTtd: penyalinan respons "kirim-ttd" ───────────────────────────────
//
// Keluhan pemilik: "share link lewat WhatsApp di riwayat BAST … tidak sama
// formatnya dengan yang di TTD elektronik".
//
// Akarnya BUKAN pesannya — melainkan penyalinan respons server. Layar Riwayat
// BAST menyusun sendiri `{judul, links}` sehingga `ringkas` ikut terbuang;
// pesan WA-nya lalu menyusut jadi perihal + tautan saja. Tak ada galat, tombol
// tetap jalan, pesannya cuma lebih pendek — kesalahan yang tak terlihat.
import { hasilTtd } from "./pesanTtd";

const RESPONS = {
  id: "sr-1",
  judul: "BAST 123/BMN/2026",
  links: [{ nama: "Budi", link: "https://x/s/abc" }],
  ringkas: {
    nomor: "123/BMN/2026",
    tanggal: "2026-08-05",
    barang: [{ kode: "3100102001", nup: "7", nama: "Genset" }],
    pihak: ["Budi (Penyerah)", "Wati (Penerima)"],
  },
};

describe("hasilTtd", () => {
  test("INTI: `ringkas` IKUT tersalin — bukan terbuang", () => {
    expect(hasilTtd(RESPONS, "BAST").ringkas).toEqual(RESPONS.ringkas);
  });

  test("pesan WA hasilnya SAMA dengan jalur TTD Elektronik", () => {
    // Pembanding: jalur TTD Elektronik meneruskan respons apa adanya.
    const dariTtdElektronik = pesanTtd(
      "Budi", RESPONS.judul, RESPONS.links[0].link, RESPONS.ringkas);
    const h = hasilTtd(RESPONS, "BAST");
    const dariRiwayatBast = pesanTtd("Budi", h.judul, h.links[0].link, h.ringkas);
    expect(dariRiwayatBast).toBe(dariTtdElektronik);
    // …dan memang membawa keterangannya, bukan sekadar dua string yang sama-sama kosong.
    expect(dariRiwayatBast).toContain("123/BMN/2026");
    expect(dariRiwayatBast).toContain("Genset");
    expect(dariRiwayatBast).toContain("Wati (Penerima)");
  });

  test("judul bawaan hanya dipakai bila server tak mengirimnya", () => {
    expect(hasilTtd({ links: [] }, "BAST").judul).toBe("BAST");
    expect(hasilTtd(RESPONS, "BAST").judul).toBe("BAST 123/BMN/2026");
  });

  test("respons tanpa ringkas / rusak tak meledak", () => {
    expect(hasilTtd(null).ringkas).toBeNull();
    expect(hasilTtd({}).links).toEqual([]);
    // links non-array (server lama/galat) tak boleh membuat `.map` melempar.
    expect(hasilTtd({ links: "bukan array" }).links).toEqual([]);
  });
});
