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
const pesan = () => host.querySelector('[role="status"]').textContent;
function lapisan(Jenis) {
  const hasil = [];
  map.eachLayer((layer) => { if (layer instanceof Jenis) hasil.push(layer); });
  return hasil;
}

beforeEach(() => {
  jest.useFakeTimers();
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
  expect(tombol().title).toMatch(/diikuti/);
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
  expect(tombol().title).toMatch(/^Tampilkan/);
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









test("SATU tombol seukuran zoom: mati → nyala+ikuti → (geser peta) kembali ke lokasi → mati", () => {
  expect(host.querySelectorAll(".peta-lokasi-bar button")).toHaveLength(1);
  expect(tombol().className).toBe("peta-lokasi-btn");
  expect(tombol().style.width).toBe("");
  tombol().click();
  sesi[0].ok(fix());
  expect(tombol().title).toMatch(/diikuti/);
  // Pengguna menggeser peta → tidak mengikuti; titik tetap diperbarui.
  map.setView([-2, 116.7], map.getZoom(), { animate: false });
  expect(tombol().title).toBe("Kembali ke lokasi Anda");
  expect(pesan()).toMatch(/Peta digeser — ketuk ◎/);
  const pusat = map.getCenter();
  jest.advanceTimersByTime(3000);
  sesi[0].ok(fix(-1.5));
  expect(lapisan(L.Marker)[0].getLatLng().lat).toBe(-1.5);
  expect(map.getCenter()).toEqual(pusat);
  // Ketuk: kembali ke lokasi (GPS TIDAK dimatikan).
  tombol().click();
  expect(map.getCenter().lat).toBeCloseTo(-1.5, 3);
  expect(tombol().title).toMatch(/diikuti/);
  expect(gps.clearWatch).not.toHaveBeenCalled();
  expect(pesan()).toMatch(/Kembali mengikuti/);
  // Ketuk lagi saat mengikuti: mati.
  tombol().click();
  expect(gps.clearWatch).toHaveBeenCalled();
  expect(lapisan(L.Marker)).toHaveLength(0);
  expect(pesan()).toBe("Lokasi dimatikan");
});

test("garis pandu ke tujuan: tampil Anda+aset sekaligus, ikut bergerak, hilang saat dihapus/lokasi mati", () => {
  tombol().click();
  sesi[0].ok(fix());
  const garis = () => lapisan(L.Polyline).filter((l) => !(l instanceof L.Circle));
  kontrol.setTujuan({ lat: -1.402, lng: 116.702 });
  expect(garis()).toHaveLength(1);
  expect(map.getBounds().contains([-1.402, 116.702])).toBe(true);
  expect(map.getBounds().contains([-1.4, 116.7])).toBe(true);
  expect(tombol().title).toMatch(/diikuti/); // gerakan kamera milik aplikasi, bukan pengguna
  jest.advanceTimersByTime(1000);
  sesi[0].ok(fix(-1.401));
  expect(garis()[0].getLatLngs()[0].lat).toBeCloseTo(-1.401, 5);
  kontrol.setTujuan(null);
  expect(garis()).toHaveLength(0);
  kontrol.setTujuan({ lat: -1.402, lng: 116.702 });
  tombol().click(); // matikan
  expect(garis()).toHaveLength(0);
});

test("berhentiMengikuti (geseran milik aplikasi) tidak memunculkan pesan 'Peta digeser'", () => {
  tombol().click();
  sesi[0].ok(fix());
  jest.advanceTimersByTime(3000);
  kontrol.berhentiMengikuti();
  map.setView([-2, 116.7], map.getZoom(), { animate: false });
  expect(tombol().title).toBe("Kembali ke lokasi Anda");
  expect(pesan()).not.toMatch(/Peta digeser/);
});
