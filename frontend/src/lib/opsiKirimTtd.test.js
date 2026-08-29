import {
  MODE_TTD, PILIHAN_BAWAAN, SIFAT_URGENSI, bersihkanPilihan, labelUrgensi,
} from "./opsiKirimTtd";

describe("daftar pilihan CERMIN server", () => {
  test("mode persis yang divalidasi server", () => {
    // routes/ttd.py menolak selain kedua nilai ini dengan 400.
    expect(MODE_TTD.map((m) => m.nilai)).toEqual(["paralel", "berurutan"]);
  });

  test("sifat urgensi persis persuratan_utils.SIFAT_URGENSI", () => {
    expect(SIFAT_URGENSI.map((u) => u.nilai))
      .toEqual(["biasa", "segera", "sangat_segera"]);
  });

  test("tiap mode menerangkan ARTINYA, bukan sekadar istilah", () => {
    // "paralel"/"berurutan" tak berarti apa-apa bagi orang yang baru pertama
    // kali mengirim dokumen.
    for (const m of MODE_TTD) expect(m.arti.length).toBeGreaterThan(20);
  });
});

describe("bersihkanPilihan", () => {
  test("nilai sah diteruskan apa adanya", () => {
    expect(bersihkanPilihan({ mode: "berurutan", sifat_urgensi: "segera" }))
      .toEqual({ mode: "berurutan", sifat_urgensi: "segera" });
  });

  test("nilai asing jatuh ke bawaannya, bukan diteruskan", () => {
    // Server memang menolaknya 400, tetapi mengirim yang pasti ditolak hanya
    // menghasilkan galat yang tak bisa dijelaskan kepada pengguna.
    expect(bersihkanPilihan({ mode: "acak", sifat_urgensi: "gawat" }))
      .toEqual(PILIHAN_BAWAAN);
  });

  test("masukan kosong/cacat tak melempar", () => {
    expect(bersihkanPilihan()).toEqual(PILIHAN_BAWAAN);
    expect(bersihkanPilihan(null)).toEqual(PILIHAN_BAWAAN);
    expect(bersihkanPilihan({})).toEqual(PILIHAN_BAWAAN);
  });

  test("bawaannya sama dengan perilaku lama", () => {
    // Tombol yang dipakai tanpa membuka dialog harus berjalan persis seperti
    // sebelum fitur ini ada.
    expect(PILIHAN_BAWAAN).toEqual({ mode: "paralel", sifat_urgensi: "biasa" });
  });
});

describe("labelUrgensi", () => {
  test("biasa tak perlu diumumkan", () => {
    expect(labelUrgensi("biasa")).toBe("");
  });

  test("yang mendesak diberi label", () => {
    expect(labelUrgensi("segera")).toBe("Segera");
    expect(labelUrgensi("sangat_segera")).toBe("Sangat Segera");
  });

  test("nilai tak dikenal tak melempar", () => {
    expect(labelUrgensi("entah")).toBe("");
    expect(labelUrgensi()).toBe("");
  });
});
