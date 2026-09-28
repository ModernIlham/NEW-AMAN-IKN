import { gambarWatermarkKamera } from "./watermarkKamera";
test("panel baru sama luas dengan panel lama dan semua detail tetap digambar", () => {
  const ctx = Object.fromEntries(["save", "restore", "beginPath", "moveTo", "lineTo", "quadraticCurveTo", "closePath", "clip", "fillRect", "fillText"].map(k => [k, jest.fn()]));
  ctx.measureText = t => ({ width: t.length * 9 });
  ctx.createLinearGradient = () => ({ addColorStop: jest.fn() });
  const lines = ["28 Sep 2026 18.24.57", "GPS -0.962036, 116.712419 (±8 m)", "3080158999 NUP 10", "Trainer Kit • Lokasi uji", "Melekat ke: Operasional — Unit/Tempat/Tugas", "Nama Pengguna: Petugas Uji"];
  const b = gambarWatermarkKamera(ctx, 960, 1280, lines);
  const fs = Math.round(960 * 0.018), lh = Math.round(fs * 1.4), pad = Math.round(fs * 0.8);
  expect(b.lebar).toBe(Math.max(...lines.map(l => l.length * 9)) + pad * 2);
  expect(b.tinggi).toBe(lh * 6 + pad * 1.4);
  expect(b.y + b.tinggi).toBeLessThan(1280);
  expect(ctx.fillText.mock.calls.map(c => c[0])).toEqual(lines);
  expect(ctx.restore).toHaveBeenCalledTimes(1);
});
