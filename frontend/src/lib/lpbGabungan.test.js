import { idTerpilih, payloadLpbGabungan } from "@/lib/lpbGabungan";

describe("idTerpilih", () => {
  it("hanya mengambil yang tercentang", () => {
    expect(idTerpilih({ a: true, b: false, c: true })).toEqual(["a", "c"]);
  });
  it("peta kosong aman", () => {
    expect(idTerpilih(null)).toEqual([]);
  });
});

describe("payloadLpbGabungan", () => {
  it("membawa pilihan penanda tangan ke server", () => {
    // Tanpa field ini LPB tetap terbit — hanya penanda tangan pilihannya
    // hilang tanpa gejala. Justru itu sebabnya diuji.
    const out = payloadLpbGabungan({
      pilih: { p1: true }, kodeKlasifikasi: "KN.02",
      penandatangan: { lpb_disetujui: "x" },
    });
    expect(out).toEqual({
      perolehan_ids: ["p1"], kode_klasifikasi: "KN.02",
      penandatangan: { lpb_disetujui: "x" },
    });
  });

  it("selalu menyertakan kunci penandatangan meski tak ada pilihan", () => {
    const out = payloadLpbGabungan({ pilih: { p1: true } });
    expect("penandatangan" in out).toBe(true);
    expect(out.penandatangan).toEqual({});
  });

  it("klasifikasi kosong dikirim sebagai string, bukan undefined", () => {
    expect(payloadLpbGabungan({ pilih: {} }).kode_klasifikasi).toBe("");
  });

  it("bentuk muatan persis tiga kunci — tambahan diam-diam akan terlihat", () => {
    expect(Object.keys(payloadLpbGabungan({ pilih: {} })).sort())
      .toEqual(["kode_klasifikasi", "penandatangan", "perolehan_ids"]);
  });
});
