// Gambar kondisi eksisting: titik, garis, area + label — dipakai bersama oleh
// peta tampilan (lib/lapisanCitra.js) dan editor (EditorGambarPeta.jsx).
//
// Label:
//   • garis "ikut"  → teks mengikuti alur garis (SVG textPath), selalu terbaca
//     dari kiri ke kanan; alur dihitung ulang tiap zoom.
//   • garis "tengah"→ teks datar di titik tengah panjang garis.
//   • area          → teks di tengah area (centroid; bila centroid jatuh di
//     luar bentuk cekung, dipakai titik tengah potongan terpanjang).
//   • titik         → di atas/kanan/bawah/kiri penanda.
// Teks SELALU dirender sebagai teks (textContent), tak pernah sebagai HTML.
import L from "leaflet";

export const GAYA_BAWAAN = {
  warna: "#2563eb", tebal: 3, opasitas: 1, isi_warna: "#2563eb", isi_opasitas: 0.25,
  putus: false, ukuran: 7,
};
export const LABEL_BAWAAN = { teks: "", warna: "#111827", ukuran: 13, tebal: true, halo: "#ffffff" };
export const POSISI_LABEL = {
  titik: ["atas", "kanan", "bawah", "kiri"],
  garis: ["ikut", "tengah"],
  area: ["tengah"],
};
const SVG_NS = "http://www.w3.org/2000/svg";
let nomorJalur = 0;

export function tipeDariGeometri(g) {
  return g?.type === "Point" ? "titik" : g?.type === "LineString" ? "garis" : g?.type === "Polygon" ? "area" : null;
}

/** Lengkapi fitur dengan gaya & label bawaan. */
export function lengkapiFitur(f) {
  const tipe = f.tipe || tipeDariGeometri(f.geometri);
  const label = { ...LABEL_BAWAAN, ...(f.label || {}) };
  if (!POSISI_LABEL[tipe]?.includes(label.posisi)) label.posisi = POSISI_LABEL[tipe]?.[0];
  const gaya = { ...GAYA_BAWAAN, ...(f.gaya || {}) };
  if (!f.gaya?.isi_warna) gaya.isi_warna = gaya.warna;
  return { ...f, tipe, gaya, label };
}

/** Opsi path Leaflet dari gaya fitur. */
export function opsiGaya(f) {
  const g = f.gaya;
  return {
    color: g.warna, weight: g.tebal, opacity: g.opasitas,
    fillColor: g.isi_warna, fillOpacity: f.tipe === "area" ? g.isi_opasitas : (f.tipe === "titik" ? g.opasitas : 0),
    dashArray: g.putus ? `${Math.max(4, g.tebal * 2.5)} ${Math.max(4, g.tebal * 2)}` : null,
    lineCap: g.putus ? "butt" : "round",
    radius: g.ukuran,
  };
}

// ── Geometri label (murni) ──────────────────────────────────────────────────

/** Titik pada separuh panjang garis. `pts` = [[x,y], …] (koordinat apa pun). */
export function titikTengahGaris(pts) {
  if (!pts?.length) return null;
  if (pts.length === 1) return pts[0];
  const seg = [];
  let total = 0;
  for (let i = 1; i < pts.length; i += 1) {
    const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    seg.push(d); total += d;
  }
  let sisa = total / 2;
  for (let i = 0; i < seg.length; i += 1) {
    if (sisa <= seg[i] || i === seg.length - 1) {
      const t = seg[i] ? Math.min(1, sisa / seg[i]) : 0;
      return [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t];
    }
    sisa -= seg[i];
  }
  return pts[pts.length - 1];
}

export function titikDalamCincin([x, y], cincin) {
  let dalam = false;
  for (let i = 0, j = cincin.length - 1; i < cincin.length; j = i, i += 1) {
    const [xi, yi] = cincin[i]; const [xj, yj] = cincin[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / ((yj - yi) || 1e-300) + xi) dalam = !dalam;
  }
  return dalam;
}

/** Titik label area: centroid bila di dalam, selain itu tengah potongan terpanjang. */
export function titikLabelArea(cincin) {
  const n = cincin.length;
  if (n < 3) return cincin[0] || null;
  let a = 0; let cx = 0; let cy = 0;
  for (let i = 0, j = n - 1; i < n; j = i, i += 1) {
    const f = cincin[j][0] * cincin[i][1] - cincin[i][0] * cincin[j][1];
    a += f; cx += (cincin[j][0] + cincin[i][0]) * f; cy += (cincin[j][1] + cincin[i][1]) * f;
  }
  if (Math.abs(a) > 1e-18) {
    const c = [cx / (3 * a), cy / (3 * a)];
    if (titikDalamCincin(c, cincin)) return c;
  }
  // Bentuk cekung: garis datar melalui tengah tinggi, ambil potongan dalam terpanjang.
  const ys = cincin.map((p) => p[1]);
  const y = (Math.min(...ys) + Math.max(...ys)) / 2;
  const xs = [];
  for (let i = 0, j = n - 1; i < n; j = i, i += 1) {
    const [xi, yi] = cincin[i]; const [xj, yj] = cincin[j];
    if ((yi > y) !== (yj > y)) xs.push(xi + (y - yi) * (xj - xi) / (yj - yi));
  }
  xs.sort((p, q) => p - q);
  let terbaik = null; let lebar = -1;
  for (let i = 0; i + 1 < xs.length; i += 2) {
    if (xs[i + 1] - xs[i] > lebar) { lebar = xs[i + 1] - xs[i]; terbaik = [(xs[i] + xs[i + 1]) / 2, y]; }
  }
  return terbaik || cincin[0];
}

