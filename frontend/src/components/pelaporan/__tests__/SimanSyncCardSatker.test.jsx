import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import { toast } from "sonner";
import SimanSyncCard from "../SimanSyncCard";
import { setSatkerAktif } from "@/lib/satkerAktif";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import { ajukanPermohonanAset, gerbangPermohonanAsetAktif } from "@/lib/permohonanAset";

const mockConfirm = jest.fn();
jest.mock("axios");
jest.mock("sonner", () => ({ toast: {
  success: jest.fn(), error: jest.fn(), warning: jest.fn(), info: jest.fn(), dismiss: jest.fn(),
} }));
jest.mock("@/components/ui/ConfirmDialog", () => ({
  useConfirm: () => ({ confirm: (...args) => mockConfirm(...args), confirmDialog: null }),
}));
jest.mock("@/lib/downloadFile", () => ({ downloadFileWithProgress: jest.fn() }));
jest.mock("@/lib/permohonanAset", () => ({
  ajukanPermohonanAset: jest.fn(), gerbangPermohonanAsetAktif: jest.fn(),
  pesanPermohonanTerkirim: () => "Permohonan tersimpan",
}));

const SATKER_A = "621001";
const SATKER_B = "621002";
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function summary(satker) {
  return { data: {
    cocok: satker === SATKER_A ? 7 : 2, selisih: 1, tidak_di_siman: 0,
    import_terakhir: { id: `import-${satker}`, waktu: "2026-01-02", filename: `${satker}.xlsx`,
      total_baris: 2, ringkasan: { siman_tanpa_aset: 1 } },
    per_kegiatan: [{ activity_id: `activity-${satker}`, nama_kegiatan: `Kegiatan ${satker}`,
      cocok: 0, selisih: 1, tidak_di_siman: 0 }],
  } };
}
function differences(satker, changes) {
  return { data: { page: 1, total: 1, total_pages: 1, items: [{
    id: `asset-${satker}`, asset_code: "3100102001", NUP: "1", asset_name: `Laptop ${satker}`,
    activity_id: `activity-${satker}`, nama_kegiatan: `Kegiatan ${satker}`,
    siman: { selisih: changes || [{ field: "brand", label: "Merk", aman: "Lama", siman: "Baru" }] },
  }] } };
}
function defaultGet(url, config) {
  const satker = config?.headers?.["X-Satker-Aktif"];
  if (url.includes("/siman/ringkasan")) return Promise.resolve(summary(satker));
  if (url.includes("/siman/selisih")) return Promise.resolve(differences(satker));
  if (url.endsWith("/inventory-activities")) return Promise.resolve({ data: [
    { id: `activity-${satker}`, nama_kegiatan: `Kegiatan ${satker}` },
  ] });
  throw new Error("Unexpected synthetic request");
}
async function ready(satker) {
  await waitFor(() => expect(screen.getByTestId("siman-sync-card")).toHaveTextContent(`${satker}.xlsx`));
}
async function openDifferences(satker) {
  fireEvent.click(screen.getByTestId("siman-toggle-selisih"));
  await screen.findByTestId(`siman-selisih-row-asset-${satker}`);
}
async function openDraft(satker) {
  fireEvent.click(screen.getByTestId("siman-buat-draft-btn"));
  const select = await screen.findByTestId("siman-draft-kegiatan");
  fireEvent.change(select, { target: { value: `activity-${satker}` } });
}
function changeSatker(satker) {
  act(() => setSatkerAktif(satker));
}

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
  localStorage.setItem("satker_aktif", SATKER_A);
  axios.get.mockImplementation(defaultGet);
  axios.post.mockResolvedValue({ data: { diterapkan: ["brand"], sisa_selisih: 0 } });
  mockConfirm.mockResolvedValue(true);
  gerbangPermohonanAsetAktif.mockResolvedValue(false);
  ajukanPermohonanAset.mockResolvedValue({ id: "request" });
  downloadFileWithProgress.mockResolvedValue({});
});
afterEach(() => jest.useRealTimers());

