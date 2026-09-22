import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import { pasangIndexedDbPalsu, pasangWebSocketPalsu } from "../../uji/lingkunganPeta";
import PetaKolaborasiPage from "../PetaKolaborasiPage";

jest.mock("leaflet", () => require("../../uji/lefletPalsu"));
jest.mock("leaflet.markercluster", () => ({}));
jest.mock("axios");

beforeAll(() => {
  pasangWebSocketPalsu(); pasangIndexedDbPalsu();
  window.HTMLElement.prototype.scrollIntoView = () => {};
});

test("tamu mencari lokasi/kode tanpa fetch baru, pilihan tetap AND, dan reset mengosongkan pencarian", async () => {
  window.history.pushState({}, "", "/peta/kolaborasi/peta-uji?token=tok-uji");
  const data = { nama_kegiatan: "Peta Uji", tamu: true, komentar: [], titik_kolaborasi: [],
    titik_aset: [
      { id: "1", lat: -1.4, lng: 116.7, kode: "3.10.01.02.001", nama: "Laptop", lokasi: "Gedung A", kondisi: "Baik", status: "Ditemukan" },
      { id: "2", lat: -1.41, lng: 116.71, kode: "3.10.01.02.001", nama: "Laptop", lokasi: "Gedung B", kondisi: "Baik", status: "Ditemukan" },
      { id: "3", lat: -1.42, lng: 116.72, kode: "3.05.01.01.001", nama: "Meja", lokasi: "Gedung A", kondisi: "Baik", status: "Ditemukan" },
      { id: "4", lat: -1.43, lng: 116.73, kode: "3.05.01.01.001", nama: "Meja", lokasi: "Gedung B", kondisi: "Baik", status: "Ditemukan" },
    ] };
  axios.get.mockImplementation(url => Promise.resolve({ data: String(url).includes("/usulan") ? { items: [] } : data }));
  render(<PetaKolaborasiPage />);
  await userEvent.click(await screen.findByTestId("peta-kolab-filter"));
  const jumlahFetch = axios.get.mock.calls.length;
  fireEvent.change(screen.getByRole("searchbox", { name: "Cari lokasi" }), { target: { value: "gedung b" } });
  expect(screen.queryByRole("button", { name: /Gedung A/ })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: /Gedung B/ }));
  fireEvent.change(screen.getByRole("searchbox", { name: "Cari barang serupa" }), { target: { value: "3100102001" } });
  await userEvent.click(within(screen.getByTestId("peta-filter-barang")).getByRole("button", { name: /Laptop/ }));
  // Hitungan toolbar memakai hasil gabungan, bukan hasil pencarian daftar opsi.
  expect(screen.getByText((_, el) => el?.tagName === "B" && el.textContent === "1")).toBeInTheDocument();
  expect(screen.getByTestId("peta-filter-lokasi-terpilih")).toHaveTextContent("Gedung B");
  expect(axios.get).toHaveBeenCalledTimes(jumlahFetch);
  await userEvent.click(screen.getByTestId("peta-kolab-filter-reset"));
  expect(screen.getByRole("searchbox", { name: "Cari lokasi" })).toHaveValue("");
  expect(screen.getByRole("searchbox", { name: "Cari barang serupa" })).toHaveValue("");
  expect(screen.queryByTestId("peta-filter-lokasi-terpilih")).toBeNull();
  expect(screen.getByText((_, el) => el?.tagName === "B" && el.textContent === "4")).toBeInTheDocument();
});