/**
 * Jalur SVG "M x y L …" untuk label yang mengikuti garis.
 * - Bila teks muat di RUAS terpanjang, label ditaruh di ruas itu saja: teks
 *   yang melintasi tikungan tajam hurufnya renggang/bertumpuk dan sulit dibaca.
 * - Arah dibalik bila garis menuju ke kiri agar teks tak terbalik.
 */
export function jalurLabel(titikLayar, panjangTeks = 0) {
  if (!titikLayar?.length) return "";
  let p = titikLayar;
  if (p.length > 2 && panjangTeks > 0) {
    let iMaks = 0; let dMaks = -1;
    for (let i = 1; i < p.length; i += 1) {
      const d = Math.hypot(p[i].x - p[i - 1].x, p[i].y - p[i - 1].y);
      if (d > dMaks) { dMaks = d; iMaks = i; }
    }
    if (dMaks >= panjangTeks + 8) p = [p[iMaks - 1], p[iMaks]];
  }
  if (p[0].x > p[p.length - 1].x) p = [...p].reverse();
  return p.map((t, i) => `${i ? "L" : "M"}${t.x.toFixed(1)} ${t.y.toFixed(1)}`).join(" ");
}

/** Perkiraan panjang teks (px) — cukup untuk memilih ruas, tanpa mengukur DOM. */
export function perkiraanPanjangTeks(teks, ukuran) {
  return String(teks || "").length * ukuran * 0.58;
}

/** Batas [[s,w],[n,e]] semua fitur; null bila kosong. */
export function batasFitur(fitur) {
  let s = Infinity; let w = Infinity; let n = -Infinity; let e = -Infinity;
  const tambah = ([lon, lat]) => { s = Math.min(s, lat); n = Math.max(n, lat); w = Math.min(w, lon); e = Math.max(e, lon); };
  for (const f of fitur || []) {
    const g = f.geometri;
    if (g?.type === "Point") tambah(g.coordinates);
    else if (g?.type === "LineString") g.coordinates.forEach(tambah);
    else if (g?.type === "Polygon") g.coordinates.forEach((r) => r.forEach(tambah));
  }
  return Number.isFinite(s) ? [[s, w], [n, e]] : null;
}

// ── Leaflet ─────────────────────────────────────────────────────────────────

const keLatLng = ([lon, lat]) => [lat, lon];

/** Layer Leaflet satu fitur. `layer._fitur` menyimpan datanya. */
export function buatLayerFitur(fiturMentah, { renderer, pane, interaktif = false } = {}) {
  const f = lengkapiFitur(fiturMentah);
  const o = { ...opsiGaya(f), renderer, pane, interactive: interaktif, bubblingMouseEvents: !interaktif };
  let layer;
  if (f.tipe === "titik") layer = L.circleMarker(keLatLng(f.geometri.coordinates), o);
  else if (f.tipe === "garis") layer = L.polyline(f.geometri.coordinates.map(keLatLng), o);
  else layer = L.polygon(f.geometri.coordinates.map((r) => r.slice(0, -1).map(keLatLng)), o);
  layer._fitur = f;
  return layer;
}

/** Geometri GeoJSON (lon,lat) dari layer Leaflet hasil gambar/ubah. */
export function geometriDariLayer(layer) {
  if (layer instanceof L.CircleMarker || layer instanceof L.Marker) {
    const p = layer.getLatLng();
    return { type: "Point", coordinates: [p.lng, p.lat] };
  }
  if (layer instanceof L.Polygon) {
    const cincin = layer.getLatLngs();
    const luar = Array.isArray(cincin[0]) ? cincin : [cincin];
    return { type: "Polygon", coordinates: luar.map((r) => {
      const pts = r.map((p) => [p.lng, p.lat]);
      return pts.length ? [...pts, pts[0]] : pts;
    }) };
  }
  if (layer instanceof L.Polyline) {
    const pts = layer.getLatLngs();
    const datar = Array.isArray(pts[0]) ? pts.flat() : pts;
    return { type: "LineString", coordinates: datar.map((p) => [p.lng, p.lat]) };
  }
  return null;
}

