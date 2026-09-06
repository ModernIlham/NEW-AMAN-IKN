/**
 * Layar Pegawai mengikuti tingkat SATKERNYA, bukan menebak Eselon I.
 *
 * Aturannya ditegakkan server; yang dijaga di sini adalah layar tidak menuntut
 * LEBIH daripada server. Form yang menebak "puncak = Eselon I" akan meminta
 * induk Eselon II untuk unit puncak sebuah Lapas — permintaan yang justru akan
 * DITERIMA server — sehingga penggunanya terhenti pada pesan galat buatan
 * layar sendiri, tanpa satu pun jalan keluar di layar itu.
 *
 * Tiga sifat yang dipatok:
 *
 * 1. Tingkat yang ditawarkan bermula di puncak satker; tingkat di atasnya
 *    milik instansi induk dan tak ditawarkan.
 * 2. Unit puncak dikirim TANPA induk, dan tak dihalangi lebih dulu.
 * 3. Bagan struktur berakar pada unit tanpa induk — bukan pada Eselon I, yang
 *    pada satker seperti ini tak pernah ada sehingga bagannya akan kosong
 *    tanpa satu pun keterangan.
 */
import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import PegawaiPage from "../PegawaiPage";

jest.mock("axios");

const ADMIN = { role: "admin", kode_satker: "333333", username: "admin" };

//: Master unit sebuah Lapas: berpuncak Eselon III, tanpa Eselon I/II.
const UNIT = [
  { id: "u3", nama_unit: "Lapas Kelas IIA Nusantara", eselon: "3", parent_id: null },
  { id: "u4", nama_unit: "Subbagian Tata Usaha", eselon: "4", parent_id: "u3" },
];

function pasangApi({ akar = 3, unit = UNIT } = {}) {
  axios.get.mockImplementation((url) => {
    const u = String(url);
    if (u.endsWith("/unit-kerja")) {
      // `akar: null` = server versi lama yang belum menyebutkan `level_akar`
      // sama sekali — field-nya benar-benar TAK ADA, bukan bernilai kosong.
      return Promise.resolve({ data: { items: unit, jumlah: unit.length,
        ...(akar == null ? {} : { level_akar: akar }) } });
    }
    if (u.endsWith("/pegawai/referensi")) return Promise.resolve({ data: {} });
    return Promise.resolve({ data: { items: [] } });
  });
  axios.post.mockResolvedValue({ data: { ok: true, id: "baru" } });
}

async function bukaKelolaUnit(opsi) {
  pasangApi(opsi);
  render(<PegawaiPage user={ADMIN} onBack={() => {}} />);
  await userEvent.click(await screen.findByTestId("pegawai-add"));
  await userEvent.click(await screen.findByTestId("pegawai-tab-jabatan"));
  await userEvent.click(await screen.findByTestId("pegawai-kelola-unit"));
  return screen.findByTestId("unit-nama");
}

const tabEselon = () => screen.getAllByRole("button", { name: /^Eselon \d$/ })
  .map((b) => b.textContent);

beforeEach(() => jest.clearAllMocks());

// ── 1. Tingkat yang ditawarkan bermula di puncak satker ─────────────────

test("tab tingkat Lapas bermula di Eselon 3 — Eselon 1 & 2 tak ditawarkan", async () => {
  await bukaKelolaUnit();
  expect(tabEselon()).toEqual(["Eselon 3", "Eselon 4", "Eselon 5"]);
});

test("satker tanpa tingkat yang dinyatakan tetap melihat Eselon 1–5", async () => {
  await bukaKelolaUnit({ akar: null, unit: [] });
  expect(tabEselon()).toEqual(["Eselon 1", "Eselon 2", "Eselon 3",
    "Eselon 4", "Eselon 5"]);
});

test("sisa unit di ATAS puncak tetap punya tab, tetapi tak dapat ditambahi", async () => {
  // Kalau tabnya hilang, unit itu tak dapat dipindah maupun dihapus: lenyap
  // dari layar, tetap hidup di basis data, dan tetap terbawa laporan.
  await bukaKelolaUnit({ unit: [...UNIT,
    { id: "u2", nama_unit: "Kanwil lama", eselon: "2", parent_id: null }] });
  expect(tabEselon()).toEqual(["Eselon 2", "Eselon 3", "Eselon 4", "Eselon 5"]);
  await userEvent.click(screen.getByRole("button", { name: "Eselon 2" }));
  expect(screen.getByTestId("unit-di-atas-puncak")).toBeInTheDocument();
  expect(screen.getByTestId("unit-tambah")).toBeDisabled();
});

