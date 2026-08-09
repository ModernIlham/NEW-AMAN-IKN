/**
 * Uji render Panel KDP — daftar dimuat dari GET /pembukuan/kdp dan dua
 * aksinya benar-benar menembak endpoint yang tepat dengan payload benar
 * (pengembangan 503 membawa nilai; penyelesaian membawa kode_baru dan
 * tombolnya terkunci sampai kodenya 10 digit).
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import PanelKdp from "../PanelKdp";

jest.mock("axios");

const DATA = {
  items: [{ id: "kdp-1", asset_code: "7010101001", NUP: "1",
    asset_name: "Pembangunan Gedung Arsip", nilai: 500000000,
    location: "Kawasan Inti" }],
  total_nilai: 500000000,
};

beforeEach(() => {
  axios.get.mockImplementation(() => Promise.resolve({ data: DATA }));
  axios.post.mockImplementation(() => Promise.resolve({
    data: { ok: true, nilai_berjalan: 750000000,
            kode_baru: "4010101001", nup_baru: "1" } }));
});

test("daftar KDP tampil dengan nilai berjalan", async () => {
  render(<PanelKdp />);
  expect(await screen.findByTestId("kdp-item-kdp-1")).toBeInTheDocument();
  expect(screen.getByText(/Pembangunan Gedung Arsip/)).toBeInTheDocument();
  expect(String(axios.get.mock.calls[0][0])).toMatch(/\/pembukuan\/kdp$/);
});

test("pengembangan mengirim nilai ke endpoint 503", async () => {
  render(<PanelKdp />);
  await screen.findByTestId("kdp-item-kdp-1");
  await userEvent.click(screen.getByTestId("kdp-pengembangan-kdp-1"));
  await userEvent.type(screen.getByTestId("kdp-nilai"), "250000000");
  await userEvent.click(screen.getByTestId("kdp-kirim"));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  const [url, body] = axios.post.mock.calls[0];
  expect(String(url)).toMatch(/\/pembukuan\/kdp\/kdp-1\/pengembangan$/);
  expect(body.nilai).toBe(250000000);
});

test("penyelesaian terkunci sampai kode 10 digit lalu mengirim kode_baru", async () => {
  render(<PanelKdp />);
  await screen.findByTestId("kdp-item-kdp-1");
  await userEvent.click(screen.getByTestId("kdp-selesaikan-kdp-1"));
  const kode = await screen.findByTestId("kdp-kode-baru");
  await userEvent.type(kode, "40101");
  expect(screen.getByTestId("kdp-kirim")).toBeDisabled();
  await userEvent.type(kode, "01001");
  await userEvent.click(screen.getByTestId("kdp-kirim"));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  const [url, body] = axios.post.mock.calls[0];
  expect(String(url)).toMatch(/\/pembukuan\/kdp\/kdp-1\/selesaikan$/);
  expect(body.kode_baru).toBe("4010101001");
});
