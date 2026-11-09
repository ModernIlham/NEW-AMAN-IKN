import L from "leaflet";
import { toast } from "sonner";
import { pasangLokasiSaya } from "./lokasiSayaPeta";

jest.mock("sonner", () => ({ toast: { error: jest.fn() } }));

let host;
let map;
let kontrol;
let gps;
let sesi;
const asliGps = Object.getOwnPropertyDescriptor(navigator, "geolocation");
const asliVisibility = Object.getOwnPropertyDescriptor(document, "visibilityState");
const asliSvg = L.Browser.svg;

function fix(lat = -1.4, accuracy = 8) {
  return { coords: { latitude: lat, longitude: 116.7, accuracy }, timestamp: Date.now() };
}

const tombol = () => host.querySelector('[data-testid="peta-lokasi-saya"]');
const ikuti = () => host.querySelector('[data-testid="peta-lokasi-saya-ikuti"]');
const pesan = () => host.querySelector('[role="status"]').textContent;
function lapisan(Jenis) {
  const hasil = [];
  map.eachLayer((layer) => { if (layer instanceof Jenis) hasil.push(layer); });
  return hasil;
}

beforeEach(() => {
  jest.useFakeTimers();
  // Legenda sekali-per-sesi diuji tersendiri; di uji lain ia menutupi status.
  sessionStorage.setItem("aman_lokasi_legenda", "1");
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  sesi = [];
  gps = {
    watchPosition: jest.fn((ok, error) => { sesi.push({ ok, error }); return sesi.length; }),
    clearWatch: jest.fn(),
  };
  Object.defineProperty(navigator, "geolocation", { configurable: true, value: gps });
  // Renderer Leaflet asli, tanpa tile jaringan. jsdom hanya perlu ukuran dan SVG.
  L.Browser.svg = true;
  host = document.createElement("div");
  Object.defineProperties(host, { clientWidth: { value: 800 }, clientHeight: { value: 600 } });
  document.body.appendChild(host);
  map = L.map(host, { zoomControl: false, attributionControl: false, zoomAnimation: false, fadeAnimation: false })
    .setView([-1.4, 116.7], 16);
  kontrol = pasangLokasiSaya(map);
});

afterEach(() => {
  kontrol.destroy();
  map?.remove();
  host.remove();
  jest.useRealTimers();
});

afterAll(() => {
  L.Browser.svg = asliSvg;
  if (asliGps) Object.defineProperty(navigator, "geolocation", asliGps);
  else delete navigator.geolocation;
  if (asliVisibility) Object.defineProperty(document, "visibilityState", asliVisibility);
  else delete document.visibilityState;
});

test("Leaflet asli: titik dan radius berpindah tanpa mengganti layer atau melakukan zoom berulang", () => {
  const fitBounds = jest.spyOn(map, "fitBounds");
  expect(gps.watchPosition).not.toHaveBeenCalled();
  tombol().click();
  expect(tombol()).toHaveAttribute("aria-pressed", "true");
  sesi[0].ok(fix());
  const [marker] = lapisan(L.Marker);
  const [circle] = lapisan(L.Circle);
  const zoom = map.getZoom();
  expect(pesan()).toBe("Lokasi aktif · ±8 m");
  jest.advanceTimersByTime(1000);
  sesi[0].ok(fix(-1.45, 40));
  expect(lapisan(L.Marker)).toEqual([marker]);
  expect(lapisan(L.Circle)).toEqual([circle]);
  expect(marker.getLatLng().lat).toBe(-1.45);
  expect(circle.getRadius()).toBe(40);
  expect(map.getBounds().contains(marker.getLatLng())).toBe(true);
  expect(map.getZoom()).toBe(zoom);
  expect(fitBounds).toHaveBeenCalledTimes(1);
  expect(ikuti()).toHaveAttribute("aria-pressed", "true");
});

test("menggeser peta menghentikan ikuti kamera; titik tetap diperbarui dan tombol ikuti memusatkan kembali", () => {
  tombol().click();
  sesi[0].ok(fix());
  map.setView([-2, 116.7], map.getZoom(), { animate: false });
  expect(ikuti()).toHaveAttribute("aria-pressed", "false");
  const pusat = map.getCenter();
  jest.advanceTimersByTime(1000);
  sesi[0].ok(fix(-1.5));
  expect(lapisan(L.Marker)[0].getLatLng().lat).toBe(-1.5);
  expect(map.getCenter()).toEqual(pusat);
  ikuti().click();
  expect(ikuti()).toHaveAttribute("aria-pressed", "true");
  expect(map.getCenter().lat).toBeCloseTo(-1.5, 3);
});

