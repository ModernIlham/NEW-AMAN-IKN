import axios from "axios";
import { toast } from "sonner";
import { downloadFileWithProgress } from "./downloadFile";
import { mulaiUnduhanPusat, pathDariUrl } from "./pusatUnduhan";

jest.mock("axios");
jest.mock("sonner", () => ({
  toast: {
    loading: jest.fn(), success: jest.fn(), error: jest.fn(),
    info: jest.fn(), dismiss: jest.fn(),
  },
}));
jest.mock("./pusatUnduhan", () => ({
  mulaiUnduhanPusat: jest.fn(), pathDariUrl: jest.fn(),
}));

const url = "/api/siman/import-1/selisih.csv";
const filename = "selisih-satker.csv";
const headers = { "X-Satker-Aktif": "621001", "X-Satker-Kode": "12345678901234621001" };
let anchorClick;
const originalCreateObjectURL = window.URL.createObjectURL;
const originalRevokeObjectURL = window.URL.revokeObjectURL;

beforeEach(() => {
  // CRA menghapus implementasi mock sebelum setiap tes.
  window.URL.createObjectURL = jest.fn(() => "blob:siman-satker");
  window.URL.revokeObjectURL = jest.fn();
  anchorClick = jest.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  axios.getUri.mockImplementation(({ url: target, params }) => `${target}?status=${params.status}`);
  pathDariUrl.mockImplementation(target => target.startsWith("/api/") ? target : null);
  mulaiUnduhanPusat.mockResolvedValue({ id: "download-job-1" });
});

afterEach(() => {
  anchorClick.mockRestore();
});

afterAll(() => {
  window.URL.createObjectURL = originalCreateObjectURL;
  window.URL.revokeObjectURL = originalRevokeObjectURL;
});

test.each(["get", "post"])("unduhan %s meneruskan header satker dan signal yang ditangkap pemanggil", async method => {
  const controller = new AbortController();
  const response = { data: new Blob(["kode_satker,nup\n621001,1"]) };
  axios[method].mockResolvedValue(response);
  const params = { status: "selisih" };
  const data = { asset_ids: ["asset-satker-1"] };

  expect(await downloadFileWithProgress(url, filename, {
    method, data, params, headers, signal: controller.signal,
    timeout: 45000, label: "Selisih SIMAN",
  })).toBe(response);

  const args = axios[method].mock.calls[0];
  expect(args[0]).toBe(url);
  if (method === "post") expect(args[1]).toBe(data);
  const config = args[method === "post" ? 2 : 1];
  expect(config).toMatchObject({ responseType: "blob", timeout: 45000 });
  expect(config.headers).toBe(headers);
  expect(config.signal).toBe(controller.signal);
  expect(config.params).toBe(params);
  expect(anchorClick).toHaveBeenCalledTimes(1);
  expect(anchorClick.mock.instances[0].download).toBe(filename);
  expect(window.URL.revokeObjectURL).toHaveBeenCalledWith("blob:siman-satker");
  expect(toast.success).toHaveBeenCalledWith("Selisih SIMAN berhasil diunduh", expect.any(Object));
  expect(mulaiUnduhanPusat).not.toHaveBeenCalled();
});

test("signal yang sudah dibatalkan menolak sebelum request maupun toast dibuat", async () => {
  const controller = new AbortController();
  controller.abort();

  await expect(downloadFileWithProgress(url, filename, {
    headers, signal: controller.signal,
  })).rejects.toMatchObject({ code: "ERR_CANCELED" });

  expect(axios.get).not.toHaveBeenCalled();
  expect(axios.post).not.toHaveBeenCalled();
  for (const mock of Object.values(toast)) expect(mock).not.toHaveBeenCalled();
  expect(window.URL.createObjectURL).not.toHaveBeenCalled();
  expect(mulaiUnduhanPusat).not.toHaveBeenCalled();
});

