import {
  barisPersediaan, barisSetelahPilihPersediaan, barisSetelahUbahKode,
  barisTanpaTautPersediaan, golonganKode, peringatanPersediaanForm,
} from "./persediaanTaut";

const MASTER = {
  id: "psd-1", kode_barang: "1010301001000007",
  nama_barang: "Kertas HVS A4", satuan: "Rim", stok: 12,
};

describe("golonganKode / barisPersediaan", () => {
  test("digit pertama menentukan golongan", () => {
    expect(golonganKode("1010301001")).toBe("1");
    expect(golonganKode("3050102001")).toBe("3");
  });

  test("kode kosong / bukan angka tak punya golongan", () => {
    expect(golonganKode("")).toBe("");
    expect(golonganKode(null)).toBe("");
    expect(golonganKode("  ")).toBe("");
    expect(golonganKode("X10")).toBe("");
  });

  test("hanya golongan 1 yang bermuara ke kartu stok", () => {
    expect(barisPersediaan("1010301001000007")).toBe(true);
    expect(barisPersediaan("3050102001")).toBe(false);
    expect(barisPersediaan("")).toBe(false);
  });
});

describe("barisSetelahPilihPersediaan", () => {
  test("kode baris NAIK ke 16 digit milik master", () => {
    const b = barisSetelahPilihPersediaan({ uraian: "", kode: "1010301001" }, MASTER);
    expect(b.kode).toBe("1010301001000007");
    expect(b.psd_master_id).toBe("psd-1");
    expect(b.psd_master_kode).toBe("1010301001000007");
    expect(b.psd_master_nama).toBe("Kertas HVS A4");
  });

  test("uraian kosong terisi nama master", () => {
    expect(barisSetelahPilihPersediaan({ uraian: "" }, MASTER).uraian)
      .toBe("Kertas HVS A4");
  });

  test("uraian yang SUDAH diisi tak ditimpa", () => {
    // Nama di BAST kerap lebih panjang daripada nama di master; menimpanya
    // berarti mengarang isi dokumen sumber.
    expect(barisSetelahPilihPersediaan({ uraian: "Kertas HVS A4 80gr" }, MASTER).uraian)
      .toBe("Kertas HVS A4 80gr");
  });

  test("field lain baris tetap utuh", () => {
    const b = barisSetelahPilihPersediaan(
      { uraian: "x", kode: "", jumlah: "7", harga_satuan: "60000" }, MASTER);
    expect(b.jumlah).toBe("7");
    expect(b.harga_satuan).toBe("60000");
  });
});

describe("barisSetelahUbahKode", () => {
  const tertaut = {
    uraian: "Kertas", kode: "1010301001000007",
    psd_master_id: "psd-1", psd_master_kode: "1010301001000007",
    psd_master_nama: "Kertas HVS A4",
  };

  test("kode yang sama persis mempertahankan tautan", () => {
    const b = barisSetelahUbahKode(tertaut, "1010301001000007");
    expect(b.psd_master_id).toBe("psd-1");
  });

  test("kode 10 digit yang jadi AWALAN master tetap tertaut", () => {
    const b = barisSetelahUbahKode(tertaut, "1010301001");
    expect(b.psd_master_id).toBe("psd-1");
    expect(b.kode).toBe("1010301001");
  });

  test("kode barang LAIN menggugurkan tautan", () => {
    // Tanpa ini: pilih "Kertas HVS A4", lalu ketik kode tinta — stok tinta
    // mendarat di kartu kertas tanpa satu pun peringatan.
    const b = barisSetelahUbahKode(tertaut, "1010302002");
    expect(b.psd_master_id).toBe("");
    expect(b.psd_master_kode).toBe("");
    expect(b.psd_master_nama).toBe("");
    expect(b.kode).toBe("1010302002");
  });

  test("kode 16 digit lain pada kodefikasi yang sama pun menggugurkan", () => {
    expect(barisSetelahUbahKode(tertaut, "1010301001000008").psd_master_id).toBe("");
  });

  test("mengosongkan kode menggugurkan tautan", () => {
    expect(barisSetelahUbahKode(tertaut, "").psd_master_id).toBe("");
  });

  test("baris tak tertaut tetap tak tertaut, dan kodenya tersimpan apa adanya", () => {
    const b = barisSetelahUbahKode({ uraian: "x", kode: "" }, "101");
    expect(b.kode).toBe("101");
    expect(b.psd_master_id).toBe("");
  });
});

test("barisTanpaTautPersediaan membersihkan KETIGA field tautan", () => {
  const b = barisTanpaTautPersediaan({
    kode: "1010301001000007", psd_master_id: "psd-1",
    psd_master_kode: "1010301001000007", psd_master_nama: "Kertas HVS A4",
  });
  expect(b.psd_master_id).toBe("");
  expect(b.psd_master_kode).toBe("");
  expect(b.psd_master_nama).toBe("");
  expect(b.kode).toBe("1010301001000007");   // kode TIDAK ikut dihapus
});

describe("peringatanPersediaanForm", () => {
  test("baris persediaan tanpa tautan masuk daftar", () => {
    const w = peringatanPersediaanForm([{ kode: "1010301001", uraian: "HVS" }]);
    expect(w).toHaveLength(1);
    expect(w[0]).toMatchObject({ index: 0, uraian: "HVS", kodePendek: true });
  });

  test("kode 16 digit tanpa tautan tetap diperingatkan, tanpa label 'pendek'", () => {
    const w = peringatanPersediaanForm([{ kode: "1010301001000007", uraian: "HVS" }]);
    expect(w).toHaveLength(1);
    expect(w[0].kodePendek).toBe(false);
  });

  test("baris tertaut, baris aset, dan baris yang sudah tercatat dilewati", () => {
    expect(peringatanPersediaanForm([
      { kode: "1010301001", uraian: "A", psd_master_id: "psd-1" },
      { kode: "3050102001", uraian: "Printer" },
      { kode: "1010301001", uraian: "B", psd_item_id: "psd-9" },
      { kode: "1010301001", uraian: "C", asset_id: "aset-9" },
    ])).toEqual([]);
  });

  test("index menunjuk posisi ASLI baris, bukan urutan hasil", () => {
    // Panel di layar menyebut "Baris n" dari index ini.
    const w = peringatanPersediaanForm([
      { kode: "3050102001", uraian: "Printer" },
      { kode: "1010301001", uraian: "HVS" },
    ]);
    expect(w.map((x) => x.index)).toEqual([1]);
  });

  test("daftar kosong / cacat tak melempar", () => {
    expect(peringatanPersediaanForm([])).toEqual([]);
    expect(peringatanPersediaanForm(null)).toEqual([]);
    expect(peringatanPersediaanForm([null, {}])).toEqual([]);
  });
});
