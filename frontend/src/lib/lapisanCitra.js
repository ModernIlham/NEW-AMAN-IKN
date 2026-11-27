// Lapisan EKSISTING — foto udara terbaru (citra) dan gambar titik/garis/area
// yang ditumpuk di atas OSM.
//
// Peta dasar OSM di kawasan yang sedang dibangun tertinggal dari kondisi
// lapangan. Admin mengunggah citra (dipotong jadi ubin di peramban) dan
// menggambar jalan/bangunan baru; modul ini memasangnya di peta mana pun.
//
// Aturan performa yang dijaga di sini:
//   • MATI = nol permintaan. Daftar lapisan baru diambil saat pertama kali
//     dinyalakan, lalu disimpan di memori modul selama sesi.
//   • Ubin hanya diminta di DALAM batas wilayah & rentang zoom citra (opsi
//     `bounds`/`minZoom`/`maxNativeZoom`) — di luar itu Leaflet tak meminta
//     apa pun, jadi geser peta di luar area tak menghasilkan ratusan 404.
//   • Pane sendiri (z 250): di atas OSM (tilePane 200), di bawah denah (380),
//     overlay (400), dan pin aset (600) — pin tetap di atas dan tetap diklik.
import L from "leaflet";
import axios from "axios";
import { ZOOM_MAKS_PETA } from "./petaDasar";
import { batasFitur, buatLabelPeta, buatLayerFitur } from "./gambarPeta";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const KUNCI_CITRA_AKTIF = "aman_map_citra";
export const KUNCI_CITRA_OPASITAS = "aman_map_citra_opasitas";
export const KUNCI_CITRA_SEMBUNYI = "aman_map_citra_sembunyi";
export const PANE_CITRA = "citraEksisting";
export const PANE_CITRA_Z = 250;

const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

/** "2026-10-15" → "15 Okt 2026"; teks lain dikembalikan apa adanya. */
export function formatTanggalCitra(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ""));
  if (!m) return String(iso || "");
  const b = Number(m[2]);
  if (b < 1 || b > 12) return String(iso);
  return `${Number(m[3])} ${BULAN[b - 1]} ${m[1]}`;
}

// ── Preferensi per perangkat (semua akses storage dibungkus try/catch) ──────

export function bacaCitraAktif() {
  try { return localStorage.getItem(KUNCI_CITRA_AKTIF) === "1"; } catch { return false; }
}
export function simpanCitraAktif(aktif) {
  try { localStorage.setItem(KUNCI_CITRA_AKTIF, aktif ? "1" : "0"); } catch { /* storage diblokir */ }
}
/** Opasitas pilihan pengguna (0,1–1) atau null = pakai bawaan tiap lapisan. */
export function bacaOpasitasCitra() {
  try {
    const n = Number(localStorage.getItem(KUNCI_CITRA_OPASITAS));
    return Number.isFinite(n) && n >= 0.1 && n <= 1 ? n : null;
  } catch { return null; }
}
export function simpanOpasitasCitra(n) {
  try { localStorage.setItem(KUNCI_CITRA_OPASITAS, String(n)); } catch { /* storage diblokir */ }
}
export function bacaCitraSembunyi() {
  try {
    const a = JSON.parse(localStorage.getItem(KUNCI_CITRA_SEMBUNYI) || "[]");
    return new Set(Array.isArray(a) ? a.map(String) : []);
  } catch { return new Set(); }
}
export function simpanCitraSembunyi(set) {
  try { localStorage.setItem(KUNCI_CITRA_SEMBUNYI, JSON.stringify([...set])); } catch { /* storage diblokir */ }
}

// ── Daftar lapisan ──────────────────────────────────────────────────────────

let janjiDaftar = null;
let waktuAmbil = 0;
// Token ubin berganti harian (server menerima hingga sehari sesudahnya), jadi
// daftar diambil ulang bila sudah berumur > 6 jam — tab yang dibiarkan terbuka
// berhari-hari tak berakhir dengan ubin 403.
const UMUR_DAFTAR_MS = 6 * 3600 * 1000;

/** URL template ubin citra (token dari daftar lapisan). */
export function urlUbin(l, token) {
  const t = encodeURIComponent(token || "");
  return `${API}/peta-lapisan/${l.id}/ubin/{z}/{x}/{y}.${l.format}?t=${t}`;
}

/** Ambil lapisan aktif (citra + gambar), urut bawah → atas. */
export function ambilDaftarCitra({ paksa = false } = {}) {
  if (paksa || (janjiDaftar && Date.now() - waktuAmbil > UMUR_DAFTAR_MS)) janjiDaftar = null;
  if (!janjiDaftar) {
    waktuAmbil = Date.now();
    janjiDaftar = axios.get(`${API}/peta-lapisan`, { timeout: 15000 })
      .then((r) => {
        const token = r?.data?.ubin_token || "";
        const items = Array.isArray(r?.data?.items) ? r.data.items : [];
        return items.filter(lapisanSah)
          .map((l) => (l.jenis === "citra" ? { ...l, url_template: urlUbin(l, token) } : l));
      })
      .catch((e) => { janjiDaftar = null; throw e; });
  }
  return janjiDaftar;
}