test("abort ketika request berjalan menolak respons terlambat tanpa unduhan atau toast baru", async () => {
  const controller = new AbortController();
  let finish;
  // Meniru adaptor yang tidak mematuhi AbortSignal dan tetap mengembalikan blob.
  axios.get.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const pending = downloadFileWithProgress(url, filename, { headers, signal: controller.signal });
  const rejected = expect(pending).rejects.toMatchObject({ code: "ERR_CANCELED" });
  const config = axios.get.mock.calls[0][1];
  expect(toast.loading).toHaveBeenCalledTimes(1);

  controller.abort();
  expect(toast.dismiss).toHaveBeenCalledWith(expect.stringMatching(/^download-/));
  config.onDownloadProgress({ loaded: 8192, total: 8192 });
  finish({ data: new Blob(["respons dari konteks satker lama"]) });
  await rejected;

  expect(toast.loading).toHaveBeenCalledTimes(1);
  expect(toast.success).not.toHaveBeenCalled();
  expect(toast.error).not.toHaveBeenCalled();
  expect(toast.info).not.toHaveBeenCalled();
  expect(window.URL.createObjectURL).not.toHaveBeenCalled();
  expect(anchorClick).not.toHaveBeenCalled();
  expect(mulaiUnduhanPusat).not.toHaveBeenCalled();
});

test("pembatalan axios diteruskan tanpa toast galat maupun fallback latar", async () => {
  const error = Object.assign(new Error("timeout dibatalkan"), { code: "ERR_CANCELED" });
  axios.get.mockRejectedValue(error);

  await expect(downloadFileWithProgress(url, filename)).rejects.toBe(error);

  expect(toast.dismiss).toHaveBeenCalledWith(expect.stringMatching(/^download-/));
  expect(toast.error).not.toHaveBeenCalled();
  expect(toast.success).not.toHaveBeenCalled();
  expect(mulaiUnduhanPusat).not.toHaveBeenCalled();
});

test.each([
  ["header satker", () => ({ headers })],
  ["signal konteks", () => ({ signal: new AbortController().signal })],
])("timeout dengan %s tidak dialihkan ke job yang dapat memakai konteks baru", async (_label, options) => {
  const error = Object.assign(new Error("timeout"), { code: "ECONNABORTED" });
  axios.get.mockRejectedValue(error);

  await expect(downloadFileWithProgress(url, filename, options())).rejects.toBe(error);

  expect(mulaiUnduhanPusat).not.toHaveBeenCalled();
  expect(toast.info).not.toHaveBeenCalled();
  expect(toast.error).toHaveBeenCalledWith(expect.stringMatching(/Waktu unduh habis/), expect.any(Object));
  expect(anchorClick).not.toHaveBeenCalled();
});

test("permintaan langsung ke Pusat Unduhan tetap sinkron bila membawa konteks satker", async () => {
  axios.get.mockResolvedValue({ data: new Blob(["satker,barang,nup"]) });

  await downloadFileWithProgress(url, filename, { headers, viaPusat: "langsung" });

  expect(axios.get).toHaveBeenCalledWith(url, expect.objectContaining({ headers }));
  expect(mulaiUnduhanPusat).not.toHaveBeenCalled();
  expect(anchorClick).toHaveBeenCalledTimes(1);
});

test("timeout unduhan umum tetap mendaftarkan job latar dengan query yang sama", async () => {
  axios.get.mockRejectedValue(Object.assign(new Error("timeout"), { code: "ECONNABORTED" }));

  expect(await downloadFileWithProgress(url, filename, {
    params: { status: "selisih" }, label: "Selisih SIMAN",
  })).toEqual({ viaPusat: true });

  expect(mulaiUnduhanPusat).toHaveBeenCalledWith({
    path: `${url}?status=selisih`, namaFile: filename, label: "Selisih SIMAN",
  });
  expect(toast.info).toHaveBeenCalledWith(expect.stringMatching(/disusun di latar belakang/), expect.any(Object));
  expect(toast.error).not.toHaveBeenCalled();
  expect(anchorClick).not.toHaveBeenCalled();
});