test("sinyal hilang mempertahankan lokasi terakhir dengan penanda basi, lalu pulih tanpa toast berulang", () => {
  tombol().click();
  sesi[0].ok(fix());
  const [marker] = lapisan(L.Marker);
  jest.advanceTimersByTime(30000);
  expect(pesan()).toMatch(/belum diperbarui/);
  expect(marker.getTooltip().getContent()).toMatch(/Lokasi terakhir/);
  expect(marker.options.opacity).toBeLessThan(1);
  jest.advanceTimersByTime(2000);
  sesi[1].ok(fix(-1.5));
  expect(marker.options.opacity).toBe(1);
  expect(pesan()).toMatch(/Lokasi aktif/);
  expect(toast.error).not.toHaveBeenCalled();
});

test("tombol dapat membatalkan pencarian; mematikan fitur menghapus titik dan callback terlambat", () => {
  tombol().click();
  expect(pesan()).toMatch(/Mencari lokasi/);
  tombol().click();
  expect(gps.clearWatch).toHaveBeenCalledWith(1);
  sesi[0].ok(fix());
  expect(lapisan(L.Marker)).toHaveLength(0);
  expect(tombol()).toHaveAttribute("aria-pressed", "false");
  tombol().click();
  sesi[1].ok(fix());
  tombol().click();
  expect(lapisan(L.Marker)).toHaveLength(0);
  expect(lapisan(L.Circle)).toHaveLength(0);
  expect(ikuti().hidden).toBe(true);
});

test("peta keep-alive menjeda GPS dan kembali memperbarui; map.remove membersihkan watch dan listener", () => {
  tombol().click();
  sesi[0].ok(fix());
  kontrol.setVisible(false);
  expect(gps.clearWatch).toHaveBeenCalledWith(1);
  expect(pesan()).toBe("Lokasi dijeda");
  jest.advanceTimersByTime(60000);
  expect(gps.watchPosition).toHaveBeenCalledTimes(1);
  kontrol.setVisible(true);
  expect(gps.watchPosition).toHaveBeenCalledTimes(2);
  sesi[1].ok(fix(-1.5));
  map.remove(); // Leaflet unload juga memanggil onRemove kontrol.
  map = null;
  expect(gps.clearWatch).toHaveBeenCalledWith(2);
  const jumlah = gps.watchPosition.mock.calls.length;
  sesi[1].ok(fix(-2));
  document.dispatchEvent(new Event("visibilitychange"));
  window.dispatchEvent(new Event("pageshow"));
  jest.advanceTimersByTime(120000);
  expect(gps.watchPosition).toHaveBeenCalledTimes(jumlah);
});

test("izin dicabut menghapus titik dan mematikan tombol dengan satu pesan izin", () => {
  tombol().click();
  sesi[0].ok(fix());
  sesi[0].error({ code: 1 });
  expect(lapisan(L.Marker)).toHaveLength(0);
  expect(tombol()).toHaveAttribute("aria-pressed", "false");
  expect(toast.error).toHaveBeenCalledTimes(1);
  expect(toast.error).toHaveBeenCalledWith(expect.stringMatching(/Izin lokasi ditolak/));
});

test("jejak perjalanan: garis bertambah saat bergerak, jitter diam diabaikan, panjang tampil, terhapus saat berhenti", () => {
  const jejakBtn = () => host.querySelector('[data-testid="peta-lokasi-saya-jejak"]');
  expect(jejakBtn().hidden).toBe(true);
  tombol().click();
  expect(jejakBtn().hidden).toBe(false);
  sesi[0].ok(fix(-1.4, 8));
  jest.advanceTimersByTime(1000);
  sesi[0].ok(fix(-1.40001, 8)); // ±1 m: jitter
  jest.advanceTimersByTime(1000);
  sesi[0].ok(fix(-1.4002, 8)); // ±22 m: langkah nyata
  const [garis] = lapisan(L.Polyline).filter((l) => !(l instanceof L.Circle));
  expect(garis.getLatLngs()).toHaveLength(2);
  expect(pesan()).toMatch(/jejak 2\d,\d m/);
  jejakBtn().click(); // sembunyikan
  expect(lapisan(L.Polyline).filter((l) => !(l instanceof L.Circle))).toHaveLength(0);
  jejakBtn().click();
  tombol().click(); // berhenti
  expect(lapisan(L.Polyline)).toHaveLength(0);
});

