import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import ReportDownloads, { dataGroupOptions } from "./ReportDownloads";
import { downloadFileWithProgress } from "../../../lib/downloadFile";

jest.mock("axios");
jest.mock("../../../lib/downloadFile", () => ({ downloadFileWithProgress: jest.fn() }));
jest.mock("@/components/persuratan/BookingNomorButton", () => () => null);

const info = { total_assets: 2, pages: [{ page: 1, start: 1, end: 2, count: 2 }] };
const props = { activityId: "kegiatan-1", data: {}, filterLaporan: "location=Gedung+A&location=Gedung+B&search=komputer", sortBy: "price_desc", filterAktifCount: 2 };
beforeEach(() => {
  localStorage.clear();
  axios.get.mockResolvedValue({ data: info });
  downloadFileWithProgress.mockResolvedValue({});
});

test.each(dataGroupOptions)("unduhan %s mempertahankan filter multi dan sort", async (key) => {
  render(<ReportDownloads {...props} />);
  await screen.findByTestId("download-data-page-1");
  expect(screen.getByTestId("data-aset-group")).toHaveValue("");
  fireEvent.change(screen.getByTestId("data-aset-group"), { target: { value: key } });
  await userEvent.click(screen.getByTestId("detail-field-spm"));
  await userEvent.click(screen.getByTestId("download-data-page-1"));
  const [url, name, opts] = downloadFileWithProgress.mock.calls[0];
  const params = new URL(url).searchParams;
  expect(params.getAll("location")).toEqual(["Gedung A", "Gedung B"]);
  expect(params.get("search")).toBe("komputer");
  expect(params.get("data_group_by")).toBe(key);
  expect(params.get("sort_by")).toBe("price_desc");
  expect(params.get("detail_fields")).toBe("spm");
  expect(params.get("page")).toBe("1");
  expect(name).toContain("Data_Aset_1-2");
  expect(opts.timeout).toBe(45000); // URL lengkap diteruskan juga ke Pusat Unduhan.
});

test("ZIP ikut pilihan kelompok dan urutan terbaru tanpa memengaruhi Barang Serupa", async () => {
  const view = render(<ReportDownloads {...props} />);
  await screen.findByTestId("download-data-page-1");
  fireEvent.change(screen.getByTestId("data-aset-group"), { target: { value: "psp" } });
  view.rerender(<ReportDownloads {...props} sortBy="name_asc" />);
  await userEvent.click(screen.getByTestId("toggle-batch-mode"));
  await userEvent.click(screen.getByLabelText("Data Aset (semua halaman)"));
  await userEvent.click(screen.getByTestId("batch-download-btn"));
  expect(downloadFileWithProgress.mock.calls[0][2].data).toEqual({
    types: ["executive-data"], detail_fields: "", data_group_by: "psp", sort_by: "name_asc",
    filter: { location: ["Gedung A", "Gedung B"], search: "komputer" },
  });
  await userEvent.click(screen.getByTestId("download-executive-grouped"));
  expect(downloadFileWithProgress.mock.calls[1][0]).not.toContain("data_group_by");
});

test("info halaman lama tidak menimpa hasil filter baru", async () => {
  let resolveLama;
  axios.get.mockImplementationOnce(() => new Promise(resolve => { resolveLama = resolve; }));
  const view = render(<ReportDownloads {...props} />);
  axios.get.mockResolvedValueOnce({ data: { total_assets: 0, pages: [] } });
  view.rerender(<ReportDownloads {...props} filterLaporan="search=kosong" />);
  await screen.findByText("Belum ada data aset");
  await act(async () => { resolveLama({ data: info }); });
  expect(screen.queryByTestId("download-data-page-1")).not.toBeInTheDocument();
});

test("pengaturan PDF dapat diperiksa dengan CSS produksi", async () => {
  render(<ReportDownloads {...props} />);
  await waitFor(() => expect(screen.getByTestId("download-data-page-1")).toBeInTheDocument());
  fireEvent.change(screen.getByTestId("data-aset-group"), { target: { value: "kode_5" } });
  expect(screen.getByTestId("data-aset-group")).toHaveValue("kode_5");
  if (process.env.AMAN_QA_DATA_FORM_DIR) {
    const fs = require("fs"), path = require("path");
    fs.mkdirSync(process.env.AMAN_QA_DATA_FORM_DIR, { recursive: true });
    const section = screen.getByTestId("pengaturan-pdf-data-aset").cloneNode(true);
    section.querySelector('[value="kode_5"]').setAttribute("selected", "");
    fs.writeFileSync(path.join(process.env.AMAN_QA_DATA_FORM_DIR, "pengaturan.html"), section.outerHTML);
  }
});
