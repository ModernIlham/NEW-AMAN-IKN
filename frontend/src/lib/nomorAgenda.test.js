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
