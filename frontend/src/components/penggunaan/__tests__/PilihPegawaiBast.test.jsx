import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import PilihPegawaiBast, { pihakDariPegawai } from "../PilihPegawaiBast";
import StatusOtomasiBast from "../StatusOtomasiBast";

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
