import { opsiPenerima, cocokkanPenerima } from "../penerimaPersediaan";

const PEGAWAI = [
  { nama: "Budi Santoso", nip: "198001012005011001", unit_kerja: "Bagian Umum" },
  { nama: "Siti Rahayu", nip: "199002022010012002", unit_kerja: "Bagian Keuangan" },
  { nama: "Andi", nip: "", unit_kerja: "Bagian TU" },
  { nama: "", nip: "1234", unit_kerja: "X" },
];

test("opsi memuat NIP pada labelnya, dan yang tak bernama dibuang", () => {
  const o = opsiPenerima(PEGAWAI);
  expect(o).toHaveLength(3);
  expect(o[0].label).toBe("Budi Santoso — 198001012005011001");
  expect(o[2].label).toBe("Andi");
});

test("masukan cacat tak melempar", () => {
  expect(opsiPenerima(null)).toEqual([]);
  expect(cocokkanPenerima("", [])).toBeNull();
  expect(cocokkanPenerima(null, null)).toBeNull();
});

test("label utuh hasil klik datalist menghasilkan NIP dan unitnya", () => {
  const o = opsiPenerima(PEGAWAI);
  expect(cocokkanPenerima("Budi Santoso — 198001012005011001", o))
    .toEqual({ nip: "198001012005011001", unit: "Bagian Umum" });
});

test("NIP telanjang juga dikenali", () => {
  const o = opsiPenerima(PEGAWAI);
  expect(cocokkanPenerima("199002022010012002", o))
    .toEqual({ nip: "199002022010012002", unit: "Bagian Keuangan" });
});

test("nama saja dikenali bila tunggal, dan tak peduli besar-kecil huruf", () => {
  const o = opsiPenerima(PEGAWAI);
  expect(cocokkanPenerima("budi santoso", o).nip).toBe("198001012005011001");
});

test("nama KEMBAR sengaja tidak ditebak", () => {
  // Menebak salah satunya berarti membekukan NIP orang lain ke bukti
  // pengeluaran, dan tak ada yang akan menyadarinya.
  const kembar = opsiPenerima([
    { nama: "Budi", nip: "1", unit_kerja: "A" },
    { nama: "Budi", nip: "2", unit_kerja: "B" },
  ]);
  expect(cocokkanPenerima("Budi", kembar)).toBeNull();
});

test("nama yang tak ada di master tidak dipaksakan cocok", () => {
  expect(cocokkanPenerima("Orang Luar", opsiPenerima(PEGAWAI))).toBeNull();
});
