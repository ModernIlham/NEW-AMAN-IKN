import { perluPeriksaAkhir, ringkasPembubuhan } from "./ringkasPembubuhan";

describe("ringkasPembubuhan", () => {
  test("memilah halaman ber-ttd dan yang tidak", () => {
    const r = ringkasPembubuhan({ jumlahHalaman: 4, halamanTtd: [2, 4],
                                  halamanDilihat: [1, 2, 3, 4] });
    expect(r.ditandatangani).toEqual([2, 4]);
    expect(r.tanpaTtd).toEqual([1, 3]);
    expect(r.belumDibuka).toEqual([]);
  });

  test("menyebut halaman yang BELUM PERNAH dibuka", () => {
    // Inti laporan pemilik: orangnya menekan Bubuhkan tanpa melihat halaman
    // lain. Yang belum pernah dimuat pratinjaunya adalah fakta pasti.
    const r = ringkasPembubuhan({ jumlahHalaman: 5, halamanTtd: [5],
                                  halamanDilihat: [5] });
    expect(r.belumDibuka).toEqual([1, 2, 3, 4]);
  });

  test("halaman ber-ttd otomatis terhitung dilihat", () => {
    // Mustahil menempatkan kotak di halaman yang tak tampil; menuduhnya
    // "belum dibuka" akan membuat peringatan tampak keliru dan diabaikan.
    const r = ringkasPembubuhan({ jumlahHalaman: 3, halamanTtd: [2],
                                  halamanDilihat: [] });
    expect(r.belumDibuka).toEqual([1, 3]);
  });

  test("urut naik dan tanpa kembar", () => {
    const r = ringkasPembubuhan({ jumlahHalaman: 4, halamanTtd: [4, 2, 2],
                                  halamanDilihat: [3, 3] });
    expect(r.ditandatangani).toEqual([2, 4]);
    expect(r.belumDibuka).toEqual([1]);
  });

  test("halaman di luar jangkauan diabaikan, bukan meracuni daftar", () => {
    const r = ringkasPembubuhan({ jumlahHalaman: 2, halamanTtd: [1, 99, 0, -3],
                                  halamanDilihat: [7] });
    expect(r.ditandatangani).toEqual([1]);
    expect(r.tanpaTtd).toEqual([2]);
    expect(r.belumDibuka).toEqual([2]);
  });

  test("masukan cacat tak melempar", () => {
    expect(() => ringkasPembubuhan()).not.toThrow();
    expect(ringkasPembubuhan({}).ditandatangani).toEqual([]);
    expect(ringkasPembubuhan({ jumlahHalaman: "x", halamanTtd: null,
                               halamanDilihat: "y" }).tanpaTtd).toEqual([]);
  });

  test("seluruh halaman ber-ttd menyisakan daftar kosong", () => {
    const r = ringkasPembubuhan({ jumlahHalaman: 2, halamanTtd: [1, 2],
                                  halamanDilihat: [1, 2] });
    expect(r.tanpaTtd).toEqual([]);
    expect(r.belumDibuka).toEqual([]);
  });
});

describe("perluPeriksaAkhir", () => {
  test("dokumen banyak halaman perlu diperiksa", () => {
    expect(perluPeriksaAkhir(2)).toBe(true);
    expect(perluPeriksaAkhir(10)).toBe(true);
  });

  test("dokumen SATU halaman tidak", () => {
    // Tak ada halaman lain untuk terlewat. Konfirmasi di sana hanya melatih
    // orang menekan "Ya" tanpa membaca — dan pelatihan itu melumpuhkan
    // konfirmasi yang benar-benar penting.
    expect(perluPeriksaAkhir(1)).toBe(false);
    expect(perluPeriksaAkhir(0)).toBe(false);
    expect(perluPeriksaAkhir(undefined)).toBe(false);
    expect(perluPeriksaAkhir("x")).toBe(false);
  });
});
