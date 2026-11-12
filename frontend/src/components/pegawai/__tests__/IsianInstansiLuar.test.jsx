import React, { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import IsianInstansiLuar from "../IsianInstansiLuar";

jest.mock("axios");

const KAB = { id: "kab1", nama: "Kabupaten Penajam Paser Utara", kelompok: "eksternal", tataran: "daerah" };

function Wadah({ catat }) {
  const [s, setS] = useState({ teks: "", instansi: null });
  return <IsianInstansiLuar teks={s.teks} instansiId={s.instansi?.id || ""} instansi={s.instansi}
    testId="mitra" onUbah={(v) => { catat(v); setS(v); }} />;
}

beforeEach(() => jest.clearAllMocks());

test("memilih saran menautkan; mengubah teks melepas tautan; teks tetap teks", async () => {
  axios.get.mockImplementation((url, cfg) => Promise.resolve({ data: {
    items: cfg.params.kelompok === "eksternal" ? [KAB] : [{ id: "w", nama: "Masyarakat (Perorangan)", wadah: true }] } }));
  const catat = jest.fn();
  const { container } = render(<Wadah catat={catat} />);
  const input = screen.getByTestId("mitra");
  fireEvent.change(input, { target: { value: "Kabupaten" } });
  await waitFor(() => expect(container.querySelectorAll("datalist option")).toHaveLength(1));
  expect(axios.get.mock.calls.map(([, c]) => c.params.kelompok).sort()).toEqual(["eksternal", "pihak_ketiga"]);
  expect(screen.getByTestId("mitra-status")).toHaveTextContent("Teks bebas");
  fireEvent.change(input, { target: { value: KAB.nama } });
  expect(catat).toHaveBeenLastCalledWith({ teks: KAB.nama, instansi: KAB });
  expect(screen.getByTestId("mitra-status")).toHaveTextContent("Tertaut");
  expect(screen.getByRole("img", { name: "Pegawai pemda" })).toBeInTheDocument();
  fireEvent.change(input, { target: { value: KAB.nama + " (Bappeda)" } });
  expect(catat).toHaveBeenLastCalledWith({ teks: KAB.nama + " (Bappeda)", instansi: null });
  expect(screen.queryByRole("img")).toBeNull();
});

test("direktori gagal dihubungi → tetap bisa diketik bebas", async () => {
  axios.get.mockRejectedValue(new Error("luring"));
  const catat = jest.fn();
  render(<Wadah catat={catat} />);
  fireEvent.change(screen.getByTestId("mitra"), { target: { value: "CV Lokal" } });
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  expect(catat).toHaveBeenLastCalledWith({ teks: "CV Lokal", instansi: null });
  expect(screen.getByTestId("mitra")).toHaveValue("CV Lokal");
});