// ── 2. Unit puncak dikirim tanpa induk ──────────────────────────────────

test("puncak Lapas tak meminta induk, dan terkirim dengan parent_id kosong", async () => {
  const nama = await bukaKelolaUnit();
  expect(screen.queryByTestId("unit-induk")).toBeNull();
  await userEvent.type(nama, "Lapas Kelas IIB Sepaku");
  await userEvent.click(screen.getByTestId("unit-tambah"));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  const [url, body] = axios.post.mock.calls[0];
  expect(String(url)).toContain("/unit-kerja");
  expect(body).toMatchObject({ nama_unit: "Lapas Kelas IIB Sepaku",
    eselon: "3", parent_id: "" });
});

test("di BAWAH puncak induk tetap diminta, dan penambahan tanpa induk dihalangi", async () => {
  await bukaKelolaUnit();
  await userEvent.click(screen.getByRole("button", { name: "Eselon 4" }));
  const induk = screen.getByTestId("unit-induk");
  expect(within(induk).getByRole("option", { name: "Lapas Kelas IIA Nusantara" }))
    .toBeInTheDocument();
  await userEvent.type(screen.getByTestId("unit-nama"), "Seksi Pembinaan");
  await userEvent.click(screen.getByTestId("unit-tambah"));
  expect(axios.post).not.toHaveBeenCalled();
});

// ── 3. Form pegawai & bagan struktur ────────────────────────────────────

test("form pegawai hanya menawarkan Eselon 3–5 dan menyebut alasannya", async () => {
  pasangApi();
  render(<PegawaiPage user={ADMIN} onBack={() => {}} />);
  await userEvent.click(await screen.findByTestId("pegawai-add"));
  await userEvent.click(await screen.findByTestId("pegawai-tab-jabatan"));
  await screen.findByTestId("pegawai-form-eselon3");
  expect(screen.queryByTestId("pegawai-form-eselon1")).toBeNull();
  expect(screen.queryByTestId("pegawai-form-eselon2")).toBeNull();
  expect(screen.getByTestId("pegawai-form-eselon5")).toBeInTheDocument();
  expect(screen.getByTestId("pegawai-akar-eselon")).toHaveTextContent(/Eselon III/);
});

test("kolom eselon lama yang TERLANJUR terisi tetap ditampilkan agar bisa dikosongkan", async () => {
  pasangApi();
  axios.get.mockImplementation((url) => {
    const u = String(url);
    if (u.endsWith("/unit-kerja")) {
      return Promise.resolve({ data: { items: UNIT, level_akar: 3 } });
    }
    if (u.endsWith("/pegawai/referensi")) return Promise.resolve({ data: {} });
    if (u.endsWith("/pegawai")) {
      return Promise.resolve({ data: { items: [{
        id: "p1", nama: "Budi", nip: "1", eselon2: "Kanwil lama",
        eselon3: "Lapas Kelas IIA Nusantara" }] } });
    }
    return Promise.resolve({ data: { items: [] } });
  });
  render(<PegawaiPage user={ADMIN} onBack={() => {}} />);
  // Baris pegawai muncul dua rupa (kartu di HP, tabel di desktop); keduanya
  // membuka form yang sama.
  await userEvent.click((await screen.findAllByLabelText("Ubah Budi"))[0]);
  await userEvent.click(await screen.findByTestId("pegawai-tab-jabatan"));
  expect(await screen.findByTestId("pegawai-form-eselon2"))
    .toHaveValue("Kanwil lama");
  expect(screen.queryByTestId("pegawai-form-eselon1")).toBeNull();
});

test("bagan struktur berakar pada unit tanpa induk, bukan pada Eselon I", async () => {
  pasangApi();
  render(<PegawaiPage user={ADMIN} onBack={() => {}} />);
  await userEvent.click(await screen.findByTestId("pegawai-struktur"));
  const pohon = await screen.findByTestId("struktur-organisasi-pohon");
  expect(within(pohon).getByText("Lapas Kelas IIA Nusantara"))
    .toBeInTheDocument();
});
