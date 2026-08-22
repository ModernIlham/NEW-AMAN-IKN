/**
 * Setelan penanda tangan pada Master Satker.
 *
 * Permintaan pemilik: *"sudah aktif semua bisa memilih siapa saja yang
 * menandatagani sesuai referensi pejabat yang sudah ditetapkan"*.
 *
 * Kegagalan paling berbahaya di layar ini TIDAK menampakkan gejala: bila
 * dialog profil tak ikut membaca `penandatangan` yang sudah tersimpan, maka
 * sekadar membuka profil lalu menekan "Simpan Profil" — untuk mengubah nomor
 * telepon, misalnya — akan MENGHAPUS seluruh pilihan penanda tangan satker
 * itu. Toast tetap berbunyi "tersimpan".
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import { SatkerPanel } from "../SatkerPage";

jest.mock("axios");

const SATKER = {
  items: [{
    kode_satker: "527001", nama_satker: "KPKNL Nusantara", terdaftar: true,
    jumlah_kegiatan: 2, alamat: "Jl. Sumbu Kebangsaan",
    penandatangan: { lpb_disetujui: "p2" },
  }],
};
const PEJABAT = {
  items: [
    { id: "p1", nama: "Andi", jabatan: "Pengurus Barang", kode_satker: "527001" },
    { id: "p2", nama: "Bagas", jabatan: "Kuasa Pengguna Barang", kode_satker: "527001" },
    { id: "p9", nama: "Zaki", jabatan: "KPB", kode_satker: "527999" },
  ],
};
const REFERENSI = {
  slot_tanda_tangan: [
    { kunci: "lpb_dibuat", label: "LPB — Dibuat oleh", peran: "pengurus_barang",
      peran_uraian: "Pengurus Barang", arti: "Petugas yang menyusun LPB" },
    { kunci: "lpb_disetujui", label: "LPB — Disetujui oleh",
      peran: "kuasa_pengguna_barang", peran_uraian: "Kuasa Pengguna Barang",
      arti: "KPB yang menyetujui" },
  ],
};

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockImplementation((url) => {
    if (String(url).endsWith("/pejabat")) return Promise.resolve({ data: PEJABAT });
    if (String(url).endsWith("/pejabat/referensi")) return Promise.resolve({ data: REFERENSI });
    return Promise.resolve({ data: SATKER });
  });
  axios.put.mockResolvedValue({ data: { ok: true } });
});

async function bukaProfil() {
  render(<SatkerPanel user={{ role: "admin", kode_satker: "527001" }} />);
  await userEvent.click(await screen.findByTestId("satker-edit-527001"));
  return screen.findByTestId("satker-ttd-panel");
}

test("pemilih tampil satu per slot yang dilayani server", async () => {
  await bukaProfil();
  expect(screen.getByTestId("satker-ttd-lpb_dibuat")).toBeInTheDocument();
  expect(screen.getByTestId("satker-ttd-lpb_disetujui")).toBeInTheDocument();
});

test("pilihan yang sudah tersimpan terbaca kembali di layar", async () => {
  await bukaProfil();
  expect(screen.getByTestId("satker-ttd-lpb_disetujui")).toHaveValue("p2");
  expect(screen.getByTestId("satker-ttd-lpb_dibuat")).toHaveValue("");
});

test("menyimpan profil TANPA menyentuh pemilih tidak menghapus pilihan lama", async () => {
  await bukaProfil();
  await userEvent.click(screen.getByTestId("satker-form-simpan"));
  await waitFor(() => expect(axios.put).toHaveBeenCalled());
  const body = axios.put.mock.calls[0][1];
  expect(body.penandatangan).toEqual({ lpb_disetujui: "p2" });
});

test("pejabat satker lain tidak ditawarkan", async () => {
  await bukaProfil();
  const sel = screen.getByTestId("satker-ttd-lpb_dibuat");
  expect(sel.innerHTML).toContain("Andi");
  expect(sel.innerHTML).not.toContain("Zaki");
});

test("referensi pejabat gagal dimuat tidak menggagalkan dialog profil", async () => {
  axios.get.mockImplementation((url) => {
    if (String(url).startsWith("undefined/api/pejabat")
        || String(url).includes("/pejabat")) return Promise.reject(new Error("mati"));
    return Promise.resolve({ data: SATKER });
  });
  render(<SatkerPanel user={{ role: "admin", kode_satker: "527001" }} />);
  await userEvent.click(await screen.findByTestId("satker-edit-527001"));
  expect(screen.getByTestId("satker-form-nama")).toBeInTheDocument();
  expect(await screen.findByText(/Daftar slot tanda tangan belum termuat/i))
    .toBeInTheDocument();
});
