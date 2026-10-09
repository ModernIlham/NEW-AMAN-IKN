import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PREFERENSI_BAWAAN } from "../../../lib/preferensiKamera";
import { bacaCache, muatPreferensi, simpanPreferensi } from "../../../lib/preferensiKameraApi";
import { gambarWatermarkKamera } from "../../../lib/watermarkKamera";
jest.mock("../../../hooks/useBackGuard", () => ({ useBackGuard: jest.fn() }));
jest.mock("../../../lib/preferensiKameraApi");
jest.mock("../../../lib/watermarkKamera");
jest.mock("../../../lib/shutterSound", () => ({ playShutterSound: jest.fn(), shutterSoundEnabled: () => false }));
jest.mock("../../../lib/haptics", () => ({ haptic: jest.fn() }));
jest.mock("../QrScanButton", () => ({ extractScannedCode: s => s }));
const fd = { asset_name: "Trainer Kit", asset_code: "3080158999", NUP: "10", location: "Lokasi uji" };
let tr, ctx;
let FullCameraSheet;
beforeAll(() => {
  const probe = jest.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ filter: "none" });
  FullCameraSheet = require("../FullCameraSheet").default;
  probe.mockRestore();
});
beforeEach(() => {
  localStorage.removeItem("aman_lensa_makro_perangkat_v1");
  bacaCache.mockReturnValue(PREFERENSI_BAWAAN); muatPreferensi.mockResolvedValue(PREFERENSI_BAWAAN);
  simpanPreferensi.mockImplementation(async p => ({ pref: p, tersimpanKeAkun: true }));
  tr = { readyState: "live", stop: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn(), getCapabilities: () => ({}) };
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: jest.fn(async () => ({ getVideoTracks: () => [tr], getTracks: () => [tr] })) } });
  Object.defineProperty(navigator, "geolocation", { configurable: true, value: undefined });
  Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", { configurable: true, get: () => 1920 });
  Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", { configurable: true, get: () => 1080 });
  Object.defineProperty(HTMLVideoElement.prototype, "readyState", { configurable: true, get: () => 4 });
  jest.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  jest.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, left: 0, top: 0, width: 390, height: 780 });
  ctx = { drawImage: jest.fn(), filter: "none" };
  jest.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(ctx);
  jest.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockReturnValue("data:image/jpeg;base64,dGVzdA==");
});
afterEach(() => jest.restoreAllMocks());
test("pilih rasio lalu potret memakai bidang yang sama, tetap terikat aset dan mutu JPEG", async () => {
  const onCapture = jest.fn();
  render(<FullCameraSheet formData={fd} sesiAset="aset-a" onClose={jest.fn()} onCapture={onCapture} />);
  await waitFor(() => expect(screen.getByTestId("full-camera-shutter")).not.toBeDisabled());
  fireEvent.loadedMetadata(screen.getByTestId("full-camera-video"));
  fireEvent.click(screen.getByTestId("full-camera-setelan"));
  await act(async () => { fireEvent.click(screen.getByTestId("setelan-rasio-1:1")); });
  expect(simpanPreferensi).toHaveBeenCalledWith({ ...PREFERENSI_BAWAAN, rasio: "1:1" });
  expect(screen.getByTestId("full-camera-video").style.width).toBe("390px");
  expect(screen.getByTestId("full-camera-video").style.height).toBe("390px");
  fireEvent.click(screen.getByTestId("full-camera-setelan"));
  fireEvent.click(screen.getByTestId("full-camera-shutter"));
  expect(ctx.drawImage).toHaveBeenCalledWith(expect.anything(), 420, 0, 1080, 1080, 0, 0, 1080, 1080);
  expect(HTMLCanvasElement.prototype.toDataURL).toHaveBeenCalledWith("image/jpeg", 0.85);
  expect(gambarWatermarkKamera).toHaveBeenCalledWith(ctx, 1080, 1080, expect.arrayContaining(["3080158999  NUP 10", "Trainer Kit • Lokasi uji"]));
  expect(onCapture).toHaveBeenCalledWith("data:image/jpeg;base64,dGVzdA==", "aset-a");
});
test("silang kecil menempel di sudut thumbnail dan tetap membutuhkan konfirmasi", async () => {
  const onRemovePhoto = jest.fn(); const { unmount } = render(<FullCameraSheet formData={fd} onClose={jest.fn()}
    photos={["data:image/jpeg;base64,dGVzdA=="]} onRemovePhoto={onRemovePhoto} />);
  await screen.findByTestId("full-camera-macro");
  await waitFor(() => expect(screen.getByTestId("full-camera-macro")).not.toBeDisabled());
  expect(screen.getByTestId("full-camera-macro")).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByTestId("full-camera-del-0")).toHaveClass("absolute", "top-0", "right-0", "w-11", "h-11");
  expect(screen.getByTestId("full-camera-del-icon-0")).toHaveClass("w-[18px]", "h-[18px]");
  expect(screen.getByAltText("Foto 1").parentElement).toHaveClass("w-14", "h-14");
  fireEvent.click(screen.getByTestId("full-camera-del-0")); expect(onRemovePhoto).not.toHaveBeenCalled();
  fireEvent.click(screen.getByTestId("full-camera-del-confirm")); expect(onRemovePhoto).toHaveBeenCalledWith(0);
  unmount(); expect(tr.stop).toHaveBeenCalledTimes(1);
});

