/**
 * Pemilih kode barang — DUA sumber dalam satu ketikan.
 *
 * Permintaan pemilik: *"ketika persediaan pastikan sudah terdaftar untuk
 * memilih sesuai kodifikasi ... yang memiliki kode 16 digit"*.
 *
 * Sebelum ini pemilih hanya menarik REFERENSI KODEFIKASI, yang maksimal 10
 * digit. Barang persediaan yang sudah punya kartu stok — dan karenanya sudah
 * ber-kode 16 digit — tak pernah muncul untuk dipilih, jadi setiap pembelian
 * ulang berakhir sebagai tebakan server dan, bila meleset, kartu stok baru.
 *
 * Yang dijaga di sini: kedua sumber benar-benar ditembak, keduanya tampil
 * berlabel, dan menekan barang terdaftar mengembalikan MASTER-nya (bukan
 * baris kodefikasi) ke pemanggil.
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import axios from "axios";
import { KodeBarangPicker } from "../PengadaanPage";

jest.mock("axios");

const KODEFIKASI = {
  data: { items: [{ kode: "1010301001", uraian: "Kertas dan Cover",
    label_level: "Sub-sub kelompok", is_persediaan: true }] },
};
const PERSEDIAAN = {
  data: { items: [{ id: "psd-1", kode_barang: "1010301001000007",
    nama_barang: "Kertas HVS A4", satuan: "Rim", stok: 12 }] },
};

function pasang(props = {}) {
  const onChange = jest.fn();
  const onPick = jest.fn();
  const onPickPersediaan = jest.fn();
  render(<KodeBarangPicker value="" onChange={onChange} onPick={onPick}
    onPickPersediaan={onPickPersediaan} testid="kode-0" {...props} />);
  return { onChange, onPick, onPickPersediaan };
}

/** Ketik di kolom kode lalu tunggu debounce 300ms berlalu. */
async function ketik(teks) {
  fireEvent.change(screen.getByTestId("kode-0"), { target: { value: teks } });
  jest.advanceTimersByTime(400);
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
}

beforeEach(() => {
  jest.useFakeTimers();
  axios.get.mockImplementation((url) => (
    url.includes("/persediaan") ? Promise.resolve(PERSEDIAAN)
      : Promise.resolve(KODEFIKASI)));
});

afterEach(() => {
  jest.runOnlyPendingTimers();
  jest.useRealTimers();
  jest.clearAllMocks();
});

it("menembak KEDUA sumber sekali ketik", async () => {
  pasang();
  await ketik("kertas");
  const url = axios.get.mock.calls.map((c) => c[0]);
  expect(url.some((u) => u.endsWith("/kodefikasi"))).toBe(true);
  expect(url.some((u) => u.endsWith("/persediaan"))).toBe(true);
});

it("menampilkan barang persediaan terdaftar beserta kode 16 digitnya", async () => {
  pasang();
  await ketik("kertas");
  expect(await screen.findByText("1010301001000007")).toBeInTheDocument();
  expect(screen.getByText(/Terdaftar di persediaan/i)).toBeInTheDocument();
});

it("memilih barang terdaftar mengembalikan MASTER-nya, bukan baris kodefikasi", async () => {
  const { onPickPersediaan, onPick } = pasang();
  await ketik("kertas");
  fireEvent.mouseDown(await screen.findByTestId("kode-0-psd-psd-1"));
  expect(onPickPersediaan).toHaveBeenCalledWith(
    expect.objectContaining({ id: "psd-1", kode_barang: "1010301001000007" }));
  expect(onPick).not.toHaveBeenCalled();
});

it("baris referensi kodefikasi tetap bisa dipilih seperti sebelumnya", async () => {
  const { onPick, onPickPersediaan } = pasang();
  await ketik("kertas");
  fireEvent.mouseDown(await screen.findByText("Kertas dan Cover"));
  expect(onPick).toHaveBeenCalledWith(
    expect.objectContaining({ kode: "1010301001" }));
  expect(onPickPersediaan).not.toHaveBeenCalled();
});

it("sumber persediaan yang MATI tak mengosongkan sumber kodefikasi", async () => {
  // `Promise.allSettled`, bukan `all`: satu endpoint yang gagal tak boleh
  // membuat pemilih ini berhenti menawarkan apa pun.
  axios.get.mockImplementation((url) => (
    url.includes("/persediaan") ? Promise.reject(new Error("offline"))
      : Promise.resolve(KODEFIKASI)));
  pasang();
  await ketik("kertas");
  expect(await screen.findByText("Kertas dan Cover")).toBeInTheDocument();
  expect(screen.queryByText(/Terdaftar di persediaan/i)).not.toBeInTheDocument();
});

it("ketikan di bawah 2 huruf tak menembak jaringan sama sekali", async () => {
  pasang();
  fireEvent.change(screen.getByTestId("kode-0"), { target: { value: "k" } });
  jest.advanceTimersByTime(400);
  expect(axios.get).not.toHaveBeenCalled();
});
