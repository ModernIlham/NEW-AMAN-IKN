/**
 * Master Pegawai tiga kelompok (PGW-07; rencana 3.10).
 *
 * Yang dipatok:
 * 1. Ranah internal memanggil HIMPUNAN URL yang sama persis dengan sebelum
 *    paket — daftar dibekukan di sini.
 * 2. Tanpa pilihan tersimpan hanya layar pilih kelompok yang tampil dan tak
 *    satu pun daftar orang diminta.
 * 3. Field per kelompok (3.7b–d) dibaca dari /luar/referensi.
 * 4. Lingkup bertingkat: mengganti tingkat atas mengosongkan yang di bawah.
 */
import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import PegawaiPage from "../PegawaiPage";

jest.mock("axios");

const ADMIN = { role: "admin", kode_satker: "333333", username: "admin" };
const SUPER = { role: "admin", kode_satker: "", username: "pusat" };
const SIMPAN = "aman.pegawai.ranah";

const REF_LUAR = {
  label_tingkat: {
    eksternal_pusat: { instansi: "Kementerian/Lembaga", satker: "Satker", level: "Eselon" },
    eksternal_daerah: { instansi: "Pemda", satker: "Perangkat Daerah", level: "Eselon" },
    pihak_ketiga: { instansi: "Badan/Pihak", satker: "Unit/Cabang", level: "Tingkat" },
  },
  field_nonaktif: {
    eksternal: ["tempat_lahir", "agama", "status_perkawinan", "pendidikan_terakhir",
      "npwp", "nama_bank", "no_rekening"],
    pihak_ketiga: ["pangkat_golongan", "kategori_pegawai", "jenis_jabatan", "eselon",
      "tempat_lahir", "agama", "status_perkawinan", "pendidikan_terakhir", "npwp",
      "nama_bank", "no_rekening", "nomor_kontrak", "tgl_mulai_kontrak",
      "tgl_selesai_kontrak", "jenis_kontrak_non_asn", "perusahaan_penyedia"],
  },
  label_field: { pihak_ketiga: { nip: "NIK", jabatan: "Jabatan pada badan" } },
  kapasitas_bertindak: { pengurus_berwenang: "Pengurus yang berwenang mewakili badan",
    petugas: "Petugas/karyawan (bukan wakil badan)", diri_sendiri: "Bertindak untuk diri sendiri" },
  dasar_kewenangan: { surat_kuasa: "Surat kuasa" },
  jenis_instansi: { eksternal: {}, pihak_ketiga: { badan_usaha_swasta: "Badan Usaha Swasta" } },
  tataran_dari_jenis: { kementerian_lembaga: "pusat", pemerintah_provinsi: "daerah",
    pemerintah_kabkota: "daerah", pemerintah_desa: "daerah" },
  induk_daerah: { pemerintah_provinsi: null, pemerintah_kabkota: "pemerintah_provinsi" },
};