test("lensa disusun vertikal dan pilihan aktif mengikuti perubahan zoom", async () => {
  tr.getCapabilities = () => ({ zoom: { min: 1, max: 5, step: 1 } });
  tr.getSettings = () => ({ zoom: 1 });
  tr.applyConstraints = jest.fn(async () => {});
  render(<FullCameraSheet formData={fd} onClose={jest.fn()} />);
  const pilihan = await screen.findByTestId("full-camera-zoom-2");
  expect(screen.getByTestId("full-camera-lensbar")).toHaveClass("flex-col");
  expect(screen.getByTestId("full-camera-sheet")).toHaveAttribute("data-lens-visible", "true");
  expect(screen.getByTestId("full-camera-zoom-1")).toHaveAttribute("aria-pressed", "true");
  expect(pilihan).toHaveAttribute("aria-pressed", "false");
  await act(async () => { fireEvent.click(pilihan); });
  expect(tr.applyConstraints).toHaveBeenCalledWith({ advanced: [{ zoom: 2 }] });
  expect(pilihan).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByTestId("full-camera-zoom-1")).toHaveAttribute("aria-pressed", "false");
});

function siapkanLensa(labels = { utama: "Back camera", makro: "Back macro" }) {
  const dibuat = [], jejak = [];
  navigator.mediaDevices.enumerateDevices = jest.fn(async () => Object.entries(labels).map(([deviceId, label]) => ({ deviceId, label, kind: "videoinput" })));
  navigator.mediaDevices.getUserMedia.mockImplementation(async req => {
    const id = req.video.deviceId?.exact || (req.video.facingMode === "user" ? "depan" : "utama");
    jejak.push(`buka:${id}`);
    const t = { readyState: "live", getSettings: () => ({ deviceId: id, facingMode: id === "depan" ? "user" : "environment" }),
      getCapabilities: () => ({}), addEventListener: jest.fn(), removeEventListener: jest.fn() };
    t.stop = jest.fn(() => { t.readyState = "ended"; jejak.push(`tutup:${id}`); });
    const stream = { getTracks: () => [t], getVideoTracks: () => [t] }; dibuat.push(stream);
    return stream;
  });
  return { dibuat, jejak };
}
async function tungguMakroSiap() {
  await waitFor(() => expect(screen.getByTestId("full-camera-macro")).not.toBeDisabled());
}
test("makro fixed-focus benar-benar mengganti device lalu kembali ke kamera asal", async () => {
  const { dibuat, jejak } = siapkanLensa();
  const capture = jest.fn();
  render(<FullCameraSheet formData={fd} sesiAset="aset-a" onClose={jest.fn()} onCapture={capture} photos={["foto-lama"]} />);
  await tungguMakroSiap();
  fireEvent.click(screen.getByTestId("full-camera-macro"));
  expect(screen.getByTestId("full-camera-shutter")).toBeDisabled();
  await waitFor(() => expect(screen.getByTestId("full-camera-macro")).toHaveAttribute("aria-pressed", "true"));
  expect(navigator.mediaDevices.getUserMedia).toHaveBeenNthCalledWith(2, { audio: false, video: { deviceId: { exact: "makro" }, width: { ideal: 1920 }, height: { ideal: 1440 } } });
  expect(jejak.indexOf("tutup:utama")).toBeLessThan(jejak.indexOf("buka:makro"));
  expect(screen.getByTestId("full-camera-video").srcObject).toBe(dibuat[1]);
  expect(screen.getByAltText("Foto 1")).toHaveAttribute("src", "foto-lama");
  fireEvent.click(screen.getByTestId("full-camera-shutter"));
  expect(capture).toHaveBeenCalledWith("data:image/jpeg;base64,dGVzdA==", "aset-a");
  await tungguMakroSiap(); fireEvent.click(screen.getByTestId("full-camera-macro"));
  await waitFor(() => expect(screen.getByTestId("full-camera-shutter")).not.toBeDisabled());
  expect(screen.getByTestId("full-camera-macro")).toHaveAttribute("aria-pressed", "false");
  expect(navigator.mediaDevices.getUserMedia.mock.calls[2][0].video.deviceId).toEqual({ exact: "utama" });
  expect(dibuat[1].getVideoTracks()[0].stop).toHaveBeenCalledTimes(1);
});
test("kamera bernama umum tidak ditebak sebagai makro, pilihan pengguna baru disimpan setelah berhasil", async () => {
  siapkanLensa({ utama: "Camera 0", tambahan: "Camera 2" });
  render(<FullCameraSheet formData={fd} onClose={jest.fn()} />);
  await tungguMakroSiap(); fireEvent.click(screen.getByTestId("full-camera-macro"));
  expect(screen.getByTestId("camera-lens-panel")).toBeInTheDocument();
  expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByTestId("camera-lens-select"), { target: { value: "tambahan" } });
  expect(localStorage.getItem("aman_lensa_makro_perangkat_v1")).toBeNull();
  fireEvent.click(screen.getByTestId("camera-lens-apply"));
  await waitFor(() => expect(screen.getByTestId("full-camera-macro")).toHaveAttribute("aria-pressed", "true"));
  expect(localStorage.getItem("aman_lensa_makro_perangkat_v1")).toBe("tambahan");
});
test("browser hanya satu kamera menjelaskan batasan, tidak mengaktifkan makro palsu", async () => {
  siapkanLensa({ utama: "Back camera" });
  render(<FullCameraSheet formData={fd} onClose={jest.fn()} />);
  await tungguMakroSiap(); fireEvent.click(screen.getByTestId("full-camera-macro"));
  expect(screen.getByTestId("camera-lens-availability")).toHaveTextContent("Browser hanya menyediakan satu kamera");
  expect(screen.getByTestId("camera-lens-apply")).toBeDisabled();
  expect(screen.getByTestId("camera-lens-focus")).toBeDisabled();
  expect(screen.getByTestId("full-camera-macro")).toHaveAttribute("aria-pressed", "false");
  expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(1);
});
test.each(["ditolak", "id-salah"])("kegagalan lensa %s memulihkan kamera asal tanpa menyimpan pilihan", async sebab => {
  const { dibuat } = siapkanLensa();
  render(<FullCameraSheet formData={fd} onClose={jest.fn()} />);
  await tungguMakroSiap();
  const salah = { ...dibuat[0].getVideoTracks()[0], stop: jest.fn() };
  if (sebab === "ditolak") navigator.mediaDevices.getUserMedia.mockRejectedValueOnce(Error("Kamera menolak"));
  else navigator.mediaDevices.getUserMedia.mockResolvedValueOnce({ getTracks: () => [salah], getVideoTracks: () => [salah] });
  fireEvent.click(screen.getByTestId("full-camera-macro"));
  await waitFor(() => expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(3));
  await tungguMakroSiap();
  expect(screen.getByTestId("full-camera-macro")).toHaveAttribute("aria-pressed", "false");
  expect(navigator.mediaDevices.getUserMedia.mock.calls[2][0].video.deviceId).toEqual({ exact: "utama" });
  expect(localStorage.getItem("aman_lensa_makro_perangkat_v1")).toBeNull();
  if (sebab === "id-salah") expect(salah.stop).toHaveBeenCalledTimes(1);
});
test("menutup kamera saat pergantian tertunda mematikan stream yang tiba terlambat", async () => {
  siapkanLensa();
  const h = render(<FullCameraSheet formData={fd} onClose={jest.fn()} />);
  await tungguMakroSiap();
  let selesai; const p = new Promise(r => { selesai = r; });
  navigator.mediaDevices.getUserMedia.mockReturnValueOnce(p);
  fireEvent.click(screen.getByTestId("full-camera-macro")); h.unmount();
  const t = { readyState: "live", getSettings: () => ({ deviceId: "makro" }), stop: jest.fn() };
  await act(async () => { selesai({ getTracks: () => [t], getVideoTracks: () => [t] }); await p; });
  expect(t.stop).toHaveBeenCalledTimes(1);
  expect(localStorage.getItem("aman_lensa_makro_perangkat_v1")).toBeNull();
});
test("bantuan fokus dekat tidak mengaku sebagai perpindahan lensa", async () => {
  const { dibuat } = siapkanLensa({ utama: "Back camera" });
  render(<FullCameraSheet formData={fd} onClose={jest.fn()} />);
  await tungguMakroSiap();
  const t = dibuat[0].getVideoTracks()[0];
  t.getCapabilities = () => ({ focusMode: ["continuous"] });
  t.getSettings = () => ({ deviceId: "utama", focusMode: "continuous" });
  t.applyConstraints = jest.fn(async () => {});
  fireEvent.click(screen.getByTestId("full-camera-macro"));
  fireEvent.click(screen.getByTestId("camera-lens-focus"));
  await screen.findByText(/Bantuan fokus otomatis aktif pada kamera ini/);
  expect(t.applyConstraints).toHaveBeenCalled();
  expect(screen.getByTestId("full-camera-macro")).toHaveAttribute("aria-pressed", "false");
  expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(1);
});

