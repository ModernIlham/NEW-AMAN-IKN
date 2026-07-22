import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
// Clustering marker berdekatan (mudah diklik saat pin bertumpuk). CSS dasar
// wajib untuk animasi + kaki spiderfy; ikon cluster kita gaya sendiri
// (iconCreateFunction) sehingga Default.css sekadar cadangan aman.
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import axios from "axios";
import { MapPinned, RefreshCw, Loader2, Move, X, Filter, Download, Camera, Layers, ChevronDown, Boxes, MousePointerClick, CheckCheck, Eraser, PencilLine, SquareDashed } from "lucide-react";
import { toast } from "sonner";
import { compressImageFile } from "../../lib/imageCompression";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuRadioGroup, DropdownMenuRadioItem,
} from "../ui/dropdown-menu";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../ui/select";
import { getSnapshotAssets } from "../../lib/offlineSnapshot";
import { downloadFileWithProgress } from "../../lib/downloadFile";
import { authMediaUrl } from "../../lib/mediaUrl";
import { useBackGuard } from "../../hooks/useBackGuard";
import Lightbox from "./PhotoLightbox";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Batas aman jumlah id terpilih yang boleh dikirim di URL ekspor terseleksi
// (UUID ~37 char/id → di bawah 8KB request-line agar tak kena 414 di proxy).
const MAX_SELECTED_EXPORT = 200;

// Koordinat aset tersimpan sebagai string — parse toleran (koma desimal).
function parseCoord(v) {
  if (v === null || v === undefined) return null;
  const n = parseFloat(String(v).trim().replace(",", "."));
  return Number.isFinite(n) && Math.abs(n) <= 180 ? n : null;
}

const STATUS_COLORS = {
  "Ditemukan": "#2563eb",
  "Tidak Ditemukan": "#dc2626",
  "Berlebih": "#d97706",
  "Sengketa": "#7c3aed",
  "Belum Diinventarisasi": "#64748b",
};

const CONDITION_COLORS = {
  "Baik": "#059669",
  "Rusak Ringan": "#d97706",
  "Rusak Berat": "#dc2626",
};

// Data pengguna barang LENGKAP = nama pengguna + NIP/NIK terisi + BAST
// sudah terunggah → pin diberi border hijau.
function isPenggunaComplete(row) {
  return !!(String(row.user || "").trim()
    && String(row.pengguna_nip || "").trim()
    && String(row.bast_file_id || "").trim());
}

function rowHasPhoto(row) {
  return (Number(row.photo_count) || 0) > 0;
}

// Pin berwarna via divIcon — menghindari masalah path ikon default leaflet
// di bundler CRA, sekaligus memberi warna per status inventarisasi.
// Border hijau = data pengguna lengkap; badge kamera = aset punya foto.
// dihapus=true → pin abu-abu diberi TANDA SILANG merah (aset telah dihapus
// lewat tombol hapus di popup — pin dibiarkan tampil sebagai jejak visual).
function markerIcon(color, hasPhoto = false, complete = false, dihapus = false, selected = false) {
  if (dihapus) {
    return L.divIcon({
      className: "",
      html: `<div style="position:relative;width:22px;height:22px;opacity:.85">
        <div style="width:22px;height:22px;border-radius:50% 50% 50% 0;background:#94a3b8;transform:rotate(-45deg);border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45)"></div>
        <svg width="26" height="26" viewBox="0 0 26 26" style="position:absolute;top:-4px;left:-2px;pointer-events:none">
          <line x1="4" y1="4" x2="22" y2="22" stroke="#fff" stroke-width="6" stroke-linecap="round"/>
          <line x1="22" y1="4" x2="4" y2="22" stroke="#fff" stroke-width="6" stroke-linecap="round"/>
          <line x1="4" y1="4" x2="22" y2="22" stroke="#dc2626" stroke-width="3.2" stroke-linecap="round"/>
          <line x1="22" y1="4" x2="4" y2="22" stroke="#dc2626" stroke-width="3.2" stroke-linecap="round"/>
        </svg>
      </div>`,
      iconSize: [22, 22],
      iconAnchor: [11, 22],
      popupAnchor: [0, -20],
    });
  }
  const border = selected ? "2.5px solid #fff" : complete ? "2.5px solid #16a34a" : "2px solid #fff";
  // Pin terpilih (mode seleksi): cincin oranye tebal + lencana centang agar
  // menonjol jelas di antara pin lain, tanpa mengubah warna status.
  const ring = selected
    ? "box-shadow:0 0 0 3px #f59e0b, 0 0 0 6px rgba(245,158,11,.35), 0 1px 5px rgba(0,0,0,.5)"
    : complete
      ? "box-shadow:0 0 0 1.5px #16a34a, 0 1px 4px rgba(0,0,0,.45)"
      : "box-shadow:0 1px 4px rgba(0,0,0,.45)";
  const badge = hasPhoto
    ? `<div style="position:absolute;top:-7px;right:-7px;width:14px;height:14px;border-radius:50%;background:#0f172a;border:1.5px solid #fff;display:flex;align-items:center;justify-content:center;">
         <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
       </div>`
    : "";
  const checkBadge = selected
    ? `<div style="position:absolute;bottom:-3px;left:-6px;width:15px;height:15px;border-radius:50%;background:#f59e0b;border:1.5px solid #fff;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 2px rgba(0,0,0,.4)">
         <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="4"><polyline points="20 6 9 17 4 12"/></svg>
       </div>`
    : "";
  return L.divIcon({
    className: "",
    html: `<div style="position:relative;width:22px;height:22px">
      <div style="width:22px;height:22px;border-radius:50% 50% 50% 0;background:${color};transform:rotate(-45deg);border:${border};${ring}"></div>
      ${badge}${checkBadge}
    </div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 22],
    popupAnchor: [0, -20],
  });
}

function esc(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Grup marker ber-CLUSTER (pin mepet → gelembung ber-angka). Dibungkus factory
// supaya bisa dibangun ULANG saat pengguna men-toggle cluster on/off. Radius
// kecil (44 px ≈ ukuran pin) → hanya pin yang benar-benar berdekatan yang
// dikelompokkan; klik cluster → perbesar ke anggota; zoom maks / hover cluster
// rapat → spiderfy (dikipas) agar tiap pin bisa diklik.
function buildClusterLayer(map) {
  const layer = L.markerClusterGroup({
    maxClusterRadius: 44,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: true,
    removeOutsideVisibleBounds: true,
    chunkedLoading: true,
    iconCreateFunction: (cluster) => {
      const n = cluster.getChildCount();
      const size = n < 10 ? 34 : n < 100 ? 40 : 46;
      return L.divIcon({
        html: `<div style="width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center;`
          + `border-radius:9999px;background:rgba(37,99,235,.92);color:#fff;font:700 12px system-ui,sans-serif;`
          + `border:2px solid #fff;box-shadow:0 1px 4px rgba(15,23,42,.4)">${n}</div>`,
        className: "aman-cluster",
        iconSize: [size, size],
      });
    },
  });
  // Spiderfy saat hover — pin bertindih (koordinat sama/nyaris) tak bisa dipisah
  // dengan memperbesar; hover cluster RAPAT (rentang <60 px) / zoom maks → kipas.
  layer.on("clustermouseover", (e) => {
    const cl = e.layer;
    if (!cl || cl._spiderfied) return;
    const n = cl.getChildCount();
    if (n < 2 || n > 15) return;
    try {
      const b = cl.getBounds();
      const nw = map.latLngToLayerPoint(b.getNorthWest());
      const se = map.latLngToLayerPoint(b.getSouthEast());
      const spanPx = Math.max(Math.abs(se.x - nw.x), Math.abs(se.y - nw.y));
      if (spanPx < 60 || map.getZoom() >= map.getMaxZoom()) cl.spiderfy();
    } catch { /* bounds belum siap — abaikan */ }
  });
  return layer;
}

/**
 * Peta Aset — LEMBAR di halaman utama (menggantikan area baris data saat
 * terbuka). Header, mode Dashboard/Inventarisasi, dan toolbar filter tetap
 * tampil di atasnya; form tambah/edit aset tetap bisa terbuka di sampingnya
 * (desktop) atau di atasnya (HP) — selesai edit kembali ke peta.
 *
 * - Mengikuti filter aktif (search + kategori + filter lanjutan) — online via
 *   GET /assets, offline via snapshot + clientFilter yang sama dengan daftar.
 * - Filter "Barang Serupa" bawaan: kelompok (kode+nama, ≥2 unit) diturunkan
 *   dari data peta sendiri sehingga jalan juga saat offline.
 * - Pin digeser (bila boleh edit) → koordinat tersimpan otomatis.
 * - Satu popup per pin (tanpa tooltip ganda). Back HP menutup peta.
 */
