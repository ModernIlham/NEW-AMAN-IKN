// Logika MURNI editor denah (tanpa Leaflet/geoman) — teruji unit.
// Sisi Leaflet-nya ada di components/spasial/DenahEditor.jsx.

/** Tutup cincin bila titik akhir belum mengulang titik awal (geoman TIDAK
 *  menutup cincin pada toGeoJSON — GeoJSON RFC 7946 mewajibkannya). */
export function tutupCincin(cincin) {
  const c = (cincin || []).filter(
    (t) => Array.isArray(t) && t.length >= 2
      && Number.isFinite(t[0]) && Number.isFinite(t[1]));
  if (c.length < 3) return null;
  const [x0, y0] = c[0];
  const [xn, yn] = c[c.length - 1];
  if (x0 !== xn || y0 !== yn) return [...c, [x0, y0]];
  return c;
}

function normalPoligon(koordinat) {
  const cincin = (koordinat || []).map(tutupCincin).filter(Boolean);
  return cincin.length ? cincin : null;
}

/**
 * Gabungkan fitur hasil menggambar menjadi SATU geometri node.
 *
 * geoman menghasilkan satu layer per goresan; sebuah node boleh terdiri dari
 * beberapa bagian terpisah (kampus dengan dua tapak) → MultiPolygon. Fitur
 * non-poligon dibuang; nol poligon = {geometry: null} (pemanggil menafsirkan
 * sebagai "hapus bentuk").
 */
export function fiturKeGeometri(fitur) {
  const poligon = [];
  for (const f of fitur || []) {
    const g = f?.geometry || f;            // terima Feature maupun geometry polos
    if (!g || typeof g !== "object") continue;
    if (g.type === "Polygon") {
      const p = normalPoligon(g.coordinates);
      if (p) poligon.push(p);
    } else if (g.type === "MultiPolygon") {
      for (const bagian of g.coordinates || []) {
        const p = normalPoligon(bagian);
        if (p) poligon.push(p);
      }
    }
  }
  if (!poligon.length) return { geometry: null };
  if (poligon.length === 1) return { geometry: { type: "Polygon", coordinates: poligon[0] } };
  return { geometry: { type: "MultiPolygon", coordinates: poligon } };
}

/** Susun payload PUT /spasial/node/{id} dari dokumen node tersimpan + geometri
 *  baru. PUT mengganti SELURUH field NodeIn, jadi semua field lama harus ikut —
 *  mengirim geometry saja akan mengosongkan nama/kode/lantai. */
export function payloadSimpan(node, geometry) {
  return {
    tipe: node?.tipe || "",
    nama: node?.nama || "",
    kode: node?.kode || "",
    parent_id: node?.parent_id || "",
    nama_alias: node?.nama_alias || [],
    lantai: node?.lantai || null,
    zona_kode: node?.zona_kode || "",
    subzona_kode: node?.subzona_kode || "",
    fungsi_kawasan: node?.fungsi_kawasan || "",
    properties: node?.properties || {},
    status: node?.status || "aktif",
    prioritas: node?.prioritas ?? null,
    // {} (bukan null!) = kosongkan bentuk; null berarti "tidak diubah".
    geometry: geometry === null ? {} : geometry,
  };
}

/** Pusat peta awal editor: bbox node sendiri → bbox induk → kawasan IKN. */
export function pusatAwal(node, induk) {
  const dariBbox = (bbox) => {
    if (!Array.isArray(bbox) || bbox.length !== 4) return null;
    const [x1, y1, x2, y2] = bbox.map(Number);
    if (![x1, y1, x2, y2].every(Number.isFinite)) return null;
    return { lat: (y1 + y2) / 2, lng: (x1 + x2) / 2, zoom: 17 };
  };
  return dariBbox(node?.bbox) || dariBbox(induk?.bbox)
    || { lat: -1.4, lng: 116.7, zoom: 13 };   // fallback: kawasan IKN
}