test("rana dan status makro menunggu video lensa baru benar-benar siap", async () => {
  siapkanLensa(); const capture = jest.fn();
  render(<FullCameraSheet formData={fd} onClose={jest.fn()} onCapture={capture} />);
  await tungguMakroSiap();
  let lanjut; HTMLMediaElement.prototype.play.mockImplementationOnce(() => new Promise(r => { lanjut = r; }));
  fireEvent.click(screen.getByTestId("full-camera-macro"));
  await waitFor(() => expect(lanjut).toBeDefined());
  expect(screen.getByTestId("full-camera-shutter")).toBeDisabled();
  expect(screen.queryByTestId("camera-lens-active")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("full-camera-shutter")); expect(capture).not.toHaveBeenCalled();
  expect(localStorage.getItem("aman_lensa_makro_perangkat_v1")).toBeNull();
  await act(async () => { lanjut(); });
  await screen.findByTestId("camera-lens-active");
  expect(screen.getByTestId("full-camera-shutter")).not.toBeDisabled();
});

test("kegagalan makro dan kamera asal berhenti setelah percobaan default", async () => {
  siapkanLensa(); render(<FullCameraSheet formData={fd} onClose={jest.fn()} />);
  await tungguMakroSiap();
  navigator.mediaDevices.getUserMedia.mockRejectedValue(Error("Kamera tidak tersedia"));
  fireEvent.click(screen.getByTestId("full-camera-macro"));
  await waitFor(() => expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(4));
  expect(navigator.mediaDevices.getUserMedia.mock.calls.slice(1).map(([r]) => r.video.deviceId?.exact || r.video.facingMode)).toEqual(["makro", "utama", "environment"]);
  expect(screen.getByTestId("full-camera-shutter")).toBeDisabled();
  expect(localStorage.getItem("aman_lensa_makro_perangkat_v1")).toBeNull();
});

