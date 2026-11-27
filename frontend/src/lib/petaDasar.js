// Peta dasar OSM — SATU sumber untuk semua peta Leaflet di aplikasi.
//
// Dulu alamat ubin, batas zoom, dan atribusi ini disalin di empat berkas
// (Peta Aset, Peta Kolaborasi, Editor Denah, Lokasi Temuan). Lapisan citra
// eksisting (lib/lapisanCitra.js) ditumpuk tepat di atas lapisan ini, jadi
// keduanya harus sepakat soal zoom dan urutan pane.
import L from "leaflet";

export const URL_OSM = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
export const ATRIBUSI_OSM =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
// maxZoom 22 di atas native OSM z19: Leaflet MEMPERBESAR ubin z19 pada z20–22
// (agak buram) supaya pin yang berdekatan tetap bisa dipisahkan.
export const ZOOM_MAKS_PETA = 22;
export const ZOOM_NATIVE_OSM = 19;

/** Pasang ubin OSM ke peta; kembalikan layer-nya. */
export function pasangPetaDasar(map) {
  return L.tileLayer(URL_OSM, {
    maxZoom: ZOOM_MAKS_PETA,
    maxNativeZoom: ZOOM_NATIVE_OSM,
    attribution: ATRIBUSI_OSM,
  }).addTo(map);
}
