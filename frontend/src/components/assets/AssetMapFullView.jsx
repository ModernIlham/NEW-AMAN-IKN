import React, { memo, useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import axios from "axios";
import { MapPinned, RefreshCw, Loader2, Move, X, Filter, Download, Camera } from "lucide-react";
import { toast } from "sonner";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { getSnapshotAssets } from "../../lib/offlineSnapshot";
import { downloadFileWithProgress } from "../../lib/downloadFile";
import { useBackGuard } from "../../hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

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
function markerIcon(color, hasPhoto = false, complete = false) {
  const border = complete ? "2.5px solid #16a34a" : "2px solid #fff";
  const ring = complete ? "box-shadow:0 0 0 1.5px #16a34a, 0 1px 4px rgba(0,0,0,.45)" : "box-shadow:0 1px 4px rgba(0,0,0,.45)";
  const badge = hasPhoto
    ? `<div style="position:absolute;top:-7px;right:-7px;width:14px;height:14px;border-radius:50%;background:#0f172a;border:1.5px solid #fff;display:flex;align-items:center;justify-content:center;">
         <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
       </div>`
    : "";
  return L.divIcon({
    className: "",
    html: `<div style="position:relative;width:22px;height:22px">
      <div style="width:22px;height:22px;border-radius:50% 50% 50% 0;background:${color};transform:rotate(-45deg);border:${border};${ring}"></div>
      ${badge}
    </div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 22],
    popupAnchor: [0, -20],
  });
}

function esc(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/**
 * Peta Aset HALAMAN PENUH per kegiatan.
 *
 * - Mengikuti filter aktif dashboard: online memakai GET /assets dengan
 *   parameter yang SAMA dengan daftar (search + kategori + filter lanjutan,
 *   via buildParams), offline memakai snapshot + clientFilter yang sama
 *   dengan daftar offline.
 * - Pin berwarna status; bisa digeser (bila boleh edit) → koordinat aset
 *   otomatis tersimpan lewat antrean simpan yang sama dengan form.
 * - Tombol Back HP menutup peta (bukan keluar aplikasi).
 */
const AssetMapFullView = memo(function AssetMapFullView({
  activityId,
  activityName = "",
  onClose,
  canEdit = false,
  onEditAsset,        // (row) => void — tutup peta lalu buka form edit
  onSaveCoords,       // (row, lat, lng) => void — simpan koordinat (throw = tolak)
  buildParams,        // () => URLSearchParams — filter aktif dashboard (tanpa page)
  clientFilter,       // (rows) => rows — filter yang sama utk data snapshot offline
  activeFilterCount = 0,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);         // L.LayerGroup pin
  const markersRef = useRef(new Map());  // id -> { marker, row, lat, lng, color, draggable }
  const didFitRef = useRef(false);       // fitBounds hanya saat muat pertama
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [truncated, setTruncated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadedOnce, setLoadedOnce] = useState(false);
  // Guard staleness: hanya hasil load TERBARU yang boleh menulis state —
  // load lama (loop multi-halaman) bisa selesai SETELAH load baru.
  const loadSeqRef = useRef(0);

  // Callback disimpan di ref agar marker tidak dibangun ulang hanya karena
  // identitas arrow function induk berubah tiap render.
  const onEditRef = useRef(onEditAsset);
  const onSaveRef = useRef(onSaveCoords);
  const onCloseRef = useRef(onClose);
  useEffect(() => { onEditRef.current = onEditAsset; onSaveRef.current = onSaveCoords; onCloseRef.current = onClose; });

  // Back HP menutup peta, bukan keluar aplikasi.
  useBackGuard(useCallback(() => onCloseRef.current?.(), []));

  // Kunci scroll latar selama peta terbuka.
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

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

  // Muat data saat halaman peta dibuka.
  useEffect(() => { didFitRef.current = false; load(); }, [load]);

  // Unduh titik peta (KML/KMZ/SHP) lengkap dengan atribut — memakai filter
  // aktif yang SAMA dengan peta/daftar (endpoint /export/geo).
  const downloadGeo = useCallback((fmt) => {
    const params = buildParams ? buildParams() : new URLSearchParams();
    params.set("format", fmt);
    const ext = fmt === "shp" ? "zip" : fmt;
    const fname = `peta_aset.${ext}`;
    downloadFileWithProgress(`${API}/export/geo?${params.toString()}`, fname, {
      label: `Peta Aset (${fmt.toUpperCase()})`,
      timeoutMessage: "Ekspor peta terlalu lama — coba persempit filter",
    }).catch(() => {});
  }, [buildParams]);

  // Init peta pada mount; rusak saat unmount.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;
    const map = L.map(containerRef.current, { zoomControl: true, attributionControl: true });
    map.setView([-1.4, 116.7], 5); // fallback: kawasan IKN
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
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
  const buildPopupEl = useCallback((entry) => {
    const row = entry.row;
    const lat = parseCoord(row.koordinat_latitude);
    const lng = parseCoord(row.koordinat_longitude);
    const el = document.createElement("div");
    el.style.minWidth = "180px";
    el.innerHTML = `
      <div style="font-weight:700;font-size:12px;margin-bottom:2px">${esc(row.asset_name || "-")}</div>
      <div style="font-size:11px;color:#475569">${esc(row.asset_code || "-")}${row.NUP ? ` &bull; NUP ${esc(row.NUP)}` : ""}</div>
      ${row.location ? `<div style="font-size:11px;color:#475569">${esc(row.location)}</div>` : ""}
      <div style="font-size:11px;color:#475569">${esc(row.inventory_status || "Belum Diinventarisasi")}</div>
      <div style="font-family:monospace;font-size:10px;color:#64748b;margin-top:2px">${lat?.toFixed(6)}, ${lng?.toFixed(6)}</div>`;
    if (onEditRef.current) {
      const btn = document.createElement("button");
      btn.textContent = "Edit Aset";
      btn.style.cssText = "margin-top:6px;padding:4px 10px;background:#2563eb;color:#fff;border:none;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer";
      btn.addEventListener("click", () => onEditRef.current?.(entry.row));
      el.appendChild(btn);
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

    for (const row of rows) {
      const lat = parseCoord(row.koordinat_latitude);
      const lng = parseCoord(row.koordinat_longitude);
      if (lat === null || lng === null) continue;
      seen.add(row.id);
      bounds.push([lat, lng]);
      const color = STATUS_COLORS[row.inventory_status] || STATUS_COLORS["Belum Diinventarisasi"];
      const hasPhoto = rowHasPhoto(row);
      const complete = isPenggunaComplete(row);
      const iconKey = `${color}|${hasPhoto}|${complete}`;
      const existing = markersRef.current.get(row.id);

      if (existing) {
        existing.row = row; // handler membaca entry.row → selalu data terbaru
        const dragging = existing.marker.dragging && existing.marker.dragging.moving && existing.marker.dragging.moving();
        if (!dragging && (existing.lat !== lat || existing.lng !== lng)) {
          existing.marker.setLatLng([lat, lng]);
        }
        existing.lat = lat; existing.lng = lng;
        if (existing.iconKey !== iconKey) { existing.marker.setIcon(markerIcon(color, hasPhoto, complete)); existing.iconKey = iconKey; }
        if (existing.draggable !== canEdit && existing.marker.dragging) {
          if (canEdit) existing.marker.dragging.enable(); else existing.marker.dragging.disable();
          existing.draggable = canEdit;
        }
        continue;
      }

      const marker = L.marker([lat, lng], { icon: markerIcon(color, hasPhoto, complete), draggable: !!canEdit });
      const entry = { marker, row, lat, lng, iconKey, draggable: !!canEdit };
      // Konten popup/tooltip sebagai fungsi → dievaluasi saat dibuka dengan
      // data terbaru; tooltip memakai TEKS ter-escape (leaflet merender HTML).
      marker.bindPopup(() => buildPopupEl(entry));
      marker.bindTooltip(() => esc(entry.row.asset_name || entry.row.asset_code || "Aset"), { direction: "top", offset: [0, -20] });

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

    // Buang pin milik baris yang sudah tidak ada (mis. filter berubah)
    for (const [id, entry] of Array.from(markersRef.current.entries())) {
      if (!seen.has(id)) {
        entry.marker.remove();
        markersRef.current.delete(id);
      }
    }

    if (bounds.length > 0 && !didFitRef.current) {
      didFitRef.current = true;
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 18 });
    }
  }, [rows, canEdit, buildPopupEl, refreshRowVersion]);

  return createPortal(
    <div className="fixed inset-0 z-[70] bg-background flex flex-col" role="dialog" aria-modal="true" aria-label="Peta Aset" data-testid="asset-map-fullview">
      {/* ── Header ── */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-card flex-shrink-0">
        <span className="w-9 h-9 rounded-lg bg-teal-600 flex items-center justify-center flex-shrink-0">
          <MapPinned className="w-5 h-5 text-white" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-bold text-foreground leading-tight">Peta Aset</h2>
          <p className="text-[11px] text-muted-foreground truncate">
            {activityName || "Kegiatan aktif"}
            {loadedOnce && <> — <span className="font-semibold text-foreground/80">{rows.length}</span> titik dari {total} aset{activeFilterCount > 0 ? " (terfilter)" : ""}{truncated ? " — sebagian belum dimuat, persempit filter" : ""}</>}
          </p>
        </div>
        {activeFilterCount > 0 && (
          <span className="hidden sm:flex items-center gap-1 px-2 h-7 rounded-full bg-blue-600/10 text-blue-600 dark:text-blue-400 text-[11px] font-semibold flex-shrink-0" data-testid="asset-map-filter-badge">
            <Filter className="w-3 h-3" />{activeFilterCount} filter aktif
          </span>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="h-9 px-2.5 rounded-lg border border-border text-xs font-medium text-foreground/80 flex items-center gap-1 hover:bg-accent flex-shrink-0"
              data-testid="asset-map-download"
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Unduh</span>
            </button>
          </DropdownMenuTrigger>
          {/* z di atas overlay peta (z-[70]) — default konten radix z-50 */}
          <DropdownMenuContent align="end" className="w-44 z-[80]">
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
        <button
          type="button"
          onClick={() => { didFitRef.current = false; load(); }}
          disabled={loading}
          className="h-9 px-2.5 rounded-lg border border-border text-xs font-medium text-foreground/80 flex items-center gap-1 hover:bg-accent disabled:opacity-50 flex-shrink-0"
          data-testid="asset-map-refresh"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          <span className="hidden sm:inline">Muat Ulang</span>
        </button>
        <button
          type="button"
          onClick={onClose}
          aria-label="Tutup peta"
          className="w-9 h-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-accent flex-shrink-0"
          data-testid="asset-map-close"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* ── Peta (isi seluruh sisa layar) ── */}
      <div className="relative flex-1 min-h-0">
        <div ref={containerRef} className="absolute inset-0 z-0" data-testid="asset-map-canvas" />
        {loading && (
          <div className="absolute inset-0 z-[500] bg-background/50 flex items-center justify-center pointer-events-none">
            <Loader2 className="w-7 h-7 animate-spin text-teal-600" />
          </div>
        )}
        {loadedOnce && !loading && rows.length === 0 && (
          <div className="absolute inset-x-0 top-3 z-[500] flex justify-center pointer-events-none px-4">
            <span className="px-3 py-1.5 rounded-full bg-background/90 border border-border text-xs text-muted-foreground shadow text-center">
              {activeFilterCount > 0
                ? "Tidak ada aset berkoordinat yang cocok dengan filter aktif"
                : "Belum ada aset dengan titik koordinat di kegiatan ini"}
            </span>
          </div>
        )}
      </div>

      {/* ── Legenda + petunjuk ── */}
      <div className="flex items-center justify-between gap-2 px-3 py-1.5 border-t border-border bg-card flex-shrink-0 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          {Object.entries(STATUS_COLORS).map(([label, color]) => (
            <span key={label} className="flex items-center gap-1 text-[10px] text-muted-foreground">
              <span className="w-2.5 h-2.5 rounded-full border border-white shadow" style={{ background: color }} />
              {label}
            </span>
          ))}
        </div>
        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
          <span className="w-3.5 h-3.5 rounded-full bg-slate-900 border border-white shadow flex items-center justify-center"><Camera className="w-2 h-2 text-white" /></span>
          punya foto
        </span>
        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
          <span className="w-2.5 h-2.5 rounded-full bg-card border-2 shadow" style={{ borderColor: "#16a34a" }} />
          pengguna + NIP + BAST lengkap
        </span>
        {canEdit && (
          <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <Move className="w-3 h-3" />Geser pin untuk membetulkan koordinat — tersimpan otomatis
          </span>
        )}
      </div>
    </div>,
    document.body
  );
});

AssetMapFullView.displayName = "AssetMapFullView";
export default AssetMapFullView;
