import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import axios from "axios";
import { MapPinned, RefreshCw, Loader2, Move, X, Filter, Download, Camera, Layers, ChevronDown } from "lucide-react";
import { toast } from "sonner";
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
  onSaveCoords,       // (row, lat, lng) => void — simpan koordinat (throw = tolak)
  buildParams,        // () => URLSearchParams — filter aktif dashboard (tanpa page)
  clientFilter,       // (rows) => rows — filter yang sama utk data snapshot offline
  activeFilterCount = 0,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);         // L.LayerGroup pin
  const markersRef = useRef(new Map());  // id -> { marker, row, lat, lng, iconKey, draggable }
  const didFitRef = useRef(false);       // fitBounds hanya saat muat pertama / ganti kelompok
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [truncated, setTruncated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadedOnce, setLoadedOnce] = useState(false);
  const [groupKey, setGroupKey] = useState("__semua__"); // filter Barang Serupa
  // Guard staleness: hanya hasil load TERBARU yang boleh menulis state —
  // load lama (loop multi-halaman) bisa selesai SETELAH load baru.
  const loadSeqRef = useRef(0);

  // Callback disimpan di ref agar marker tidak dibangun ulang hanya karena
  // identitas arrow function induk berubah tiap render.
  const onEditRef = useRef(onEditAsset);
  const onSaveRef = useRef(onSaveCoords);
  const onCloseRef = useRef(onClose);
  useEffect(() => { onEditRef.current = onEditAsset; onSaveRef.current = onSaveCoords; onCloseRef.current = onClose; });

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
    const ext = fmt === "shp" ? "zip" : fmt;
    const fname = `peta_aset.${ext}`;
    downloadFileWithProgress(`${API}/export/geo?${params.toString()}`, fname, {
      label: `Peta Aset (${fmt.toUpperCase()})`,
      timeoutMessage: "Ekspor peta terlalu lama — coba persempit filter",
    }).catch(() => {});
  }, [buildParams]);

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
    return Array.from(byKey.values()).filter((g) => g.count >= 2)
      .sort((a, b) => b.count - a.count).slice(0, 100);
  }, [rows]);

  // Baris yang tampil = baris peta ± filter kelompok Barang Serupa.
  const displayRows = useMemo(() => {
    if (groupKey === "__semua__") return rows;
    return rows.filter((r) => `${r.asset_code || ""}||${r.asset_name || ""}` === groupKey);
  }, [rows, groupKey]);

  // Ganti kelompok → pusatkan ulang peta ke pin kelompok tsb.
  const changeGroup = useCallback((v) => {
    setGroupKey(v);
    didFitRef.current = false;
  }, []);

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
  // Tata letak padat: bingkai foto (bila ada) + identitas, pill status/kondisi
  // berwarna, baris info berlabel, koordinat, tombol Edit selebar popup.
  const buildPopupEl = useCallback((entry) => {
    const row = entry.row;
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
    if (onEditRef.current) {
      const btn = document.createElement("button");
      btn.textContent = "Edit Aset";
      btn.style.cssText = "display:block;width:100%;margin-top:7px;padding:7px 0;background:#2563eb;color:#fff;border:none;border-radius:8px;font-size:11.5px;font-weight:700;cursor:pointer";
      btn.addEventListener("click", () => {
        entry.marker.closePopup();
        onEditRef.current?.(entry.row); // peta tetap terbuka — form edit muncul di atas/sampingnya
      });
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

    for (const row of displayRows) {
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
      // SATU popup per pin (tanpa tooltip hover — dulu tooltip + popup tampil
      // bertumpuk saat pin diketuk di layar sentuh).
      marker.bindPopup(() => buildPopupEl(entry));

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

    // Buang pin milik baris yang tak tampil (filter kelompok/filter berubah)
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
  }, [displayRows, canEdit, buildPopupEl, refreshRowVersion]);

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
                    <span className="font-semibold text-foreground/80">{displayRows.length}</span>/{total} titik{activeFilterCount > 0 ? " · terfilter" : ""}{truncated ? " · belum semua termuat" : ""}
                  </span>
                  <span className="hidden sm:inline">
                    <span className="font-semibold text-foreground/80">{displayRows.length}</span> titik dari {total} aset{activeFilterCount > 0 ? " (terfilter)" : ""}{truncated ? " — sebagian belum dimuat" : ""}
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
          <DropdownMenuContent align="end" className="w-64">
            {groups.length > 0 && (
              <>
                <DropdownMenuLabel className="text-[11px] flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-violet-500" />Barang Serupa
                </DropdownMenuLabel>
                <div className="max-h-52 overflow-y-auto">
                  <DropdownMenuRadioGroup value={groupKey} onValueChange={changeGroup}>
                    <DropdownMenuRadioItem className="min-h-[42px]" value="__semua__" data-testid="map-menu-group-all">Semua barang</DropdownMenuRadioItem>
                    {groups.map((g) => (
                      <DropdownMenuRadioItem className="min-h-[42px]" key={g.key} value={g.key}>{g.name} · {g.count} unit</DropdownMenuRadioItem>
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
            <SelectContent className="max-h-72">
              <SelectItem value="__semua__">Semua barang</SelectItem>
              {groups.map((g) => (
                <SelectItem key={g.key} value={g.key}>{g.name} · {g.count} unit</SelectItem>
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

      {/* ── Peta ── */}
      <div className="relative bg-card rounded-xl border border-border shadow-sm overflow-hidden">
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
    </div>
  );
});

AssetMapFullView.displayName = "AssetMapFullView";
export default AssetMapFullView;