test("kerucut arah tampil hanya saat bergerak dengan heading sah; onPosisi menerima fix & null", () => {
  kontrol.destroy();
  const onPosisi = jest.fn();
  kontrol = pasangLokasiSaya(map, { onPosisi });
  tombol().click();
  sesi[0].ok({ coords: { latitude: -1.4, longitude: 116.7, accuracy: 8, heading: 90, speed: 1.4 }, timestamp: Date.now() });
  const arah = host.querySelector("[data-arah]");
  expect(arah.style.display).toBe("block");
  expect(arah.style.transform).toBe("rotate(90deg)");
  expect(onPosisi).toHaveBeenLastCalledWith(expect.objectContaining({ lat: -1.4, heading: 90 }));
  jest.advanceTimersByTime(1000);
  sesi[0].ok({ coords: { latitude: -1.4, longitude: 116.7, accuracy: 8, heading: 90, speed: 0 }, timestamp: Date.now() });
  expect(arah.style.display).toBe("none");
  tombol().click();
  expect(onPosisi).toHaveBeenLastCalledWith(null);
});

test("layar tetap menyala: hanya bila didukung, atas permintaan, dilepas saat lokasi dimatikan", async () => {
  const lepas = jest.fn(() => Promise.resolve());
  const request = jest.fn(() => Promise.resolve({ release: lepas, addEventListener: jest.fn() }));
  Object.defineProperty(navigator, "wakeLock", { configurable: true, value: { request } });
  try {
    kontrol.destroy();
    kontrol = pasangLokasiSaya(map);
    const layar = () => host.querySelector('[data-testid="peta-lokasi-saya-layar"]');
    expect(layar().hidden).toBe(true);
    tombol().click();
    expect(layar().hidden).toBe(false);
    expect(request).not.toHaveBeenCalled(); // tidak otomatis
    layar().click();
    await Promise.resolve(); await Promise.resolve();
    expect(request).toHaveBeenCalledWith("screen");
    expect(layar()).toHaveAttribute("aria-pressed", "true");
    tombol().click();
    expect(lepas).toHaveBeenCalled();
  } finally {
    delete navigator.wakeLock;
  }
});

test("tombol memakai kelas ukuran yang sama dengan tombol zoom (bukan 44 px inline)", () => {
  for (const b of host.querySelectorAll(".peta-lokasi-btn")) {
    expect(b.style.width).toBe("");
    expect(b.style.minHeight).toBe("");
  }
  expect(host.querySelectorAll(".peta-lokasi-bar .peta-lokasi-btn")).toHaveLength(4);
});

test("tiap ketukan menjelaskan efeknya di kotak status, lalu kembali ke status lokasi", () => {
  tombol().click();
  sesi[0].ok(fix());
  const klik = (id) => host.querySelector(`[data-testid="peta-lokasi-saya-${id}"]`).click();
  klik("jejak");
  expect(pesan()).toMatch(/Garis jejak disembunyikan/);
  klik("jejak");
  expect(pesan()).toMatch(/^Jejak: garis putus-putus/);
  map.fire("movestart");
  expect(pesan()).toMatch(/Ikuti berhenti karena peta digeser/);
  klik("ikuti");
  expect(pesan()).toMatch(/^Ikuti: peta bergeser otomatis/);
  klik("ikuti");
  expect(pesan()).toBe("Peta dipusatkan ke lokasi Anda");
  jest.advanceTimersByTime(3000);
  expect(pesan()).toBe("Lokasi aktif · ±8 m");
  tombol().click();
  expect(pesan()).toMatch(/Lokasi dimatikan/);
  jest.advanceTimersByTime(3000);
  expect(host.querySelector('[role="status"]').hidden).toBe(true);
});

test("legenda tombol tampil SEKALI per sesi saat lokasi pertama dinyalakan", () => {
  sessionStorage.removeItem("aman_lokasi_legenda");
  tombol().click();
  expect(pesan()).toMatch(/ikuti lokasi · .* jejak .* layar tetap menyala/);
  jest.advanceTimersByTime(7000);
  tombol().click();
  tombol().click();
  expect(pesan()).not.toMatch(/Tombol di bawah/);
});
