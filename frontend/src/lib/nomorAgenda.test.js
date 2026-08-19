/**
 * Lencana agenda: klien mengikuti server, tidak menebak sendiri.
 *
 * Bentuk lencana bergantung pada METODE DERET satker — deret bulanan
 * menyertakan bulan ("K-005/VIII/2026") karena tanpa itu nomor 001 bulan Juli
 * dan 001 bulan Agustus tampil identik di layar.
 *
 * Setelan itu ada di server. Klien yang merakit sendiri harus menebak
 * setelannya, dan tebakan yang salah menghasilkan lencana yang PERCAYA DIRI
 * tapi keliru — lebih menyesatkan daripada bentuk ringkas yang jujur. Karena
 * itu blok "rakitan lokal" di bawah tetap menguji bentuk tahunan: itulah
 * jaring pengaman untuk data yang datang tanpa lencana.
 */
import { labelAgenda, noAgendaTampil } from "./nomorAgenda";

describe("noAgendaTampil", () => {
  test("tiga digit ber-nol-depan", () => {
    expect(noAgendaTampil(5)).toBe("005");
    expect(noAgendaTampil(150)).toBe("150");
  });

  test("sisipan menempel dua digit", () => {
    expect(noAgendaTampil(5, 1)).toBe("005.01");
    expect(noAgendaTampil(5, 12)).toBe("005.12");
  });

  test("nilai kosong/aneh tidak meledak", () => {
    expect(noAgendaTampil(undefined)).toBe("000");
    expect(noAgendaTampil(7, null)).toBe("007");
    expect(noAgendaTampil(7, "x")).toBe("007");
  });
});

describe("labelAgenda", () => {
  test("keluar dan masuk berawalan beda", () => {
    expect(labelAgenda({ jenis: "keluar", no_agenda: 5, tahun: 2026 })).toBe("K-005/2026");
    expect(labelAgenda({ jenis: "masuk", no_agenda: 9, tahun: 2026 })).toBe("M-009/2026");
  });

  test("sisipan ikut di lencana", () => {
    expect(labelAgenda({ jenis: "keluar", no_agenda: 5, sisipan: 1, tahun: 2026 }))
      .toBe("K-005.01/2026");
  });
});

describe("lencana dari server", () => {
  test("dipakai apa adanya", () => {
    expect(labelAgenda({
      jenis: "keluar", no_agenda: 1, tahun: 2026,
      label_agenda: "K-001/VIII/2026",
    })).toBe("K-001/VIII/2026");
  });

  test("menang atas rakitan lokal", () => {
    // Kalau rakitan lokal yang menang, deret bulanan kembali menampilkan dua
    // baris "K-001/2026" persis seperti keluhan awal pemilik.
    expect(labelAgenda({
      jenis: "keluar", no_agenda: 1, sisipan: 0, tahun: 2026,
      label_agenda: "K-001/VII/2026",
    })).not.toBe("K-001/2026");
  });

  test("lencana kosong/spasi tidak dianggap ada", () => {
    expect(labelAgenda({
      jenis: "keluar", no_agenda: 7, tahun: 2026, label_agenda: "   ",
    })).toBe("K-007/2026");
  });
});
