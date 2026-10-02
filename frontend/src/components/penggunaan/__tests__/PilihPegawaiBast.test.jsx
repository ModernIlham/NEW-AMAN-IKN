import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import PilihPegawaiBast, { pihakDariPegawai } from "../PilihPegawaiBast";
import StatusOtomasiBast from "../StatusOtomasiBast";

test("nama kembar dibedakan UUID dan tanpa NIP tidak mewarisi identitas lama", () => {
  const daftar = [{ id: "pegawai-1", nama: "Budi", nip: "123", email: "satu@example.test" }, { id: "pegawai-2", nama: "Budi", nip: "", email: "dua@example.test" }];
  const pilih = jest.fn();
  render(<PilihPegawaiBast daftar={daftar} onPilih={pilih} testId="pilih" />);
  fireEvent.change(screen.getByTestId("pilih"), { target: { value: "pegawai-2" } });
  expect(pilih).toHaveBeenCalledWith(daftar[1]);
  expect({ nip: "nomor-lama", ...pihakDariPegawai(daftar[1]) }).toMatchObject({ pegawai_id: "pegawai-2", nama: "Budi", nip: "" });
  fireEvent.change(screen.getByTestId("pilih-cari"), { target: { value: "dua@example" } });
  expect(screen.queryByRole("option", { name: /satu@example/ })).not.toBeInTheDocument();
  expect(screen.getByRole("option", { name: /dua@example/ })).toBeInTheDocument();
});

test("nama yang diketik tidak mengikat identitas sampai dipilih eksplisit", () => {
  const pilih = jest.fn();
  render(<PilihPegawaiBast daftar={[{ id: "p", nama: "Budi" }]} onPilih={pilih} testId="pilih" />);
  fireEvent.change(screen.getByTestId("pilih-cari"), { target: { value: "Budi" } });
  expect(pilih).not.toHaveBeenCalled();
  expect(pihakDariPegawai(null)).toEqual({ pegawai_id: "", nama: "", nip: "", jabatan: "", alamat: "" });
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