test("ganti satker menghapus ringkasan, impor, penyaring, pilihan dan draft satker lama", async () => {
  const nextSummary = deferred();
  axios.get.mockImplementation((url, config) => (
    url.includes("/siman/ringkasan") && config.headers["X-Satker-Aktif"] === SATKER_B
      ? nextSummary.promise : defaultGet(url, config)
  ));
  render(<SimanSyncCard isAdmin />);
  await ready(SATKER_A);
  fireEvent.click(screen.getByTestId("siman-tandai-hilang"));
  fireEvent.click(screen.getByTestId(`siman-kegiatan-activity-${SATKER_A}`));
  await screen.findByTestId(`siman-selisih-row-asset-${SATKER_A}`);
  await openDraft(SATKER_A);

  changeSatker(SATKER_B);

  expect(screen.getByTestId("siman-sync-card")).not.toHaveTextContent(`${SATKER_A}.xlsx`);
  expect(screen.queryByTestId("siman-draft-kegiatan")).not.toBeInTheDocument();
  expect(screen.queryByTestId("siman-selisih-list")).not.toBeInTheDocument();
  expect(screen.getByTestId("siman-tandai-hilang")).not.toBeChecked();
  await act(async () => nextSummary.resolve(summary(SATKER_B)));
  await ready(SATKER_B);
  await openDifferences(SATKER_B);
  const lastList = axios.get.mock.calls.filter(([url]) => url.includes("/siman/selisih")).pop();
  expect(lastList[0]).not.toContain("activity_id=");
  expect(lastList[1].headers["X-Satker-Aktif"]).toBe(SATKER_B);
  await openDraft(SATKER_B);
  expect([...screen.getByTestId("siman-draft-kegiatan").options].map((option) => option.value))
    .toEqual(["", `activity-${SATKER_B}`]);
});

test("respons ringkasan A yang terlambat tidak menimpa B dan permintaan A dibatalkan", async () => {
  const old = deferred();
  axios.get.mockImplementationOnce(() => old.promise).mockImplementation(defaultGet);
  render(<SimanSyncCard isAdmin />);
  const oldRequest = axios.get.mock.calls[0][1];

  changeSatker(SATKER_B);
  await ready(SATKER_B);
  await act(async () => old.resolve(summary(SATKER_A)));

  expect(oldRequest.signal.aborted).toBe(true);
  expect(oldRequest.headers["X-Satker-Aktif"]).toBe(SATKER_A);
  expect(screen.getByTestId("siman-sync-card")).not.toHaveTextContent(`${SATKER_A}.xlsx`);
  expect(toast.error).not.toHaveBeenCalled();
});

test("pergantian antar tab mengabaikan kegagalan permintaan satker lama", async () => {
  const old = deferred();
  axios.get.mockImplementationOnce(() => old.promise).mockImplementation(defaultGet);
  render(<SimanSyncCard isAdmin />);
  act(() => {
    localStorage.setItem("satker_aktif", SATKER_B);
    window.dispatchEvent(new StorageEvent("storage", { key: "satker_aktif", newValue: SATKER_B }));
  });
  await ready(SATKER_B);
  await act(async () => old.reject(new Error("Late failure from A")));
  expect(screen.queryByTestId("siman-ringkas-gagal")).not.toBeInTheDocument();
  expect(screen.getByTestId("siman-sync-card")).toHaveTextContent("2 cocok");
});

test("balik A setelah B tetap mengabaikan respons dari sesi A sebelumnya", async () => {
  const oldA = deferred();
  axios.get.mockImplementationOnce(() => oldA.promise).mockImplementation(defaultGet);
  render(<SimanSyncCard isAdmin />);
  changeSatker(SATKER_B);
  await ready(SATKER_B);
  changeSatker(SATKER_A);
  await ready(SATKER_A);
  await act(async () => oldA.resolve({ data: { ...summary(SATKER_A).data, cocok: 999 } }));
  expect(screen.getByTestId("siman-ringkas-badge")).toHaveTextContent("7 cocok");
  expect(screen.getByTestId("siman-ringkas-badge")).not.toHaveTextContent("999");
});

test("daftar selisih yang terlambat tidak muncul di satker pengganti", async () => {
  const old = deferred();
  axios.get.mockImplementation((url, config) => (
    url.includes("/siman/selisih") && config.headers["X-Satker-Aktif"] === SATKER_A
      ? old.promise : defaultGet(url, config)
  ));
  render(<SimanSyncCard isAdmin />);
  await ready(SATKER_A);
  fireEvent.click(screen.getByTestId("siman-toggle-selisih"));
  await waitFor(() => expect(axios.get.mock.calls.some(([url]) => url.includes("/siman/selisih"))).toBe(true));
  changeSatker(SATKER_B);
  await ready(SATKER_B);
  await openDifferences(SATKER_B);
  await act(async () => old.resolve(differences(SATKER_A)));
  expect(screen.queryByTestId(`siman-selisih-row-asset-${SATKER_A}`)).not.toBeInTheDocument();
  expect(screen.getByTestId(`siman-selisih-row-asset-${SATKER_B}`)).toBeInTheDocument();
});

