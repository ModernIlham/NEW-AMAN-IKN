import React, { memo, useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import axios from "axios";
import { MapPinned, ChevronDown, RefreshCw, Loader2, Move } from "lucide-react";
import { toast } from "sonner";
import { getSnapshotAssets } from "../../lib/offlineSnapshot";

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

// Pin berwarna via divIcon — menghindari masalah path ikon default leaflet
// di bundler CRA, sekaligus memberi warna per status inventarisasi.
function markerIcon(color) {
  return L.divIcon({
    className: "",
    html: `<div style="width:22px;height:22px;border-radius:50% 50% 50% 0;background:${color};transform:rotate(-45deg);border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45)"></div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 22],
    popupAnchor: [0, -20],
  });
}

function esc(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/**
 * Panel "Peta Aset" per kegiatan: semua aset yang punya titik koordinat
 * ditampilkan sebagai pin berwarna status. Pin bisa DIGESER (bila boleh edit)
 * — begitu dilepas, koordinat aset otomatis tersimpan lewat antrean simpan
 * yang sama dengan form (If-Match + Idempotency-Key + retry offline).
 */
const AssetMapPanel = memo(function AssetMapPanel({
  activityId,
  isOpen,
  onToggle,
  canEdit = false,
  onEditAsset,        // (row) => void — buka form edit aset
  onSaveCoords,       // (row, lat, lng) => void — simpan koordinat (throw = tolak)
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);         // L.LayerGroup pin
  const markersRef = useRef(new Map());  // id -> { marker, row, lat, lng, color, draggable }
  const didFitRef = useRef(false);       // fitBounds hanya saat muat pertama
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadedOnce, setLoadedOnce] = useState(false);

  // Callback disimpan di ref agar marker tidak dibangun ulang hanya karena
  // identitas arrow function induk berubah tiap render.
  const onEditRef = useRef(onEditAsset);
  const onSaveRef = useRef(onSaveCoords);
  useEffect(() => { onEditRef.current = onEditAsset; onSaveRef.current = onSaveCoords; });

  const load = useCallback(async () => {
    if (!activityId) return;
    setLoading(true);
    try {
      let all = [];
      if (navigator.onLine) {
        // Sumber massal bebas-media (proyeksi list, maks 1000 baris/halaman)
        let skip = 0;
        for (let page = 0; page < 50; page++) {
          const r = await axios.get(`${API}/assets/offline-snapshot`, {
            params: { activity_id: activityId, skip, limit: 1000 },
          });
          const items = r.data?.items || [];
          all = all.concat(items);
          skip += items.length;
          if (skip >= (r.data?.total || 0) || items.length === 0) break;
        }
      } else {
        all = await getSnapshotAssets(activityId);
      }
      setTotal(all.length);
      setRows(all.filter((a) => parseCoord(a.koordinat_latitude) !== null && parseCoord(a.koordinat_longitude) !== null));
      setLoadedOnce(true);
    } catch {
      // Jaringan gagal di tengah — coba snapshot lokal sebagai cadangan
      try {
        const cached = await getSnapshotAssets(activityId);
        setTotal(cached.length);
        setRows(cached.filter((a) => parseCoord(a.koordinat_latitude) !== null && parseCoord(a.koordinat_longitude) !== null));
        setLoadedOnce(true);
        toast.info("Peta memakai data snapshot offline");
      } catch {
        toast.error("Gagal memuat data peta");
      }
    } finally {
      setLoading(false);
    }
  }, [activityId]);

  // Muat data saat panel dibuka (dan saat ganti kegiatan).
  useEffect(() => {
    if (isOpen && activityId) { didFitRef.current = false; load(); }
  }, [isOpen, activityId, load]);

  // Init peta saat panel terbuka; rusak saat panel ditutup/unmount.
  useEffect(() => {
    if (!isOpen || !containerRef.current || mapRef.current) return undefined;
    const map = L.map(containerRef.current, { zoomControl: true, attributionControl: true });
    map.setView([-1.4, 116.7], 5); // fallback: kawasan IKN
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    // Ukuran container baru benar setelah layout — hitung ulang.
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
  }, [isOpen]);

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
      const existing = markersRef.current.get(row.id);

      if (existing) {
        existing.row = row; // handler membaca entry.row → selalu data terbaru
        const dragging = existing.marker.dragging && existing.marker.dragging.moving && existing.marker.dragging.moving();
        if (!dragging && (existing.lat !== lat || existing.lng !== lng)) {
          existing.marker.setLatLng([lat, lng]);
        }
        existing.lat = lat; existing.lng = lng;
        if (existing.color !== color) { existing.marker.setIcon(markerIcon(color)); existing.color = color; }
        if (existing.draggable !== canEdit && existing.marker.dragging) {
          if (canEdit) existing.marker.dragging.enable(); else existing.marker.dragging.disable();
          existing.draggable = canEdit;
        }
        continue;
      }

      const marker = L.marker([lat, lng], { icon: markerIcon(color), draggable: !!canEdit });
      const entry = { marker, row, lat, lng, color, draggable: !!canEdit };
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

    // Buang pin milik baris yang sudah tidak ada
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

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden" data-testid="asset-map-panel">
      {/* Header — selalu tampil (pola panel dashboard) */}
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-accent/40 transition-colors"
        data-testid="asset-map-toggle"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <MapPinned className="w-4 h-4 text-teal-600" />
          Peta Aset
          {loadedOnce && (
            <span className="text-[11px] font-medium text-muted-foreground">
              {rows.length} titik dari {total} aset
            </span>
          )}
        </span>
        <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {isOpen && (
        <div className="border-t border-border">
          <div className="flex items-center justify-between px-3 py-1.5 gap-2 flex-wrap">
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground min-w-0">
              {canEdit && (
                <span className="flex items-center gap-1"><Move className="w-3 h-3" />Geser pin untuk membetulkan koordinat — tersimpan otomatis</span>
              )}
            </div>
            <button
              type="button"
              onClick={() => { didFitRef.current = false; load(); }}
              disabled={loading}
              className="h-7 px-2 rounded-md border border-border text-[11px] font-medium text-foreground/80 flex items-center gap-1 hover:bg-accent disabled:opacity-50"
              data-testid="asset-map-refresh"
            >
              {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
              Muat Ulang
            </button>
          </div>
          <div className="relative">
            <div ref={containerRef} className="h-[420px] w-full z-0" data-testid="asset-map-canvas" />
            {loading && (
              <div className="absolute inset-0 z-[500] bg-background/50 flex items-center justify-center pointer-events-none">
                <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
              </div>
            )}
            {loadedOnce && !loading && rows.length === 0 && (
              <div className="absolute inset-x-0 top-3 z-[500] flex justify-center pointer-events-none">
                <span className="px-3 py-1.5 rounded-full bg-background/90 border border-border text-xs text-muted-foreground shadow">
                  Belum ada aset dengan titik koordinat di kegiatan ini
                </span>
              </div>
            )}
          </div>
          {/* Legenda status */}
          <div className="flex items-center gap-3 px-3 py-1.5 flex-wrap border-t border-border">
            {Object.entries(STATUS_COLORS).map(([label, color]) => (
              <span key={label} className="flex items-center gap-1 text-[10px] text-muted-foreground">
                <span className="w-2.5 h-2.5 rounded-full border border-white shadow" style={{ background: color }} />
                {label}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});

AssetMapPanel.displayName = "AssetMapPanel";
export default AssetMapPanel;
