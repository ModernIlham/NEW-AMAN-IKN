import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
// Clustering marker berdekatan — sama seperti Peta Aset (AssetMapFullView).
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import axios from "axios";
import { toast } from "sonner";
import {
  MapPin, MessageSquarePlus, Plus, X, Loader2, Send, Users, Clock,
  AlertTriangle, RefreshCcw, WifiOff, Layers, Boxes, Trash2, ShieldCheck,
  Eraser, MousePointerClick, MessageSquare, ChevronLeft, ChevronRight, ImageIcon,
} from "lucide-react";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Warna pin per status inventarisasi — SAMA dengan Peta Aset agar konsisten.
const STATUS_COLORS = {
  "Ditemukan": "#2563eb",
  "Tidak Ditemukan": "#dc2626",
  "Berlebih": "#d97706",
  "Sengketa": "#7c3aed",
  "Belum Diinventarisasi": "#64748b",
};
const STATUS_DEFAULT = "#64748b";
const CONDITION_COLORS = { "Baik": "#059669", "Rusak Ringan": "#d97706", "Rusak Berat": "#dc2626" };
const COLLAB_COLOR = "#0d9488"; // teal — titik kolaborasi (dibedakan dari aset)

// Pin teardrop berwarna via divIcon — gaya sama dengan Peta Aset; cincin oranye
// saat terpilih, lencana angka bila punya komentar.
function pinIcon(color, { selected = false, badge = 0 } = {}) {
  const border = selected ? "2.5px solid #fff" : "2px solid #fff";
  const ring = selected
    ? "box-shadow:0 0 0 3px #f59e0b,0 0 0 6px rgba(245,158,11,.35),0 1px 5px rgba(0,0,0,.5)"
    : "box-shadow:0 1px 4px rgba(0,0,0,.45)";
  const badgeHtml = badge > 0
    ? `<div style="position:absolute;top:-7px;right:-7px;min-width:15px;height:15px;padding:0 3px;border-radius:999px;background:#0f172a;border:1.5px solid #fff;display:flex;align-items:center;justify-content:center;font:700 8.5px system-ui,sans-serif;color:#fff">${badge > 9 ? "9+" : badge}</div>`
    : "";
  return L.divIcon({
    className: "",
    html: `<div style="position:relative;width:22px;height:22px">
      <div style="width:22px;height:22px;border-radius:50% 50% 50% 0;background:${color};transform:rotate(-45deg);border:${border};${ring}"></div>${badgeHtml}
    </div>`,
    iconSize: [22, 22], iconAnchor: [11, 22], popupAnchor: [0, -20],
  });
}