test("flip membatalkan perpindahan tertunda dan respons lama tidak mengganti kamera depan", async () => {
  const { dibuat } = siapkanLensa();
  render(<FullCameraSheet formData={fd} onClose={jest.fn()} />);
  await tungguMakroSiap();
  let lanjut; navigator.mediaDevices.getUserMedia.mockReturnValueOnce(new Promise(r => { lanjut = r; }));
  fireEvent.click(screen.getByTestId("full-camera-macro"));
  fireEvent.click(screen.getByTestId("full-camera-flip"));
  await tungguMakroSiap();
  const depan = dibuat[dibuat.length - 1];
  const lama = { readyState: "live", getSettings: () => ({ deviceId: "makro" }), stop: jest.fn() };
  await act(async () => { lanjut({ getTracks: () => [lama], getVideoTracks: () => [lama] }); });
  expect(lama.stop).toHaveBeenCalledTimes(1);
  expect(screen.getByTestId("full-camera-video").srcObject).toBe(depan);
  expect(depan.getVideoTracks()[0].getSettings().deviceId).toBe("depan");
  expect(depan.getVideoTracks()[0].readyState).toBe("live");
  expect(screen.getByTestId("full-camera-macro")).toHaveAttribute("aria-pressed", "false");
});

test("portal tidak membaca/menulis preferensi staf dan tidak menawarkan edit induk", async () => {
  bacaCache.mockClear(); muatPreferensi.mockClear(); simpanPreferensi.mockClear();
  Object.defineProperty(navigator, "geolocation", { configurable: true, value: { watchPosition: ok => { ok({ coords: { latitude: -0.96, longitude: 116.7, accuracy: 7 }, timestamp: Date.now() }); return 1; }, clearWatch: jest.fn() } });
  const onCapture = jest.fn(), close = jest.fn();
  const view = render(<FullCameraSheet modePemegang formData={fd} sesiAset="portal-1" onCapture={onCapture} onClose={close} panelLaporan={<p>Panel laporan observasi</p>} onScanAsset={jest.fn()} />);
  await waitFor(() => expect(screen.getByTestId("full-camera-shutter")).not.toBeDisabled());
  expect(bacaCache).not.toHaveBeenCalled(); expect(muatPreferensi).not.toHaveBeenCalled();
  fireEvent.click(screen.getByTestId("full-camera-setelan"));
  fireEvent.click(screen.getByTestId("setelan-rasio-1:1"));
  expect(simpanPreferensi).not.toHaveBeenCalled();
  fireEvent.click(screen.getByTestId("full-camera-setelan"));
  fireEvent.click(screen.getByTestId("full-camera-edit-btn"));
  expect(screen.getByText("Panel laporan observasi")).toBeInTheDocument();
  expect(screen.queryByTestId("full-camera-edit-asset_name")).not.toBeInTheDocument();
  expect(screen.queryByTestId("full-camera-autoinv")).not.toBeInTheDocument();
  expect(screen.queryByTestId("full-camera-savenew")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("full-camera-edit-done"));
  fireEvent.click(screen.getByTestId("full-camera-shutter"));
  expect(onCapture).toHaveBeenCalledWith(expect.any(String), "portal-1", { waktu: expect.any(String), gps: { lat: -0.96, lng: 116.7, accuracy: 7 } });
  expect(screen.queryByText("Kamera biasa")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("camera-pemegang-selesai")); expect(close).toHaveBeenCalled();
  view.unmount(); expect(tr.stop).toHaveBeenCalled();
});

