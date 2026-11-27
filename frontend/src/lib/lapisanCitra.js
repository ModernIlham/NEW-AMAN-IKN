// Lapisan CITRA EKSISTING — foto udara terbaru yang ditumpuk di atas OSM.
//
// Peta dasar OSM di kawasan yang sedang dibangun tertinggal dari kondisi
// lapangan. Admin mendaftarkan citra (drone/ortofoto) yang sudah dipotong jadi
// ubin XYZ di server; modul ini memasangnya di peta mana pun.
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

// ── Daftar lapisan (sekali per sesi) ────────────────────────────────────────

let janjiDaftar = null;

/** Ambil lapisan aktif. Satu permintaan per sesi; gagal → boleh dicoba ulang. */
export function ambilDaftarCitra({ paksa = false } = {}) {
  if (paksa) janjiDaftar = null;
  if (!janjiDaftar) {
    janjiDaftar = axios.get(`${API}/peta-lapisan`, { timeout: 15000 })
      .then((r) => (Array.isArray(r?.data?.items) ? r.data.items : []).filter(lapisanSah))
      .catch((e) => { janjiDaftar = null; throw e; });
  }
  return janjiDaftar;
}

/** Dipanggil setelah admin mengubah registri, agar peta mengambil versi baru. */
export function lupakanDaftarCitra() { janjiDaftar = null; }

/** Lapisan yang layak dipasang: aktif, beralamat, berbatas & berzoom wajar. */
export function lapisanSah(l) {
  const b = l?.batas;
  return !!(l && l.aktif !== false && typeof l.url_template === "string" && l.url_template
    && b && [b.barat, b.selatan, b.timur, b.utara].every(Number.isFinite)
    && b.barat < b.timur && b.selatan < b.utara
    && Number.isInteger(l.zoom_min) && Number.isInteger(l.zoom_maks) && l.zoom_min <= l.zoom_maks);
}

/** Batas citra → [[selatan, barat], [utara, timur]] (urutan lat,lng Leaflet). */
export function batasLeaflet(l) {
  const b = l.batas;
  return [[b.selatan, b.barat], [b.utara, b.timur]];
}

/** Apakah viewport {barat,selatan,timur,utara} beririsan dengan batas citra. */
export function viewportMengenai(l, v) {
  if (!v || !l?.batas) return false;
  const b = l.batas;
  return !(v.timur < b.barat || v.barat > b.timur || v.utara < b.selatan || v.selatan > b.utara);
}

