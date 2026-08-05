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
