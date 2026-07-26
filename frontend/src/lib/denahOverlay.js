// Konversi sudut overlay denah (Fase 7) — murni & teruji.
//
// Server menyimpan sudut sebagai {tl, tr, bl} ber-[BUJUR, LINTANG] (lon-first,
// konsisten GeoJSON RFC 7946 di seluruh backend); Leaflet berbicara
// [LINTANG, BUJUR]. Dua fungsi kecil ini satu-satunya tempat pembalikan itu
// terjadi — tersebar di komponen = resep denah mendarat di Samudra Hindia.

export const URUTAN_SUDUT = ["tl", "tr", "bl"];

export function sudutKeLatLng(sudut) {
  if (!sudut) return null;
  const hasil = {};
  for (const k of URUTAN_SUDUT) {
    const p = sudut[k];
    if (!Array.isArray(p) || p.length < 2) return null;
    const lon = Number(p[0]);
    const lat = Number(p[1]);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
    hasil[k] = [lat, lon];
  }
  return hasil;
}

export function latLngKeSudut(latlng) {
  if (!latlng) return null;
  const hasil = {};
  for (const k of URUTAN_SUDUT) {
    const p = latlng[k];
    // Terima [lat, lng] maupun objek L.LatLng {lat, lng}.
    const lat = Array.isArray(p) ? Number(p[0]) : Number(p?.lat);
    const lon = Array.isArray(p) ? Number(p[1]) : Number(p?.lng);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
    hasil[k] = [lon, lat];
  }
  return hasil;
}