test("portal hanya memotret dengan GPS baru maksimal 8 m, pulih setelah akurat/izin diberikan", async () => {
  let fix, gagal;
  const clear = jest.fn();
  Object.defineProperty(navigator, "geolocation", { configurable: true, value: { watchPosition: (ok, err) => { fix = ok; gagal = err; return 42; }, clearWatch: clear } });
  const onCapture = jest.fn();
  const view = render(<FullCameraSheet modePemegang formData={fd} sesiAset="p1" onCapture={onCapture} onClose={jest.fn()} />);
  await act(async () => {});
  expect(screen.getByTestId("full-camera-shutter")).toBeDisabled();
  for (const accuracy of [26, 8.01, NaN, -1]) {
    act(() => fix({ coords: { latitude: -0.96, longitude: 116.7, accuracy }, timestamp: Date.now() }));
    expect(screen.getByTestId("full-camera-shutter")).toBeDisabled();
    fireEvent.click(screen.getByTestId("full-camera-shutter"));
  }
  expect(onCapture).not.toHaveBeenCalled();
  for (const accuracy of [8, 7.5]) {
    act(() => fix({ coords: { latitude: -0.96, longitude: 116.7, accuracy }, timestamp: Date.now() }));
    expect(screen.getByTestId("full-camera-shutter")).not.toBeDisabled();
    fireEvent.click(screen.getByTestId("full-camera-shutter"));
    expect(onCapture.mock.calls.at(-1)[2].gps).toEqual({ lat: -0.96, lng: 116.7, accuracy });
  }
  act(() => fix({ coords: { latitude: -0.96, longitude: 116.7, accuracy: 2 }, timestamp: Date.now() - 61000 }));
  expect(screen.getByTestId("full-camera-shutter")).toBeDisabled();
  act(() => gagal({ code: 1 }));
  fireEvent.click(screen.getByTestId("full-camera-shutter"));
  expect(screen.getByTestId("full-camera-shutter")).toBeDisabled();
  expect(onCapture).toHaveBeenCalledTimes(2);
  act(() => fix({ coords: { latitude: -0.96, longitude: 116.7, accuracy: 3 }, timestamp: Date.now() }));
  expect(screen.getByTestId("full-camera-shutter")).not.toBeDisabled();
  // Melewati satu menit di antara render dan ketukan: guard fungsi harus tetap menolak.
  const waktu = Date.now(); const jam = jest.spyOn(Date, "now").mockReturnValue(waktu + 61000);
  fireEvent.click(screen.getByTestId("full-camera-shutter"));
  expect(onCapture).toHaveBeenCalledTimes(2);
  jam.mockRestore();
  view.unmount(); expect(clear).toHaveBeenCalledWith(42);
});

test("portal tanpa dukungan GPS tidak membuka rana tanpa koordinat", async () => {
  render(<FullCameraSheet modePemegang formData={fd} onClose={jest.fn()} />);
  await act(async () => {});
  expect(screen.getByTestId("full-camera-shutter")).toBeDisabled();
  expect(screen.getByTestId("camera-pemegang-gps")).toHaveTextContent("maksimal 8 m");
});

test("pilihan lokal kamera bernama umum digunakan lagi tanpa menebak lensa", async () => {
  localStorage.setItem("aman_lensa_makro_perangkat_v1", "tambahan");
  siapkanLensa({ utama: "Camera 0", tambahan: "Camera 2" });
  render(<FullCameraSheet formData={fd} onClose={jest.fn()} />);
  await tungguMakroSiap(); fireEvent.click(screen.getByTestId("full-camera-macro"));
  await screen.findByTestId("camera-lens-active");
  expect(screen.queryByTestId("camera-lens-panel")).not.toBeInTheDocument();
  expect(navigator.mediaDevices.getUserMedia.mock.calls[1][0].video.deviceId).toEqual({ exact: "tambahan" });
});
