import React, { useState } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import PanelLapanganPeta, { buatTokoPosisi } from "../PanelLapanganPeta";
import { siapkanTitikAset } from "../../../lib/asetTerdekat";

const P = { lat: -1, lng: 116, accuracy: 5 };
const row = (id, dLat, status = "Belum Diinventarisasi") => ({ id, asset_name: `Aset ${id}`, asset_code: "301", NUP: id,
  inventory_status: status, koordinat_latitude: String(-1 + dLat), koordinat_longitude: "116" });
const rows = [row("1", 0.0002, "Ditemukan"), row("2", 0.0001), row("3", 0.003)];
const titik = siapkanTitikAset(rows);

function Uji({ toko, ...props }) {
  const [tujuan, setTujuan] = useState(null);
  return <PanelLapanganPeta toko={toko} titik={titik} tujuan={tujuan} onPandu={setTujuan} onFokus={() => {}} {...props} />;
}

beforeEach(() => localStorage.removeItem("aman_peta_terdekat_belum"));

test("tersembunyi saat lokasi mati; ringkasan dengan pil akurasi; daftar terurut; fokus & edit", () => {
  const toko = buatTokoPosisi();
  const onFokus = jest.fn(), onEdit = jest.fn();
  render(<Uji toko={toko} onFokus={onFokus} onEdit={onEdit} />);
  expect(screen.queryByTestId("panel-lapangan")).not.toBeInTheDocument();
  act(() => toko.set(P));
  expect(screen.getByTestId("panel-lapangan-toggle")).toHaveTextContent("2 aset ≤ 50 m");
  expect(screen.getByTestId("panel-lapangan-akurasi")).toHaveTextContent("GPS ±5 m");
  fireEvent.click(screen.getByTestId("panel-lapangan-toggle"));
  expect(screen.getAllByTestId(/^terdekat-\d$/).map((b) => b.dataset.testid)).toEqual(["terdekat-2", "terdekat-1", "terdekat-3"]);
  fireEvent.click(screen.getByTestId("terdekat-2"));
  expect(onFokus).toHaveBeenCalledWith(expect.objectContaining({ id: "2" }));
  // Daftar dilipat agar popup pin di bawahnya bisa diketuk.
  expect(screen.queryByTestId("panel-lapangan-isi")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("panel-lapangan-toggle"));
  fireEvent.click(screen.getByTestId("terdekat-edit-1"));
  expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ id: "1" }));
});

test("pandu: menuju → tiba (getar sekali) → titik = lokasi saya (dua ketuk) → selesai; lokasi mati menghentikan pandu", () => {
  const toko = buatTokoPosisi();
  const onSetTitik = jest.fn(() => true);
  const getar = jest.fn();
  Object.defineProperty(navigator, "vibrate", { configurable: true, value: getar });
  render(<Uji toko={toko} onSetTitik={onSetTitik} onEdit={() => {}} />);
  act(() => toko.set(P));
  fireEvent.click(screen.getByTestId("panel-lapangan-toggle"));
  fireEvent.click(screen.getByTestId("terdekat-pandu-3"));
  expect(screen.getByTestId("panel-lapangan-pandu-judul")).toHaveTextContent("Menuju Aset 3");
  expect(screen.getByTestId("panel-lapangan-pandu-jarak")).toHaveTextContent(/333,\d m · Utara/);
  expect(screen.queryByTestId("panel-lapangan-pandu-set-titik")).not.toBeInTheDocument();
  expect(screen.getByTestId("panel-lapangan-pandu-gmaps")).toHaveAttribute("href", expect.stringContaining("destination=-0.997000,116.000000"));
  act(() => toko.set({ lat: -0.99701, lng: 116, accuracy: 4 }));
  expect(screen.getByTestId("panel-lapangan-pandu-judul")).toHaveTextContent("Anda di lokasi Aset 3");
  expect(getar).toHaveBeenCalledTimes(1);
  act(() => toko.set({ lat: -0.997005, lng: 116, accuracy: 4 }));
  expect(getar).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByTestId("panel-lapangan-pandu-set-titik"));
  expect(onSetTitik).not.toHaveBeenCalled();
  expect(screen.getByTestId("panel-lapangan-pandu-set-titik")).toHaveTextContent("Ketuk lagi");
  fireEvent.click(screen.getByTestId("panel-lapangan-pandu-set-titik"));
  expect(onSetTitik).toHaveBeenCalledWith(expect.objectContaining({ id: "3" }));
  fireEvent.click(screen.getByTestId("panel-lapangan-pandu-selesai"));
  expect(screen.getByTestId("panel-lapangan")).toBeInTheDocument();
  // Daftar tetap terbuka setelah selesai memandu — lanjut ke aset berikutnya.
  fireEvent.click(screen.getByTestId("terdekat-pandu-2"));
  act(() => toko.set(null));
  act(() => toko.set(P));
  expect(screen.queryByTestId("panel-lapangan-pandu")).not.toBeInTheDocument();
  delete navigator.vibrate;
});

test("gerbang presisi 8 m: tambah & set titik nonaktif dengan alasan saat GPS kasar", () => {
  const toko = buatTokoPosisi();
  const onTambah = jest.fn();
  toko.set({ ...P, accuracy: 23 });
  render(<Uji toko={toko} onTambahDiSini={onTambah} onSetTitik={() => true} />);
  expect(screen.getByTestId("panel-lapangan-akurasi")).toHaveTextContent("GPS ±23 m");
  fireEvent.click(screen.getByTestId("panel-lapangan-toggle"));
  expect(screen.getByTestId("panel-lapangan-tambah")).toBeDisabled();
  expect(screen.getByText(/Tunggu GPS ≤ 8 m \(kini ±23 m\)/)).toBeInTheDocument();
  act(() => toko.set({ ...P, accuracy: 6 }));
  fireEvent.click(screen.getByTestId("panel-lapangan-tambah"));
  expect(onTambah).toHaveBeenCalled();
  expect(screen.queryByTestId("panel-lapangan-isi")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("panel-lapangan-toggle"));
  fireEvent.click(screen.getByTestId("panel-lapangan-belum"));
  expect(screen.queryByTestId("terdekat-1")).not.toBeInTheDocument();
  expect(localStorage.getItem("aman_peta_terdekat_belum")).toBe("1");
});
