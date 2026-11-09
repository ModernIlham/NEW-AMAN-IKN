import { buatPemantauLokasi } from "./pantauLokasi";

let gps;
let pemantau;
let onPosition;
let onStatus;
let sesi;
const asliGps = Object.getOwnPropertyDescriptor(navigator, "geolocation");
const asliSecure = Object.getOwnPropertyDescriptor(window, "isSecureContext");
const asliVisibility = Object.getOwnPropertyDescriptor(document, "visibilityState");

function fix(tambahan = {}) {
  return { coords: { latitude: -1.4, longitude: 116.7, accuracy: 8, ...tambahan }, timestamp: Date.now() };
}

function visibilitas(nilai) {
  Object.defineProperty(document, "visibilityState", { configurable: true, value: nilai });
  document.dispatchEvent(new Event("visibilitychange"));
}

beforeEach(() => {
  jest.useFakeTimers();
  sesi = [];
  gps = {
    watchPosition: jest.fn((ok, error, options) => {
      sesi.push({ ok, error, options });
      return sesi.length - 1; // ID 0 juga sah.
    }),
    clearWatch: jest.fn(),
  };
  Object.defineProperty(navigator, "geolocation", { configurable: true, value: gps });
  Object.defineProperty(window, "isSecureContext", { configurable: true, value: true });
  visibilitas("visible");
  onPosition = jest.fn();
  onStatus = jest.fn();
  pemantau = buatPemantauLokasi({ onPosition, onStatus });
});

afterEach(() => {
  pemantau.destroy();
  jest.useRealTimers();
});

afterAll(() => {
  for (const [obj, key, descriptor] of [
    [navigator, "geolocation", asliGps], [window, "isSecureContext", asliSecure],
    [document, "visibilityState", asliVisibility],
  ]) {
    if (descriptor) Object.defineProperty(obj, key, descriptor);
    else delete obj[key];
  }
});

test("hanya aktif setelah diminta; satu watch segar terus mengikuti perjalanan meski akurasi menurun", () => {
  expect(gps.watchPosition).not.toHaveBeenCalled();
  pemantau.start();
  pemantau.start();
  expect(gps.watchPosition).toHaveBeenCalledTimes(1);
  expect(sesi[0].options).toEqual({ enableHighAccuracy: true, maximumAge: 0, timeout: 15000 });
  sesi[0].ok(fix());
  jest.advanceTimersByTime(1000);
  sesi[0].ok(fix({ latitude: -1.5, accuracy: 180 }));
  expect(onPosition.mock.calls.map(([p]) => p.lat)).toEqual([-1.4, -1.5]);
  expect(onStatus).toHaveBeenLastCalledWith(expect.objectContaining({ status: "weak", active: true }));
  expect(gps.clearWatch).not.toHaveBeenCalled();
});

test("pembaruan rapat digabung maksimal sekali per detik, dengan fix paling baru tetap digambar", () => {
  pemantau.start();
  sesi[0].ok(fix());
  jest.advanceTimersByTime(100);
  sesi[0].ok(fix({ latitude: -1.41 }));
  jest.advanceTimersByTime(100);
  sesi[0].ok(fix({ latitude: -1.42 }));
  expect(onPosition).toHaveBeenCalledTimes(1);
  jest.advanceTimersByTime(800);
  expect(onPosition).toHaveBeenCalledTimes(2);
  expect(onPosition).toHaveBeenLastCalledWith(expect.objectContaining({ lat: -1.42 }));
});

test("menolak koordinat rusak, cache lama, timestamp masa depan, dan callback yang urutannya mundur", () => {
  pemantau.start();
  for (const hasil of [
    fix({ latitude: NaN }), fix({ longitude: 181 }), fix({ latitude: -91 }),
    fix({ accuracy: -1 }), fix({ accuracy: Infinity }), fix({ latitude: null }),
    { ...fix(), timestamp: Date.now() - 15001 }, { ...fix(), timestamp: Date.now() + 6000 },
  ]) sesi[0].ok(hasil);
  expect(onPosition).not.toHaveBeenCalled();
  sesi[0].ok(fix());
  const lama = fix({ latitude: -1.6 });
  jest.advanceTimersByTime(1000);
  sesi[0].ok(fix({ latitude: -1.5 }));
  sesi[0].ok(lama);
  expect(onPosition).toHaveBeenCalledTimes(2);
  expect(onPosition).toHaveBeenLastCalledWith(expect.objectContaining({ lat: -1.5 }));
});

test.each([2, 3])("galat GPS sementara %i memulai ulang dengan backoff, mengabaikan callback watch lama", (code) => {
  pemantau.start();
  sesi[0].ok(fix());
  sesi[0].error({ code });
  expect(gps.clearWatch).toHaveBeenCalledWith(0);
  expect(onStatus).toHaveBeenLastCalledWith(expect.objectContaining({ status: "retrying", active: true }));
  sesi[0].ok(fix({ latitude: -2 }));
  jest.advanceTimersByTime(1999);
  expect(gps.watchPosition).toHaveBeenCalledTimes(1);
  jest.advanceTimersByTime(1);
  expect(gps.watchPosition).toHaveBeenCalledTimes(2);
  sesi[1].error({ code });
  jest.advanceTimersByTime(3999);
  expect(gps.watchPosition).toHaveBeenCalledTimes(2);
  jest.advanceTimersByTime(1);
  sesi[2].ok(fix({ latitude: -1.5 }));
  expect(onPosition.mock.calls.map(([p]) => p.lat)).toEqual([-1.4, -1.5]);
  expect(onStatus).toHaveBeenLastCalledWith(expect.objectContaining({ status: "live" }));
});

