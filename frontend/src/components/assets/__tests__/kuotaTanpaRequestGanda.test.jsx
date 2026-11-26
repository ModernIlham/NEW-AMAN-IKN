/**
 * Toolbar me-mount indikator kuota versi desktop DAN HP sekaligus (satu
 * disembunyikan CSS). Dulu masing-masing mengambil datanya sendiri sehingga
 * tiap pembukaan dashboard menembak dua endpoint kuota masing-masing DUA kali.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import TinifyQuotaIndicator, { TinifyQuotaMobile, resetKuotaBersama } from "../TinifyQuotaIndicator";

jest.mock("axios");

const kuota = {
  quotas: [{ service: "uploadcare", name: "Uploadcare", terpasang: true, used: 66, limit: 1000, remaining: 934 }],
  aktif: "uploadcare",
};

beforeEach(() => {
  resetKuotaBersama();
  axios.get.mockReset();
  axios.get.mockImplementation((url) => Promise.resolve({
    data: url.includes("pdf-") ? { quotas: [], aktif: "" } : kuota }));
});

test("dua varian ter-mount = satu request per endpoint, angka sama di keduanya", async () => {
  render(<><TinifyQuotaIndicator /><TinifyQuotaMobile /></>);
  await waitFor(() => expect(screen.getByTestId("kuota-indikator")).toHaveTextContent("934"));
  expect(screen.getByTestId("kuota-indikator-hp")).toHaveTextContent("934");
  const urls = axios.get.mock.calls.map(([u]) => u);
  expect(urls.filter((u) => u.endsWith("/compression-quotas") && !u.includes("pdf-"))).toHaveLength(1);
  expect(urls.filter((u) => u.endsWith("/pdf-compression-quotas"))).toHaveLength(1);
});

test("kegagalan total tidak di-cache: mount berikutnya mencoba lagi", async () => {
  axios.get.mockRejectedValue(new Error("offline"));
  const { unmount } = render(<TinifyQuotaIndicator />);
  await waitFor(() => expect(axios.get).toHaveBeenCalledTimes(2));
  unmount();
  axios.get.mockImplementation((url) => Promise.resolve({
    data: url.includes("pdf-") ? { quotas: [], aktif: "" } : kuota }));
  render(<TinifyQuotaIndicator />);
  await waitFor(() => expect(screen.getByTestId("kuota-indikator")).toHaveTextContent("934"));
  expect(axios.get).toHaveBeenCalledTimes(4);
});