// DESIGN MARKER KEDUA (opsional, via toggle): sampul foto aset DI DALAM marker
// agar langsung terlihat apa fotonya. coverSrc dibangun pemanggil (URL foto
// ber-token). Klik marker TETAP membuka popup info yang SAMA. Aset tanpa foto
// tetap pakai pin (ditangani buildIcon di komponen). Border/cincin ikut seleksi.
function photoMarkerIconKolab(coverSrc, { color, selected = false, badge = 0 } = {}) {
  // Sampul dimuat via <img loading="lazy"> (BUKAN background-image) → browser
  // MENUNDA fetch untuk marker di luar viewport (teruji real-Leaflet: marker
  // jauh tak menembak request sampai digeser masuk) → batasi request/memori
  // sampul meski clustering dimatikan. onerror → sembunyikan img sehingga warna
  // latar tampil (degradasi anggun). src di-escape sebagai atribut HTML.
  const src = String(coverSrc || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
  const imgHtml = coverSrc
    ? `<img src="${src}" loading="lazy" decoding="async" alt="" onerror="this.style.display='none'" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"/>`
    : "";
  const bc = selected ? "#f59e0b" : "#ffffff";
  const ring = selected
    ? "box-shadow:0 0 0 3px #f59e0b,0 0 0 6px rgba(245,158,11,.35),0 2px 6px rgba(0,0,0,.5)"
    : "box-shadow:0 2px 6px rgba(0,0,0,.5)";
  const badgeHtml = badge > 0
    ? `<div style="position:absolute;top:-6px;right:-6px;min-width:15px;height:15px;padding:0 3px;border-radius:999px;background:#0f172a;border:1.5px solid #fff;display:flex;align-items:center;justify-content:center;font:700 8.5px system-ui,sans-serif;color:#fff">${badge > 9 ? "9+" : badge}</div>`
    : "";
  return L.divIcon({
    className: "",
    html: `<div style="position:relative;width:46px;height:54px">
      <div style="position:relative;width:46px;height:46px;border-radius:12px;overflow:hidden;border:3px solid ${bc};${ring};background-color:${color}">${imgHtml}</div>
      <div style="position:absolute;left:50%;top:43px;transform:translateX(-50%);width:0;height:0;border-left:7px solid transparent;border-right:7px solid transparent;border-top:9px solid ${bc}"></div>
      ${badgeHtml}
    </div>`,
    iconSize: [46, 54], iconAnchor: [23, 54], popupAnchor: [0, -50],
  });
}

// Marker pratinjau (sebelum disimpan) — pin emerald berdenyut + lingkaran halo.
function previewIcon() {
  return L.divIcon({
    className: "",
    html: `<div style="position:relative;width:30px;height:30px">
      <div style="position:absolute;inset:0;border-radius:50%;background:rgba(5,150,105,.22)"></div>
      <div style="position:absolute;left:8px;top:5px;width:16px;height:16px;border-radius:50% 50% 50% 0;background:#059669;transform:rotate(-45deg);border:2.5px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.5)"></div>
    </div>`,
    iconSize: [30, 30], iconAnchor: [15, 25],
  });
}

function buildCluster() {
  return L.markerClusterGroup({
    maxClusterRadius: 44, spiderfyOnMaxZoom: true, showCoverageOnHover: false,
    zoomToBoundsOnClick: true, removeOutsideVisibleBounds: true, chunkedLoading: true,
    iconCreateFunction: (cluster) => {
      const n = cluster.getChildCount();
      const size = n < 10 ? 34 : n < 100 ? 40 : 46;
      return L.divIcon({
        html: `<div style="width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center;`
          + `border-radius:9999px;background:rgba(37,99,235,.92);color:#fff;font:700 12px system-ui,sans-serif;`
          + `border:2px solid #fff;box-shadow:0 1px 4px rgba(15,23,42,.4)">${n}</div>`,
        className: "", iconSize: [size, size],
      });
    },
  });
}

function fmtWaktu(iso) {
  try {
    return new Date(iso).toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch { return "-"; }
}

// Sisa masa tayang → teks singkat ("2 hari 3 jam" / "Berakhir").
function sisaTayang(iso) {
  if (!iso) return "";
  const ms = new Date(iso).getTime() - Date.now();
  if (isNaN(ms)) return "";
  if (ms <= 0) return "Masa tayang berakhir";
  const jam = Math.floor(ms / 3600000);
  const hari = Math.floor(jam / 24);
  if (hari >= 1) return `Sisa ${hari} hari ${jam % 24} jam`;
  if (jam >= 1) return `Sisa ${jam} jam`;
  return `Sisa ${Math.max(1, Math.floor(ms / 60000))} menit`;
}

const apiErr = (e, fb) => e?.response?.data?.detail || fb;

/**
 * Muat foto lewat axios→blob agar membawa Bearer (operator, termasuk saat share
 * KEDALUWARSA) MAUPUN ?token= (tamu) — <img src> biasa hanya bisa kirim token,
 * sehingga operator gagal memuat foto arsip pasca-kedaluwarsa. Object URL
 * dibebaskan saat lepas untuk cegah bocor memori.
 */
function FotoImg({ url, alt = "", className = "", spinner = false, ...rest }) {
  const [src, setSrc] = useState(null);
  const [gagal, setGagal] = useState(false);
  useEffect(() => {
    let alive = true;
    let obj = null;
    setSrc(null); setGagal(false);
    axios.get(url, { responseType: "blob", timeout: 25000 })
      .then((r) => { if (alive) { obj = URL.createObjectURL(r.data); setSrc(obj); } })
      .catch(() => { if (alive) setGagal(true); });
    return () => { alive = false; if (obj) URL.revokeObjectURL(obj); };
  }, [url]);
  if (src) return <img src={src} alt={alt} className={className} {...rest} />;
  if (gagal) {
    return spinner
      ? <div className="text-white/60 text-sm p-8" {...rest}>Gagal memuat foto</div>
      : <div className={`${className} bg-muted`} {...rest} />;
  }
  return spinner
    ? <div className="flex items-center justify-center p-8" {...rest}><Loader2 className="w-8 h-8 animate-spin text-white/70" /></div>
    : <div className={`${className} bg-muted animate-pulse`} {...rest} />;
}

/**
 * Halaman PUBLIK peta kolaboratif (link ber-token). Paritas fitur dengan Peta
 * Aset: pin berwarna per status, clustering, filter status + Barang Serupa,
 * info titik lengkap, tambah titik ber-marker pratinjau, komentar per titik,
 * kontrol skala/utara/lokasi, dan moderasi untuk operator/admin satker.
 */
export default function PetaKolaborasiPage() {
  const { id, token } = useMemo(() => {
    const m = window.location.pathname.match(/^\/peta\/kolaborasi\/([\w-]+)/);
    const t = new URLSearchParams(window.location.search).get("token") || "";
    return { id: m ? m[1] : "", token: t };
  }, []);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // `menyegarkan` SENGAJA dipisah dari `loading`. `loading` mengganti SELURUH
  // pohon dengan layar pemuat — termasuk <div ref={mapElRef}> tempat Leaflet
  // hidup. Dulu tombol "Muat ulang" memakai `loading`, sehingga wadah peta
  // dilepas, lalu wadah BARU dipasang saat selesai — sementara `mapRef.current`
  // masih memegang peta lama yang terikat node yang sudah dibuang. Efek init
  // pun `return` lebih awal (mapRef sudah terisi) dan wadah baru tinggal kotak
  // PUTIH. Muat ulang kini tak pernah melepas peta.
  const [menyegarkan, setMenyegarkan] = useState(false);
  const [galat, setGalat] = useState("");
  const [koneksi, setKoneksi] = useState(false);
  const [nama, setNama] = useState(() => { try { return localStorage.getItem("peta_nama") || ""; } catch { return ""; } });
  const [namaDialog, setNamaDialog] = useState(false);
  const [namaDraf, setNamaDraf] = useState("");
  const aksiSetelahNama = useRef(null);

  const [dipilih, setDipilih] = useState(null); // {jenis:'aset'|'titik', id, ...info}
  const [modeTambah, setModeTambah] = useState(false);
  const [formTitik, setFormTitik] = useState(null); // {lat,lng,nama_titik,keterangan}
  const [komentarTeks, setKomentarTeks] = useState("");
  const [kirim, setKirim] = useState(false);
  const [fotoView, setFotoView] = useState(null); // {assetId, jumlah, index} — tampilan foto layar penuh

  // Toolbar (paritas Peta Aset)
  const [statusFilter, setStatusFilter] = useState("__semua__");
  const [groupKey, setGroupKey] = useState("__semua__");
  const [clusterOn, setClusterOn] = useState(true);
  // Gaya marker: "pin" (design 1, bawaan) ↔ "photo" (design 2, sampul foto).
  const [markerStyle, setMarkerStyle] = useState(() => {
    try { return localStorage.getItem("aman_petakolab_marker_style") === "photo" ? "photo" : "pin"; }
    catch { return "pin"; }
  });
  const [moderasi, setModerasi] = useState(false);       // mode seleksi (operator)
  const [terpilih, setTerpilih] = useState(() => new Set()); // id titik kolaborasi terpilih

  const mapElRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const markersRef = useRef(new Map());   // "aset:id"|"titik:id" -> { marker, point, iconKey, color, badge, selected }
  const previewRef = useRef(null);
  const fitOnceRef = useRef(false);
  const scaleElRef = useRef(null);
  const modeTambahRef = useRef(false);
  const dipilihRef = useRef(null);
  const terpilihRef = useRef(terpilih);
  const moderasiRef = useRef(false);
  const clusterOnRef = useRef(true);
  const bolehModerasiRef = useRef(false);
  const roRef = useRef(null);
  useEffect(() => { modeTambahRef.current = modeTambah; }, [modeTambah]);
  useEffect(() => { dipilihRef.current = dipilih; }, [dipilih]);
  useEffect(() => { terpilihRef.current = terpilih; }, [terpilih]);
  useEffect(() => { moderasiRef.current = moderasi; }, [moderasi]);
  useEffect(() => { bolehModerasiRef.current = !!data?.boleh_moderasi; }, [data]);

  const muat = useCallback(async () => {
    if (!id) { setGalat("Link peta tidak lengkap."); setLoading(false); return; }
    try {
      const r = await axios.get(`${API}/peta/kolaborasi/${id}`, { params: { token }, timeout: 20000 });
      setData(r.data); setGalat(""); setKoneksi(false);
    } catch (e) {
      if (!e?.response) setKoneksi(true);
      else setGalat(e.response?.data?.detail || "Link tidak valid atau masa tayang telah berakhir.");
    } finally { setLoading(false); setMenyegarkan(false); }
  }, [id, token]);

  useEffect(() => { muat(); }, [muat]);

  const bolehModerasi = !!data?.boleh_moderasi;

  // Hitung komentar per target (lencana angka pada pin).
  const komentarCount = useMemo(() => {
    const m = {};
    (data?.komentar || []).forEach((k) => {
      const key = `${k.target_jenis}:${k.target_id}`;
      m[key] = (m[key] || 0) + 1;
    });
    return m;
  }, [data]);

  // Kelompok Barang Serupa (kode+nama, ≥2 unit) — dari titik aset.
  const groups = useMemo(() => {
    const byKey = new Map();
    (data?.titik_aset || []).forEach((a) => {
      const key = `${a.kode || ""}||${a.nama || ""}`;
      const g = byKey.get(key) || { key, code: a.kode || "-", name: a.nama || "-", count: 0 };
      g.count += 1; byKey.set(key, g);
    });
    return Array.from(byKey.values()).filter((g) => g.count >= 2).sort((a, b) => b.count - a.count);
  }, [data]);

  const statuses = useMemo(() => {
    const s = new Set();
    (data?.titik_aset || []).forEach((a) => { if (a.status) s.add(a.status); });
    return Array.from(s);
  }, [data]);

  // Titik aset setelah filter status + kelompok.
  const asetTampil = useMemo(() => {
    let base = data?.titik_aset || [];
    if (statusFilter !== "__semua__") base = base.filter((a) => (a.status || "Belum Diinventarisasi") === statusFilter);
    if (groupKey !== "__semua__") base = base.filter((a) => `${a.kode || ""}||${a.nama || ""}` === groupKey);
    return base;
  }, [data, statusFilter, groupKey]);

  const bukaDetailAset = useCallback((a) => setDipilih({
    jenis: "aset", id: a.id, kode: a.kode, nup: a.nup, nama: a.nama,
    kategori: a.kategori, status: a.status, kondisi: a.kondisi,
    merk: a.merk, tipe: a.tipe, lokasi: a.lokasi,
    jumlah_foto: a.jumlah_foto || 0,
  }), []);
  const bukaDetailTitik = useCallback((t) => setDipilih({
    jenis: "titik", id: t.id, nama_titik: t.nama_titik, keterangan: t.keterangan,
    oleh: t.oleh, created_at: t.created_at,
  }), []);

  const toggleTerpilih = useCallback((tid) => {
    setTerpilih((prev) => {
      const n = new Set(prev);
      if (n.has(tid)) n.delete(tid); else n.add(tid);
      return n;
    });
  }, []);

  // ── Inisialisasi peta SEKALI (tidak dibangun ulang saat data berubah) +
  //    kontrol skala/utara/lokasi. Peta dibuat saat container mount & data
  //    pertama ada; DIHANCURKAN hanya saat unmount (efek terpisah di bawah). ──
  useEffect(() => {
    // Peta yang WADAHNYA sudah lepas dari dokumen tak bisa dipakai lagi: Leaflet
    // masih memegang node lama, sedangkan React sudah memasang node baru. Ini
    // terjadi setiap kali pohon sempat diganti layar penuh (galat/koneksi lalu
    // "Coba lagi"). Tanpa pembongkaran ini, cabang `mapRef.current` di bawah
    // memulangkan efek lebih awal dan wadah baru tinggal kotak putih.
    const lama = mapRef.current;
    if (lama && typeof lama.getContainer === "function" && !document.body.contains(lama.getContainer())) {
      try { roRef.current?.disconnect(); } catch { /* noop */ }
      try { lama.remove(); } catch { /* noop */ }
      roRef.current = null; mapRef.current = null; layerRef.current = null;
      markersRef.current = new Map(); previewRef.current = null;
      fitOnceRef.current = false;
    }
    if (!data || mapRef.current || !mapElRef.current) return;
    const map = L.map(mapElRef.current, { zoomControl: true, attributionControl: true, maxZoom: 22, tapHold: true });
    map.attributionControl.setPrefix(false); // prefiks "Leaflet" opsional; © OpenStreetMap tetap (wajib lisensi)
    map.setView([-1.4, 116.7], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 22, maxNativeZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    L.control.scale({ metric: true, imperial: false, maxWidth: 140, position: "bottomleft" }).addTo(map);

    // Kompas utara (top-right, tak menutup info).
    const NorthControl = L.Control.extend({
      onAdd() {
        const d = L.DomUtil.create("div", "leaflet-bar");
        d.style.cssText = "background:#fff;width:32px;height:38px;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:default";
        d.title = "Arah utara — peta selalu menghadap utara";
        d.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 L6 20 L12 16 L18 20 Z" fill="#dc2626"/><path d="M12 16 L12 3" stroke="#0f172a" stroke-width="1.5"/></svg><span style="font-size:9px;font-weight:800;color:#0f172a;line-height:1;margin-top:1px">U</span>';
        L.DomEvent.disableClickPropagation(d);
        return d;
      },
    });
    new NorthControl({ position: "topright" }).addTo(map);

    // Lokasi saya (di bawah kontrol zoom, top-left).
    const lok = { marker: null, lingkaran: null, tombol: null, mencari: false };
    const hapusLok = () => {
      if (lok.marker) { map.removeLayer(lok.marker); lok.marker = null; }
      if (lok.lingkaran) { map.removeLayer(lok.lingkaran); lok.lingkaran = null; }
    };
    const LokasiControl = L.Control.extend({
      onAdd() {
        const d = L.DomUtil.create("div", "leaflet-bar");
        const a = L.DomUtil.create("a", "", d);
        a.href = "#"; a.title = "Tampilkan lokasi Anda"; a.setAttribute("role", "button");
        a.setAttribute("aria-label", "Tampilkan lokasi Anda");
        a.style.cssText = "display:flex;align-items:center;justify-content:center;width:30px;height:30px";
        a.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#0f172a" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><circle cx="12" cy="12" r="8"/></svg>';
        lok.tombol = a;
        L.DomEvent.disableClickPropagation(d);
        L.DomEvent.on(a, "click", (e) => {
          L.DomEvent.preventDefault(e);
          if (lok.mencari) return;
          if (lok.marker) { hapusLok(); return; }
          lok.mencari = true; a.style.opacity = "0.4";
          map.locate({ setView: false, enableHighAccuracy: true, timeout: 15000 });
        });
        return d;
      },
    });
    new LokasiControl({ position: "topleft" }).addTo(map);
    map.on("locationfound", (ev) => {
      lok.mencari = false; if (lok.tombol) lok.tombol.style.opacity = "1";
      hapusLok();
      const akurasi = Math.round(ev.accuracy || 0);
      lok.lingkaran = L.circle(ev.latlng, { radius: ev.accuracy || 0, color: "#2563eb", weight: 1, fillColor: "#3b82f6", fillOpacity: 0.12, interactive: false }).addTo(map);
      lok.marker = L.marker(ev.latlng, {
        icon: L.divIcon({ className: "", html: '<div style="width:16px;height:16px;border-radius:50%;background:#2563eb;border:3px solid #fff;box-shadow:0 0 0 2px rgba(37,99,235,.35),0 1px 4px rgba(0,0,0,.4)"></div>', iconSize: [16, 16], iconAnchor: [8, 8] }),
      }).addTo(map).bindTooltip(`Lokasi Anda (±${akurasi} m)`, { direction: "top" });
      map.setView(ev.latlng, Math.max(map.getZoom(), 17));
    });
    map.on("locationerror", (ev) => {
      lok.mencari = false; if (lok.tombol) lok.tombol.style.opacity = "1";
      toast.error(ev?.message && /denied|ditolak/i.test(ev.message)
        ? "Izin lokasi ditolak — aktifkan izin lokasi browser untuk fitur ini"
        : "Gagal mendapatkan lokasi Anda — pastikan GPS aktif lalu coba lagi");
    });

    // Info skala nominal + zoom (bottom-left, tak tertutup tombol zoom).
    const scaleInfo = L.control({ position: "bottomleft" });
    scaleInfo.onAdd = () => {
      const d = L.DomUtil.create("div", "");
      d.style.cssText = "background:rgba(255,255,255,.9);padding:2px 7px;border-radius:6px;font:600 11px system-ui,sans-serif;color:#0f172a;box-shadow:0 1px 3px rgba(0,0,0,.25);margin-bottom:4px;white-space:nowrap";
      scaleElRef.current = d;
      return d;
    };
    scaleInfo.addTo(map);
    const updateScale = () => {
      const el = scaleElRef.current; if (!el) return;
      const z = map.getZoom(); const lat = map.getCenter().lat;
      const mpp = 40075016.686 * Math.abs(Math.cos(lat * Math.PI / 180)) / Math.pow(2, z + 8);
      el.textContent = `Skala 1:${Math.round(mpp / 0.00028).toLocaleString("id-ID")} · zoom ${z}`;
    };
    map.on("zoomend moveend", updateScale); updateScale();

    layerRef.current = (clusterOnRef.current ? buildCluster() : L.layerGroup()).addTo(map);
    mapRef.current = map;
    setTimeout(() => map.invalidateSize(), 60);
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => map.invalidateSize()) : null;
    if (ro) ro.observe(mapElRef.current);
    roRef.current = ro;
    // TANPA cleanup di sini — perubahan `data` TIDAK boleh menghancurkan peta
    // (view/zoom/lokasi pengguna & marker tetap). Teardown di efek unmount.
  }, [data]);

  // Hancurkan peta HANYA saat komponen dilepas.
  useEffect(() => () => {
    try { roRef.current?.disconnect(); } catch { /* noop */ }
    const m = mapRef.current;
    if (m) { try { m.remove(); } catch { /* noop */ } }
    mapRef.current = null; layerRef.current = null;
    markersRef.current = new Map(); previewRef.current = null;
  }, []);

  // Klik peta di mode "tambah titik" → marker PRATINJAU (draggable) + form.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return undefined;
    const onClick = (ev) => {
      if (!modeTambahRef.current) return;
      if (previewRef.current) { try { map.removeLayer(previewRef.current); } catch { /* noop */ } }
      const pm = L.marker(ev.latlng, { icon: previewIcon(), draggable: true, zIndexOffset: 1000, keyboard: false })
        .addTo(map)
        .bindTooltip("Titik akan ditaruh di sini — seret untuk menggeser", { permanent: true, direction: "top", offset: [0, -18] })
        .openTooltip();
      previewRef.current = pm;
      setFormTitik({ lat: ev.latlng.lat, lng: ev.latlng.lng, nama_titik: "", keterangan: "" });
      setModeTambah(false);
      pm.on("dragend", () => {
        const ll = pm.getLatLng();
        setFormTitik((f) => (f ? { ...f, lat: ll.lat, lng: ll.lng } : f));
      });
    };
    map.on("click", onClick);
    return () => map.off("click", onClick);
    // `data` sebagai pemicu: peta baru ada SETELAH data termuat (efek init di atas).
  }, [data]);

  const buangPreview = useCallback(() => {
    const map = mapRef.current;
    if (map && previewRef.current) { try { map.removeLayer(previewRef.current); } catch { /* noop */ } }
    previewRef.current = null;
  }, []);

  useEffect(() => {
    try { localStorage.setItem("aman_petakolab_marker_style", markerStyle); } catch { /* diblokir */ }
  }, [markerStyle]);

  // Bangun ikon marker sesuai gaya aktif. Gaya "photo" HANYA untuk titik ASET
  // yang punya foto → tampilkan sampul (URL ber-token, sama seperti FotoImg
  // untuk tamu). Titik kolaborasi & aset tanpa foto tetap pin. Dipakai bersama
  // oleh sinkron marker & efek sorot seleksi agar keduanya konsisten.
  const buildIcon = useCallback((entry) => {
    const p = entry.point;
    if (markerStyle === "photo" && entry.jenis === "aset" && (Number(p?.jumlah_foto) || 0) > 0) {
      const q = new URLSearchParams();
      q.set("thumb", "1");
      if (token) q.set("token", token);
      const cover = `${API}/peta/kolaborasi/${id}/aset/${encodeURIComponent(p.id)}/foto/${p.thumbnail_index || 0}?${q.toString()}`;
      return photoMarkerIconKolab(cover, { color: entry.color, badge: entry.badge, selected: entry.selected });
    }
    return pinIcon(entry.color, { badge: entry.badge, selected: entry.selected });
  }, [markerStyle, id, token]);

  // Sinkron marker INKREMENTAL (tak clear+bangun-ulang) — meniru AssetMapFullView
  // agar view/cluster/spiderfy & seleksi tetap saat data/filter berubah. Handler
  // klik membaca entry.point sehingga selalu data terbaru. Seleksi (cincin)
  // diterapkan terpisah oleh efek di bawah.
  useEffect(() => {
    const map = mapRef.current, layer = layerRef.current;
    if (!map || !layer || !data) return;
    const seen = new Set();
    const bounds = [];
    const pasang = (key, point, latlng, color, badge, klik) => {
      seen.add(key);
      bounds.push(latlng);
      const jenis = key.startsWith("aset:") ? "aset" : "titik";
      // iconKey ikut memuat gaya + identitas sampul (thumbnail_index) → ganti
      // gaya / ganti sampul memicu rebuild ikon lewat jalur inkremental.
      const usePhoto = markerStyle === "photo" && jenis === "aset" && (Number(point?.jumlah_foto) || 0) > 0;
      const iconKey = `${color}|${badge}|${usePhoto ? `p${point.thumbnail_index || 0}` : "n"}`;
      const existing = markersRef.current.get(key);
      if (existing) {
        existing.point = point;
        if (existing.lat !== latlng[0] || existing.lng !== latlng[1]) {
          existing.marker.setLatLng(latlng);
          existing.lat = latlng[0]; existing.lng = latlng[1];
          layer.refreshClusters?.(existing.marker);
        }
        if (existing.iconKey !== iconKey) {
          existing.color = color; existing.badge = badge; existing.iconKey = iconKey;
          existing.marker.setIcon(buildIcon(existing));
        }
        return;
      }
      const entry = { marker: null, point, iconKey, color, badge, selected: false, lat: latlng[0], lng: latlng[1], jenis };
      const m = L.marker(latlng, { icon: buildIcon(entry) });
      entry.marker = m;
      m.on("click", () => klik(entry));
      layer.addLayer(m);
      markersRef.current.set(key, entry);
    };

    asetTampil.forEach((a) => pasang(
      `aset:${a.id}`, a, [a.lat, a.lng],
      STATUS_COLORS[a.status] || STATUS_DEFAULT, komentarCount[`aset:${a.id}`] || 0,
      (entry) => bukaDetailAset(entry.point)));
    (data.titik_kolaborasi || []).forEach((t) => pasang(
      `titik:${t.id}`, t, [t.lat, t.lng], COLLAB_COLOR, komentarCount[`titik:${t.id}`] || 0,
      (entry) => {
        if (moderasiRef.current && bolehModerasiRef.current) toggleTerpilih(entry.point.id);
        else bukaDetailTitik(entry.point);
      }));

    for (const [key, entry] of Array.from(markersRef.current.entries())) {
      if (!seen.has(key)) { layer.removeLayer(entry.marker); markersRef.current.delete(key); }
    }
    if (!fitOnceRef.current && bounds.length) {
      try { map.fitBounds(L.latLngBounds(bounds), { padding: [40, 40], maxZoom: 18 }); } catch { /* noop */ }
      fitOnceRef.current = true;
    }
  }, [data, asetTampil, komentarCount, bukaDetailAset, bukaDetailTitik, toggleTerpilih, buildIcon, markerStyle]);

  // Sorot cincin seleksi (detail `dipilih` + moderasi `terpilih`) secara
  // INKREMENTAL — hanya setIcon pada marker yang berubah status pilih; `data`
  // di deps agar cincin diterapkan ulang setelah sinkron membuat marker baru.
  useEffect(() => {
    const keys = new Set();
    if (dipilih) keys.add(`${dipilih.jenis}:${dipilih.id}`);
    terpilih.forEach((tid) => keys.add(`titik:${tid}`));
    markersRef.current.forEach((entry, key) => {
      const want = keys.has(key);
      if (entry.selected !== want) {
        entry.selected = want;
        entry.marker.setIcon(buildIcon(entry));
      }
    });
  }, [dipilih, terpilih, data, buildIcon]);

  // Hidup/matikan clustering: pindahkan marker yang sudah ada ke layer baru
  // (tanpa membangun ulang marker) — pin & seleksi tetap.
  const toggleCluster = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const on = !clusterOnRef.current;
    clusterOnRef.current = on; setClusterOn(on);
    const old = layerRef.current;
    const next = on ? buildCluster() : L.layerGroup();
    for (const entry of markersRef.current.values()) {
      try { if (old) old.removeLayer(entry.marker); } catch { /* noop */ }
      next.addLayer(entry.marker);
    }
    if (old) map.removeLayer(old);
    next.addTo(map);
    layerRef.current = next;
  }, []);

  // Ganti filter → pusatkan ulang peta ke subset (reset flag fit).
  const changeStatus = useCallback((v) => { setStatusFilter(v); fitOnceRef.current = false; }, []);
  const changeGroup = useCallback((v) => { setGroupKey(v); fitOnceRef.current = false; }, []);

  const butuhNama = useCallback((aksi) => {
    if (data && !data.tamu) { aksi(); return; }
    if (nama.trim()) { aksi(); return; }
    aksiSetelahNama.current = aksi;
    setNamaDraf(nama);
    setNamaDialog(true);
  }, [data, nama]);

  const simpanNama = () => {
    const n = namaDraf.trim().slice(0, 60);
    if (!n) { toast.error("Isi nama Anda dulu"); return; }
    setNama(n); try { localStorage.setItem("peta_nama", n); } catch { /* noop */ }
    setNamaDialog(false);
    const aksi = aksiSetelahNama.current; aksiSetelahNama.current = null;
    if (aksi) aksi();
  };

  const komentarUntuk = useMemo(() => {
    if (!data || !dipilih) return [];
    return (data.komentar || []).filter((k) => k.target_jenis === dipilih.jenis && k.target_id === dipilih.id);
  }, [data, dipilih]);

  // URL foto aset via endpoint peta ber-token (thumb=kecil / tanpa=foto ASLI).
  const fotoUrl = useCallback((assetId, idx, thumb) => {
    const q = new URLSearchParams();
    if (thumb) q.set("thumb", "1");
    if (token) q.set("token", token);
    return `${API}/peta/kolaborasi/${id}/aset/${encodeURIComponent(assetId)}/foto/${idx}?${q.toString()}`;
  }, [id, token]);

  const kirimTitik = async () => {
    if (!formTitik) return;
    if (!formTitik.nama_titik.trim()) { toast.error("Nama titik wajib diisi"); return; }
    butuhNama(async () => {
      setKirim(true);
      try {
        const r = await axios.post(`${API}/peta/kolaborasi/${id}/titik`, {
          lat: formTitik.lat, lng: formTitik.lng,
          nama_titik: formTitik.nama_titik.trim(), keterangan: (formTitik.keterangan || "").trim(),
          oleh: nama,
        }, { params: { token }, timeout: 20000 });
        setData((d) => ({ ...d, titik_kolaborasi: [...(d.titik_kolaborasi || []), r.data] }));
        setFormTitik(null); buangPreview();
        toast.success("Titik ditambahkan");
      } catch (e) { toast.error(apiErr(e, "Gagal menambah titik")); }
      finally { setKirim(false); }
    });
  };

  const kirimKomentar = async () => {
    if (!dipilih || !komentarTeks.trim()) { toast.error("Tulis komentar dulu"); return; }
    butuhNama(async () => {
      setKirim(true);
      try {
        const r = await axios.post(`${API}/peta/kolaborasi/${id}/komentar`, {
          target_jenis: dipilih.jenis, target_id: dipilih.id,
          teks: komentarTeks.trim(), oleh: nama,
        }, { params: { token }, timeout: 20000 });
        setData((d) => ({ ...d, komentar: [...(d.komentar || []), r.data] }));
        setKomentarTeks("");
        toast.success("Komentar terkirim");
      } catch (e) { toast.error(apiErr(e, "Gagal mengirim komentar")); }
      finally { setKirim(false); }
    });
  };

  // ── Moderasi (operator/admin satker) ──
  const hapusKontribusi = useCallback(async (kontribId) => {
    try {
      await axios.delete(`${API}/peta/kolaborasi/${id}/kontribusi/${kontribId}`, { params: { token } });
      setData((d) => ({
        ...d,
        titik_kolaborasi: (d.titik_kolaborasi || []).filter((t) => t.id !== kontribId),
        komentar: (d.komentar || []).filter((k) => k.id !== kontribId && k.target_id !== kontribId),
      }));
      setTerpilih((prev) => { const n = new Set(prev); n.delete(kontribId); return n; });
      setDipilih((cur) => (cur && cur.jenis === "titik" && cur.id === kontribId ? null : cur));
      return true;
    } catch (e) { toast.error(apiErr(e, "Gagal menghapus")); return false; }
  }, [id, token]);

  const hapusTerpilih = async () => {
    const ids = Array.from(terpilih);
    if (!ids.length) return;
    let ok = 0;
    for (const tid of ids) { if (await hapusKontribusi(tid)) ok += 1; }
    if (ok) toast.success(`${ok} titik dihapus`);
    setTerpilih(new Set());
  };

  // ── Status layar ──
  if (loading) return <div className="min-h-screen flex items-center justify-center bg-background"><Loader2 className="w-7 h-7 animate-spin text-blue-600" /></div>;
  if (koneksi) return (
    <div className="min-h-screen flex items-center justify-center bg-background p-6">
      <div className="text-center max-w-sm">
        <WifiOff className="w-10 h-10 text-amber-500 mx-auto mb-3" />
        <p className="font-semibold text-foreground">Koneksi bermasalah</p>
        <p className="text-sm text-muted-foreground mt-1">Link Anda mungkin masih berlaku — periksa internet lalu coba lagi.</p>
        <button onClick={() => { setLoading(true); muat(); }} className="mt-4 inline-flex items-center gap-1.5 px-4 h-10 rounded-lg bg-teal-700 text-white text-sm font-semibold">
          <RefreshCcw className="w-4 h-4" />Coba lagi
        </button>
      </div>
    </div>
  );
  if (galat) return (
    <div className="min-h-screen flex items-center justify-center bg-background p-6">
      <div className="text-center max-w-sm">
        <AlertTriangle className="w-10 h-10 text-red-500 mx-auto mb-3" />
        <p className="font-semibold text-foreground">Tidak dapat membuka peta</p>
        <p className="text-sm text-muted-foreground mt-1">{galat}</p>
      </div>
    </div>
  );

  const bolehKontribusi = !!data?.boleh_kontribusi;
  const bolehTitik = bolehKontribusi && (data?.tamu ? data?.izinkan_titik_publik : true);
  const bolehKomentar = bolehKontribusi && (data?.tamu ? data?.izinkan_komentar_publik : true);
  const jmlAset = (data?.titik_aset || []).length;
  const jmlKolab = (data?.titik_kolaborasi || []).length;

  return (
    <div className="fixed inset-0 flex flex-col bg-background text-foreground">
      {/* Header */}
      <header className="bg-card border-b border-border px-3 py-2 flex items-center gap-2 z-[500] shadow-sm">
        <span className="w-9 h-9 rounded-lg bg-teal-700 flex items-center justify-center flex-shrink-0">
          <MapPin className="w-5 h-5 text-white" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold text-foreground truncate leading-tight">{data?.judul || "Peta Kolaboratif"}</p>
          <p className="text-[11px] text-muted-foreground truncate flex items-center gap-1.5">
            {data?.nama_kegiatan ? <span className="truncate">{data.nama_kegiatan}</span> : null}
            <span className="inline-flex items-center gap-0.5 flex-shrink-0"><Clock className="w-3 h-3" />{sisaTayang(data?.berlaku_sampai)}</span>
          </p>
        </div>
        {bolehModerasi && (
          <span className="hidden sm:inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-900/40 px-2 py-1 rounded-full flex-shrink-0">
            <ShieldCheck className="w-3 h-3" />Operator
          </span>
        )}
        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-blue-700 dark:text-blue-300 bg-blue-100 dark:bg-blue-900/40 px-2 py-1 rounded-full flex-shrink-0">
          <Users className="w-3 h-3" />Kolaboratif
        </span>
      </header>

      {data?.kedaluwarsa && (
        <div className="bg-amber-50 dark:bg-amber-950/40 border-b border-amber-200 dark:border-amber-900 px-3 py-1.5 text-[11px] text-amber-800 dark:text-amber-300 flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          Masa tayang berakhir — mode arsip (hanya lihat). Perpanjang dari aplikasi untuk berkontribusi lagi.
        </div>
      )}

      {/* Toolbar: hitungan + filter + kelompok + cluster + moderasi + muat ulang */}
      <div className="bg-card border-b border-border px-2 py-1.5 flex items-center gap-1.5 flex-wrap">
        <span className="text-[11px] text-muted-foreground px-1 flex-shrink-0">
          <b className="text-foreground">{asetTampil.length}</b>/{jmlAset} aset · <b className="text-foreground">{jmlKolab}</b> kolaborasi
        </span>
        <div className="flex-1" />
        {statuses.length > 0 && (
          <Select value={statusFilter} onValueChange={changeStatus}>
            <SelectTrigger className="h-8 w-auto px-2 text-[11px] gap-1 flex-shrink-0" aria-label="Filter status" data-testid="peta-kolab-filter-status">
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: statusFilter === "__semua__" ? "#94a3b8" : (STATUS_COLORS[statusFilter] || STATUS_DEFAULT) }} />
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="z-[900]">
              <SelectItem value="__semua__">Semua status</SelectItem>
              {statuses.map((s) => (<SelectItem key={s} value={s}>{s}</SelectItem>))}
            </SelectContent>
          </Select>
        )}
        {groups.length > 0 && (
          <Select value={groupKey} onValueChange={changeGroup}>
            <SelectTrigger className="h-8 w-auto max-w-[200px] px-2 text-[11px] gap-1 flex-shrink-0" aria-label="Filter barang serupa" data-testid="peta-kolab-filter-grup">
              <Layers className="w-3.5 h-3.5 text-violet-500 flex-shrink-0" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="max-h-80 min-w-[260px] z-[900]">
              <SelectItem value="__semua__">Semua barang ({groups.length} jenis)</SelectItem>
              {groups.map((g) => (
                <SelectItem key={g.key} value={g.key}>
                  <span className="flex items-center gap-2 w-full">
                    <span className="font-mono text-[10px] text-muted-foreground shrink-0">{g.code}</span>
                    <span className="flex-1 truncate">{g.name}</span>
                    <span className="text-[10px] font-semibold text-violet-600 dark:text-violet-400 shrink-0">{g.count}</span>
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <button
          type="button" onClick={toggleCluster} aria-pressed={clusterOn} aria-label={clusterOn ? "Pengelompokan marker: aktif" : "Pengelompokan marker: mati"}
          className={`h-8 w-8 rounded-lg border flex items-center justify-center flex-shrink-0 transition-colors ${clusterOn ? "border-blue-500 bg-blue-500/10 text-blue-600 dark:text-blue-400" : "border-border text-foreground/80 hover:bg-muted"}`}
          title={clusterOn ? "Pengelompokan marker aktif — ketuk untuk mematikan" : "Marker tampil satu per satu — ketuk untuk mengelompokkan"}
          data-testid="peta-kolab-cluster"
        >
          <Boxes className="w-4 h-4" />
        </button>
        <button
          type="button" onClick={() => setMarkerStyle((s) => (s === "photo" ? "pin" : "photo"))} aria-pressed={markerStyle === "photo"} aria-label={markerStyle === "photo" ? "Gaya marker: foto sampul" : "Gaya marker: pin"}
          className={`h-8 w-8 rounded-lg border flex items-center justify-center flex-shrink-0 transition-colors ${markerStyle === "photo" ? "border-blue-500 bg-blue-500/10 text-blue-600 dark:text-blue-400" : "border-border text-foreground/80 hover:bg-muted"}`}
          title={markerStyle === "photo" ? "Marker menampilkan foto sampul aset — ketuk untuk kembali ke pin" : "Marker berbentuk pin — ketuk untuk menampilkan foto sampul di marker"}
          data-testid="peta-kolab-marker-style"
        >
          <ImageIcon className="w-4 h-4" />
        </button>
        {bolehModerasi && (
          <button
            type="button" onClick={() => setModerasi((v) => { if (v) setTerpilih(new Set()); return !v; })} aria-pressed={moderasi} aria-label={moderasi ? "Mode moderasi: aktif" : "Mode moderasi"}
            className={`h-8 w-8 rounded-lg border flex items-center justify-center flex-shrink-0 transition-colors ${moderasi ? "border-amber-500 bg-amber-500/10 text-amber-600 dark:text-amber-400" : "border-border text-foreground/80 hover:bg-muted"}`}
            title="Moderasi — pilih titik kolaborasi untuk dihapus"
            data-testid="peta-kolab-moderasi"
          >
            <MousePointerClick className="w-4 h-4" />
          </button>
        )}
        {/* Muat ulang memakai `menyegarkan`, BUKAN `loading`: peta tetap terpasang
            selama data diambil (lihat catatan di deklarasi state). */}
        <button
          type="button" onClick={() => { if (menyegarkan) return; fitOnceRef.current = false; setMenyegarkan(true); muat(); }}
          disabled={menyegarkan}
          className="h-8 w-8 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0 disabled:opacity-60"
          aria-label="Muat ulang peta" title="Muat ulang peta" data-testid="peta-kolab-refresh"
        >
          {menyegarkan ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCcw className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Bilah moderasi terpilih */}
      {moderasi && bolehModerasi && (
        <div className="bg-amber-500/10 border-b border-amber-500/40 px-2 py-1.5 flex items-center gap-1.5 flex-wrap">
          <span className="flex items-center gap-1.5 px-2 h-7 rounded-lg bg-amber-500 text-white text-[11px] font-bold flex-shrink-0">
            <MousePointerClick className="w-3 h-3" />{terpilih.size} terpilih
          </span>
          <span className="text-[11px] text-muted-foreground px-1 hidden sm:inline">Ketuk titik kolaborasi (teal) untuk pilih/lepas</span>
          <div className="flex-1" />
          <button type="button" onClick={() => setTerpilih(new Set())} disabled={terpilih.size === 0}
            className="h-7 px-2 rounded-lg border border-border text-[11px] font-medium text-foreground/80 flex items-center gap-1 hover:bg-muted disabled:opacity-50 flex-shrink-0">
            <Eraser className="w-3.5 h-3.5" />Kosongkan
          </button>
          <button type="button" onClick={hapusTerpilih} disabled={terpilih.size === 0}
            className="h-7 px-2.5 rounded-lg bg-red-600 text-white text-[11px] font-bold flex items-center gap-1 hover:bg-red-700 disabled:opacity-50 flex-shrink-0"
            data-testid="peta-kolab-hapus-terpilih">
            <Trash2 className="w-3.5 h-3.5" />Hapus ({terpilih.size})
          </button>
        </div>
      )}

      {/* Peta */}
      <div className="relative flex-1 min-h-0">
        <div ref={mapElRef} className="absolute inset-0 z-0" data-testid="peta-kolaborasi-map" />

        {/* Tombol Tambah Titik (FAB) */}
        {bolehTitik && (
          <button
            onClick={() => { setDipilih(null); if (modeTambah) { setModeTambah(false); } else { buangPreview(); setModeTambah(true); toast.info("Ketuk peta untuk menaruh titik"); } }}
            aria-label={modeTambah ? "Batal tambah titik" : "Tambah titik"}
            title={modeTambah ? "Batal" : "Tambah titik kolaborasi"}
            className={`absolute bottom-5 right-4 z-[500] h-14 w-14 rounded-full shadow-lg flex items-center justify-center ${modeTambah ? "bg-red-600 text-white" : "bg-emerald-600 text-white"}`}
            data-testid="peta-tambah-titik"
          >
            {modeTambah ? <X className="w-6 h-6" /> : <Plus className="w-6 h-6" />}
          </button>
        )}
        {modeTambah && (
          <div className="absolute bottom-20 left-1/2 -translate-x-1/2 z-[500] bg-slate-900/90 text-white text-[11px] px-3 py-1.5 rounded-full shadow">Ketuk lokasi di peta untuk menaruh titik</div>
        )}
      </div>

      {/* Legenda footer — TIDAK menutup kontrol zoom di dalam peta */}
      <div className="bg-card border-t border-border px-3 py-1.5 flex items-center gap-x-3 gap-y-1 flex-wrap">
        {Object.entries(STATUS_COLORS).map(([label, color]) => (
          <span key={label} className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <span className="w-2.5 h-2.5 rounded-full border border-white shadow" style={{ background: color }} />{label}
          </span>
        ))}
        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
          <span className="w-2.5 h-2.5 rounded-full border border-white shadow" style={{ background: COLLAB_COLOR }} />Titik kolaborasi
        </span>
        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
          <span className="w-3.5 h-3.5 rounded-full bg-slate-900 border border-white shadow flex items-center justify-center"><MessageSquare className="w-2 h-2 text-white" /></span>ada komentar
        </span>
      </div>

      {/* Panel detail titik + komentar (bottom sheet) */}
      {dipilih && (
        <div className="absolute inset-x-0 bottom-0 z-[600] bg-card rounded-t-2xl shadow-2xl max-h-[62vh] flex flex-col border-t border-border" data-testid="peta-panel-titik">
          <div className="flex items-start gap-2 p-3 border-b border-border">
            <span className={`w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0`} style={{ background: dipilih.jenis === "aset" ? (STATUS_COLORS[dipilih.status] || STATUS_DEFAULT) : COLLAB_COLOR }} />
            <div className="min-w-0 flex-1">
              {dipilih.jenis === "aset" ? (
                <>
                  <p className="text-sm font-bold text-foreground line-clamp-2">{dipilih.nama || "-"}</p>
                  <p className="text-[11px] text-muted-foreground truncate">{dipilih.kode || "-"}{dipilih.nup ? ` · NUP ${dipilih.nup}` : ""}</p>
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {dipilih.status && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[9.5px] font-bold border" style={{ background: `${STATUS_COLORS[dipilih.status] || STATUS_DEFAULT}1a`, color: STATUS_COLORS[dipilih.status] || STATUS_DEFAULT, borderColor: `${STATUS_COLORS[dipilih.status] || STATUS_DEFAULT}40` }}>{dipilih.status}</span>
                    )}
                    {dipilih.kondisi && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[9.5px] font-bold border" style={{ background: `${CONDITION_COLORS[dipilih.kondisi] || STATUS_DEFAULT}1a`, color: CONDITION_COLORS[dipilih.kondisi] || STATUS_DEFAULT, borderColor: `${CONDITION_COLORS[dipilih.kondisi] || STATUS_DEFAULT}40` }}>{dipilih.kondisi}</span>
                    )}
                  </div>
                  {(() => {
                    const rows = [
                      ["Kategori", dipilih.kategori],
                      ["Merk/Tipe", [dipilih.merk, dipilih.tipe].filter((v) => String(v || "").trim()).join(" — ")],
                      ["Lokasi", dipilih.lokasi],
                    ].filter(([, v]) => String(v || "").trim());
                    return rows.length ? (
                      <div className="mt-2 pt-1.5 border-t border-border space-y-0.5">
                        {rows.map(([label, value]) => (
                          <div key={label} className="flex gap-2 text-[11px]">
                            <span className="flex-shrink-0 w-16 text-muted-foreground">{label}</span>
                            <span className="min-w-0 text-foreground/90 font-medium break-words">{value}</span>
                          </div>
                        ))}
                      </div>
                    ) : null;
                  })()}
                  {dipilih.jumlah_foto > 0 && (
                    <div className="mt-2 pt-1.5 border-t border-border">
                      <p className="text-[10px] text-muted-foreground mb-1 flex items-center gap-1"><ImageIcon className="w-3 h-3" />Foto ({dipilih.jumlah_foto}) — ketuk untuk lihat asli</p>
                      <div className="flex gap-1.5 overflow-x-auto pb-1">
                        {Array.from({ length: Math.min(dipilih.jumlah_foto, 8) }).map((_, i) => (
                          <button key={i} type="button"
                            onClick={() => setFotoView({ assetId: dipilih.id, jumlah: dipilih.jumlah_foto, index: i })}
                            className="relative w-14 h-14 flex-shrink-0 rounded-lg overflow-hidden border border-border bg-muted cursor-zoom-in"
                            title="Ketuk untuk lihat foto asli" data-testid={`peta-foto-thumb-${i}`}>
                            <FotoImg url={fotoUrl(dipilih.id, i, true)} className="w-full h-full object-cover" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <>
                  <p className="text-sm font-bold text-foreground line-clamp-2">{dipilih.nama_titik || "Titik kolaborasi"}</p>
                  {dipilih.keterangan && <p className="text-xs text-muted-foreground whitespace-pre-wrap break-words mt-0.5">{dipilih.keterangan}</p>}
                  {dipilih.oleh && <p className="text-[10px] text-muted-foreground/80 mt-1">oleh {dipilih.oleh}{dipilih.created_at ? ` · ${fmtWaktu(dipilih.created_at)}` : ""}</p>}
                </>
              )}
            </div>
            {bolehModerasi && dipilih.jenis === "titik" && (
              <button onClick={() => hapusKontribusi(dipilih.id)} title="Hapus titik ini" className="p-1.5 rounded-md hover:bg-red-50 dark:hover:bg-red-950 text-red-500 flex-shrink-0" data-testid="peta-kolab-hapus-titik"><Trash2 className="w-4 h-4" /></button>
            )}
            <button onClick={() => setDipilih(null)} className="p-1.5 rounded-md hover:bg-muted text-muted-foreground flex-shrink-0"><X className="w-4 h-4" /></button>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {komentarUntuk.length === 0 ? (
              <p className="text-xs text-muted-foreground/80 text-center py-4">Belum ada komentar di titik ini.</p>
            ) : komentarUntuk.map((k) => (
              <div key={k.id} className="bg-muted rounded-lg px-3 py-2 group relative">
                <p className="text-sm text-foreground/90 whitespace-pre-wrap break-words">{k.teks}</p>
                <p className="text-[10px] text-muted-foreground mt-1">{k.oleh} · {fmtWaktu(k.created_at)}</p>
                {bolehModerasi && (
                  <button onClick={() => hapusKontribusi(k.id)} title="Hapus komentar" className="absolute top-1.5 right-1.5 p-1 rounded-md text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950"><Trash2 className="w-3.5 h-3.5" /></button>
                )}
              </div>
            ))}
          </div>
          {bolehKomentar ? (
            <div className="p-2 border-t border-border flex items-end gap-2">
              <textarea
                value={komentarTeks} onChange={(e) => setKomentarTeks(e.target.value)}
                rows={1} maxLength={1000} placeholder="Tulis komentar…"
                className="flex-1 resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring max-h-24"
                data-testid="peta-komentar-input"
              />
              <button onClick={kirimKomentar} disabled={kirim} className="h-10 w-10 rounded-lg bg-teal-700 text-white flex items-center justify-center flex-shrink-0 disabled:opacity-50" data-testid="peta-komentar-kirim">
                {kirim ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>
          ) : (
            <div className="p-2 border-t border-border text-[11px] text-muted-foreground text-center flex items-center justify-center gap-1">
              <MessageSquarePlus className="w-3.5 h-3.5" />{data?.kedaluwarsa ? "Mode arsip — komentar dinonaktifkan." : "Komentar publik dinonaktifkan pembagi."}
            </div>
          )}
        </div>
      )}

      {/* Form titik baru — bottom sheet (marker pratinjau tetap terlihat di peta) */}
      {formTitik && (
        <div className="absolute inset-x-0 bottom-0 z-[650] bg-card rounded-t-2xl shadow-2xl border-t border-border p-4 space-y-3" data-testid="peta-titik-form">
          <div className="flex items-center justify-between">
            <p className="text-sm font-bold text-foreground flex items-center gap-1.5"><MapPin className="w-4 h-4 text-emerald-600" />Titik Kolaborasi Baru</p>
            <span className="text-[11px] text-muted-foreground font-mono">{formTitik.lat.toFixed(6)}, {formTitik.lng.toFixed(6)}</span>
          </div>
          <p className="text-[11px] text-muted-foreground -mt-1">Seret marker hijau di peta untuk menggeser titik.</p>
          <input
            autoFocus value={formTitik.nama_titik} maxLength={120}
            onChange={(e) => setFormTitik((f) => ({ ...f, nama_titik: e.target.value }))}
            placeholder="Nama/label titik *"
            className="w-full rounded-lg border border-border bg-background px-3 h-10 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
            data-testid="peta-titik-nama"
          />
          <textarea
            value={formTitik.keterangan} maxLength={1000} rows={2}
            onChange={(e) => setFormTitik((f) => ({ ...f, keterangan: e.target.value }))}
            placeholder="Keterangan (opsional)"
            className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <div className="flex flex-wrap gap-2 justify-end">
            <button onClick={() => { setFormTitik(null); buangPreview(); }} className="px-3 h-10 rounded-lg border border-border text-sm text-foreground/80">Batal</button>
            <button onClick={kirimTitik} disabled={kirim} className="px-4 h-10 rounded-lg bg-emerald-600 text-white text-sm font-semibold flex items-center gap-1.5 disabled:opacity-50" data-testid="peta-titik-simpan">
              {kirim ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}Tambah
            </button>
          </div>
        </div>
      )}

      {/* Foto layar penuh — HANYA foto ASLI (ketuk latar untuk tutup) */}
      {fotoView && (
        <div className="fixed inset-0 z-[900] bg-black flex items-center justify-center" onClick={() => setFotoView(null)} data-testid="peta-foto-fullscreen">
          <FotoImg key={`${fotoView.assetId}-${fotoView.index}`} url={fotoUrl(fotoView.assetId, fotoView.index, false)} alt="Foto aset" spinner
            className="max-w-full max-h-full object-contain select-none" onClick={(e) => e.stopPropagation()} />
          <button onClick={() => setFotoView(null)} aria-label="Tutup foto"
            className="absolute top-3 right-3 w-11 h-11 rounded-full bg-white/15 text-white flex items-center justify-center backdrop-blur hover:bg-white/25" data-testid="peta-foto-tutup">
            <X className="w-6 h-6" />
          </button>
          {fotoView.jumlah > 1 && (
            <>
              <button onClick={(e) => { e.stopPropagation(); setFotoView((v) => ({ ...v, index: (v.index - 1 + v.jumlah) % v.jumlah })); }}
                aria-label="Foto sebelumnya" className="absolute left-2 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-white/15 text-white flex items-center justify-center hover:bg-white/25">
                <ChevronLeft className="w-6 h-6" />
              </button>
              <button onClick={(e) => { e.stopPropagation(); setFotoView((v) => ({ ...v, index: (v.index + 1) % v.jumlah })); }}
                aria-label="Foto berikutnya" className="absolute right-2 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-white/15 text-white flex items-center justify-center hover:bg-white/25">
                <ChevronRight className="w-6 h-6" />
              </button>
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-white/90 text-xs bg-black/50 px-2.5 py-1 rounded-full">{fotoView.index + 1} / {fotoView.jumlah}</div>
            </>
          )}
        </div>
      )}

      {/* Dialog nama tamu */}
      {namaDialog && (
        <div className="fixed inset-0 z-[800] bg-black/40 flex items-center justify-center p-3">
          <div className="bg-card rounded-2xl w-full max-w-xs p-4 space-y-3 border border-border">
            <p className="text-sm font-bold text-foreground">Siapa nama Anda?</p>
            <p className="text-[11px] text-muted-foreground">Nama ini ditampilkan pada titik & komentar yang Anda tambahkan.</p>
            <input
              autoFocus value={namaDraf} maxLength={60}
              onChange={(e) => setNamaDraf(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") simpanNama(); }}
              placeholder="Nama Anda"
              className="w-full rounded-lg border border-border bg-background px-3 h-10 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              data-testid="peta-nama-input"
            />
            <div className="flex flex-wrap gap-2 justify-end">
              <button onClick={() => { setNamaDialog(false); aksiSetelahNama.current = null; }} className="px-3 h-10 rounded-lg border border-border text-sm text-foreground/80">Batal</button>
              <button onClick={simpanNama} className="px-4 h-10 rounded-lg bg-teal-700 text-white text-sm font-semibold" data-testid="peta-nama-simpan">Lanjut</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
