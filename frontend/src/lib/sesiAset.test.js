import { buatSesiAset, fotoNyasar } from "./sesiAset";

describe("buatSesiAset", () => {
  test("aset yang sudah ada dibedakan oleh id-nya", () => {
    expect(buatSesiAset("a1", 0)).not.toBe(buatSesiAset("a2", 0));
  });

  test("dua aset BARU berturut-turut TIDAK boleh berpenanda sama", () => {
    // Inti alur "Simpan & Aset Baru": keduanya belum punya id, jadi kalau
    // penanda hanya bersandar pada id, keduanya identik dan foto aset kedua
    // bisa menempel di aset pertama tanpa terdeteksi.
    expect(buatSesiAset(null, 0)).not.toBe(buatSesiAset(null, 1));
  });

  test("penanda yang sama untuk aset & hitungan yang sama", () => {
    expect(buatSesiAset("a1", 3)).toBe(buatSesiAset("a1", 3));
  });

  test("hitungan tak sah dianggap nol, bukan NaN", () => {
    // `NaN#NaN` tak pernah sama dengan dirinya sendiri bila dibandingkan lewat
    // Number — di sini string, tapi tetap: nilai rusak jangan sampai membuat
    // SETIAP foto dianggap nyasar.
    expect(buatSesiAset("a1", undefined)).toBe(buatSesiAset("a1", 0));
    expect(buatSesiAset("a1", NaN)).toBe(buatSesiAset("a1", 0));
  });
});

describe("fotoNyasar", () => {
  test("penanda cocok → foto diterima", () => {
    expect(fotoNyasar("a1#0", "a1#0")).toBe(false);
  });

  test("form sudah pindah aset → foto DITOLAK", () => {
    expect(fotoNyasar("a1#0", "a2#0")).toBe(true);
  });

  test("simpan-lalu-aset-baru di tengah jepretan → foto DITOLAK", () => {
    // Persis kejadian saat rana ditekan bersamaan dengan "Simpan & Aset Baru".
    expect(fotoNyasar("baru#0", "baru#1")).toBe(true);
  });

  test("pemanggil tanpa penanda tetap diterima — unggah galeri tak boleh mati", () => {
    expect(fotoNyasar(undefined, "a1#0")).toBe(false);
    expect(fotoNyasar(null, "a1#0")).toBe(false);
  });
});
