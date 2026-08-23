import { bolehLeburkan, peringatanJumlahLebur } from "@/lib/peleburanBaris";

const BARIS = { kode: "3050104001", uraian: "RAM", jumlah: 1, harga_satuan: 2000000 };

describe("bolehLeburkan", () => {
  it("baris biasa ditawari", () => {
    expect(bolehLeburkan(BARIS)).toBe(true);
  });

  it("baris yang sudah di kartu stok TIDAK ditawari", () => {
    // Tombol yang pasti ditolak server hanyalah undangan untuk mencoba.
    expect(bolehLeburkan({ ...BARIS, psd_item_id: "i-1" })).toBe(false);
  });

  it("baris yang sudah tertaut/terlebur TIDAK ditawari", () => {
    expect(bolehLeburkan({ ...BARIS, asset_id: "a-1" })).toBe(false);
  });

  it("spasi saja bukan tautan", () => {
    expect(bolehLeburkan({ ...BARIS, asset_id: "   " })).toBe(true);
  });

  it("baris kosong tak meledak", () => {
    expect(bolehLeburkan(null)).toBe(true);
    expect(bolehLeburkan({})).toBe(true);
  });
});

describe("peringatanJumlahLebur", () => {
  it("jumlah 1 tak memperingatkan apa pun", () => {
    expect(peringatanJumlahLebur(BARIS)).toBe("");
  });

  it("jumlah lebih dari 1 memperingatkan 1 NUP 1 barang", () => {
    const t = peringatanJumlahLebur({ ...BARIS, jumlah: 3 });
    expect(t).toContain("3 unit");
    expect(t).toContain("1 NUP untuk 1 barang");
    expect(t).toMatch(/ulangi peleburan/);
  });

  it("pecahan juga diperingatkan", () => {
    expect(peringatanJumlahLebur({ ...BARIS, jumlah: 2.5 })).toContain("2.5 unit");
  });

  it("baris tanpa jumlah dianggap 1", () => {
    // Baris era lama tak boleh memunculkan peringatan palsu — peringatan yang
    // muncul untuk keadaan normal akan dilatih diabaikan.
    expect(peringatanJumlahLebur({ ...BARIS, jumlah: undefined })).toBe("");
    expect(peringatanJumlahLebur({})).toBe("");
    expect(peringatanJumlahLebur(null)).toBe("");
  });

  it("jumlah tak terbaca tidak memunculkan peringatan ngawur", () => {
    expect(peringatanJumlahLebur({ ...BARIS, jumlah: "abc" })).toBe("");
  });
});