function elemenLabel(f) {
  const lb = f.label;
  const el = document.createElement("div");
  el.textContent = lb.teks;
  const halo = lb.halo
    ? `-1px -1px 0 ${lb.halo},1px -1px 0 ${lb.halo},-1px 1px 0 ${lb.halo},1px 1px 0 ${lb.halo},0 0 3px ${lb.halo}`
    : "none";
  const jarak = (f.gaya.ukuran || 6) + 4;
  const geser = {
    atas: `translate(-50%, calc(-100% - ${jarak}px))`,
    bawah: `translate(-50%, ${jarak}px)`,
    kanan: `translate(${jarak}px, -50%)`,
    kiri: `translate(calc(-100% - ${jarak}px), -50%)`,
  }[f.tipe === "titik" ? lb.posisi : ""] || "translate(-50%, -50%)";
  el.style.cssText = `position:absolute;left:0;top:0;white-space:nowrap;pointer-events:none;`
    + `font:${lb.tebal ? 700 : 500} ${lb.ukuran}px system-ui,-apple-system,"Segoe UI",sans-serif;`
    + `color:${lb.warna};text-shadow:${halo};transform:${geser};line-height:1.15`;
  return el;
}

/**
 * Pengelola label satu kelompok fitur di satu peta. `renderer` = L.svg milik
 * kelompok (wadah textPath label garis), `paneLabel` = pane label datar.
 */
export function buatLabelPeta(map, { renderer, paneLabel, zoomMin = 0 }) {
  let datar = [];      // L.marker divIcon
  let ikut = [];       // {fitur, path, text}
  let fiturKini = [];

  const tampil = () => map.getZoom() >= zoomMin;

  const susunJalur = () => {
    for (const it of ikut) {
      const pts = it.fitur.geometri.coordinates.map(([lon, lat]) => map.latLngToLayerPoint([lat, lon]));
      it.path.setAttribute("d", jalurLabel(pts, perkiraanPanjangTeks(it.fitur.label.teks, it.fitur.label.ukuran)));
      it.text.style.display = tampil() ? "" : "none";
    }
    for (const m of datar) {
      const el = m.getElement?.();
      if (el) el.style.display = tampil() ? "" : "none";
    }
  };

  const lepas = () => {
    datar.forEach((m) => map.removeLayer(m));
    ikut.forEach((it) => { it.path.remove(); it.text.remove(); });
    datar = []; ikut = [];
  };

  const atur = (fitur) => {
    lepas();
    // Label "ikut garis" ditulis ke <svg> renderer; pastikan renderer sudah
    // ada di peta walau belum ada path yang memakainya.
    if (renderer && !renderer._map) map.addLayer(renderer);
    fiturKini = fitur;
    for (const mentah of fitur) {
      const f = lengkapiFitur(mentah);
      if (!f.label.teks) continue;
      if (f.tipe === "garis" && f.label.posisi === "ikut") {
        const akar = renderer?._rootGroup;
        if (!akar) continue;
        const id = `aman-label-jalur-${++nomorJalur}`;
        const path = document.createElementNS(SVG_NS, "path");
        path.setAttribute("id", id); path.setAttribute("fill", "none"); path.setAttribute("stroke", "none");
        const text = document.createElementNS(SVG_NS, "text");
        text.setAttribute("dy", String(-(f.gaya.tebal / 2 + 3)));
        text.setAttribute("fill", f.label.warna);
        text.setAttribute("font-size", String(f.label.ukuran));
        text.setAttribute("font-weight", f.label.tebal ? "700" : "500");
        text.setAttribute("font-family", "system-ui,-apple-system,'Segoe UI',sans-serif");
        if (f.label.halo) {
          text.setAttribute("stroke", f.label.halo); text.setAttribute("stroke-width", "3");
          text.setAttribute("paint-order", "stroke"); text.setAttribute("stroke-linejoin", "round");
        }
        text.style.pointerEvents = "none";
        const tp = document.createElementNS(SVG_NS, "textPath");
        tp.setAttribute("href", `#${id}`);
        tp.setAttribute("startOffset", "50%");
        tp.setAttribute("text-anchor", "middle");
        tp.textContent = f.label.teks;
        text.appendChild(tp);
        akar.appendChild(path); akar.appendChild(text);
        ikut.push({ fitur: f, path, text });
        continue;
      }
      let titik;
      if (f.tipe === "titik") titik = keLatLng(f.geometri.coordinates);
      else if (f.tipe === "garis") titik = keLatLng(titikTengahGaris(f.geometri.coordinates));
      else titik = keLatLng(titikLabelArea(f.geometri.coordinates[0]));
      const m = L.marker(titik, {
        pane: paneLabel, interactive: false, keyboard: false,
        icon: L.divIcon({ className: "", html: elemenLabel(f), iconSize: [0, 0], iconAnchor: [0, 0] }),
      }).addTo(map);
      datar.push(m);
    }
    susunJalur();
  };

  map.on("zoomend viewreset", susunJalur);
  return {
    atur,
    setZoomMin(z) { zoomMin = z; susunJalur(); },
    segarkan: susunJalur,
    lepas() { lepas(); map.off("zoomend viewreset", susunJalur); },
    get fitur() { return fiturKini; },
  };
}
