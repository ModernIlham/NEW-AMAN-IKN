/**
 * Uji penjaga nama tamu Peta Kolaborasi — regresi bug "selalu Tamu".
 *
 * Bug aslinya: aksi ditahan sebagai closure React lalu dijalankan pada tick
 * yang sama dengan setNama(), sehingga aksi masih membaca nama LAMA (kosong).
 * POST terkirim `oleh: ""` → backend menyimpannya sebagai "Tamu" PERMANEN.
 * Uji ini mengunci kontraknya: nama datang sebagai ARGUMEN, bukan dari state.
 */
import { buatPenjagaNama } from "./penjagaNama";

describe("buatPenjagaNama", () => {
  test("INTI: aksi tertunda menerima nama BARU sebagai argumen", () => {
    const p = buatPenjagaNama();
    const dipanggil = [];
    const perlu = p.jalankan((n) => dipanggil.push(n), { perluNama: true, nama: "" });

    expect(perlu).toBe(true);          // dialog harus dibuka
    expect(dipanggil).toEqual([]);     // aksi belum jalan

    p.lanjutkan("Budi Santoso");
    expect(dipanggil).toEqual(["Budi Santoso"]);   // BUKAN "" dan BUKAN "Tamu"
  });

  test("nama yang sudah ada langsung dipakai tanpa membuka dialog", () => {
    const p = buatPenjagaNama();
    const dipanggil = [];
    const perlu = p.jalankan((n) => dipanggil.push(n), { perluNama: true, nama: "Ani" });
    expect(perlu).toBe(false);
    expect(dipanggil).toEqual(["Ani"]);
  });

  test("nama berisi spasi saja tetap dianggap kosong", () => {
    const p = buatPenjagaNama();
    expect(p.jalankan(() => {}, { perluNama: true, nama: "   " })).toBe(true);
  });

  test("pengguna login (perluNama=false) tak pernah ditanya", () => {
    const p = buatPenjagaNama();
    const dipanggil = [];
    const perlu = p.jalankan((n) => dipanggil.push(n), { perluNama: false, nama: "" });
    expect(perlu).toBe(false);
    expect(dipanggil).toEqual([""]);   // backend memakai identitas sesi, bukan ini
  });

  test("batal membuang aksi — tak ada kiriman siluman setelahnya", () => {
    const p = buatPenjagaNama();
    const dipanggil = [];
    p.jalankan((n) => dipanggil.push(n), { perluNama: true, nama: "" });
    expect(p.adaTertunda()).toBe(true);
    p.batalkan();
    expect(p.adaTertunda()).toBe(false);
    expect(p.lanjutkan("Budi")).toBe(false);
    expect(dipanggil).toEqual([]);
  });

  test("lanjutkan dua kali hanya menjalankan sekali (anti kirim ganda)", () => {
    const p = buatPenjagaNama();
    const dipanggil = [];
    p.jalankan((n) => dipanggil.push(n), { perluNama: true, nama: "" });
    expect(p.lanjutkan("Budi")).toBe(true);
    expect(p.lanjutkan("Budi")).toBe(false);
    expect(dipanggil).toEqual(["Budi"]);
  });

  test("aksi berikutnya tak mewarisi aksi lama", () => {
    const p = buatPenjagaNama();
    const urut = [];
    p.jalankan(() => urut.push("pertama"), { perluNama: true, nama: "" });
    p.jalankan(() => urut.push("kedua"), { perluNama: true, nama: "" });
    p.lanjutkan("Budi");
    expect(urut).toEqual(["kedua"]);   // hanya yang terakhir ditahan
  });
});
