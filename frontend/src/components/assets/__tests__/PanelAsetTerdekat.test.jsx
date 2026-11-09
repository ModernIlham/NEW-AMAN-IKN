import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import PanelAsetTerdekat, { buatTokoPosisi } from "../PanelAsetTerdekat";
import { siapkanTitikAset } from "../../../lib/asetTerdekat";

const P = { lat: -1, lng: 116, accuracy: 6 };
const row = (id, dLat, status = "Belum Diinventarisasi") => ({ id, asset_name: `Aset ${id}`, asset_code: "301", NUP: id,
  inventory_status: status, koordinat_latitude: String(-1 + dLat), koordinat_longitude: "116" });
const titik = siapkanTitikAset([row("1", 0.0002, "Ditemukan"), row("2", 0.0001), row("3", 0.003)]);

beforeEach(() => localStorage.removeItem("aman_peta_terdekat_belum"));

test("tersembunyi selama lokasi mati; ringkasan & daftar terurut saat aktif", () => {
  const toko = buatTokoPosisi();
  const onFokus = jest.fn(), onEdit = jest.fn();
  render(<PanelAsetTerdekat toko={toko} titik={titik} onFokus={onFokus} onEdit={onEdit} />);
  expect(screen.queryByTestId("panel-aset-terdekat")).not.toBeInTheDocument();
  act(() => toko.set(P));
  expect(screen.getByTestId("panel-aset-terdekat-toggle")).toHaveTextContent("2 aset ≤ 50 m");
  expect(screen.getByTestId("panel-aset-terdekat-toggle")).toHaveTextContent("terdekat 11,1 m");
  fireEvent.click(screen.getByTestId("panel-aset-terdekat-toggle"));
  const tombol = screen.getAllByTestId(/^terdekat-\d$/);
  expect(tombol.map((b) => b.dataset.testid)).toEqual(["terdekat-2", "terdekat-1", "terdekat-3"]);
  fireEvent.click(tombol[0]);
  expect(onFokus).toHaveBeenCalledWith(expect.objectContaining({ id: "2" }));
  fireEvent.click(screen.getByTestId("terdekat-edit-1"));
  expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ id: "1" }));
  act(() => toko.set(null));
  expect(screen.queryByTestId("panel-aset-terdekat")).not.toBeInTheDocument();
});

test("filter 'belum diinventarisasi' tersimpan; peringatan saat akurasi GPS kasar; tanpa tombol edit bila tak berhak", () => {
  const toko = buatTokoPosisi();
  toko.set({ ...P, accuracy: 60 });
  render(<PanelAsetTerdekat toko={toko} titik={titik} onFokus={() => {}} />);
  fireEvent.click(screen.getByTestId("panel-aset-terdekat-toggle"));
  fireEvent.click(screen.getByTestId("panel-aset-terdekat-belum"));
  expect(screen.queryByTestId("terdekat-1")).not.toBeInTheDocument();
  expect(screen.getByTestId("panel-aset-terdekat-toggle")).toHaveTextContent("1 aset belum didata ≤ 50 m");
  expect(localStorage.getItem("aman_peta_terdekat_belum")).toBe("1");
  expect(screen.getByText(/Akurasi GPS ±60 m/)).toBeInTheDocument();
  expect(screen.queryByTestId("terdekat-edit-2")).not.toBeInTheDocument();
});