test("pilihan kegiatan draft lama tidak masuk ke pemilih satker baru", async () => {
  const old = deferred();
  axios.get.mockImplementation((url, config) => (
    url.endsWith("/inventory-activities") && config.headers["X-Satker-Aktif"] === SATKER_A
      ? old.promise : defaultGet(url, config)
  ));
  render(<SimanSyncCard isAdmin />);
  await ready(SATKER_A);
  fireEvent.click(screen.getByTestId("siman-buat-draft-btn"));
  changeSatker(SATKER_B);
  await ready(SATKER_B);
  await openDraft(SATKER_B);
  await act(async () => old.resolve({ data: [{ id: "old-a", nama_kegiatan: "Old A" }] }));
  expect(screen.getByTestId("siman-draft-kegiatan")).not.toHaveTextContent("Old A");
});

test("unggahan tetap terikat A dan hasil/progresnya diabaikan setelah beralih ke B", async () => {
  const upload = deferred();
  axios.post.mockReturnValue(upload.promise);
  render(<SimanSyncCard isAdmin />);
  await ready(SATKER_A);
  fireEvent.change(screen.getByTestId("siman-file-input"), { target: { files: [new File(["synthetic"], "fixture.xlsx")] } });
  const config = axios.post.mock.calls[0][2];
  changeSatker(SATKER_B);
  await ready(SATKER_B);
  const getsAfterSwitch = axios.get.mock.calls.length;
  await act(async () => {
    config.onUploadProgress({ loaded: 80, total: 100 });
    upload.resolve({ data: { ringkasan: { aset_dicek: 999 }, peringatan: ["Old upload"] } });
  });
  expect(config.headers["X-Satker-Aktif"]).toBe(SATKER_A);
  expect(config.signal.aborted).toBe(true);
  expect(screen.getByTestId("siman-import-btn")).toBeEnabled();
  expect(screen.getByTestId("siman-import-btn")).not.toHaveTextContent("80%");
  expect(toast.success).not.toHaveBeenCalled();
  expect(toast.warning).not.toHaveBeenCalled();
  expect(axios.get).toHaveBeenCalledTimes(getsAfterSwitch);
});

test("jeda retry unggahan tidak mengirim ulang file A dalam konteks B", async () => {
  render(<SimanSyncCard isAdmin />);
  await ready(SATKER_A);
  jest.useFakeTimers();
  axios.post.mockRejectedValue(new Error("Network unavailable"));
  fireEvent.change(screen.getByTestId("siman-file-input"), { target: { files: [new File(["synthetic"], "fixture.xlsx")] } });
  await act(async () => {});
  expect(axios.post).toHaveBeenCalledTimes(1);
  changeSatker(SATKER_B);
  await act(async () => { jest.advanceTimersByTime(6000); });
  expect(axios.post).toHaveBeenCalledTimes(1);
  expect(screen.getByTestId("siman-import-btn")).toBeEnabled();
});

test("hasil penerapan A tidak menyegarkan atau memberi toast sukses di B", async () => {
  const pending = deferred();
  axios.post.mockReturnValue(pending.promise);
  render(<SimanSyncCard isAdmin />);
  await ready(SATKER_A);
  await openDifferences(SATKER_A);
  fireEvent.click(screen.getByTestId(`siman-selisih-row-asset-${SATKER_A}`));
  fireEvent.click(screen.getByTestId(`siman-terapkan-asset-${SATKER_A}`));
  const config = axios.post.mock.calls[0][2];
  changeSatker(SATKER_B);
  await ready(SATKER_B);
  const getsAfterSwitch = axios.get.mock.calls.length;
  await act(async () => pending.resolve({ data: { diterapkan: ["brand"] } }));
  expect(config.headers["X-Satker-Aktif"]).toBe(SATKER_A);
  expect(config.signal.aborted).toBe(true);
  expect(toast.success).not.toHaveBeenCalled();
  expect(axios.get).toHaveBeenCalledTimes(getsAfterSwitch);
});

test("hasil pembuatan draft A tidak menjadi hasil draft di B", async () => {
  const pending = deferred();
  axios.post.mockReturnValue(pending.promise);
  render(<SimanSyncCard isAdmin />);
  await ready(SATKER_A);
  await openDraft(SATKER_A);
  fireEvent.click(screen.getByTestId("siman-draft-jalankan"));
  expect(axios.post.mock.calls[0][0]).toContain(`import-${SATKER_A}`);
  changeSatker(SATKER_B);
  await ready(SATKER_B);
  await openDraft(SATKER_B);
  await act(async () => pending.resolve({ data: { dibuat: 999, kegiatan: "Old A" } }));
  expect(screen.getByTestId("siman-sync-card")).not.toHaveTextContent("999 draft dibuat");
  expect(toast.success).not.toHaveBeenCalled();
  expect(screen.getByTestId("siman-draft-jalankan")).toBeEnabled();
});

