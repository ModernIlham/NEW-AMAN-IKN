import React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axios from "axios";
import PenggunaanPage from "../PenggunaanPage";

jest.mock("axios");

const nik = "6401010101900001";
const row = { nama: "Pemegang Uji", nip: nik, label_identitas: "NIK",
  jumlah_aset: 1, jumlah_kegiatan: 1, jumlah_bast: 0, pegawai_terdaftar: true };
function api(gagal = false) {
  axios.get.mockImplementation((url) => {
    if (url.endsWith("/penggunaan/pemegang")) {
      if (gagal) return Promise.reject(new Error("putus"));
      return Promise.resolve({ data: { items: [row, { ...row, nama: "Tanpa Nomor", nip: "", label_identitas: "" }], total_pemegang: 2 } });
    }
    if (url.endsWith("/penggunaan/pemegang/aset")) return Promise.resolve({ data: { items: [{ id: "a", asset_name: "Kursi Uji" }] } });
    return Promise.resolve({ data: { items: [] } });
  });
}
beforeEach(() => jest.clearAllMocks());

test.each([false, true])("NIK tidak dilabel NIP, nama tanpa nomor tetap terlihat; tema gelap=%s", async gelap => {
  document.documentElement.classList.toggle("dark", gelap);
  api();
  render(<PenggunaanPage user={{ role: "admin" }} />);
  const pemegang = await screen.findByTestId("penggunaan-row-Pemegang Uji");
  expect(within(pemegang).getByText(new RegExp(`NIK ${nik}`))).toBeInTheDocument();
  expect(pemegang).not.toHaveTextContent(`NIP ${nik}`);
  expect(screen.getByTestId("penggunaan-row-Tanpa Nomor")).toBeInTheDocument();
  fireEvent.click(pemegang);
  expect(await screen.findByText("Kursi Uji")).toBeInTheDocument();
  expect(within(screen.getByRole("dialog")).getByText(`NIK ${nik}`)).toBeInTheDocument();
  document.documentElement.classList.remove("dark");
});

test("kegagalan API dibedakan dari daftar kosong dan bisa dicoba lagi", async () => {
  api(true);
  render(<PenggunaanPage user={{ role: "admin" }} />);
  const coba = await screen.findByTestId("pemegang-coba-lagi");
  expect(screen.queryByText("Belum ada pemegang tercatat")).not.toBeInTheDocument();
  api();
  fireEvent.click(coba);
  await waitFor(() => expect(screen.getByTestId("penggunaan-row-Pemegang Uji")).toBeInTheDocument());
  expect(screen.queryByTestId("pemegang-coba-lagi")).not.toBeInTheDocument();
});
