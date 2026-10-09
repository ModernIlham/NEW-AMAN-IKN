import { gpsPemegangLayak } from "./gpsKameraPemegang";
const now = 1791500000000;
const fix = { lat: "-0.962000", lng: "116.700000", accuracy: 8, timestamp: now };
test.each([0, 4, 7.99, 8])("akurasi %s m boleh tanpa pembulatan", accuracy => {
  expect(gpsPemegangLayak({ ...fix, accuracy }, now)).toBe(true);
});
test.each([8.001, 8.4, 9, -1, NaN, Infinity, null, undefined, "8"])("akurasi invalid %s ditolak", accuracy => {
  expect(gpsPemegangLayak({ ...fix, accuracy }, now)).toBe(false);
});
test.each([now - 60001, now + 1, 0, undefined, NaN])("fix usang/tanpa timestamp asli ditolak: %s", timestamp => {
  expect(gpsPemegangLayak({ ...fix, timestamp }, now)).toBe(false);
});
test("batas satu menit dan koordinat harus valid", () => {
  expect(gpsPemegangLayak({ ...fix, timestamp: now - 60000 }, now)).toBe(true);
  expect(gpsPemegangLayak(null, now)).toBe(false);
  for (const lat of ["", null, undefined, NaN, 91, -91]) expect(gpsPemegangLayak({ ...fix, lat }, now)).toBe(false);
  for (const lng of ["", null, undefined, NaN, 181, -181]) expect(gpsPemegangLayak({ ...fix, lng }, now)).toBe(false);
});