/** Dipanggil setelah admin mengubah registri, agar peta mengambil versi baru. */
export function lupakanDaftarCitra() { janjiDaftar = null; }

/** Lapisan yang layak dipasang. */
export function lapisanSah(l) {
  if (!l || l.aktif === false) return false;
  if (l.jenis === "gambar") return Array.isArray(l.fitur);
  const b = l.batas;
  return !!(l.jenis === "citra" && l.status !== "memproses" && l.format
    && b && [b.barat, b.selatan, b.timur, b.utara].every(Number.isFinite)
    && b.barat < b.timur && b.selatan < b.utara
    && Number.isInteger(l.zoom_min) && Number.isInteger(l.zoom_maks) && l.zoom_min <= l.zoom_maks);
}

/** Batas lapisan → [[selatan, barat], [utara, timur]] (urutan lat,lng Leaflet). */
export function batasLeaflet(l) {
  if (l.jenis === "gambar") return batasFitur(l.fitur);
  const b = l.batas;
  return [[b.selatan, b.barat], [b.utara, b.timur]];
}

/** Apakah viewport {barat,selatan,timur,utara} beririsan dengan lapisan. */
export function viewportMengenai(l, v) {
  const bl = l ? batasLeaflet(l) : null;
  if (!v || !bl) return false;
  const [[s, w], [n, e]] = bl;
  return !(v.timur < w || v.barat > e || v.utara < s || v.selatan > n);
}

