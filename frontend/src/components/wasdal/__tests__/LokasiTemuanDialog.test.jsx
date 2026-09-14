import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import L from "leaflet";
import LokasiTemuanDialog from "../LokasiTemuanDialog";
import { titikSah } from "@/lib/titikDenah";

jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn(), put: jest.fn() }));
jest.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children }) => <div>{children}</div>,
  DialogContent: ({ children, ...p }) => <div {...p}>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
  DialogDescription: ({ children }) => <p>{children}</p>,
}));
jest.mock("leaflet", () => {
  const layer = { addTo: jest.fn().mockReturnThis(), remove: jest.fn(), setLatLng: jest.fn().mockReturnThis() };
  const map = { attributionControl: { setPrefix: jest.fn() }, setView: jest.fn().mockReturnThis(),
    on: jest.fn(), invalidateSize: jest.fn(), remove: jest.fn(),
    getBounds: () => ({ getWest: () => 116, getEast: () => 117, getSouth: () => -2, getNorth: () => -1 }) };
  return { map: jest.fn(() => map), marker: jest.fn(() => layer), tileLayer: jest.fn(() => layer), geoJSON: jest.fn(() => layer) };
});

const lama = { node_id: "lantai-lama", node_tipe: "LANTAI", titik: [116.7, -1.4], jalur_nama: "Gedung A / Lantai 1" };
const deteksi = { rantai: [{ id: "gedung-baru", nama: "Gedung B" }], lantai_terpilih: "lantai-baru",
  lantai: [{ id: "lantai-baru", nama: "Lantai 2", status: "aktif" }] };
const tunda = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };

beforeEach(() => {
  jest.clearAllMocks();
  const layer = { addTo: jest.fn().mockReturnThis(), remove: jest.fn(), setLatLng: jest.fn().mockReturnThis() };
  const map = { attributionControl: { setPrefix: jest.fn() }, setView: jest.fn().mockReturnThis(),
    on: jest.fn(), invalidateSize: jest.fn(), remove: jest.fn(),
    getBounds: () => ({ getWest: () => 116, getEast: () => 117, getSouth: () => -2, getNorth: () => -1 }) };
  L.map.mockReturnValue(map);
  [L.marker, L.tileLayer, L.geoJSON].forEach(fn => fn.mockReturnValue(layer));
  axios.post.mockResolvedValue({ data: deteksi });
  axios.get.mockImplementation(url => Promise.resolve({ data: url.includes("ruangan-di-titik")
    ? { ditemukan: true, ruangan: { id: "ruang-baru", nama: "Ruang Baru" } } : { features: [] } }));
  axios.put.mockResolvedValue({ data: { lokasi_spasial: { node_id: "ruang-baru" }, asset: { version: 4 } } });
});

const buka = (props = {}) => render(<LokasiTemuanDialog judul="Meja" submitUrl="/api/assets/a1/lokasi-spasial"
  lokasiAwal={lama} titikAwal={[116.8, -1.5]} version={3} {...props} />);
const siap = () => waitFor(() => expect(screen.getByTestId("lokasi-temuan-simpan")).toBeEnabled());

test("buka lalu simpan mempertahankan lantai tersimpan, bukan hasil deteksi ruangan", async () => {
  buka(); await siap();
  fireEvent.click(screen.getByTestId("lokasi-temuan-simpan"));
  await waitFor(() => expect(axios.put).toHaveBeenCalledWith(expect.any(String),
    { lat: -1.4, lon: 116.7, node_id: "lantai-lama" }, expect.objectContaining({ headers: expect.objectContaining({ "If-Match": "3" }) })));
});

test("gunakan koordinat terbaru memindahkan marker, node, dan payload", async () => {
  const onSaved = jest.fn(); buka({ onSaved }); await siap();
  fireEvent.click(screen.getByTestId("lokasi-temuan-koordinat-terbaru"));
  await waitFor(() => expect(screen.getByTestId("lokasi-temuan-ruangan")).toHaveValue("ruang-baru"));
  await siap(); fireEvent.click(screen.getByTestId("lokasi-temuan-simpan"));
  await waitFor(() => expect(axios.put).toHaveBeenCalledWith(expect.any(String),
    { lat: -1.5, lon: 116.8, node_id: "ruang-baru" }, expect.any(Object)));
  expect(L.marker().setLatLng).toHaveBeenCalledWith([-1.5, 116.8]);
  expect(onSaved).toHaveBeenCalledWith({ node_id: "ruang-baru" }, expect.objectContaining({ asset: { version: 4 } }));
});