const INSTANSI = [
  { id: "kl1", nama: "Kementerian Satu", kelompok: "eksternal", tataran: "pusat",
    jenis: "kementerian_lembaga", version: 1 },
  { id: "kl2", nama: "Kementerian Dua", kelompok: "eksternal", tataran: "pusat",
    jenis: "kementerian_lembaga", version: 1 },
  { id: "pv1", nama: "Provinsi Kalimantan Timur", kelompok: "eksternal", tataran: "daerah",
    jenis: "pemerintah_provinsi", provinsi_id: "pv1", provinsi_nama: "Provinsi Kalimantan Timur" },
  { id: "pv2", nama: "Provinsi Jawa Barat", kelompok: "eksternal", tataran: "daerah",
    jenis: "pemerintah_provinsi", provinsi_id: "pv2", provinsi_nama: "Provinsi Jawa Barat" },
  { id: "kb1", nama: "Kabupaten Penajam Paser Utara", kelompok: "eksternal", tataran: "daerah",
    jenis: "pemerintah_kabkota", provinsi_id: "pv1", provinsi_nama: "Provinsi Kalimantan Timur" },
  { id: "kb2", nama: "Kabupaten Bandung", kelompok: "eksternal", tataran: "daerah",
    jenis: "pemerintah_kabkota", provinsi_id: "pv2", provinsi_nama: "Provinsi Jawa Barat" },
  { id: "bu1", nama: "PT Maju", kelompok: "pihak_ketiga", jenis: "badan_usaha_swasta", version: 1 },
];
const SATKER = [
  { id: "s1", instansi_id: "kl1", nama_satker: "Sekretariat Jenderal" },
  { id: "s2", instansi_id: "kl1", nama_satker: "Inspektorat" },
  { id: "s3", instansi_id: "kl2", nama_satker: "Biro Umum Dua" },
  { id: "s9", instansi_id: "bu1", nama_satker: "Kantor Pusat PT Maju" },
];
const ORANG_LUAR = [{ id: "o1", nama: "Sari", nip: "", kelompok: "pihak_ketiga",
  satker_luar_id: "s9", instansi_id: "bu1", label_unit: "PT Maju — Kantor Pusat" }];

const jalur = (url) => String(url).replace(/^.*\/api/, "");

function pasangApi() {
  axios.get.mockImplementation((url, cfg = {}) => {
    const u = jalur(url);
    const p = cfg.params || {};
    const items = (data) => Promise.resolve({ data: { items: data, total: data.length } });
    if (u === "/luar/referensi") return Promise.resolve({ data: REF_LUAR });
    if (u === "/pegawai/referensi") {
      return Promise.resolve({ data: { status_kepegawaian: [{ kode: "pns", uraian: "PNS" },
        { kode: "non_asn", uraian: "Non-ASN" }], status: [{ kode: "aktif", uraian: "Aktif" }] } });
    }
    if (u === "/luar/instansi") {
      return items(INSTANSI.filter((i) => i.kelompok === p.kelompok
        && (!p.tataran || i.tataran === p.tataran)
        && (!p.jenis || i.jenis === p.jenis)
        && (!p.provinsi_id || i.provinsi_id === p.provinsi_id)));
    }
    if (u === "/luar/satker") return items(SATKER.filter((s) => s.instansi_id === p.instansi_id));
    if (u === "/pegawai-luar") return items(ORANG_LUAR.filter((o) => o.kelompok === p.kelompok));
    if (u === "/pegawai-luar/rekap-lingkup") {
      return Promise.resolve({ data: { jumlah: 0, per_tataran: {}, per_instansi: [], per_satker: [] } });
    }
    if (u === "/unit-kerja" || u === "/unit-kerja-luar") {
      return Promise.resolve({ data: { items: [], level_akar: 1 } });
    }
    return items([]);
  });
  axios.post.mockResolvedValue({ data: { ok: true } });
}

const panggilan = () => axios.get.mock.calls.map(([url, cfg]) => ({ u: jalur(url), p: cfg?.params || {} }));
const urlDipanggil = () => new Set(panggilan().map((c) => c.u));
const simpan = (v) => window.localStorage.setItem(SIMPAN, JSON.stringify(v));

function buka({ user = ADMIN, ...props } = {}) {
  pasangApi();
  return render(<PegawaiPage user={user} onBack={() => {}} wajibPilihKelompok {...props} />);
}

async function pilihLingkup(instansiId, satkerId) {
  const sel = await screen.findByTestId("lingkup-instansi");
  await waitFor(() => expect(within(sel).queryByRole("option", { name: new RegExp(
    INSTANSI.find((i) => i.id === instansiId).nama) })).not.toBeNull());
  await userEvent.selectOptions(sel, instansiId);
  if (!satkerId) return;
  const s = screen.getByTestId("lingkup-satker");
  await waitFor(() => expect(within(s).queryByRole("option", {
    name: SATKER.find((x) => x.id === satkerId).nama_satker })).not.toBeNull());
  await userEvent.selectOptions(s, satkerId);
}