/** Atribusi yang tampil di sudut peta saat lapisan terpasang. */
export function atribusiCitra(l) {
  const asal = String(l?.sumber || l?.nama || "").replace(/[<>&"]/g, "");
  const tgl = formatTanggalCitra(l?.tanggal_rekam);
  return `Citra eksisting: ${[asal, tgl].filter(Boolean).join(", ")}`;
}

/** Opsi L.tileLayer untuk satu lapisan citra. */
export function opsiUbinCitra(l, opasitas) {
  return {
    pane: PANE_CITRA,
    bounds: batasLeaflet(l),
    // Di bawah zoom terendah ubin, Leaflet memakai ubin zoom terendah yang
    // diperkecil (minNativeZoom) — jumlah ubinnya tetap sama sedikitnya.
    minZoom: Math.max(0, l.zoom_min - 5),
    minNativeZoom: l.zoom_min,
    maxNativeZoom: l.zoom_maks,
    maxZoom: ZOOM_MAKS_PETA,
    opacity: opasitas ?? l.opasitas ?? 1,
    attribution: atribusiCitra(l),
    zIndex: Number(l.urutan) || 1,   // urutan dari admin: makin besar makin atas
  };
}

/** Urutan tampil di panel: paling ATAS dulu (gambar di atas citra). */
export function urutCitra(daftar) {
  const nilai = (l) => (l.jenis === "gambar" ? 100000 : 0) + (Number(l.urutan) || 0);
  return [...daftar].sort((a, b) => nilai(b) - nilai(a));
}

// ── Pengelola layer pada satu peta (tanpa React) ────────────────────────────

export const PANE_GAMBAR = "gambarEksisting";
export const PANE_GAMBAR_Z = 390;     // di atas denah (380), di bawah overlay (400) & pin (600)
export const PANE_LABEL = "labelEksisting";
export const PANE_LABEL_Z = 395;

function siapkanPane(map, nama, z) {
  if (!map.getPane(nama)) {
    const p = map.createPane(nama);
    p.style.zIndex = String(z);
    p.style.pointerEvents = "none"; // lapisan eksisting hanya latar — klik tembus
  }
}

/**
 * Pengelola lapisan eksisting untuk satu instance peta.
 * `atur(daftar, {sembunyi, opasitas})` menyamakan layer terpasang dengan
 * keadaan yang diminta (opasitas = pilihan pengguna untuk CITRA); `lepas()`
 * mencabut semuanya.
 */
export function buatPengelolaCitra(map) {
  const layer = new Map(); // id → {jenis, ly, label?, versi}   (Map bawaan JS)
  siapkanPane(map, PANE_CITRA, PANE_CITRA_Z);
  siapkanPane(map, PANE_GAMBAR, PANE_GAMBAR_Z);
  siapkanPane(map, PANE_LABEL, PANE_LABEL_Z);
  const lepasSatu = (id) => {
    const it = layer.get(id);
    if (!it) return;
    try { it.label?.lepas(); } catch { /* peta dilepas */ }
    map.removeLayer(it.ly);
    layer.delete(id);
  };
  return {
    atur(daftar, { sembunyi = new Set(), opasitas = null } = {}) {
      const mau = new Map(daftar.filter((l) => !sembunyi.has(String(l.id))).map((l) => [String(l.id), l]));
      for (const id of [...layer.keys()]) {
        const l = mau.get(id);
        if (!l || l.version !== layer.get(id).versi) lepasSatu(id);
      }
      for (const [id, l] of mau) {
        const ada = layer.get(id);
        if (l.jenis === "citra") {
          if (ada) { ada.ly.setOpacity(opasitas ?? l.opasitas ?? 1); ada.ly.setZIndex(Number(l.urutan) || 1); continue; }
          layer.set(id, { jenis: "citra", versi: l.version, ly: L.tileLayer(l.url_template, opsiUbinCitra(l, opasitas)).addTo(map) });
        } else if (!ada) {
          const renderer = L.svg({ pane: PANE_GAMBAR, padding: 0.3 });
          const grup = L.featureGroup(l.fitur.map((f) => buatLayerFitur(f, { renderer, pane: PANE_GAMBAR }))).addTo(map);
          const label = buatLabelPeta(map, { renderer, paneLabel: PANE_LABEL, zoomMin: l.label_zoom_min ?? 15 });
          label.atur(l.fitur);
          layer.set(id, { jenis: "gambar", versi: l.version, ly: grup, label, urutan: Number(l.urutan) || 0 });
        }
      }
      // Urutan tumpukan gambar: bawah → atas sesuai `urutan` admin.
      [...layer.values()].filter((it) => it.jenis === "gambar")
        .sort((a, b) => a.urutan - b.urutan)
        .forEach((it) => { try { it.ly.bringToFront(); } catch { /* belum dirender */ } });
    },
    lepas() {
      for (const id of [...layer.keys()]) lepasSatu(id);
    },
    jumlahTerpasang: () => layer.size,
  };
}

// ── Kontrol ringkas untuk peta selain Peta Aset ─────────────────────────────

const IKON_CITRA = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13 7 9 3 5 7l4 4"/><path d="m17 11 4 4-4 4-4-4"/><path d="m8 12 4 4 6-6-4-4Z"/><path d="m16 8 3-3"/><path d="M9 21a6 6 0 0 0-6-6"/></svg>';

/**
 * Tombol Leaflet "Lapisan eksisting" (pojok kanan atas) untuk Peta Kolaborasi,
 * Editor Denah, dan Lokasi Temuan. Berbagi preferensi dengan tombol di Peta
 * Aset. Opasitas & pilihan per lapisan diatur dari Peta Aset.
 * Kembalikan fungsi pembersih.
 */
export function pasangKontrolCitra(map, { posisi = "topright", onPesan } = {}) {
  const pengelola = buatPengelolaCitra(map);
  let aktif = bacaCitraAktif();
  let tombol = null;
  let hidup = true;

  const segarkanTombol = (judul) => {
    if (!tombol) return;
    tombol.setAttribute("aria-pressed", aktif ? "true" : "false");
    tombol.style.color = aktif ? "#b45309" : "#334155";
    tombol.style.background = aktif ? "#fef3c7" : "#fff";
    tombol.title = judul || (aktif ? "Sembunyikan lapisan eksisting" : "Tampilkan lapisan eksisting");
  };

  const terapkan = async () => {
    if (!aktif) { pengelola.lepas(); segarkanTombol(); return; }
    try {
      const daftar = await ambilDaftarCitra();
      if (!hidup || !aktif) return;
      try { pengelola.atur(daftar, { sembunyi: bacaCitraSembunyi(), opasitas: bacaOpasitasCitra() }); }
      catch { return; /* peta dilepas di tengah jalan */ }
      if (daftar.length === 0) {
        segarkanTombol("Belum ada lapisan eksisting");
        onPesan?.("Belum ada lapisan eksisting.");
      } else {
        segarkanTombol(`Lapisan eksisting tampil (${daftar.length})`);
      }
    } catch {
      if (hidup) { segarkanTombol("Lapisan eksisting gagal dimuat"); onPesan?.("Lapisan eksisting gagal dimuat."); }
    }
  };

  const Kontrol = L.Control.extend({
    onAdd() {
      const wadah = L.DomUtil.create("div", "leaflet-bar");
      const b = L.DomUtil.create("a", "", wadah);
      b.href = "#";
      b.setAttribute("role", "button");
      b.setAttribute("data-testid", "peta-citra-toggle");
      b.setAttribute("aria-label", "Lapisan eksisting");
      b.innerHTML = IKON_CITRA;
      b.style.cssText = "display:flex;align-items:center;justify-content:center";
      L.DomEvent.disableClickPropagation(wadah);
      L.DomEvent.on(b, "click", (e) => {
        L.DomEvent.preventDefault(e);
        aktif = !aktif;
        simpanCitraAktif(aktif);
        segarkanTombol(aktif ? "Memuat lapisan eksisting…" : undefined);
        terapkan();
      });
      tombol = b;
      segarkanTombol();
      return wadah;
    },
  });
  const kontrol = new Kontrol({ position: posisi }).addTo(map);
  // Peta dihancurkan (map.remove) tanpa memanggil pembersih → jangan sentuh lagi.
  map.on("unload", () => { hidup = false; });
  if (aktif) terapkan();

  return () => {
    hidup = false;
    try { pengelola.lepas(); } catch { /* peta sudah dilepas */ }
    try { kontrol.remove(); } catch { /* peta sudah dilepas */ }
  };
}
