import { bacaPilihanLensa, bukaLensa, cariLensaMakro, daftarLensa, simpanPilihanLensa } from "./lensaKamera";

test("daftar hanya memuat kamera ber-ID, deduplikasi, dan tidak menebak nama kosong", () => {
  expect(daftarLensa([{ kind: "audioinput", deviceId: "mic" }, { kind: "videoinput", deviceId: "" },
    { kind: "videoinput", deviceId: "a", label: "" }, { kind: "videoinput", deviceId: "a", label: "Sama" }]))
    .toEqual([{ id: "a", label: "Kamera 1" }]);
});
test("makro hanya pilihan tersimpan yang masih ada atau satu label eksplisit", () => {
  const umum = [{ id: "a", label: "Ultra wide" }, { id: "b", label: "camera2" }];
  expect(cariLensaMakro(umum, "")).toBeNull();
  expect(cariLensaMakro(umum, "b")).toBe(umum[1]);
  expect(cariLensaMakro(umum, "hilang")).toBeNull();
  const bernama = [...umum, { id: "c", label: "Back macro camera" }];
  expect(cariLensaMakro(bernama, "").id).toBe("c");
  expect(cariLensaMakro([...bernama, { id: "d", label: "Makro 2" }], "")).toBeNull();
});
test("pemilihan ID memakai exact tanpa facingMode yang bertentangan", async () => {
  const t = { readyState: "live", getSettings: () => ({ deviceId: "m" }), stop: jest.fn() };
  const stream = { getVideoTracks: () => [t], getTracks: () => [t] };
  const media = { getUserMedia: jest.fn(async () => stream) };
  expect(await bukaLensa({ deviceId: "m", facing: "environment", resolusi: 1920 }, media)).toBe(stream);
  expect(media.getUserMedia).toHaveBeenCalledWith({ audio: false, video: { deviceId: { exact: "m" }, width: { ideal: 1920 }, height: { ideal: 1440 } } });
});
test.each([{}, { deviceId: "lain" }])("kamera tidak terkonfirmasi %p dihentikan", async setting => {
  const t = { readyState: "live", getSettings: () => setting, stop: jest.fn() };
  await expect(bukaLensa({ deviceId: "m", resolusi: 1280 }, { getUserMedia: async () => ({ getTracks: () => [t], getVideoTracks: () => [t] }) })).rejects.toThrow("tidak mengonfirmasi");
  expect(t.stop).toHaveBeenCalledTimes(1);
});
test("preferensi lensa hanya cache lokal yang dapat dibersihkan", () => {
  simpanPilihanLensa("uji"); expect(bacaPilihanLensa()).toBe("uji");
  simpanPilihanLensa(""); expect(bacaPilihanLensa()).toBe("");
});