beforeEach(() => { jest.clearAllMocks(); window.localStorage.clear(); });

// ── 1. Regresi internal ──────────────────────────────────────────────────
// Dibekukan dari PegawaiPage sebelum PGW-07: empat GET saat halaman dibuka.
const URL_INTERNAL_BEKU = ["/pegawai", "/pegawai/perlu-serah-terima",
  "/pegawai/referensi", "/unit-kerja"];

test("ranah internal memanggil himpunan URL yang sama dengan sebelum paket", async () => {
  simpan({ kelompok: "internal", tataran: "pusat" });
  buka();
  await screen.findByTestId("pegawai-add");
  await waitFor(() => expect(urlDipanggil().size).toBe(URL_INTERNAL_BEKU.length));
  expect([...urlDipanggil()].sort()).toEqual([...URL_INTERNAL_BEKU].sort());
  // Panggilan daftar internal tetap tanpa parameter apa pun.
  expect(axios.get.mock.calls.find(([u]) => jalur(u) === "/pegawai")).toHaveLength(1);
});

test("tanpa prop wajibPilihKelompok, halaman langsung membuka internal seperti dulu", async () => {
  pasangApi();
  render(<PegawaiPage user={ADMIN} onBack={() => {}} />);
  await screen.findByTestId("pegawai-add");
  await waitFor(() => expect([...urlDipanggil()].sort()).toEqual([...URL_INTERNAL_BEKU].sort()));
});

// ── 2. Pintu masuk ───────────────────────────────────────────────────────
test("tanpa pilihan tersimpan: layar pilih tampil dan tak satu pun daftar diminta", async () => {
  buka();
  expect(await screen.findByTestId("pegawai-pilih-kelompok-layar")).toBeInTheDocument();
  await new Promise((r) => setTimeout(r, 50));
  const u = urlDipanggil();
  for (const daftar of ["/pegawai", "/pegawai-luar", "/unit-kerja", "/unit-kerja-luar",
    "/pegawai/perlu-serah-terima"]) expect(u.has(daftar)).toBe(false);
  expect(screen.queryByTestId("pegawai-add")).toBeNull();
  expect(screen.queryByText(/semua kelompok/i)).toBeNull();
  // Memilih satu langsung memuat daftarnya — tanpa tombol "terapkan" — dan diingat.
  await userEvent.click(screen.getByTestId("pegawai-kelompok-internal"));
  await waitFor(() => expect(urlDipanggil().has("/pegawai")).toBe(true));
  expect(JSON.parse(window.localStorage.getItem(SIMPAN)).kelompok).toBe("internal");
});

test("dengan pilihan tersimpan: kelompok itu langsung dimuat", async () => {
  simpan({ kelompok: "pihak_ketiga", tataran: "pusat" });
  buka();
  await waitFor(() => expect(panggilan().some((c) => c.u === "/pegawai-luar"
    && c.p.kelompok === "pihak_ketiga")).toBe(true));
  expect(screen.queryByTestId("pegawai-pilih-kelompok-layar")).toBeNull();
  expect(screen.getByTestId("pegawai-kelompok-pihak_ketiga")).toHaveAttribute("aria-pressed", "true");
  expect(urlDipanggil().has("/pegawai")).toBe(false);
});

