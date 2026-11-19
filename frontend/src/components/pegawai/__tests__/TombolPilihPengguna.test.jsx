/**
 * Pemilih pengguna semua kelompok (Ubah Massal, Nov 2026). Laporan pemilik:
 * panel Ubah Massal hanya punya tombol "Orang luar" — pegawai INTERNAL tidak
 * bisa dicari sehingga harus diketik manual.
 */
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import TombolPilihPengguna from "../TombolPilihPengguna";
import { _setelUlangPenampung } from "@/hooks/useKelompokOrang";

jest.mock("axios");

const PEGAWAI = [
  { id: "p1", nama: "Budi Santoso", nip: "199001012015011001", jabatan: "Kepala Subbagian Umum", status: "aktif" },
  { id: "p2", nama: "Sari Wulandari", nip: "198805122014022003", jabatan: "Analis BMN", status: "aktif" },
  { id: "p3", nama: "Almarhum Contoh", nip: "197001011995031001", status: "meninggal" },
];

beforeEach(() => {
  jest.clearAllMocks(); window.localStorage.clear(); _setelUlangPenampung();
  axios.get.mockImplementation((url) => Promise.resolve(
    url.endsWith("/pegawai") ? { data: { items: PEGAWAI } } : { data: { items: [] } }));
  axios.post.mockResolvedValue({ data: { nomor: {} } });
});

test("menawarkan ketiga kelompok, Internal sebagai bawaan", async () => {
  render(<TombolPilihPengguna onPilih={() => {}} testId="t" />);
  fireEvent.click(screen.getByTestId("t"));
  expect(await screen.findByTestId("t-kelompok-internal")).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByTestId("t-kelompok-eksternal")).toBeInTheDocument();
  expect(screen.getByTestId("t-kelompok-pihak_ketiga")).toBeInTheDocument();
});

test("daftar internal dari Master Pegawai; pegawai meninggal tidak dapat dipilih", async () => {
  render(<TombolPilihPengguna onPilih={() => {}} testId="t" />);
  fireEvent.click(screen.getByTestId("t"));
  expect(await screen.findByTestId("t-opt-199001012015011001")).toBeInTheDocument();
  expect(screen.getByTestId("t-opt-198805122014022003")).toBeInTheDocument();
  expect(screen.queryByTestId("t-opt-197001011995031001")).toBeNull();
  expect(axios.get.mock.calls.filter(([u]) => u.endsWith("/pegawai"))).toHaveLength(1);
});

test("pencarian nama/NIP lalu memilih memanggil onPilih dengan data pegawai", async () => {
  const pilih = jest.fn();
  render(<TombolPilihPengguna onPilih={pilih} testId="t" />);
  fireEvent.click(screen.getByTestId("t"));
  await screen.findByTestId("t-opt-199001012015011001");
  fireEvent.change(screen.getByTestId("t-cari"), { target: { value: "1988" } });
  expect(screen.queryByTestId("t-opt-199001012015011001")).toBeNull();
  fireEvent.click(screen.getByTestId("t-opt-198805122014022003"));
  expect(pilih).toHaveBeenCalledWith(expect.objectContaining({ nama: "Sari Wulandari", nip: "198805122014022003" }));
});

test("Master Pegawai gagal dimuat (offline) → pesan, tanpa galat", async () => {
  axios.get.mockRejectedValue(new Error("Network Error"));
  render(<TombolPilihPengguna onPilih={() => {}} testId="t" />);
  fireEvent.click(screen.getByTestId("t"));
  expect(await screen.findByText(/tak tersedia \(offline\)/)).toBeInTheDocument();
});

test("kelompok luar memakai pencarian direktori orang luar", async () => {
  render(<TombolPilihPengguna onPilih={() => {}} testId="t" />);
  fireEvent.click(screen.getByTestId("t"));
  fireEvent.click(await screen.findByTestId("t-kelompok-pihak_ketiga"));
  await waitFor(() => expect(axios.get.mock.calls.some(([, o]) => o?.params?.kelompok === "pihak_ketiga")).toBe(true));
});
