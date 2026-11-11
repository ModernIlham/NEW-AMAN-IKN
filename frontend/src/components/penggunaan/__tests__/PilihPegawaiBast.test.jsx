import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import PilihPegawaiBast, { pihakDariPegawai } from "../PilihPegawaiBast";
import StatusOtomasiBast from "../StatusOtomasiBast";

jest.mock("axios");

test("nama kembar dibedakan UUID dan tanpa NIP tidak mewarisi identitas lama", () => {
  const daftar = [{ id: "pegawai-1", nama: "Budi", nip: "123", email: "satu@example.test" }, { id: "pegawai-2", nama: "Budi", nip: "", email: "dua@example.test" }];
  const pilih = jest.fn();
  render(<PilihPegawaiBast daftar={daftar} onPilih={pilih} testId="pilih" />);
  fireEvent.click(screen.getByTestId("pilih"));
  fireEvent.click(screen.getByTestId("pilih-option-pegawai-2"));
  expect(pilih).toHaveBeenCalledWith(daftar[1]);
  expect({ nip: "nomor-lama", ...pihakDariPegawai(daftar[1]) }).toMatchObject({ pegawai_id: "pegawai-2", nama: "Budi", nip: "" });
  fireEvent.click(screen.getByTestId("pilih"));
  fireEvent.change(screen.getByTestId("pilih-search"), { target: { value: "dua@example" } });
  expect(screen.queryByRole("option", { name: /satu@example/ })).not.toBeInTheDocument();
  expect(screen.getByRole("option", { name: /dua@example/ })).toBeInTheDocument();
});

test("nama yang diketik tidak mengikat identitas sampai dipilih eksplisit", () => {
  const pilih = jest.fn();
  render(<PilihPegawaiBast daftar={[{ id: "p", nama: "Budi" }]} onPilih={pilih} testId="pilih" />);
  fireEvent.click(screen.getByTestId("pilih"));
  fireEvent.change(screen.getByTestId("pilih-search"), { target: { value: "Budi" } });
  expect(pilih).not.toHaveBeenCalled();
  expect(pihakDariPegawai(null)).toEqual({ pegawai_id: "", nama: "", nip: "", jabatan: "", alamat: "" });
});

test("satu baris pilihan saat tertutup dan identitas yang hilang tidak disembunyikan", () => {
  const view = render(<PilihPegawaiBast daftar={[{ id: "p", nama: "Budi", nip: "123" }]} value="p" onPilih={jest.fn()} testId="pilih" />);
  expect(screen.getByTestId("pilih")).toHaveTextContent("Budi");
  expect(screen.queryByTestId("pilih-search")).not.toBeInTheDocument();
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  view.rerender(<PilihPegawaiBast daftar={[]} value="p" onPilih={jest.fn()} testId="pilih" />);
  expect(screen.getByRole("alert")).toHaveTextContent("Pegawai tertaut tidak tersedia");
  expect(screen.getByTestId("pilih")).toHaveTextContent("Pilihan tertaut tidak tersedia");
});

test("pihak luar tetap tersedia dan pegawai meninggal tidak dapat dipilih", () => {
  const pilih = jest.fn();
  render(<PilihPegawaiBast daftar={[{ id: "p", nama: "Budi", status: "meninggal" }]} onPilih={pilih} testId="pilih" />);
  fireEvent.click(screen.getByTestId("pilih"));
  expect(screen.queryByTestId("pilih-option-p")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("pilih-option-empty"));
  expect(pilih).toHaveBeenCalledWith(null);
});

test("ringkasan otomasi memuat penolakan spesifik dan tombol pemeriksaan sumber", () => {
  const bast = { id: "b1", portal_otomasi: { version: 3, status: "sebagian", alasan: "Email belum disetujui", hasil: [{ asset_id: "a1", status: "aktif" }, { asset_id: "a2", status: "perlu_tinjauan", alasan: "Identitas pegawai belum terpetakan" }] } };
  const sync = jest.fn();
  render(<StatusOtomasiBast bast={bast} onSinkronkan={sync} />);
  expect(screen.getByTestId("bast-portal-status-b1")).toHaveTextContent("Sebagian penugasan perlu ditinjau");
  expect(screen.getByText("Identitas pegawai belum terpetakan")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("bast-portal-sinkron-b1")); expect(sync).toHaveBeenCalledWith(bast);
});

test("BAST lama tidak ditawari retry yang pasti ditolak backend", () => {
  render(<StatusOtomasiBast bast={{ id: "lama" }} onSinkronkan={jest.fn()} />);
  expect(screen.queryByTestId("bast-portal-sinkron-lama")).not.toBeInTheDocument();
  expect(screen.getByTestId("bast-portal-status-lama")).toHaveTextContent("Dokumen lama tidak diterapkan otomatis");
});


// ── PGW-08: orang luar dari direktori ───────────────────────────────────
const PETUGAS = { id: "luar-1", nama: "Teknisi Andi", nip: "3201", kelompok: "pihak_ketiga",
  tataran: "", ranah: "luar", kunci_ikon: "pihak_ketiga", kapasitas_bertindak: "petugas",
  instansi_nama: "PT Maju", satker_luar_nama: "Kantor Pusat", alamat: "" };

test("pihak luar dari direktori: alamat jatuh ke instansi — satker; id direktori ikut", () => {
  expect(pihakDariPegawai(PETUGAS)).toEqual({ pegawai_id: "luar-1", nama: "Teknisi Andi",
    nip: "3201", jabatan: "", alamat: "PT Maju — Kantor Pusat", kelompok: "pihak_ketiga",
    tataran: "", instansi_nama: "PT Maju" });
  expect(pihakDariPegawai({ ...PETUGAS, alamat: "Jl. Mawar 1" }).alamat).toBe("Jl. Mawar 1");
});

test("memilih petugas pihak ketiga memunculkan peringatan lunak tanpa alarm 'tidak tersedia'", async () => {
  axios.get.mockResolvedValue({ data: { items: [PETUGAS] } });
  const pilih = jest.fn();
  const { rerender } = render(<PilihPegawaiBast daftar={[]} onPilih={pilih} testId="pilih" />);
  fireEvent.click(screen.getByTestId("pilih-pilih-kelompok-pihak_ketiga"));
  fireEvent.click(await screen.findByTestId("pilih-luar-opt-luar-1"));
  expect(pilih).toHaveBeenCalledWith(PETUGAS);
  rerender(<PilihPegawaiBast daftar={[]} value="luar-1" pihak={pihakDariPegawai(PETUGAS)}
    onPilih={pilih} testId="pilih" />);
  expect(screen.getByTestId("pilih-peringatan-petugas")).toBeInTheDocument();
  expect(screen.getByTestId("pilih-luar-terpilih")).toHaveTextContent("Teknisi Andi");
  expect(screen.queryByText(/Pegawai tertaut tidak tersedia/)).toBeNull();
  await waitFor(() => expect(axios.get.mock.calls[0][1].params).toMatchObject({ kelompok: "pihak_ketiga" }));
});

test("BAST lama yang ditaut ke orang luar dikenali dari kelompok yang dibekukan", () => {
  render(<PilihPegawaiBast daftar={[]} value="luar-9" onPilih={jest.fn()} testId="pilih"
    pihak={{ pegawai_id: "luar-9", nama: "Bu Rina", kelompok: "eksternal", tataran: "daerah",
      instansi_nama: "Kabupaten X" }} />);
  expect(screen.queryByText(/Pegawai tertaut tidak tersedia/)).toBeNull();
  expect(screen.getByRole("img", { name: "Pegawai pemda" })).toBeInTheDocument();
});
