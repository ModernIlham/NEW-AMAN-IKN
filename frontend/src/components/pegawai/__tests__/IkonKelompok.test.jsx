import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import IkonKelompok from "../IkonKelompok";
import { _setelUlangPenampung } from "@/hooks/useKelompokOrang";

jest.mock("axios");

beforeEach(() => {
  jest.clearAllMocks();
  window.localStorage.clear();
  _setelUlangPenampung();
});

test("tiap kelompok punya nama terakses yang berbeda", () => {
  render(<>
    {["internal", "eksternal_pusat", "eksternal_daerah", "pihak_ketiga"].map((k) => (
      <IkonKelompok key={k} kunciIkon={k} />))}
  </>);
  const nama = screen.getAllByRole("img").map((el) => el.getAttribute("aria-label"));
  expect(nama).toEqual(["Pegawai internal", "Pegawai kementerian/lembaga", "Pegawai pemda", "Pihak ketiga"]);
});

test("kunci tak dikenal → tidak merender apa pun", () => {
  const { container } = render(<IkonKelompok kunciIkon="bukan" />);
  expect(container).toBeEmptyDOMElement();
});

test("nomor tak dikenal server → tanpa ikon; jawabannya diingat", async () => {
  axios.post.mockResolvedValue({ data: { nomor: { "111": "pihak_ketiga" } } });
  render(<><IkonKelompok nomor="111" /><IkonKelompok nomor="999" /></>);
  expect(await screen.findByRole("img", { name: "Pihak ketiga" })).toBeInTheDocument();
  expect(screen.getAllByRole("img")).toHaveLength(1);
  expect(JSON.parse(window.localStorage.getItem("aman.kelompokOrang.v1"))["999"].k).toBeNull();
});

test("penjawab kelompok gagal → layar tetap tampil tanpa ikon", async () => {
  axios.post.mockRejectedValue(new Error("luring"));
  render(<div><p>Baris tetap ada</p><IkonKelompok nomor="123" /></div>);
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  expect(screen.getByText("Baris tetap ada")).toBeInTheDocument();
  expect(screen.queryByRole("img")).toBeNull();
});

test("seratus baris dengan sepuluh nomor berbeda → satu permintaan", async () => {
  const jawab = Object.fromEntries([...Array(10)].map((_, i) => [`19800${i}`, "internal"]));
  axios.post.mockResolvedValue({ data: { nomor: jawab } });
  render(<ul>{[...Array(100)].map((_, i) => (
    <li key={i}><IkonKelompok nomor={`19800${i % 10}`} /></li>))}</ul>);
  await waitFor(() => expect(screen.getAllByRole("img")).toHaveLength(100));
  expect(axios.post).toHaveBeenCalledTimes(1);
  const [url, body] = axios.post.mock.calls[0];
  expect(String(url)).toMatch(/\/direktori-pegawai\/kelompok$/);
  expect([...body.nomor].sort()).toEqual(Object.keys(jawab).sort());
});

test("jawaban tersimpan dipakai saat luring, tanpa bertanya lagi", async () => {
  window.localStorage.setItem("aman.kelompokOrang.v1", JSON.stringify({
    "777": { k: "eksternal_daerah", t: Date.now() } }));
  render(<IkonKelompok nomor="777" />);
  expect(screen.getByRole("img", { name: "Pegawai pemda" })).toBeInTheDocument();
  await new Promise((r) => setTimeout(r, 80));
  expect(axios.post).not.toHaveBeenCalled();
});