// ── 3. Field per kelompok ────────────────────────────────────────────────
test("pihak ketiga: tanpa agama, pangkat, rekening; ada Kapasitas Bertindak", async () => {
  simpan({ kelompok: "pihak_ketiga", tataran: "pusat" });
  buka();
  await pilihLingkup("bu1", "s9");
  await waitFor(() => expect(screen.getByTestId("pegawai-add")).toBeEnabled());
  await userEvent.click(screen.getByTestId("pegawai-add"));
  expect(await screen.findByTestId("pegawai-form-lingkup")).toHaveTextContent("PT Maju — Kantor Pusat PT Maju");
  expect(screen.getByText("NIK")).toBeInTheDocument();
  await userEvent.click(screen.getByTestId("pegawai-tab-pribadi"));
  expect(screen.queryByText("Agama")).toBeNull();
  await userEvent.click(screen.getByTestId("pegawai-tab-kepegawaian"));
  expect(screen.queryByTestId("pegawai-form-pangkat")).toBeNull();
  expect(screen.getByTestId("pegawai-form-status-peg")).toBeDisabled();
  expect(screen.getByTestId("pegawai-form-status-peg")).toHaveValue("non_asn");
  expect(screen.getByText("Kapasitas Bertindak")).toBeInTheDocument();
  expect(screen.queryByTestId("pegawai-form-jenis-kontrak")).toBeNull();
  await userEvent.click(screen.getByTestId("pegawai-tab-kontak"));
  expect(screen.queryByTestId("pegawai-form-rekening")).toBeNull();
});

test("eksternal: tanpa agama dan rekening; pangkat dan kontrak tetap ada", async () => {
  simpan({ kelompok: "eksternal", tataran: "pusat" });
  buka();
  await pilihLingkup("kl1", "s1");
  await waitFor(() => expect(screen.getByTestId("pegawai-add")).toBeEnabled());
  await userEvent.click(screen.getByTestId("pegawai-add"));
  await userEvent.click(await screen.findByTestId("pegawai-tab-pribadi"));
  expect(screen.queryByText("Agama")).toBeNull();
  await userEvent.click(screen.getByTestId("pegawai-tab-kepegawaian"));
  expect(screen.getByTestId("pegawai-form-pangkat")).toBeInTheDocument();
  expect(screen.queryByText("Kapasitas Bertindak")).toBeNull();
  await userEvent.selectOptions(screen.getByTestId("pegawai-form-status-peg"), "non_asn");
  expect(screen.getByTestId("pegawai-form-jenis-kontrak")).toBeInTheDocument();
  await userEvent.click(screen.getByTestId("pegawai-tab-kontak"));
  expect(screen.queryByTestId("pegawai-form-rekening")).toBeNull();
  await userEvent.click(screen.getByTestId("pegawai-tab-jabatan"));
  expect(screen.queryByTestId("pegawai-form-kode-satker")).toBeNull();
});

// ── 4. Lingkup bertingkat ────────────────────────────────────────────────
test("mengganti instansi mengosongkan satker; daftar satker hanya milik instansi itu", async () => {
  simpan({ kelompok: "eksternal", tataran: "pusat" });
  buka();
  await pilihLingkup("kl1", "s1");
  const satker = screen.getByTestId("lingkup-satker");
  expect(within(satker).getAllByRole("option").map((o) => o.value).filter(Boolean)).toEqual(["s1", "s2"]);
  expect(screen.getByTestId("pegawai-lingkup-label")).toHaveTextContent("Kementerian Satu — Sekretariat Jenderal");
  await userEvent.selectOptions(screen.getByTestId("lingkup-instansi"), "kl2");
  expect(screen.getByTestId("lingkup-satker")).toHaveValue("");
  await waitFor(() => expect(within(screen.getByTestId("lingkup-satker")).getAllByRole("option")
    .map((o) => o.value).filter(Boolean)).toEqual(["s3"]));
  await waitFor(() => expect(panggilan().filter((c) => c.u === "/pegawai-luar").pop().p)
    .toEqual(expect.objectContaining({ instansi_id: "kl2" })));
  expect(panggilan().filter((c) => c.u === "/pegawai-luar").pop().p.satker_luar_id).toBeUndefined();
});

