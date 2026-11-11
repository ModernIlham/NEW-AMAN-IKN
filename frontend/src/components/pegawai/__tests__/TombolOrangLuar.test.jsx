import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import TombolOrangLuar from "../TombolOrangLuar";
import IkonKelompok from "../IkonKelompok";
import { _setelUlangPenampung } from "@/hooks/useKelompokOrang";

jest.mock("axios");

beforeEach(() => { jest.clearAllMocks(); window.localStorage.clear(); _setelUlangPenampung(); });

test("hanya kelompok luar yang ditawarkan; memilih orang memanggil onPilih", async () => {
  const orang = { id: "o9", nama: "Bu Rina", nip: "6471", kunci_ikon: "eksternal_daerah",
    instansi_nama: "Kabupaten X", satker_luar_nama: "Dinas PU" };
  axios.get.mockResolvedValue({ data: { items: [orang] } });
  const pilih = jest.fn();
  render(<TombolOrangLuar onPilih={pilih} testId="t" />);
  fireEvent.click(screen.getByTestId("t"));
  expect(await screen.findByTestId("t-kelompok-eksternal")).toBeInTheDocument();
  expect(screen.queryByTestId("t-kelompok-internal")).toBeNull();
  fireEvent.click(screen.getByTestId("t-tataran-daerah"));
  await waitFor(() => expect(axios.get.mock.calls.at(-1)[1].params)
    .toMatchObject({ kelompok: "eksternal", tataran: "daerah" }));
  fireEvent.click(await screen.findByTestId("t-cari-opt-o9"));
  expect(pilih).toHaveBeenCalledWith(orang);
});

test("nomor yang sedang diketik baru ditanyakan setelah berhenti — satu permintaan", async () => {
  jest.useFakeTimers();
  try {
    axios.post.mockResolvedValue({ data: { nomor: { "19800101": "internal" } } });
    const { rerender } = render(<IkonKelompok nomor="1" />);
    await act(async () => { jest.advanceTimersByTime(60); });
    expect(axios.post).toHaveBeenCalledTimes(1); // nomor awal (baris yang baru dipasang)
    for (const n of ["19", "1980", "198001", "19800101"]) {
      rerender(<IkonKelompok nomor={n} />);
      await act(async () => { jest.advanceTimersByTime(100); });
    }
    expect(axios.post).toHaveBeenCalledTimes(1);
    // Jeda ketik 400 ms → nomor terakhir masuk antre; lalu tumpukan 40 ms.
    await act(async () => { jest.advanceTimersByTime(450); });
    await act(async () => { jest.advanceTimersByTime(100); });
    expect(axios.post).toHaveBeenCalledTimes(2);
    expect(axios.post.mock.calls[1][1]).toEqual({ nomor: ["19800101"] });
  } finally {
    jest.useRealTimers();
  }
});