/** Atribusi yang tampil di sudut peta saat lapisan terpasang. */
export function atribusiCitra(l) {
  const asal = String(l?.sumber || l?.nama || "").replace(/[<>&"]/g, "");
  const tgl = formatTanggalCitra(l?.tanggal_rekam);
  return `Citra eksisting: ${[asal, tgl].filter(Boolean).join(", ")}`;
}

/** Opsi L.tileLayer untuk satu lapisan. */
export function opsiUbinCitra(l, opasitas) {
  return {
    pane: PANE_CITRA,
    bounds: batasLeaflet(l),
    minZoom: l.zoom_min,
    minNativeZoom: l.zoom_min,
    maxNativeZoom: l.zoom_maks,
    maxZoom: ZOOM_MAKS_PETA,
    opacity: opasitas ?? l.opasitas ?? 0.85,
    attribution: atribusiCitra(l),
    // Lapisan yang lebih baru ditumpuk di atas yang lama di wilayah yang sama.
    zIndex: Number(String(l.tanggal_rekam || "").replace(/\D/g, "")) || 1,
  };
}

/** Urutan tampil di panel: terbaru dulu. */
export function urutCitra(daftar) {
  return [...daftar].sort((a, b) => String(b.tanggal_rekam).localeCompare(String(a.tanggal_rekam))
    || String(a.nama).localeCompare(String(b.nama)));
}

// ── Pengelola layer pada satu peta (tanpa React) ────────────────────────────

/**
 * Pengelola lapisan citra untuk satu instance peta.
 * `atur(daftar, {sembunyi, opasitas})` menyamakan layer terpasang dengan
 * keadaan yang diminta; `lepas()` mencabut semuanya.
 */
export function buatPengelolaCitra(map) {
  const layer = new Map(); // id → L.TileLayer   (Map bawaan JS)
  if (!map.getPane(PANE_CITRA)) {
    const p = map.createPane(PANE_CITRA);
    p.style.zIndex = String(PANE_CITRA_Z);
    p.style.pointerEvents = "none"; // citra hanya latar — klik tembus ke peta
  }
  return {
    atur(daftar, { sembunyi = new Set(), opasitas = null } = {}) {
      const mau = new Map(daftar.filter((l) => !sembunyi.has(String(l.id))).map((l) => [String(l.id), l]));
      for (const [id, ly] of layer) {
        if (!mau.has(id)) { map.removeLayer(ly); layer.delete(id); }
      }
      for (const [id, l] of mau) {
        const ada = layer.get(id);
        if (ada) { ada.setOpacity(opasitas ?? l.opasitas ?? 0.85); continue; }
        const ly = L.tileLayer(l.url_template, opsiUbinCitra(l, opasitas)).addTo(map);
        layer.set(id, ly);
      }
    },
    lepas() {
      for (const ly of layer.values()) map.removeLayer(ly);
      layer.clear();
    },
    jumlahTerpasang: () => layer.size,
  };
}

// ── Kontrol ringkas untuk peta selain Peta Aset ─────────────────────────────

const IKON_CITRA = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13 7 9 3 5 7l4 4"/><path d="m17 11 4 4-4 4-4-4"/><path d="m8 12 4 4 6-6-4-4Z"/><path d="m16 8 3-3"/><path d="M9 21a6 6 0 0 0-6-6"/></svg>';

/**
 * Tombol Leaflet "Citra eksisting" (pojok kanan atas) untuk Peta Kolaborasi,
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
    tombol.title = judul || (aktif ? "Sembunyikan citra eksisting" : "Tampilkan citra eksisting");
  };

  const terapkan = async () => {
    if (!aktif) { pengelola.lepas(); segarkanTombol(); return; }
    try {
      const daftar = await ambilDaftarCitra();
      if (!hidup || !aktif) return;
      try { pengelola.atur(daftar, { sembunyi: bacaCitraSembunyi(), opasitas: bacaOpasitasCitra() }); }
      catch { return; /* peta dilepas di tengah jalan */ }
      if (daftar.length === 0) {
        segarkanTombol("Belum ada citra eksisting terdaftar");
        onPesan?.("Belum ada citra eksisting yang didaftarkan admin.");
      } else {
        segarkanTombol(`Citra eksisting tampil (${daftar.length} lapisan)`);
      }
    } catch {
      if (hidup) { segarkanTombol("Daftar citra gagal dimuat"); onPesan?.("Daftar citra eksisting gagal dimuat."); }
    }
  };

  const Kontrol = L.Control.extend({
    onAdd() {
      const wadah = L.DomUtil.create("div", "leaflet-bar");
      const b = L.DomUtil.create("a", "", wadah);
      b.href = "#";
      b.setAttribute("role", "button");
      b.setAttribute("data-testid", "peta-citra-toggle");
      b.setAttribute("aria-label", "Citra eksisting");
      b.innerHTML = IKON_CITRA;
      b.style.cssText = "display:flex;align-items:center;justify-content:center";
      L.DomEvent.disableClickPropagation(wadah);
      L.DomEvent.on(b, "click", (e) => {
        L.DomEvent.preventDefault(e);
        aktif = !aktif;
        simpanCitraAktif(aktif);
        segarkanTombol(aktif ? "Memuat citra eksisting…" : undefined);
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

// ── Pemeriksaan ubin (dialog admin) ─────────────────────────────────────────

/** Koordinat ubin XYZ (skema Google/OSM) yang memuat titik lon/lat pada zoom z. */
export function ubinUntukTitik(lon, lat, z) {
  const n = 2 ** z;
  const latRad = (Math.max(-85.0511, Math.min(85.0511, lat)) * Math.PI) / 180;
  const x = Math.floor(((lon + 180) / 360) * n);
  const y = Math.floor(((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n);
  return { z, x: Math.min(n - 1, Math.max(0, x)), y: Math.min(n - 1, Math.max(0, y)) };
}

/** Isi {z}/{x}/{y} (dan {s} → "a") pada alamat ubin. */
export function isiAlamatUbin(template, { z, x, y }) {
  return String(template).replace(/\{z\}/g, z).replace(/\{x\}/g, x).replace(/\{y\}/g, y).replace(/\{s\}/g, "a");
}

/**
 * Periksa satu ubin di TENGAH batas citra pada zoom maksimum. Hanya untuk
 * alamat lokal ("/…"): alamat luar umumnya terhalang CORS untuk dibaca.
 * Mengembalikan {status: "ok"|"html"|"hilang"|"galat"|"luar", url, pesan}.
 *
 * "html" adalah jebakan utama: tanpa blok nginx yang benar, jalur yang tak
 * ada jatuh ke fallback SPA dan dijawab index.html berstatus 200 — terlihat
 * "berhasil" padahal tak satu ubin pun tersaji.
 */
export async function periksaUbinCitra(l, { fetchFn = typeof fetch === "function" ? fetch : null } = {}) {
  const b = l.batas;
  const t = ubinUntukTitik((b.barat + b.timur) / 2, (b.selatan + b.utara) / 2, l.zoom_maks);
  const url = isiAlamatUbin(l.url_template, t);
  if (!String(l.url_template).startsWith("/")) {
    return { status: "luar", url, pesan: "Alamat di luar server ini — buka tautan contoh untuk memeriksa." };
  }
  if (!fetchFn) return { status: "galat", url, pesan: "Peramban tidak mendukung pemeriksaan." };
  try {
    const r = await fetchFn(url, { method: "GET", cache: "no-store", credentials: "same-origin" });
    const jenis = String(r.headers?.get?.("content-type") || "").toLowerCase();
    if (r.status === 404) return { status: "hilang", url, pesan: "Ubin contoh tidak ditemukan (404). Periksa folder ubin dan alamatnya." };
    if (!r.ok) return { status: "galat", url, pesan: `Server menjawab ${r.status}.` };
    if (jenis.includes("text/html")) {
      return { status: "html", url, pesan: "Server menjawab halaman web, bukan gambar — jalur ubin belum disajikan nginx." };
    }
    if (!jenis.startsWith("image/")) return { status: "galat", url, pesan: `Jenis berkas tak dikenal: ${jenis || "kosong"}.` };
    return { status: "ok", url, pesan: "Ubin contoh tersaji dengan benar." };
  } catch {
    return { status: "galat", url, pesan: "Ubin contoh gagal diambil (jaringan)." };
  }
}