const AssetMapFullView = memo(function AssetMapFullView({
  activityId,
  activityName = "",
  onClose,
  canEdit = false,
  onEditAsset,        // (row) => void — buka form edit (peta TETAP terbuka)
  onDeleteAsset,      // async (id) => bool — hapus aset (konfirmasi di pemanggil)
  onSaveCoords,       // (row, lat, lng) => void — simpan koordinat (throw = tolak)
  buildParams,        // () => URLSearchParams — filter aktif dashboard (tanpa page)
  clientFilter,       // (rows) => rows — filter yang sama utk data snapshot offline
  activeFilterCount = 0,
  selectedIds = null, // Set<id> aset terpilih di daftar → peta & ekspor hanya ini
  onQuickAdd,         // (lat, lng, nama) => void — tambah cepat aset di titik peta
  onSelectionChange,  // (updater|Set) => void — ubah himpunan aset terpilih (map→daftar)
  onBatchEditSelected,// () => void — tutup peta & buka Edit Massal utk aset terpilih
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);         // L.LayerGroup pin
  const markersRef = useRef(new Map());  // id -> { marker, row, lat, lng, iconKey, draggable }
  const didFitRef = useRef(false);       // fitBounds hanya saat muat pertama / ganti kelompok
  const scaleInfoElRef = useRef(null);   // elemen info skala/zoom (diperbarui saat zoom)
  const onPhotoClickRef = useRef(null);  // dipanggil DOM popup → buka lightbox foto
  const [lightboxRow, setLightboxRow] = useState(null); // aset yang fotonya dibuka
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [truncated, setTruncated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadedOnce, setLoadedOnce] = useState(false);
  const [groupKey, setGroupKey] = useState("__semua__"); // filter Barang Serupa
  const [clusterOn, setClusterOn] = useState(true); // kelompokkan pin berdekatan
  const clusterOnRef = useRef(true);
  // Mode Seleksi: klik/ketuk pin = pilih/lepas (bukan buka popup); Shift+seret
  // (PC) atau tombol "Pilih Area" (HP) = kotak seleksi. Hanya bila pemanggil
  // memberi onSelectionChange (butuh izin ubah). Terhubung ke selectedIds daftar.
  const canSelect = typeof onSelectionChange === "function";
  const [selectMode, setSelectMode] = useState(false);
  const [drawArea, setDrawArea] = useState(false); // HP: gambar kotak seleksi 1×
  const selectModeRef = useRef(false);
  const drawAreaRef = useRef(false);
  const mapWrapRef = useRef(null);       // pembungkus ber-posisi utk overlay kotak
  useEffect(() => { selectModeRef.current = selectMode; }, [selectMode]);
  useEffect(() => { drawAreaRef.current = drawArea; }, [drawArea]);
  // Guard staleness: hanya hasil load TERBARU yang boleh menulis state —
  // load lama (loop multi-halaman) bisa selesai SETELAH load baru.
  const loadSeqRef = useRef(0);

  // Callback disimpan di ref agar marker tidak dibangun ulang hanya karena
  // identitas arrow function induk berubah tiap render.
  const onEditRef = useRef(onEditAsset);
  const onDeleteRef = useRef(onDeleteAsset);
  const onSaveRef = useRef(onSaveCoords);
  const deletedIdsRef = useRef(new Set()); // id aset terhapus → pin diberi tanda silang
  const onCloseRef = useRef(onClose);
  const onQuickAddRef = useRef(onQuickAdd);
  useEffect(() => { onEditRef.current = onEditAsset; onDeleteRef.current = onDeleteAsset; onSaveRef.current = onSaveCoords; onCloseRef.current = onClose; onQuickAddRef.current = onQuickAdd; });
  onPhotoClickRef.current = (row) => setLightboxRow(row);

  // Back HP menutup lembar peta (kembali ke baris data), bukan keluar app.
  useBackGuard(useCallback(() => onCloseRef.current?.(), []));

  const load = useCallback(async () => {
    if (!activityId) return;
    const seq = ++loadSeqRef.current;
    const fresh = () => seq === loadSeqRef.current;
    setLoading(true);
    try {
      const byId = new Map(); // dedupe id — halaman bisa tumpang-tindih saat data berubah di tengah paging
      let serverTotal = 0;
      let hitCap = false;
      if (navigator.onLine) {
        // Data MENGIKUTI FILTER AKTIF: query yang sama dengan daftar aset,
        // dipaging sampai habis (page_size maks server = 500, plafon 50k).
        for (let page = 1; page <= 100; page++) {
          const params = buildParams ? buildParams() : new URLSearchParams();
          params.set("page", String(page));
          params.set("page_size", "500");
          params.set("sort_by", "newest");
          const r = await axios.get(`${API}/assets?${params.toString()}`);
          if (!fresh()) return; // hasil basi — load baru sudah berjalan
          const items = r.data?.items || [];
          for (const it of items) { if (it && it.id) byId.set(it.id, it); }
          serverTotal = r.data?.total || 0;
          if (page >= (r.data?.total_pages || 1) || items.length === 0) break;
          if (page === 100) hitCap = true;
        }
      } else {
        const cached = await getSnapshotAssets(activityId);
        if (!fresh()) return;
        const filtered = clientFilter ? clientFilter(cached) : cached;
        for (const it of filtered) { if (it && it.id) byId.set(it.id, it); }
        serverTotal = filtered.length;
      }
      const all = Array.from(byId.values());
      setTotal(Math.max(serverTotal, all.length));
      setTruncated(hitCap || all.length < serverTotal); // paging terpotong → beri tahu
      setRows(all.filter((a) => parseCoord(a.koordinat_latitude) !== null && parseCoord(a.koordinat_longitude) !== null));
      setLoadedOnce(true);
    } catch {
      // Jaringan gagal di tengah — snapshot lokal (dengan filter yang sama)
      try {
        const cached = await getSnapshotAssets(activityId);
        if (!fresh()) return;
        const filtered = clientFilter ? clientFilter(cached) : cached;
        setTotal(filtered.length);
        setTruncated(false);
        setRows(filtered.filter((a) => parseCoord(a.koordinat_latitude) !== null && parseCoord(a.koordinat_longitude) !== null));
        setLoadedOnce(true);
        toast.info("Peta memakai data snapshot offline");
      } catch {
        if (fresh()) toast.error("Gagal memuat data peta");
      }
    } finally {
      if (fresh()) setLoading(false);
    }
  }, [activityId, buildParams, clientFilter]);

  // Muat data saat lembar peta dibuka.
  useEffect(() => { didFitRef.current = false; load(); }, [load]);

  // Unduh titik peta (KML/KMZ/SHP) lengkap dengan atribut — memakai filter
  // aktif yang SAMA dengan peta/daftar (endpoint /export/geo).
  const downloadGeo = useCallback((fmt) => {
    const params = buildParams ? buildParams() : new URLSearchParams();
    params.set("format", fmt);
    // Ada aset terpilih → ekspor HANYA yang terpilih (irisan filter ∩ pilihan).
    if (selectedIds && selectedIds.size > 0) {
      if (selectedIds.size > MAX_SELECTED_EXPORT) {
        toast.error(`Terlalu banyak aset terpilih untuk ekspor terseleksi (maks ${MAX_SELECTED_EXPORT}). Persempit pilihan, atau kosongkan seleksi untuk ekspor sesuai filter.`);
        return;
      }
      params.set("ids", Array.from(selectedIds).join(","));
    }
    const ext = fmt === "shp" ? "zip" : fmt;
    const fname = `peta_aset.${ext}`;
    downloadFileWithProgress(`${API}/export/geo?${params.toString()}`, fname, {
      label: `Peta Aset (${fmt.toUpperCase()})`,
      timeoutMessage: "Ekspor peta terlalu lama — coba persempit filter",
    }).catch(() => {});
  }, [buildParams, selectedIds]);

  // Kelompok Barang Serupa diturunkan dari data peta (kode+nama, ≥2 unit) —
  // ikut filter aktif dan tetap tersedia saat offline.
  const groups = useMemo(() => {
    const byKey = new Map();
    for (const r of rows) {
      const key = `${r.asset_code || ""}||${r.asset_name || ""}`;
      const g = byKey.get(key) || { key, code: r.asset_code || "-", name: r.asset_name || "-", count: 0 };
      g.count += 1;
      byKey.set(key, g);
    }
    // Tampilkan SEMUA kelompok terdeteksi (tak dibatasi) — daftar bisa digulir.
    // Dulu di-`slice(0, 100)` sehingga kelompok terbanyak-ke-101 dst. tak muncul.
    return Array.from(byKey.values()).filter((g) => g.count >= 2)
      .sort((a, b) => b.count - a.count);
  }, [rows]);

  // Baris yang tampil = baris peta, disaring: seleksi (bila ada) lalu kelompok
  // Barang Serupa. Ada aset terpilih di daftar → peta HANYA menampilkan pin
  // aset terpilih tersebut (juga berpengaruh ke unduh GIS terseleksi).
  const hasSelection = !!(selectedIds && selectedIds.size > 0);
  const selCount = selectedIds ? selectedIds.size : 0;
  const displayRows = useMemo(() => {
    let base = rows;
    // Di luar Mode Seleksi, seleksi daftar MENYARING peta (tampilkan yang
    // terpilih saja). Di dalam Mode Seleksi, tampilkan SEMUA agar pin lain
    // masih bisa ditambahkan/dilepas (yang terpilih ditandai cincin oranye).
    if (!selectMode && selectedIds && selectedIds.size > 0) base = rows.filter((r) => selectedIds.has(r.id));
    if (groupKey === "__semua__") return base;
    return base.filter((r) => `${r.asset_code || ""}||${r.asset_name || ""}` === groupKey);
  }, [rows, groupKey, selectedIds, selectMode]);

  // Pusatkan ulang peta saat seleksi dinyalakan/dimatikan (bukan tiap toggle).
  useEffect(() => { didFitRef.current = false; }, [hasSelection]);

  // ── Aksi seleksi (map → daftar via onSelectionChange, kunci = id aset) ──
  const doToggleOne = useCallback((id) => {
    onSelectionChange?.((prev) => {
      const next = new Set(prev || []);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, [onSelectionChange]);
  const doSelectMany = useCallback((ids) => {
    if (!ids || !ids.length) return;
    onSelectionChange?.((prev) => {
      const next = new Set(prev || []);
      ids.forEach((id) => next.add(id));
      return next;
    });
  }, [onSelectionChange]);
  const doSelectAllVisible = useCallback(() => {
    doSelectMany(displayRows.map((r) => r.id));
  }, [displayRows, doSelectMany]);
  const doClearSelection = useCallback(() => {
    onSelectionChange?.(() => new Set());
  }, [onSelectionChange]);
  // Ref agar handler leaflet (dibuat sekali) selalu memanggil versi terbaru.
  const toggleOneRef = useRef(doToggleOne);
  const selectManyRef = useRef(doSelectMany);
  useEffect(() => { toggleOneRef.current = doToggleOne; selectManyRef.current = doSelectMany; });

  // Ganti kelompok → pusatkan ulang peta ke pin kelompok tsb.
  const changeGroup = useCallback((v) => {
    setGroupKey(v);
    didFitRef.current = false;
  }, []);

  // Hidup/matikan clustering: bangun layer baru (cluster ↔ layer biasa) lalu
  // PINDAHKAN semua marker yang sudah ada ke layer itu — pin & popup tetap.
  const toggleCluster = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const on = !clusterOnRef.current;
    clusterOnRef.current = on;
    setClusterOn(on);
    const old = layerRef.current;
    const next = on ? buildClusterLayer(map) : L.layerGroup();
    for (const entry of markersRef.current.values()) {
      try { if (old) old.removeLayer(entry.marker); } catch { /* abaikan */ }
      next.addLayer(entry.marker);
    }
    if (old) map.removeLayer(old);
    next.addTo(map);
    layerRef.current = next;
  }, []);

  // Init peta pada mount; rusak saat unmount.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;
    // maxZoom 22 (di atas native OSM z19) agar pin yang berdekatan bisa
    // dipisahkan saat diperbesar; ubin OSM native mentok z19 → maxNativeZoom
    // memberi tahu Leaflet untuk MEMPERBESAR ubin z19 pada z20–22 (agak
    // buram tapi posisi pin makin presisi).
    // tapHold: tekan-lama di iOS Safari ikut memicu event contextmenu
    // (Android/desktop sudah bawaan) — dipakai TAMBAH CEPAT di titik peta.
    const map = L.map(containerRef.current, {
      zoomControl: true, attributionControl: true, maxZoom: 22, tapHold: true,
    });
    map.setView([-1.4, 116.7], 5); // fallback: kawasan IKN
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 22,
      maxNativeZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    // Grup marker ber-CLUSTER: pin yang saling MEPET (dalam ~44 px) dikumpulkan
    // jadi satu gelembung ber-angka; klik → perbesar ke area anggotanya, dan
    // di zoom maksimum pin yang bertindih di-SPIDERFY (dikipas) agar bisa
    // diklik satu per satu. Bisa dimatikan pengguna lewat tombol "Cluster".
    layerRef.current = (clusterOnRef.current ? buildClusterLayer(map) : L.layerGroup()).addTo(map);

    // ── Kontrol orientasi & skala (info saat zoom) ──
    // Bar skala metrik (meter/km) — tanpa imperial.
    L.control.scale({ metric: true, imperial: false, maxWidth: 140, position: "bottomleft" }).addTo(map);
    // Kompas arah utara (peta selalu menghadap utara / north-up).
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

    // ── "TAMPILKAN LOKASI ANDA": tombol di bawah kontrol zoom (topleft —
    //    kontrol menumpuk berurutan) → GPS perangkat → titik biru +
    //    lingkaran akurasi + pan ke lokasi; klik lagi = sembunyikan. ──
    const lokasiSaya = { marker: null, lingkaran: null, tombol: null, mencari: false };
    const IKON_LOKASI = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#0f172a" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><circle cx="12" cy="12" r="8"/></svg>';
    const hapusLokasiSaya = () => {
      if (lokasiSaya.marker) { map.removeLayer(lokasiSaya.marker); lokasiSaya.marker = null; }
      if (lokasiSaya.lingkaran) { map.removeLayer(lokasiSaya.lingkaran); lokasiSaya.lingkaran = null; }
    };
    const LokasiControl = L.Control.extend({
      onAdd() {
        const d = L.DomUtil.create("div", "leaflet-bar");
        const a = L.DomUtil.create("a", "", d);
        a.href = "#";
        a.title = "Tampilkan lokasi Anda";
        a.setAttribute("role", "button");
        a.setAttribute("aria-label", "Tampilkan lokasi Anda");
        a.setAttribute("data-testid", "peta-lokasi-saya");
        a.style.cssText = "display:flex;align-items:center;justify-content:center;width:30px;height:30px";
        a.innerHTML = IKON_LOKASI;
        lokasiSaya.tombol = a;
        L.DomEvent.disableClickPropagation(d);
        L.DomEvent.on(a, "click", (e) => {
          L.DomEvent.preventDefault(e);
          if (lokasiSaya.mencari) return;
          // Toggle: lokasi sedang tampil → sembunyikan.
          if (lokasiSaya.marker) { hapusLokasiSaya(); return; }
          lokasiSaya.mencari = true;
          a.style.opacity = "0.4";
          map.locate({ setView: false, enableHighAccuracy: true, timeout: 15000 });
        });
        return d;
      },
    });
    new LokasiControl({ position: "topleft" }).addTo(map);
    map.on("locationfound", (ev) => {
      lokasiSaya.mencari = false;
      if (lokasiSaya.tombol) lokasiSaya.tombol.style.opacity = "1";
      hapusLokasiSaya();
      const akurasi = Math.round(ev.accuracy || 0);
      lokasiSaya.lingkaran = L.circle(ev.latlng, {
        radius: ev.accuracy || 0, color: "#2563eb", weight: 1,
        fillColor: "#3b82f6", fillOpacity: 0.12, interactive: false,
      }).addTo(map);
      lokasiSaya.marker = L.marker(ev.latlng, {
        interactive: true,
        icon: L.divIcon({
          className: "",
          html: '<div style="width:16px;height:16px;border-radius:50%;background:#2563eb;border:3px solid #fff;box-shadow:0 0 0 2px rgba(37,99,235,.35),0 1px 4px rgba(0,0,0,.4)"></div>',
          iconSize: [16, 16], iconAnchor: [8, 8],
        }),
      }).addTo(map).bindTooltip(`Lokasi Anda (±${akurasi} m)`, { direction: "top" });
      // Pan + zoom secukupnya ke lokasi (jangan menjauh bila sudah dekat).
      map.setView(ev.latlng, Math.max(map.getZoom(), 17));
    });
    map.on("locationerror", (ev) => {
      lokasiSaya.mencari = false;
      if (lokasiSaya.tombol) lokasiSaya.tombol.style.opacity = "1";
      toast.error(ev?.message && /denied|ditolak/i.test(ev.message)
        ? "Izin lokasi ditolak — aktifkan izin lokasi browser untuk fitur ini"
        : "Gagal mendapatkan lokasi Anda — pastikan GPS aktif lalu coba lagi");
    });
    // Info skala nominal (1:N) + level zoom — diperbarui tiap zoom/geser.
    const scaleInfo = L.control({ position: "bottomleft" });
    scaleInfo.onAdd = () => {
      const d = L.DomUtil.create("div", "");
      d.style.cssText = "background:rgba(255,255,255,.9);padding:2px 7px;border-radius:6px;font:600 11px system-ui,sans-serif;color:#0f172a;box-shadow:0 1px 3px rgba(0,0,0,.25);margin-bottom:4px;white-space:nowrap";
      scaleInfoElRef.current = d;
      return d;
    };
    scaleInfo.addTo(map);
    const updateScaleInfo = () => {
      const el = scaleInfoElRef.current;
      if (!el) return;
      const z = map.getZoom();
      const lat = map.getCenter().lat;
      // meter per piksel pada lintang ini → skala nominal (piksel OGC 0,28mm).
      const mpp = 40075016.686 * Math.abs(Math.cos(lat * Math.PI / 180)) / Math.pow(2, z + 8);
      const ratio = Math.round(mpp / 0.00028);
      el.textContent = `Skala 1:${ratio.toLocaleString("id-ID")} · zoom ${z}`;
    };
    map.on("zoomend moveend", updateScaleInfo);
    updateScaleInfo();

    // ── TAMBAH CEPAT: klik kanan (desktop) / tekan lama (HP & tablet) di
    //    area peta → "+ Tambah aset di sini" → cukup ketik NAMA BARANG;
    //    kategori dummy + kode aset + NUP berurutan + "Belum
    //    Diinventarisasi" diisi otomatis (default halaman tambah aset) dan
    //    titik terbentuk di koordinat yang ditekan. ──
    map.on("contextmenu", (ev) => {
      if (!onQuickAddRef.current) return; // viewer / tanpa izin edit
      const { lat, lng } = ev.latlng;
      const wrap = L.DomUtil.create("div", "");
      wrap.style.cssText = "font:12px system-ui,sans-serif;min-width:216px";
      wrap.innerHTML =
        '<button type="button" data-aksi="tambah" data-testid="peta-tambah-disini" style="width:100%;display:flex;align-items:center;justify-content:center;gap:6px;background:#2563eb;color:#fff;border:0;border-radius:8px;padding:9px 10px;font-weight:700;font-size:12px;cursor:pointer">＋ Tambah aset di sini</button>' +
        `<div style="margin-top:5px;color:#64748b;font-size:10px;text-align:center">${lat.toFixed(6)}, ${lng.toFixed(6)}</div>`;
      // Popup TIDAK boleh tertutup oleh apa pun selain tombol tutup /
      // selesai simpan: closeOnClick & autoClose DIMATIKAN dan SEMUA event
      // dari isi popup dihentikan sebelum mencapai peta — klik/ketukan ke
      // input (serta resize akibat keyboard virtual HP + klik sintesisnya)
      // sebelumnya dianggap interaksi peta (preclick Leaflet) sehingga
      // popup hilang saat mulai mengetik nama.
      const popup = L.popup({ closeButton: true, autoClose: false,
                              closeOnClick: false, className: "aman-peta-tambah" })
        .setLatLng(ev.latlng).setContent(wrap).openOn(map);
      L.DomEvent.disableClickPropagation(wrap);
      L.DomEvent.disableScrollPropagation(wrap);
      L.DomEvent.on(wrap,
        "pointerdown mousedown touchstart touchend mouseup click dblclick contextmenu keydown keyup keypress wheel",
        L.DomEvent.stopPropagation);
      wrap.querySelector('[data-aksi="tambah"]').addEventListener("click", () => {
        wrap.innerHTML =
          '<p style="margin:0 0 6px;font-weight:700;color:#0f172a">Aset baru di titik ini</p>' +
          '<input data-isi="nama" data-testid="peta-tambah-nama" placeholder="Nama barang…" autocomplete="off" style="width:100%;box-sizing:border-box;border:1.5px solid #cbd5e1;border-radius:8px;padding:8px 10px;font-size:13px;outline:none;color:#0f172a;background:#fff" />' +
          // Foto opsional — ATURAN SAMA dengan form aset: maks 6, kompresi
          // klien, multi-upload; foto pertama jadi sampul; ada foto →
          // status inventarisasi otomatis "Ditemukan".
          '<div style="display:flex;align-items:center;gap:6px;margin-top:7px">' +
          '<button type="button" data-aksi="kamera" style="flex:1;background:#f1f5f9;color:#0f172a;border:1px solid #cbd5e1;border-radius:8px;padding:7px 6px;font-weight:600;font-size:11px;cursor:pointer">📷 Kamera</button>' +
          '<button type="button" data-aksi="galeri" data-testid="peta-tambah-foto" style="flex:1;background:#f1f5f9;color:#0f172a;border:1px solid #cbd5e1;border-radius:8px;padding:7px 6px;font-weight:600;font-size:11px;cursor:pointer">🖼 Pilih Foto</button>' +
          '<span data-isi="jumlah" style="color:#64748b;font-size:10px;white-space:nowrap">0/6</span>' +
          '</div>' +
          '<input type="file" accept="image/*" capture="environment" data-isi="in-kamera" style="display:none" />' +
          '<input type="file" accept="image/*" multiple data-isi="in-galeri" style="display:none" />' +
          '<div data-isi="pratinjau" style="display:flex;gap:4px;flex-wrap:wrap;margin-top:6px"></div>' +
          '<p style="margin:6px 0;color:#64748b;font-size:10px;line-height:1.4">Kategori dummy + NUP & status inventarisasi terisi otomatis — lengkapi detail lain nanti dari daftar aset.</p>' +
          '<button type="button" data-aksi="simpan" data-testid="peta-tambah-simpan" style="width:100%;background:#059669;color:#fff;border:0;border-radius:8px;padding:9px 10px;font-weight:700;font-size:12px;cursor:pointer">Simpan Titik Aset</button>';
        const input = wrap.querySelector('[data-isi="nama"]');
        const inKamera = wrap.querySelector('[data-isi="in-kamera"]');
        const inGaleri = wrap.querySelector('[data-isi="in-galeri"]');
        const elJumlah = wrap.querySelector('[data-isi="jumlah"]');
        const elPratinjau = wrap.querySelector('[data-isi="pratinjau"]');
        const btnSimpan = wrap.querySelector('[data-aksi="simpan"]');
        const fotos = [];
        let memproses = false;
        const gambarUlangPratinjau = () => {
          elJumlah.textContent = memproses ? "memproses…" : `${fotos.length}/6`;
          elPratinjau.innerHTML = "";
          fotos.forEach((f, i) => {
            const kotak = document.createElement("div");
            kotak.style.cssText = "position:relative;width:40px;height:40px";
            kotak.innerHTML =
              `<img src="${f}" alt="" style="width:40px;height:40px;object-fit:cover;border-radius:6px;border:1px solid #cbd5e1" />` +
              '<button type="button" style="position:absolute;top:-6px;right:-6px;width:16px;height:16px;border-radius:50%;background:#dc2626;color:#fff;border:0;font-size:10px;line-height:1;cursor:pointer;padding:0">×</button>';
            kotak.querySelector("button").addEventListener("click", () => {
              fotos.splice(i, 1);
              gambarUlangPratinjau();
            });
            elPratinjau.appendChild(kotak);
          });
        };
        const tambahBerkas = async (files) => {
          const daftar = Array.from(files || []);
          if (!daftar.length) return;
          if (fotos.length >= 6) { toast.error("Maks 6 foto"); return; }
          memproses = true;
          btnSimpan.disabled = true;
          btnSimpan.style.opacity = "0.6";
          gambarUlangPratinjau();
          for (const file of daftar) {
            if (fotos.length >= 6) { toast.error("Maks 6 foto — sisanya dilewati"); break; }
            try {
              fotos.push(await compressImageFile(file));
            } catch { toast.error(`Gagal memproses ${file.name || "foto"}`); }
          }
          memproses = false;
          btnSimpan.disabled = false;
          btnSimpan.style.opacity = "1";
          gambarUlangPratinjau();
        };
        wrap.querySelector('[data-aksi="kamera"]').addEventListener("click", () => inKamera.click());
        wrap.querySelector('[data-aksi="galeri"]').addEventListener("click", () => inGaleri.click());
        inKamera.addEventListener("change", (fe) => { tambahBerkas(fe.target.files); fe.target.value = ""; });
        inGaleri.addEventListener("change", (fe) => { tambahBerkas(fe.target.files); fe.target.value = ""; });
        const simpan = () => {
          if (memproses) return;
          const nama = (input.value || "").trim();
          if (!nama) { input.style.borderColor = "#dc2626"; input.focus(); return; }
          onQuickAddRef.current?.(lat, lng, nama, fotos.slice());
          map.closePopup(popup);
          // Marker SEMENTARA (biru pudar) — pin final tampil setelah antrean
          // simpan tersinkron dan peta dimuat ulang.
          L.marker([lat, lng], { icon: markerIcon("#2563eb", fotos.length > 0, false), opacity: 0.75 })
            .addTo(map)
            .bindTooltip(`${nama} — tersimpan di antrean`, { direction: "top" });
        };
        btnSimpan.addEventListener("click", simpan);
        input.addEventListener("keydown", (ke) => {
          ke.stopPropagation(); // jangan sampai memicu pintasan keyboard peta
          if (ke.key === "Enter") simpan();
        });
        setTimeout(() => input.focus(), 80);
      });
    });

    mapRef.current = map;
    setTimeout(() => map.invalidateSize(), 60);
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => map.invalidateSize()) : null;
    if (ro) ro.observe(containerRef.current);
    return () => {
      if (ro) ro.disconnect();
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
      markersRef.current = new Map();
    };
  }, []);

  // Versi terbaru pasca-simpan (best-effort): antrean menyimpan async, jadi
  // versi server diambil sesaat kemudian agar drag berikutnya memakai
  // If-Match yang benar (baris peta bisa di luar halaman list).
  const refreshRowVersion = useCallback((id) => {
    if (!navigator.onLine) return;
    setTimeout(async () => {
      try {
        const r = await axios.get(`${API}/assets/${id}`, { params: { exclude_media: true } });
        const v = r.data?.version;
        if (v != null) setRows((prev) => prev.map((x) => (x.id === id ? { ...x, version: v } : x)));
      } catch { /* best-effort */ }
    }, 2500);
  }, []);

  // Konten popup dibangun ulang tiap dibuka (data baris terbaru dari entry).
  // Tata letak padat: bingkai foto (bila ada) + identitas, pill status/kondisi
  // berwarna, baris info berlabel, koordinat, tombol Edit selebar popup.
  const buildPopupEl = useCallback((entry) => {
    const row = entry.row;
    // Aset sudah dihapus (pin bersilang) → popup ringkas tanpa aksi.
    if (entry.deleted) {
      const elHapus = document.createElement("div");
      elHapus.style.cssText = "width:200px;line-height:1.4";
      elHapus.innerHTML = `
        <div style="font-weight:700;font-size:12.5px;color:#0f172a">${esc(row.asset_name || "-")}</div>
        <div style="font-size:10.5px;color:#64748b;margin-top:2px">${esc(row.asset_code || "-")}${row.NUP ? ` &bull; NUP ${esc(row.NUP)}` : ""}</div>
        <div style="margin-top:7px;padding:6px 8px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;color:#b91c1c;font-size:11px;font-weight:600">Aset ini telah dihapus.</div>`;
      return elHapus;
    }
    const lat = parseCoord(row.koordinat_latitude);
    const lng = parseCoord(row.koordinat_longitude);
    const photoCount = Number(row.photo_count) || 0;
    const status = row.inventory_status || "Belum Diinventarisasi";
    const statusColor = STATUS_COLORS[status] || STATUS_COLORS["Belum Diinventarisasi"];
    const condColor = CONDITION_COLORS[row.condition] || "#64748b";

    const el = document.createElement("div");
    el.style.cssText = "width:232px;line-height:1.35";

    // ── Kepala: bingkai foto (hanya bila aset punya foto) + nama/kode ──
    const head = document.createElement("div");
    head.style.cssText = "display:flex;gap:8px;align-items:flex-start";
    // Sumber gambar: online = streaming 256px (ter-cache browser); offline =
    // thumbnail sampul yang ikut snapshot. Tanpa keduanya → tanpa bingkai,
    // blok judul otomatis melebar (flex).
    const coverSrc = navigator.onLine
      ? authMediaUrl(`${API}/assets/${row.id}/photos/${row.thumbnail_index || 0}?v=${row.version || 1}&w=256`)
      : (row.thumbnail || "");
    if (photoCount > 0 && coverSrc) {
      const frame = document.createElement("div");
      frame.style.cssText = "position:relative;width:62px;height:62px;flex:0 0 62px;border-radius:10px;overflow:hidden;border:2px solid #e2e8f0;box-shadow:0 1px 3px rgba(15,23,42,.18);background:#f1f5f9";
      const img = document.createElement("img");
      img.alt = "";
      img.loading = "lazy";
      img.style.cssText = "width:100%;height:100%;object-fit:cover;display:block";
      const fallback = row.thumbnail || "";
      img.onerror = () => {
        // Streaming gagal (token/jaringan) → pakai thumbnail snapshot;
        // tanpa cadangan → lepas bingkai supaya tak ada kotak kosong.
        if (fallback && img.src !== fallback) img.src = fallback;
        else frame.remove();
      };
      img.src = coverSrc;
      frame.appendChild(img);
      if (photoCount > 1) {
        const badge = document.createElement("span");
        badge.textContent = `${photoCount} foto`;
        badge.style.cssText = "position:absolute;bottom:3px;right:3px;background:rgba(15,23,42,.78);color:#fff;font-size:8.5px;font-weight:700;padding:1px 5px;border-radius:6px";
        frame.appendChild(badge);
      }
      // Klik bingkai foto → buka lightbox yang SAMA seperti mode galeri.
      frame.style.cursor = "zoom-in";
      frame.title = "Klik untuk memperbesar foto";
      frame.addEventListener("click", (e) => {
        e.stopPropagation();
        onPhotoClickRef.current?.(entry.row);
      });
      head.appendChild(frame);
    }
    const title = document.createElement("div");
    title.style.cssText = "min-width:0;flex:1";
    title.innerHTML = `
      <div style="font-weight:700;font-size:12.5px;color:#0f172a;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">${esc(row.asset_name || "-")}</div>
      <div style="font-size:10.5px;color:#64748b;margin-top:2px">${esc(row.asset_code || "-")}${row.NUP ? ` &bull; NUP ${esc(row.NUP)}` : ""}</div>`;
    head.appendChild(title);
    el.appendChild(head);

    // ── Pill status inventarisasi + kondisi + kelengkapan pengguna ──
    const pill = (text, color) =>
      `<span style="display:inline-flex;align-items:center;padding:2px 7px;border-radius:999px;font-size:9.5px;font-weight:700;background:${color}1a;color:${color};border:1px solid ${color}40">${esc(text)}</span>`;
    const badges = document.createElement("div");
    badges.style.cssText = "display:flex;flex-wrap:wrap;gap:4px;margin-top:7px";
    badges.innerHTML = pill(status, statusColor)
      + (row.condition ? pill(row.condition, condColor) : "")
      + (isPenggunaComplete(row) ? pill("Pengguna lengkap ✓", "#16a34a") : "");
    el.appendChild(badges);

    // ── Baris info berlabel — hanya yang terisi, supaya tetap padat ──
    const infoRows = [
      ["Merk/Tipe", [row.brand, row.model].filter((v) => String(v || "").trim()).join(" — ")],
      ["Kategori", row.category],
      ["Lokasi", row.location],
      ["Pengguna", String(row.user || "").trim()
        ? `${row.user}${String(row.pengguna_nip || "").trim() ? ` · ${row.pengguna_nip}` : ""}`
        : ""],
    ].filter(([, v]) => String(v || "").trim());
    if (infoRows.length > 0) {
      const info = document.createElement("div");
      info.style.cssText = "margin-top:7px;padding-top:6px;border-top:1px solid #f1f5f9";
      info.innerHTML = infoRows.map(([label, value]) => `
        <div style="display:flex;gap:6px;font-size:10.5px;margin-top:2px">
          <span style="flex:0 0 56px;color:#94a3b8">${esc(label)}</span>
          <span style="min-width:0;color:#334155;font-weight:500;word-break:break-word">${esc(value)}</span>
        </div>`).join("");
      el.appendChild(info);
    }

    // ── Koordinat + tombol Edit ──
    const coords = document.createElement("div");
    coords.style.cssText = "font-family:ui-monospace,SFMono-Regular,monospace;font-size:9.5px;color:#94a3b8;margin-top:6px";
    coords.textContent = `${lat?.toFixed(6)}, ${lng?.toFixed(6)}`;
    el.appendChild(coords);
    if (onEditRef.current || onDeleteRef.current) {
      const aksi = document.createElement("div");
      aksi.style.cssText = "display:flex;gap:6px;margin-top:7px";
      if (onEditRef.current) {
        const btn = document.createElement("button");
        btn.textContent = "Edit Aset";
        btn.style.cssText = "display:block;flex:1;min-width:0;padding:7px 0;background:#2563eb;color:#fff;border:none;border-radius:8px;font-size:11.5px;font-weight:700;cursor:pointer";
        btn.addEventListener("click", () => {
          entry.marker.closePopup();
          onEditRef.current?.(entry.row); // peta tetap terbuka — form edit muncul di atas/sampingnya
        });
        aksi.appendChild(btn);
      }
      if (onDeleteRef.current) {
        // Ikon hapus: langsung menghapus aset (konfirmasi + guard online di
        // handler dashboard yang sama dengan daftar). Sukses → pin diberi
        // tanda silang, popup ditutup.
        const del = document.createElement("button");
        del.title = "Hapus aset ini";
        del.setAttribute("data-testid", "map-delete-asset");
        del.setAttribute("aria-label", "Hapus aset");
        del.style.cssText = "flex:0 0 44px;display:flex;align-items:center;justify-content:center;padding:7px 0;background:#fee2e2;color:#dc2626;border:1px solid #fecaca;border-radius:8px;cursor:pointer";
        del.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>`;
        del.addEventListener("click", async () => {
          if (del.disabled) return;
          del.disabled = true;
          try {
            const ok = await onDeleteRef.current?.(entry.row.id);
            if (!ok) return; // batal / offline / gagal — toast dari handler
            entry.deleted = true;
            deletedIdsRef.current.add(entry.row.id);
            entry.iconKey = "dihapus";
            entry.marker.setIcon(markerIcon("", false, false, true));
            entry.marker.dragging?.disable?.();
            entry.draggable = false;
            entry.marker.closePopup();
          } finally { del.disabled = false; }
        });
        aksi.appendChild(del);
      }
      el.appendChild(aksi);
    }
    return el;
  }, []);

  // Sinkronkan pin secara INKREMENTAL — tidak clearLayers() setiap perubahan,
  // supaya drag pin lain yang sedang berlangsung & popup terbuka tidak mati.
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    const seen = new Set();
    const bounds = [];

    for (const row of displayRows) {
      const lat = parseCoord(row.koordinat_latitude);
      const lng = parseCoord(row.koordinat_longitude);
      if (lat === null || lng === null) continue;
      // Aset yang dihapus lewat popup: pin bersilang dipertahankan apa
      // adanya (jangan di-reset ikon/drag-nya oleh sinkronisasi data).
      if (deletedIdsRef.current.has(row.id)) {
        seen.add(row.id);
        continue;
      }
      seen.add(row.id);
      bounds.push([lat, lng]);
      const color = STATUS_COLORS[row.inventory_status] || STATUS_COLORS["Belum Diinventarisasi"];
      const hasPhoto = rowHasPhoto(row);
      const complete = isPenggunaComplete(row);
      const selected = !!(selectedIds && selectedIds.has(row.id));
      const iconKey = `${color}|${hasPhoto}|${complete}|${selected}`;
      const existing = markersRef.current.get(row.id);

      if (existing) {
        existing.row = row; // handler membaca entry.row → selalu data terbaru
        const dragging = existing.marker.dragging && existing.marker.dragging.moving && existing.marker.dragging.moving();
        if (!dragging && (existing.lat !== lat || existing.lng !== lng)) {
          existing.marker.setLatLng([lat, lng]);
          layer.refreshClusters?.(existing.marker); // beri tahu cluster posisi berubah
        }
        existing.lat = lat; existing.lng = lng;
        if (existing.iconKey !== iconKey) { existing.marker.setIcon(markerIcon(color, hasPhoto, complete, false, selected)); existing.iconKey = iconKey; }
        if (existing.draggable !== canEdit && existing.marker.dragging) {
          if (canEdit) existing.marker.dragging.enable(); else existing.marker.dragging.disable();
          existing.draggable = canEdit;
        }
        continue;
      }

      const marker = L.marker([lat, lng], { icon: markerIcon(color, hasPhoto, complete, false, selected), draggable: !!canEdit });
      const entry = { marker, row, lat, lng, iconKey, draggable: !!canEdit };
      // SATU popup per pin (tanpa tooltip hover — dulu tooltip + popup tampil
      // bertumpuk saat pin diketuk di layar sentuh). Dalam Mode Seleksi, klik
      // pin = pilih/lepas (bukan buka popup) — kendali klik diambil alih di
      // bawah (buang auto-open bawaan leaflet agar tak bentrok).
      marker.bindPopup(() => buildPopupEl(entry));
      if (marker._openPopup) marker.off("click", marker._openPopup, marker);
      marker.on("click", () => {
        if (selectModeRef.current && toggleOneRef.current) toggleOneRef.current(entry.row.id);
        else marker.openPopup();
      });

      marker.on("dragend", () => {
        const ll = marker.getLatLng();
        const newLat = ll.lat.toFixed(6);
        const newLng = ll.lng.toFixed(6);
        try {
          onSaveRef.current?.(entry.row, newLat, newLng);
        } catch {
          // Ditolak (baris terkunci / sedang dibuka di form) → kembalikan pin
          marker.setLatLng([entry.lat, entry.lng]);
          return;
        }
        entry.lat = parseFloat(newLat); entry.lng = parseFloat(newLng);
        layerRef.current?.refreshClusters?.(marker); // posisi baru → cluster diperbarui
        setRows((prev) => prev.map((r) => (r.id === entry.row.id
          ? { ...r, koordinat_latitude: newLat, koordinat_longitude: newLng }
          : r)));
        toast.success(navigator.onLine
          ? `Koordinat "${entry.row.asset_name || entry.row.asset_code}" tersimpan`
          : `Koordinat "${entry.row.asset_name || entry.row.asset_code}" masuk antrean — tersinkron saat online`);
        refreshRowVersion(entry.row.id);
      });

      marker.addTo(layer);
      markersRef.current.set(row.id, entry);
    }

    // Buang pin milik baris yang tak tampil (filter kelompok/filter berubah).
    // KECUALI pin bersilang (aset baru dihapus): dibiarkan tampil sebagai
    // jejak visual sampai peta ditutup, meski barisnya hilang dari data.
    for (const [id, entry] of Array.from(markersRef.current.entries())) {
      if (!seen.has(id)) {
        if (deletedIdsRef.current.has(id)) continue;
        layer.removeLayer(entry.marker); // dari cluster group (bukan .remove())
        markersRef.current.delete(id);
      }
    }

    if (bounds.length > 0 && !didFitRef.current) {
      didFitRef.current = true;
      // Batasi auto-fit di z19 (native OSM) agar tidak langsung buram;
      // pengguna dapat memperbesar manual hingga z22 untuk memisahkan pin.
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 19 });
    }
  }, [displayRows, canEdit, buildPopupEl, refreshRowVersion, selectedIds]);

  // Mode Seleksi mematikan box-zoom bawaan Shift+seret (kita pakai Shift+seret
  // untuk KOTAK SELEKSI). Dipulihkan saat mode dimatikan.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.boxZoom) return;
    if (selectMode) map.boxZoom.disable(); else map.boxZoom.enable();
    return () => { try { mapRef.current?.boxZoom?.enable(); } catch { /* map dilepas */ } };
  }, [selectMode]);

  // Bilah Mode Seleksi / "Pilih Area" muncul-hilang DI ATAS peta → kanvas
  // leaflet bergeser & lebarnya bisa berubah (scrollbar). Hitung ulang ukuran
  // setelah tata letak mengendap (rAF + fallback timeout) agar ubin tak basi.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return undefined;
    const recalc = () => { try { map.invalidateSize({ animate: false }); } catch { /* map dilepas */ } };
    const raf = requestAnimationFrame(recalc);
    const t = setTimeout(recalc, 160);
    return () => { cancelAnimationFrame(raf); clearTimeout(t); };
  }, [selectMode, drawArea]);

  // Kursor crosshair saat Mode Seleksi — DISETEL LEWAT REF (inline style), BUKAN
  // className React. Elemen kanvas ini juga dikelola Leaflet (menambah kelas
  // .leaflet-container/.leaflet-fade-anim dll.); bila className-nya diubah React
  // saat mode berganti, seluruh kelas Leaflet TERTIMPA → basemap hilang &
  // hanya marker tersisa. Menyetel style.cursor tak menyentuh daftar kelas.
  useEffect(() => {
    const el = containerRef.current;
    if (el) el.style.cursor = selectMode ? "crosshair" : "";
  }, [selectMode]);

  // Kotak seleksi (rubber-band) berbasis Pointer Events → jalan di PC (Shift+
  // seret) maupun HP (tombol "Pilih Area" lalu seret satu jari). Semua pin di
  // dalam kotak ditambahkan ke seleksi. Pan peta dinonaktifkan selama menggambar.
  useEffect(() => {
    const wrap = mapWrapRef.current;
    const map = mapRef.current;
    if (!wrap || !map) return;
    let active = false, startX = 0, startY = 0, boxEl = null, capId = null;
    const shouldStart = (e) => selectModeRef.current && (e.shiftKey || drawAreaRef.current);
    // Jangan mulai kotak bila menekan PIN/popup/kontrol (biarkan klik pin =
    // pilih/lepas). Kotak hanya dari area kosong peta.
    const onControlOrMarker = (e) => {
      const t = e.target;
      return !!(t && t.closest && (t.closest(".leaflet-marker-icon") || t.closest(".leaflet-popup") || t.closest(".leaflet-control") || t.closest(".leaflet-marker-pane")));
    };
    const rectOf = () => wrap.getBoundingClientRect();
    const onDown = (e) => {
      if (active || !shouldStart(e) || onControlOrMarker(e)) return;
      if (e.pointerType === "mouse" && e.button !== 0) return;
      const r = rectOf();
      active = true; startX = e.clientX - r.left; startY = e.clientY - r.top;
      try { map.dragging.disable(); } catch { /* noop */ }
      boxEl = document.createElement("div");
      boxEl.style.cssText = "position:absolute;z-index:650;pointer-events:none;border:2px dashed #f59e0b;background:rgba(245,158,11,.14);border-radius:4px;left:" + startX + "px;top:" + startY + "px;width:0;height:0;";
      wrap.appendChild(boxEl);
      capId = e.pointerId;
      try { wrap.setPointerCapture(capId); } catch { /* noop */ }
      e.preventDefault();
    };
    const onMove = (e) => {
      if (!active || !boxEl) return;
      const r = rectOf();
      const x = e.clientX - r.left, y = e.clientY - r.top;
      boxEl.style.left = Math.min(startX, x) + "px";
      boxEl.style.top = Math.min(startY, y) + "px";
      boxEl.style.width = Math.abs(x - startX) + "px";
      boxEl.style.height = Math.abs(y - startY) + "px";
    };
    const onUp = (e) => {
      if (!active) return;
      active = false;
      try { map.dragging.enable(); } catch { /* noop */ }
      try { if (capId != null) wrap.releasePointerCapture(capId); } catch { /* noop */ }
      const r = rectOf();
      const x = e.clientX - r.left, y = e.clientY - r.top;
      const moved = Math.abs(x - startX) > 6 || Math.abs(y - startY) > 6;
      if (boxEl) { boxEl.remove(); boxEl = null; }
      if (drawAreaRef.current) setDrawArea(false); // sekali pakai (HP)
      if (!moved) return; // ketukan kecil → biarkan handler pin yang tangani
      const p1 = map.containerPointToLatLng([Math.min(startX, x), Math.min(startY, y)]);
      const p2 = map.containerPointToLatLng([Math.max(startX, x), Math.max(startY, y)]);
      const b = L.latLngBounds(p1, p2);
      const ids = [];
      for (const entry of markersRef.current.values()) {
        if (deletedIdsRef.current.has(entry.row.id)) continue;
        if (b.contains([entry.lat, entry.lng])) ids.push(entry.row.id);
      }
      if (ids.length) { selectManyRef.current?.(ids); toast.success(`${ids.length} pin terpilih dari area`); }
      else toast.info("Tidak ada pin di dalam area itu");
    };
    wrap.addEventListener("pointerdown", onDown);
    wrap.addEventListener("pointermove", onMove);
    wrap.addEventListener("pointerup", onUp);
    wrap.addEventListener("pointercancel", onUp);
    return () => {
      wrap.removeEventListener("pointerdown", onDown);
      wrap.removeEventListener("pointermove", onMove);
      wrap.removeEventListener("pointerup", onUp);
      wrap.removeEventListener("pointercancel", onUp);
      if (boxEl) boxEl.remove();
    };
  }, []);

  return (
    <div className="space-y-2" data-testid="asset-map-fullview">
      {/* ── Bar peta: info + filter kelompok + unduh + tutup ──
          HP: SATU baris — [ikon · judul · menu gabungan · tutup]; filter
          Barang Serupa + Unduh + Muat Ulang dilebur ke SATU tombol ber-menu
          (ikonnya menandai filter aktif). sm+ tetap kontrol terpisah. */}
      <div className="bg-card rounded-xl border border-border shadow-sm p-1.5 sm:p-2 flex items-center gap-1.5 sm:gap-2 flex-wrap">
        <span className="w-8 h-8 rounded-lg bg-teal-600 flex items-center justify-center flex-shrink-0">
          <MapPinned className="w-4 h-4 text-white" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold text-foreground leading-tight">Peta Aset</p>
          <p className="text-[11px] text-muted-foreground truncate">
            {loadedOnce
              ? (
                <>
                  <span className="sm:hidden">
                    <span className="font-semibold text-foreground/80">{displayRows.length}</span>/{total} titik{hasSelection ? " · terpilih" : activeFilterCount > 0 ? " · terfilter" : ""}{truncated ? " · belum semua termuat" : ""}
                  </span>
                  <span className="hidden sm:inline">
                    <span className="font-semibold text-foreground/80">{displayRows.length}</span> titik {hasSelection ? "aset terpilih" : `dari ${total} aset${activeFilterCount > 0 ? " (terfilter)" : ""}`}{truncated ? " — sebagian belum dimuat" : ""}
                  </span>
                </>
              )
              : (activityName || "Memuat…")}
          </p>
        </div>
        {/* ── Menu gabungan (hanya HP): Barang Serupa + Unduh + Muat Ulang
            dalam satu tombol — ikon Layers menyala violet + titik penanda
            saat filter kelompok aktif ── */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label="Menu peta: filter barang serupa, unduh, muat ulang"
              className="relative h-9 px-2 rounded-lg border border-border flex sm:hidden items-center gap-0.5 hover:bg-muted flex-shrink-0"
              data-testid="asset-map-mobile-menu"
            >
              {loading
                ? <Loader2 className="w-4 h-4 animate-spin text-teal-600" />
                : <Layers className={`w-4 h-4 ${groupKey !== "__semua__" ? "text-violet-500" : "text-muted-foreground"}`} />}
              {groupKey !== "__semua__" && (
                <span className="absolute top-1.5 right-5 w-1.5 h-1.5 rounded-full bg-violet-500" aria-hidden="true" />
              )}
              <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-72">
            {groups.length > 0 && (
              <>
                <DropdownMenuLabel className="text-[11px] flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-violet-500" />Barang Serupa ({groups.length} jenis)
                </DropdownMenuLabel>
                <div className="max-h-60 overflow-y-auto">
                  <DropdownMenuRadioGroup value={groupKey} onValueChange={changeGroup}>
                    <DropdownMenuRadioItem className="min-h-[42px] border-b border-border/60" value="__semua__" data-testid="map-menu-group-all">Semua barang</DropdownMenuRadioItem>
                    {groups.map((g) => (
                      <DropdownMenuRadioItem className="min-h-[42px] border-b border-border/40 last:border-b-0" key={g.key} value={g.key}>
                        <span className="flex items-center gap-2 w-full">
                          <span className="font-mono text-[10px] text-muted-foreground shrink-0">{g.code}</span>
                          <span className="flex-1 truncate">{g.name}</span>
                          <span className="text-[10px] font-semibold text-violet-600 dark:text-violet-400 shrink-0">{g.count} unit</span>
                        </span>
                      </DropdownMenuRadioItem>
                    ))}
                  </DropdownMenuRadioGroup>
                </div>
                <DropdownMenuSeparator />
              </>
            )}
            <DropdownMenuLabel className="text-[11px] flex items-center gap-1.5">
              <Download className="w-3.5 h-3.5 text-muted-foreground" />Unduh Titik Peta
            </DropdownMenuLabel>
            <DropdownMenuItem className="min-h-[42px]" onClick={() => downloadGeo("kml")} data-testid="map-menu-kml">KML (Google Earth)</DropdownMenuItem>
            <DropdownMenuItem className="min-h-[42px]" onClick={() => downloadGeo("kmz")} data-testid="map-menu-kmz">KMZ (terkompresi)</DropdownMenuItem>
            <DropdownMenuItem className="min-h-[42px]" onClick={() => downloadGeo("shp")} data-testid="map-menu-shp">SHP (Shapefile ZIP)</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="min-h-[42px]" onClick={() => { didFitRef.current = false; load(); }} disabled={loading} data-testid="map-menu-refresh">
              <RefreshCw className="w-4 h-4 mr-2" />Muat Ulang Peta
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="min-h-[42px]" onClick={toggleCluster} data-testid="map-menu-cluster-toggle">
              <Boxes className={`w-4 h-4 mr-2 ${clusterOn ? "text-blue-600 dark:text-blue-400" : "text-muted-foreground"}`} />
              Pengelompokan Marker: {clusterOn ? "Aktif" : "Mati"}
            </DropdownMenuItem>
            {canSelect && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="min-h-[42px]" onClick={() => setSelectMode((v) => { if (v) setDrawArea(false); return !v; })} data-testid="map-menu-select-toggle">
                  <MousePointerClick className={`w-4 h-4 mr-2 ${selectMode ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground"}`} />
                  Mode Seleksi: {selectMode ? "Aktif" : "Mati"}
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
        <button
          type="button"
          onClick={onClose}
          aria-label="Tutup peta"
          className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0 sm:order-last"
          data-testid="asset-map-close"
        >
          <X className="w-4 h-4" />
        </button>
        {activeFilterCount > 0 && (
          <span className="hidden md:flex items-center gap-1 px-2 h-7 rounded-full bg-blue-600/10 text-blue-600 dark:text-blue-400 text-[11px] font-semibold flex-shrink-0" data-testid="asset-map-filter-badge">
            <Filter className="w-3 h-3" />{activeFilterCount} filter
          </span>
        )}
        {/* Filter Barang Serupa (≥sm) — di HP menyatu ke menu gabungan */}
        {groups.length > 0 && (
          <Select value={groupKey} onValueChange={changeGroup}>
            <SelectTrigger className="hidden sm:flex h-9 w-auto max-w-[240px] px-2 text-[11px] gap-1 flex-shrink-0" aria-label="Filter barang serupa" data-testid="asset-map-group-filter">
              <Layers className="w-3.5 h-3.5 text-violet-500 flex-shrink-0" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="max-h-80 min-w-[280px]">
              <SelectItem value="__semua__" className="border-b border-border/60">Semua barang ({groups.length} jenis)</SelectItem>
              {groups.map((g) => (
                <SelectItem key={g.key} value={g.key} className="border-b border-border/40 last:border-b-0">
                  <span className="flex items-center gap-2 w-full">
                    <span className="font-mono text-[10px] text-muted-foreground shrink-0">{g.code}</span>
                    <span className="flex-1 truncate">{g.name}</span>
                    <span className="text-[10px] font-semibold text-violet-600 dark:text-violet-400 shrink-0">{g.count} unit</span>
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="h-9 px-2.5 rounded-lg border border-border text-xs font-medium text-foreground/80 hidden sm:flex items-center gap-1 hover:bg-muted flex-shrink-0"
              data-testid="asset-map-download"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Unduh</span>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-44">
            <DropdownMenuItem onClick={() => downloadGeo("kml")} data-testid="map-download-kml">
              <MapPinned className="w-4 h-4 mr-2" />KML (Google Earth)
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => downloadGeo("kmz")} data-testid="map-download-kmz">
              <MapPinned className="w-4 h-4 mr-2" />KMZ (terkompresi)
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => downloadGeo("shp")} data-testid="map-download-shp">
              <MapPinned className="w-4 h-4 mr-2" />SHP (Shapefile ZIP)
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        {canSelect && (
          <button
            type="button"
            onClick={() => setSelectMode((v) => { if (v) setDrawArea(false); return !v; })}
            aria-pressed={selectMode}
            className={`h-9 px-2.5 rounded-lg border text-xs font-semibold hidden sm:flex items-center justify-center gap-1 flex-shrink-0 transition-colors ${
              selectMode
                ? "border-amber-500 bg-amber-500/10 text-amber-600 dark:text-amber-400"
                : "border-border text-foreground/80 hover:bg-muted"
            }`}
            aria-label={selectMode ? "Matikan mode seleksi" : "Hidupkan mode seleksi pin"}
            title={selectMode ? "Klik pin = pilih/lepas · Shift+seret = kotak seleksi" : "Pilih beberapa pin untuk Edit Massal"}
            data-testid="asset-map-select-toggle"
          >
            <MousePointerClick className="w-3.5 h-3.5" />
            <span>{selectMode ? "Mode Seleksi: Aktif" : "Mode Seleksi"}</span>
          </button>
        )}
        <button
          type="button"
          onClick={toggleCluster}
          aria-pressed={clusterOn}
          className={`h-9 px-2.5 rounded-lg border text-xs font-medium hidden sm:flex items-center justify-center gap-1 flex-shrink-0 transition-colors ${
            clusterOn
              ? "border-blue-500 bg-blue-500/10 text-blue-600 dark:text-blue-400"
              : "border-border text-foreground/80 hover:bg-muted"
          }`}
          aria-label={clusterOn ? "Matikan pengelompokan marker" : "Hidupkan pengelompokan marker"}
          title={clusterOn ? "Marker berdekatan dikelompokkan — klik untuk matikan" : "Marker tampil satu per satu — klik untuk kelompokkan"}
          data-testid="asset-map-cluster-toggle"
        >
          <Boxes className="w-3.5 h-3.5" />
          <span>Cluster: {clusterOn ? "Aktif" : "Mati"}</span>
        </button>
        <button
          type="button"
          onClick={() => { didFitRef.current = false; load(); }}
          disabled={loading}
          className="h-9 px-2.5 rounded-lg border border-border text-xs font-medium text-foreground/80 hidden sm:flex items-center justify-center gap-1 hover:bg-muted disabled:opacity-50 flex-shrink-0"
          aria-label="Muat ulang peta"
          data-testid="asset-map-refresh"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          <span>Muat Ulang</span>
        </button>
      </div>

      {/* ── Bilah Mode Seleksi ── (klik pin = pilih/lepas · Shift+seret / Pilih
          Area = kotak · Edit Massal membawa pilihan ke daftar) */}
      {canSelect && selectMode && (
        <div className="bg-amber-500/10 border border-amber-500/40 rounded-xl shadow-sm p-1.5 sm:p-2 flex items-center gap-1.5 flex-wrap" data-testid="asset-map-selection-bar">
          <span className="flex items-center gap-1.5 px-2 h-8 rounded-lg bg-amber-500 text-white text-xs font-bold flex-shrink-0">
            <MousePointerClick className="w-3.5 h-3.5" />{selCount} terpilih
          </span>
          <span className="hidden md:inline text-[11px] text-muted-foreground px-1">
            Klik pin = pilih/lepas · <b>Shift+seret</b> = kotak seleksi
          </span>
          <span className="md:hidden text-[11px] text-muted-foreground px-1">
            Ketuk pin = pilih/lepas
          </span>
          <div className="flex-1" />
          <button type="button" onClick={() => setDrawArea((v) => !v)} aria-pressed={drawArea}
            className={`h-8 px-2.5 rounded-lg border text-xs font-medium flex items-center gap-1 flex-shrink-0 min-h-0 transition-colors sm:hidden ${drawArea ? "border-amber-500 bg-amber-500/20 text-amber-700 dark:text-amber-300" : "border-border text-foreground/80 hover:bg-muted"}`}
            title="Seret satu jari untuk menggambar kotak seleksi" data-testid="asset-map-draw-area">
            <SquareDashed className="w-3.5 h-3.5" />{drawArea ? "Gambar kotak…" : "Pilih Area"}
          </button>
          <button type="button" onClick={doSelectAllVisible} disabled={displayRows.length === 0}
            className="h-8 px-2.5 rounded-lg border border-border text-xs font-medium text-foreground/80 flex items-center gap-1 hover:bg-muted disabled:opacity-50 flex-shrink-0"
            data-testid="asset-map-select-all-visible">
            <CheckCheck className="w-3.5 h-3.5" />Pilih Semua
          </button>
          <button type="button" onClick={doClearSelection} disabled={selCount === 0}
            className="h-8 px-2.5 rounded-lg border border-border text-xs font-medium text-foreground/80 flex items-center gap-1 hover:bg-muted disabled:opacity-50 flex-shrink-0"
            data-testid="asset-map-clear-selection">
            <Eraser className="w-3.5 h-3.5" />Kosongkan
          </button>
          {typeof onBatchEditSelected === "function" && (
            <button type="button" onClick={() => onBatchEditSelected()} disabled={selCount === 0}
              className="h-8 px-3 rounded-lg bg-amber-600 text-white text-xs font-bold flex items-center gap-1 hover:bg-amber-700 disabled:opacity-50 flex-shrink-0 shadow-sm"
              data-testid="asset-map-batch-edit">
              <PencilLine className="w-3.5 h-3.5" />Edit Massal ({selCount})
            </button>
          )}
        </div>
      )}

      {/* ── Peta ── */}
      <div ref={mapWrapRef} className="relative bg-card rounded-xl border border-border shadow-sm overflow-hidden">
        <div ref={containerRef} className="h-[58vh] sm:h-[62vh] lg:h-[calc(100vh-330px)] min-h-[360px] w-full z-0" data-testid="asset-map-canvas" />
        {loading && (
          <div className="absolute inset-0 z-[500] bg-background/50 flex items-center justify-center pointer-events-none">
            <Loader2 className="w-7 h-7 animate-spin text-teal-600" />
          </div>
        )}
        {loadedOnce && !loading && displayRows.length === 0 && (
          <div className="absolute inset-x-0 top-3 z-[500] flex justify-center pointer-events-none px-4">
            <span className="px-3 py-1.5 rounded-full bg-background/90 border border-border text-xs text-muted-foreground shadow text-center">
              {activeFilterCount > 0 || groupKey !== "__semua__"
                ? "Tidak ada aset berkoordinat yang cocok dengan filter aktif"
                : "Belum ada aset dengan titik koordinat di kegiatan ini"}
            </span>
          </div>
        )}
      </div>

      {/* ── Legenda + petunjuk ── */}
      <div className="bg-card rounded-xl border border-border shadow-sm px-3 py-1.5 flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          {Object.entries(STATUS_COLORS).map(([label, color]) => (
            <span key={label} className="flex items-center gap-1 text-[10px] text-muted-foreground">
              <span className="w-2.5 h-2.5 rounded-full border border-white shadow" style={{ background: color }} />
              {label}
            </span>
          ))}
          <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <span className="w-3.5 h-3.5 rounded-full bg-slate-900 border border-white shadow flex items-center justify-center"><Camera className="w-2 h-2 text-white" /></span>
            punya foto
          </span>
          <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <span className="w-2.5 h-2.5 rounded-full bg-card border-2 shadow" style={{ borderColor: "#16a34a" }} />
            pengguna + NIP + BAST lengkap
          </span>
        </div>
        {canEdit && (
          <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <Move className="w-3 h-3" />Geser pin untuk membetulkan koordinat — tersimpan otomatis
          </span>
        )}
      </div>

      {/* Lightbox foto — sama seperti mode galeri; dibuka dari popup marker */}
      {lightboxRow && (
        <Lightbox
          asset={lightboxRow}
          onClose={() => setLightboxRow(null)}
          onEdit={onEditAsset}
          siblings={displayRows}
          onSelectAsset={setLightboxRow}
        />
      )}
    </div>
  );
});

AssetMapFullView.displayName = "AssetMapFullView";
export default AssetMapFullView;