test("deteksi ulang sengaja boleh mempersempit lantai lama ke ruangan", async () => {
  axios.post.mockResolvedValue({ data: { ...deteksi, lantai_terpilih: "lantai-lama",
    lantai: [{ id: "lantai-lama", nama: "Lantai Lama", status: "aktif" }] } });
  buka(); await siap();
  fireEvent.click(screen.getByTestId("lokasi-temuan-deteksi-ulang"));
  await waitFor(() => expect(screen.getByTestId("lokasi-temuan-ruangan")).toHaveValue("ruang-baru"));
  await siap(); fireEvent.click(screen.getByTestId("lokasi-temuan-simpan"));
  expect(axios.put.mock.calls[0][1].node_id).toBe("ruang-baru");
});

test("simpan menunggu deteksi ruangan selesai", async () => {
  const pending = tunda();
  axios.get.mockImplementation(url => url.includes("ruangan-di-titik") ? pending.promise : Promise.resolve({ data: { features: [] } }));
  buka({ lokasiAwal: null });
  await waitFor(() => expect(axios.get).toHaveBeenCalledWith(expect.stringContaining("ruangan-di-titik"), expect.any(Object)));
  expect(screen.getByTestId("lokasi-temuan-simpan")).toBeDisabled();
  await act(async () => pending.resolve({ data: { ditemukan: true, ruangan: { id: "r", nama: "R" } } }));
  await siap();
});

test("respons deteksi lama yang terlambat tidak mengembalikan node lama", async () => {
  const pending = tunda();
  axios.post.mockReturnValueOnce(pending.promise).mockResolvedValue({ data: deteksi });
  buka();
  const klik = L.map().on.mock.calls.find(([event]) => event === "click")[1];
  act(() => klik({ latlng: { lat: -1.6, lng: 116.9 } }));
  await waitFor(() => expect(screen.getByTestId("lokasi-temuan-ruangan")).toHaveValue("ruang-baru"));
  await act(async () => pending.resolve({ data: { rantai: [{ id: "usang", nama: "Usang" }] } }));
  await siap(); fireEvent.click(screen.getByTestId("lokasi-temuan-simpan"));
  expect(axios.put.mock.calls[0][1]).toEqual({ lat: -1.6, lon: 116.9, node_id: "ruang-baru" });
});

test("ulang jaringan memakai kunci sama; klik ganda tidak menulis dua kali", async () => {
  const pending = tunda();
  axios.put.mockRejectedValueOnce(new Error("offline")).mockReturnValue(pending.promise);
  buka(); await siap();
  fireEvent.click(screen.getByTestId("lokasi-temuan-simpan")); await siap();
  fireEvent.click(screen.getByTestId("lokasi-temuan-simpan"));
  fireEvent.click(screen.getByTestId("lokasi-temuan-simpan"));
  expect(axios.put).toHaveBeenCalledTimes(2);
  expect(axios.put.mock.calls[0][2]).toEqual(axios.put.mock.calls[1][2]);
  await act(async () => pending.resolve({ data: {} }));
});

test("konflik menahan penyimpanan dan tidak memberi keberhasilan palsu", async () => {
  const onSaved = jest.fn(); axios.put.mockRejectedValue({ response: { status: 409, data: { detail: "Versi berubah" } } });
  buka({ onSaved }); await siap(); fireEvent.click(screen.getByTestId("lokasi-temuan-simpan"));
  await screen.findByRole("alert");
  expect(screen.getByTestId("lokasi-temuan-simpan")).toBeDisabled();
  expect(onSaved).not.toHaveBeenCalled();
});

test("wasdal tetap tanpa header versi wajib dan callback lokasi lama tetap bekerja", async () => {
  const onSaved = jest.fn(); buka({ version: undefined, onSaved }); await siap();
  fireEvent.click(screen.getByTestId("lokasi-temuan-hapus"));
  expect(axios.put).toHaveBeenCalledWith(expect.any(String), { hapus: true }, undefined);
  await waitFor(() => expect(onSaved).toHaveBeenCalled());
});

test.each([[null, null], ["", ""], [116, 91], [181, -1], ["116rusak", -1], [true, -1]])("koordinat rusak ditolak: %j", (...p) => {
  expect(titikSah(p)).toBeNull();
});
