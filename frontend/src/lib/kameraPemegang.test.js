import { buktiJepretan, cocokScanPemegang } from "./kameraPemegang";
const aset = [
  { id: "t1", status: "diterima", asset_id: "a1", kode_register: "REG-1", asset_code: "3050101001", NUP: "1" },
  { id: "t2", status: "diterima", asset_id: "a2", asset_code: "3050101001", NUP: "2" },
  { id: "t3", status: "dicabut", asset_id: "a3", asset_code: "3050101001", NUP: "3" },
];
test.each(["#REG-1", "#3050101001-1", "3050101001|1", "a1"])("scan tepat %s hanya memilih amanah sendiri", value => {
  expect(cocokScanPemegang(aset, value).map(a => a.id)).toEqual(["t1"]);
});
test("kode ambigu tidak dipilih diam-diam; asing/cabut/URL tidak diikuti", () => {
  expect(cocokScanPemegang(aset, "3050101001")).toHaveLength(2);
  ["", "a3", "a4", "https://asing.example/a1", "REG"].forEach(value => expect(cocokScanPemegang(aset, value)).toEqual([]));
});
test("hasil kamera menjaga metadata dan batas foto/ukuran tanpa kompresi ulang", () => {
  const meta = { waktu: "2026-10-03T10:00:00Z", gps: { lat: -0.9, lng: 116.7, accuracy: 20 } };
  const photo = buktiJepretan("data:image/jpeg;base64,YQ==", meta);
  expect(photo).toMatchObject({ mime: "image/jpeg", data_base64: "YQ==", pengambilan: meta });
  expect(() => buktiJepretan("data:image/jpeg;base64,YQ==", meta, [photo, photo, photo])).toThrow("tiga");
  expect(() => buktiJepretan(`data:image/jpeg;base64,${"A".repeat(4 * 1024 * 1024 + 4)}`, meta)).toThrow("3 MB");
  expect(() => buktiJepretan("javascript:alert(1)", meta)).toThrow("tidak dapat dibaca");
});

test("validasi base64 tanpa regex: isi rusak & awalan salah ditolak, foto besar sah diterima", () => {
  const meta = { waktu: "2026-10-03T10:00:00Z", gps: null };
  ["data:image/jpeg;base64,", "data:image/jpeg;base64,YQ=x", "data:image/jpeg;base64,Y Q==", "data:image/jpeg;base64,YQ===",
    "data:image/png;base64,YQ==", null, 42].forEach((v) => expect(() => buktiJepretan(v, meta)).toThrow("tidak dapat dibaca"));
  const besar = buktiJepretan(`data:image/jpeg;base64,${"QUFB".repeat(700 * 1024)}`, meta); // ±2,1 MB
  expect(besar.data_base64).toHaveLength(4 * 700 * 1024);
});