test("konfirmasi reklasifikasi lama tidak mengirim transaksi setelah ganti satker", async () => {
  const confirmation = deferred();
  mockConfirm.mockReturnValue(confirmation.promise);
  axios.get.mockImplementation((url, config) => url.includes("/siman/selisih")
    ? Promise.resolve(differences(config.headers["X-Satker-Aktif"], [{ field: "asset_code", label: "Kode Barang", aman: "3100102001", siman: "3100102002" }]))
    : defaultGet(url, config));
  render(<SimanSyncCard isAdmin />);
  await ready(SATKER_A);
  await openDifferences(SATKER_A);
  fireEvent.click(screen.getByTestId(`siman-selisih-row-asset-${SATKER_A}`));
  fireEvent.click(screen.getByTestId(`siman-reklas-asset-${SATKER_A}`));
  changeSatker(SATKER_B);
  await ready(SATKER_B);
  await act(async () => confirmation.resolve(true));
  expect(axios.post).not.toHaveBeenCalled();
  expect(gerbangPermohonanAsetAktif).not.toHaveBeenCalled();
});

test("CSV memakai header dan sinyal konteks yang ditangkap saat tombol ditekan", async () => {
  render(<SimanSyncCard isAdmin />);
  await ready(SATKER_A);
  fireEvent.click(screen.getByTestId("siman-csv-belum"));
  const [url, , options] = downloadFileWithProgress.mock.calls[0];
  expect(url).toContain(`import-${SATKER_A}`);
  expect(options.headers["X-Satker-Aktif"]).toBe(SATKER_A);
  expect(options.signal.aborted).toBe(false);
  changeSatker(SATKER_B);
  expect(options.signal.aborted).toBe(true);
  await ready(SATKER_B);
});

test("CSV dari DOM lama tidak dimulai ketika satker penyimpanan sudah berubah sebelum event", async () => {
  render(<SimanSyncCard isAdmin />);
  await ready(SATKER_A);
  localStorage.setItem("satker_aktif", SATKER_B);

  fireEvent.click(screen.getByTestId("siman-csv-belum"));

  expect(downloadFileWithProgress).not.toHaveBeenCalled();
  expect(axios.post).not.toHaveBeenCalled();
});

test("pergantian satker ketika gerbang reklasifikasi dibaca mencegah transaksi lanjutan", async () => {
  const gate = deferred();
  gerbangPermohonanAsetAktif.mockReturnValue(gate.promise);
  axios.get.mockImplementation((url, config) => url.includes("/siman/selisih")
    ? Promise.resolve(differences(config.headers["X-Satker-Aktif"], [{ field: "asset_code", label: "Kode Barang", aman: "3100102001", siman: "3100102002" }]))
    : defaultGet(url, config));
  render(<SimanSyncCard isAdmin />);
  await ready(SATKER_A);
  await openDifferences(SATKER_A);
  fireEvent.click(screen.getByTestId(`siman-selisih-row-asset-${SATKER_A}`));
  fireEvent.click(screen.getByTestId(`siman-reklas-asset-${SATKER_A}`));
  await waitFor(() => expect(gerbangPermohonanAsetAktif).toHaveBeenCalledTimes(1));
  const config = gerbangPermohonanAsetAktif.mock.calls[0][0];

  changeSatker(SATKER_B);
  await ready(SATKER_B);
  await act(async () => gate.resolve(false));

  expect(config.headers["X-Satker-Aktif"]).toBe(SATKER_A);
  expect(config.signal.aborted).toBe(true);
  expect(axios.post).not.toHaveBeenCalled();
  expect(ajukanPermohonanAset).not.toHaveBeenCalled();
  expect(toast.success).not.toHaveBeenCalled();
});

test("StrictMode tetap memakai controller hidup untuk permintaan yang baru", async () => {
  render(<React.StrictMode><SimanSyncCard isAdmin /></React.StrictMode>);
  await ready(SATKER_A);
  const calls = axios.get.mock.calls.filter(([url]) => url.includes("/siman/ringkasan"));
  expect(calls.length).toBeGreaterThanOrEqual(2);
  expect(calls[0][1].signal.aborted).toBe(true);
  expect(calls[calls.length - 1][1].signal.aborted).toBe(false);
});