test("jeda retry dibatasi 30 detik dan direset setelah GPS kembali berhasil", () => {
  pemantau.start();
  for (const jeda of [2000, 4000, 8000, 16000, 30000, 30000]) {
    sesi[sesi.length - 1].error({ code: 3 });
    const jumlah = gps.watchPosition.mock.calls.length;
    jest.advanceTimersByTime(jeda - 1);
    expect(gps.watchPosition).toHaveBeenCalledTimes(jumlah);
    jest.advanceTimersByTime(1);
    expect(gps.watchPosition).toHaveBeenCalledTimes(jumlah + 1);
  }
  sesi[sesi.length - 1].ok(fix());
  sesi[sesi.length - 1].error({ code: 2 });
  const jumlah = gps.watchPosition.mock.calls.length;
  jest.advanceTimersByTime(2000);
  expect(gps.watchPosition).toHaveBeenCalledTimes(jumlah + 1);
});

test("GPS senyap ditandai basi sesudah 30 detik, lalu dipulihkan otomatis", () => {
  pemantau.start();
  sesi[0].ok(fix());
  jest.advanceTimersByTime(29999);
  expect(gps.clearWatch).not.toHaveBeenCalled();
  jest.advanceTimersByTime(1);
  expect(onStatus).toHaveBeenLastCalledWith(expect.objectContaining({ status: "stale" }));
  expect(gps.clearWatch).toHaveBeenCalledWith(0);
  jest.advanceTimersByTime(2000);
  sesi[1].ok(fix({ latitude: -1.5 }));
  expect(onPosition).toHaveBeenLastCalledWith(expect.objectContaining({ lat: -1.5 }));
});

test("izin ditolak menghentikan pemantauan tanpa retry; pengguna bisa mencoba lagi", () => {
  pemantau.start();
  sesi[0].error({ code: 1 });
  expect(onStatus).toHaveBeenLastCalledWith(expect.objectContaining({ status: "error", active: false, message: expect.stringMatching(/Izin lokasi ditolak/) }));
  jest.advanceTimersByTime(120000);
  expect(gps.watchPosition).toHaveBeenCalledTimes(1);
  pemantau.start();
  expect(gps.watchPosition).toHaveBeenCalledTimes(2);
});

test("tab tersembunyi, peta keep-alive tersembunyi, dan pagehide menghentikan GPS lalu melanjutkan satu watch", () => {
  pemantau.start();
  sesi[0].ok(fix());
  visibilitas("hidden");
  expect(onStatus).toHaveBeenLastCalledWith(expect.objectContaining({ status: "paused", active: true }));
  expect(gps.clearWatch).toHaveBeenCalledWith(0);
  jest.advanceTimersByTime(120000);
  expect(gps.watchPosition).toHaveBeenCalledTimes(1);
  pemantau.setVisible(false);
  visibilitas("visible");
  expect(gps.watchPosition).toHaveBeenCalledTimes(1);
  pemantau.setVisible(true);
  expect(gps.watchPosition).toHaveBeenCalledTimes(2);
  window.dispatchEvent(new Event("pagehide"));
  expect(gps.clearWatch).toHaveBeenCalledWith(1);
  window.dispatchEvent(new Event("pageshow"));
  visibilitas("visible");
  expect(gps.watchPosition).toHaveBeenCalledTimes(3);
});

test("stop saat mencari/mengantri update/retry membuang timer dan seluruh callback terlambat", () => {
  pemantau.start();
  pemantau.stop();
  sesi[0].ok(fix());
  expect(onPosition).not.toHaveBeenCalled();
  pemantau.start();
  sesi[1].ok(fix());
  jest.advanceTimersByTime(100);
  sesi[1].ok(fix({ latitude: -2 }));
  pemantau.stop();
  jest.advanceTimersByTime(2000);
  expect(onPosition).toHaveBeenCalledTimes(1);
  pemantau.start();
  sesi[2].error({ code: 3 });
  pemantau.destroy();
  sesi[2].ok(fix());
  jest.advanceTimersByTime(120000);
  window.dispatchEvent(new Event("pageshow"));
  visibilitas("visible");
  pemantau.start();
  expect(gps.watchPosition).toHaveBeenCalledTimes(3);
  expect(jest.getTimerCount()).toBe(0);
});

test("pemanggilan penyedia sinkron yang menolak izin tetap membersihkan ID watch", () => {
  gps.watchPosition.mockImplementation((_ok, error) => { error({ code: 1 }); return 42; });
  pemantau.start();
  expect(gps.clearWatch).toHaveBeenCalledWith(42);
  expect(jest.getTimerCount()).toBe(0);
});

test("perangkat tanpa API lokasi dan koneksi HTTP mendapat pesan yang bisa ditindaklanjuti", () => {
  Object.defineProperty(navigator, "geolocation", { configurable: true, value: undefined });
  pemantau.start();
  expect(onStatus).toHaveBeenLastCalledWith(expect.objectContaining({ status: "error", message: expect.stringMatching(/tidak didukung/) }));
  Object.defineProperty(window, "isSecureContext", { configurable: true, value: false });
  pemantau.start();
  expect(onStatus).toHaveBeenLastCalledWith(expect.objectContaining({ status: "error", message: expect.stringMatching(/HTTPS/) }));
});