test("Instansi Eksternal: Pusat/Daerah; Daerah meminta tataran=daerah dan memakai 'Perangkat Daerah'", async () => {
  simpan({ kelompok: "internal", tataran: "pusat" });
  buka();
  await userEvent.click(await screen.findByTestId("pegawai-kelompok-eksternal"));
  expect(await screen.findByTestId("pegawai-tataran-pusat")).toBeInTheDocument();
  await pilihLingkup("kl1");
  await userEvent.click(screen.getByTestId("pegawai-tataran-daerah"));
  await waitFor(() => expect(panggilan().some((c) => c.u === "/pegawai-luar"
    && c.p.tataran === "daerah")).toBe(true));
  expect(await screen.findByLabelText("Perangkat Daerah")).toBeInTheDocument();
  await userEvent.click(screen.getByTestId("pegawai-tataran-pusat"));
  expect(screen.getByTestId("lingkup-instansi")).toHaveValue("");
  expect(JSON.parse(window.localStorage.getItem(SIMPAN))).toEqual({ kelompok: "eksternal", tataran: "pusat" });
});

test("Daerah: provinsi dulu; hanya kab/kota provinsi itu, bersama nama provinsinya", async () => {
  simpan({ kelompok: "eksternal", tataran: "daerah" });
  buka();
  expect(await screen.findByTestId("lingkup-instansi")).toBeDisabled();
  const prov = screen.getByTestId("lingkup-provinsi");
  await waitFor(() => expect(within(prov).queryByRole("option", { name: "Provinsi Kalimantan Timur" })).not.toBeNull());
  await userEvent.selectOptions(prov, "pv1");
  await waitFor(() => expect(panggilan().some((c) => c.u === "/luar/instansi"
    && c.p.provinsi_id === "pv1")).toBe(true));
  await waitFor(() => expect(panggilan().some((c) => c.u === "/pegawai-luar"
    && c.p.provinsi_id === "pv1")).toBe(true));
  const inst = screen.getByTestId("lingkup-instansi");
  await waitFor(() => expect(inst).toBeEnabled());
  await waitFor(() => expect(within(inst).queryByRole("option", {
    name: "Kabupaten Penajam Paser Utara, Provinsi Kalimantan Timur" })).not.toBeNull());
  expect(within(inst).queryByRole("option", { name: /Kabupaten Bandung/ })).toBeNull();
});

test("tanpa satker terpilih, tombol Tambah nonaktif", async () => {
  simpan({ kelompok: "eksternal", tataran: "pusat" });
  buka();
  expect(await screen.findByTestId("pegawai-add")).toBeDisabled();
  expect(screen.getByTestId("pegawai-pilih-satker-dulu")).toBeInTheDocument();
  await pilihLingkup("kl1");
  expect(screen.getByTestId("pegawai-add")).toBeDisabled();
});

test("hapus permanen tidak ada untuk admin biasa; ada untuk super-admin", async () => {
  simpan({ kelompok: "pihak_ketiga", tataran: "pusat" });
  const { unmount } = buka();
  await screen.findAllByLabelText("Ubah Sari");
  expect(screen.queryByTestId("pegawai-delete-o1")).toBeNull();
  expect(screen.queryByTestId("pegawai-delete-o1-m")).toBeNull();
  await userEvent.click(screen.getByTestId("lingkup-kelola"));
  await screen.findByTestId("kelola-instansi-bu1");
  expect(screen.queryByTestId("kelola-instansi-bu1-hapus")).toBeNull();
  expect(screen.getByTestId("kelola-instansi-bu1-aktif")).toBeInTheDocument();
  unmount();
  buka({ user: SUPER });
  await screen.findAllByLabelText("Ubah Sari");
  expect(screen.getByTestId("pegawai-delete-o1")).toBeInTheDocument();
  await userEvent.click(screen.getByTestId("lingkup-kelola"));
  expect(await screen.findByTestId("kelola-instansi-bu1-hapus")).toBeInTheDocument();
});
