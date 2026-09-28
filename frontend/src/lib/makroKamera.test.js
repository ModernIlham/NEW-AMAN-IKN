import { bacaFokus, cariFokusMakro, deteksiMakro, skorKetajaman, terapkanFokus } from "./makroKamera";

function kamera(cap = { focusMode: ["continuous", "manual"], focusDistance: { min: 0, max: 10, step: 0.5 } }) {
  const settings = { focusMode: "continuous", focusDistance: 4, zoom: 2, torch: true };
  return { readyState: "live", getCapabilities: () => cap, getSettings: () => ({ ...settings }),
    getConstraints: () => ({ width: { ideal: 1920 }, advanced: [{ focusMode: "continuous", zoom: 2 }] }),
    applyConstraints: jest.fn(async c => Object.assign(settings, ...c.advanced)), settings };
}
test("deteksi berdasarkan kamera aktif, bukan hanya nama fitur browser", () => {
  expect(deteksiMakro(kamera()).jenis).toBe("manual");
  expect(deteksiMakro(kamera({ focusMode: ["continuous"] })).jenis).toBe("otomatis");
  expect(deteksiMakro(kamera({})).jenis).toBe("none");
  expect(deteksiMakro({ getCapabilities: () => { throw Error(); } }).jenis).toBe("none");
});
test("pencarian memilih detail terbaik, tetap dalam rentang dan mempertahankan zoom/senter", async () => {
  const tr = kamera();
  expect(await cariFokusMakro(tr, () => 100 - (tr.settings.focusDistance - 1.5) ** 2, () => true, async () => {})).toBe("manual");
  expect(tr.settings.focusDistance).toBe(1.5);
  expect(tr.settings).toMatchObject({ focusMode: "manual", zoom: 2, torch: true });
  for (const [c] of tr.applyConstraints.mock.calls) {
    const d = c.advanced.at(-1).focusDistance;
    expect(d).toBeGreaterThanOrEqual(0); expect(d).toBeLessThanOrEqual(10);
    expect(c.width).toEqual({ ideal: 1920 });
  }
});
test("opsi fokus otomatis diverifikasi dari settings, bukan promise sukses saja", async () => {
  const tr = kamera({ focusMode: ["continuous"] });
  expect(await cariFokusMakro(tr, jest.fn(), () => true)).toBe("otomatis");
  expect(tr.settings.pointsOfInterest).toEqual([{ x: 0.5, y: 0.5 }]);
  tr.settings.focusMode = "continuous";
  tr.getCapabilities = () => ({ focusMode: ["single-shot", "continuous"] });
});
test("kamera yang mengabaikan fokus manual tidak diklaim berhasil", async () => {
  const tr = kamera(); tr.applyConstraints.mockImplementation(async () => {});
  await expect(cariFokusMakro(tr, () => 10, () => true, async () => {})).rejects.toThrow(/mengabaikan/);
});
test("pencarian berhenti saat kamera berubah dan objek tanpa detail tidak diklaim tajam", async () => {
  const tr = kamera(); let aktif = true;
  await expect(cariFokusMakro(tr, () => 0, () => aktif, async () => { aktif = false; })).rejects.toThrow(/dibatalkan/);
  expect(tr.applyConstraints).toHaveBeenCalledTimes(1);
  await expect(cariFokusMakro(kamera(), () => 0, () => true, async () => {})).rejects.toThrow(/Detail belum cukup/);
});
test("fokus awal dapat dipulihkan tanpa menghapus constraint resolusi", async () => {
  const tr = kamera(), awal = bacaFokus(tr);
  await terapkanFokus(tr, { focusMode: "manual", focusDistance: 0.5 });
  await terapkanFokus(tr, awal);
  expect(bacaFokus(tr)).toEqual(awal);
});
test("skor membedakan bidang polos dari tepi detail", () => {
  const data = new Uint8ClampedArray(16 * 16 * 4).fill(100);
  expect(skorKetajaman({ data, width: 16, height: 16 })).toBe(0);
  for (let i = 0; i < data.length; i += 8) data[i] = data[i + 1] = data[i + 2] = 255;
  expect(skorKetajaman({ data, width: 16, height: 16 })).toBeGreaterThan(4);
});
