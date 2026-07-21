// ============================================================================
// DASHBOARD PAGE - FULL FEATURED VERSION WITH ACTIVITY-BASED WORKFLOW
// OPTIMIZED: Virtual scrolling for large datasets (1M+ assets)
// REFACTORED: Custom hooks extracted to /hooks/ for maintainability
// ============================================================================
import React, { useState, useEffect, useRef, useMemo, useCallback, memo, useReducer, lazy, Suspense } from "react";
import {
  Package, Plus, X, ChevronDown, ChevronUp, Loader2, Star,
  Users, PanelLeftClose, PanelLeftOpen, Lock, Pen, CheckSquare,
  BarChart3, ClipboardList, Layers,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "@/lib/utils";
import { downloadFileWithProgress, makeDownloadProgress } from "@/lib/downloadFile";
import { authMediaUrl } from "@/lib/mediaUrl";
import { reserveDummyNup, cariKategoriDummy } from "@/lib/dummyNup";
import { syncSnapshot, getSnapshotAssets, snapshotMeta, isSnapshotExpired, upsertSnapshotAsset, removeSnapshotAsset } from "@/lib/offlineSnapshot";

// Import refactored components
import {
  LoadingIndicator,
  VirtualizedAssetTable,
  VirtualizedMobileCards,
  AssetForm,
  CategoryManagerDialog,
  BulkDeleteDialog,
  AssetGalleryView,
} from "@/components/assets";
import CetakStikerDialog from "@/components/assets/CetakStikerDialog";
// Heavy panels - lazy loaded (only when user opens them)
const BatchEditPanel = lazy(() => import("@/components/assets/BatchEditPanel"));
const AnalyticsPanel = lazy(() => import("@/components/assets/AnalyticsPanel"));
const RekapitulasiPanel = lazy(() => import("@/components/assets/RekapitulasiPanel"));
const AuditLogPanel = lazy(() => import("@/components/assets/AuditLogPanel"));
const AssetGroupsPanel = lazy(() => import("@/components/assets/AssetGroupsPanel"));
const AssetMapFullView = lazy(() => import("@/components/assets/AssetMapFullView"));
const PhotoLightbox = lazy(() => import("@/components/assets/PhotoLightbox"));
import DashboardHeader from "@/components/assets/DashboardHeader";
import StatsBar from "@/components/assets/StatsBar";
import InventoryProgressBar from "@/components/assets/InventoryProgressBar";
import DashboardToolbar from "@/components/assets/DashboardToolbar";
import AssetPagination from "@/components/assets/AssetPagination";
import ScrollToTop from "@/components/assets/ScrollToTop";
import ListLoadingSkeleton from "@/components/assets/ListLoadingSkeleton";
import ActivitySelectionPage from "@/pages/ActivitySelectionPage";

import { TooltipProvider } from "@/components/ui/tooltip";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useOfflineSync } from "@/hooks/useOfflineSync";
import { useOptimisticQueue } from "@/hooks/useOptimisticQueue";
import { haptic } from "@/lib/haptics";
import { useUnsyncedGuard } from "@/hooks/useUnsyncedGuard";
import { useRowLocking } from "@/hooks/useRowLocking";
import { useAssetFilters } from "@/hooks/useAssetFilters";
import { usePullToRefresh } from "@/hooks/usePullToRefresh";
import { useDragDropImport } from "@/hooks/useDragDropImport";
import { useBackGuard } from "@/hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Satu segmen dari kontrol gabungan (Analytics/Rekapitulasi/Barang Serupa).
// Tiga segmen berbagi satu kartu ber-divider → tampil sebagai satu kesatuan
// desain menyamping (bukan tiga tombol/kartu terpisah), hemat ruang di semua
// viewport dan memperlebar area data. Badge jumlah dibuat seperti NOTIFIKASI:
// mengambang di atas-tengah, sedikit menjorok keluar kotak, agar tidak
// menutupi teks label (label kini punya ruang penuh).
function PanelSegment({ active, onClick, testid, icon: Icon, label, badge, activeCls, iconCls, badgeCls, roundedL, roundedR }) {
  return (
    <button
      type="button" onClick={onClick} data-testid={testid} aria-pressed={active}
      className={`relative flex-1 min-w-0 flex items-center justify-center gap-1.5 px-2 py-2 text-[11px] sm:text-xs font-semibold transition-colors ${roundedL ? "rounded-l-xl" : ""} ${roundedR ? "rounded-r-xl" : ""} ${active ? activeCls : "text-foreground hover:bg-muted"}`}
    >
      {badge != null && (
        <span
          className={`absolute -top-2 left-1/2 -translate-x-1/2 z-10 text-[9px] leading-none px-1.5 py-0.5 rounded-full font-bold shadow-sm ring-2 ring-card whitespace-nowrap pointer-events-none ${badgeCls || "bg-blue-600 text-white"}`}
          data-testid={`${testid}-badge`}
        >
          {badge}
        </span>
      )}
      <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${active ? "" : iconCls}`} />
      <span className="truncate">{label}</span>
      {active
        ? <ChevronUp className="w-3.5 h-3.5 flex-shrink-0" />
        : <ChevronDown className="w-3.5 h-3.5 flex-shrink-0 opacity-60" />}
    </button>
  );
}

// ============================================================================
// OFFLINE READ PATH — client-side filter/sort over the local snapshot.
// Mirrors the server behavior of GET /assets (routes/assets.py) as closely
// as feasible so switching between live and cached data feels identical.
// ============================================================================
// Same fields the server-side multi-field search covers
const SNAPSHOT_SEARCH_FIELDS = [
  "asset_code", "asset_name", "serial_number", "location", "brand", "model",
  "category", "eselon1", "eselon2", "user", "supplier", "condition", "status",
  "nomor_spm", "kode_register", "notes",
];

function filterSnapshotRows(rows, { search, category, filters }) {
  let out = rows;
  if (search) {
    const q = search.toLowerCase();
    out = out.filter(r => SNAPSHOT_SEARCH_FIELDS.some(f => String(r[f] ?? "").toLowerCase().includes(q)));
  }
  if (category && category !== "Semua") out = out.filter(r => r.category === category);
  if (filters) {
    const eq = (field, val) => { if (val) out = out.filter(r => String(r[field] ?? "") === val); };
    const sub = (field, val) => { if (val) { const v = val.toLowerCase(); out = out.filter(r => String(r[field] ?? "").toLowerCase().includes(v)); } };
    eq("condition", filters.condition);
    eq("status", filters.status);
    sub("location", filters.location);
    sub("eselon1", filters.eselon1);
    sub("eselon2", filters.eselon2);
    eq("stiker_status", filters.stiker);
    eq("inventory_status", filters.inventoryStatus);
    sub("nomor_spm", filters.nomorSpm);
    sub("supplier", filters.perolehanDari);
    sub("user", filters.user);
    sub("pengguna_nip", filters.penggunaNip);
    const pMin = parseFloat(filters.priceMin);
    const pMax = parseFloat(filters.priceMax);
    if (!Number.isNaN(pMin)) out = out.filter(r => (Number(r.purchase_price) || 0) >= pMin);
    if (!Number.isNaN(pMax)) out = out.filter(r => (Number(r.purchase_price) || 0) <= pMax);
    // Rentang tanggal beli (purchase_date YYYY-MM-DD) — bukan tanggal input.
    // Selaras dengan filter server (/assets & ekspor geo) agar peta ikut tersaring.
    // Aset tanpa tanggal beli keluar dari hasil saat rentang diisi.
    if (filters.dateFrom) out = out.filter(r => String(r.purchase_date ?? "").slice(0, 10) >= filters.dateFrom && String(r.purchase_date ?? "").trim() !== "");
    if (filters.dateTo) out = out.filter(r => { const d = String(r.purchase_date ?? "").slice(0, 10); return d !== "" && d <= filters.dateTo; });
  }
  return out;
}

function sortSnapshotRows(rows, sortBy) {
  const s = (v) => String(v ?? "");
  const n = (v) => Number(v) || 0;
  const cmp = {
    newest: (a, b) => s(b.created_at).localeCompare(s(a.created_at)),
    oldest: (a, b) => s(a.created_at).localeCompare(s(b.created_at)),
    name_asc: (a, b) => s(a.asset_name).localeCompare(s(b.asset_name)),
    name_desc: (a, b) => s(b.asset_name).localeCompare(s(a.asset_name)),
    price_asc: (a, b) => n(a.purchase_price) - n(b.purchase_price),
    price_desc: (a, b) => n(b.purchase_price) - n(a.purchase_price),
    category_asc: (a, b) => s(a.category).localeCompare(s(b.category)),
    category_desc: (a, b) => s(b.category).localeCompare(s(a.category)),
    location_asc: (a, b) => s(a.location).localeCompare(s(b.location)),
    eselon1_asc: (a, b) => s(a.eselon1).localeCompare(s(b.eselon1)),
    condition_asc: (a, b) => s(a.condition).localeCompare(s(b.condition)),
    status_asc: (a, b) => s(a.status).localeCompare(s(b.status)),
  }[sortBy];
  // Rows arrive already newest-first from getSnapshotAssets
  return cmp ? [...rows].sort(cmp) : rows;
}

// Lazy-loaded dialogs (loaded on demand when user opens them)
const LazyImportDialog = lazy(() => import("@/components/assets/ImportDialog"));
const LazyUserManagementDialog = lazy(() => import("@/components/assets/UserManagementDialog"));
const LazyKartuInventarisasiDialog = lazy(() => import("@/components/assets/KartuInventarisasiDialog"));
const LazyAssetTimelineDialog = lazy(() => import("@/components/assets/AssetTimelineDialog"));
// Pengesahan (finalisasi kegiatan) hanya di halaman Kegiatan
// (ActivitySelectionPage), tidak di halaman data.

// Baris CREATE optimistik (id = tempId) dianggap SUDAH terwakili oleh baris
// server bila id-nya sama ATAU kode aset + NUP-nya cocok. Ini mencegah baris
// KEMBAR (temp + baris server) muncul saat sebuah refetch (mis. dipicu event
// WebSocket) berlomba dengan konfirmasi simpan: server sudah mengembalikan
// baris asli (id nyata), tetapi baris pending masih ber-id tempId sehingga
// dedup lama yang hanya membandingkan id gagal mengenalinya sebagai aset sama.
function serverHasPendingRow(serverRow, pendingRow) {
  if (!serverRow || !pendingRow) return false;
  if (serverRow.id === pendingRow.id) return true;
  const code = (pendingRow.asset_code || "").trim();
  if (
    code &&
    serverRow.asset_code === pendingRow.asset_code &&
    String(serverRow.NUP ?? "") === String(pendingRow.NUP ?? "")
  ) return true;
  return false;
}

// ============================================================================
// ASSET MANAGEMENT DASHBOARD (within Activity context)
// ============================================================================
function AssetManagementPage({ user, onLogout, activity, onBack, onActivityRefresh, dark, toggleDark, onShowInfo }) {
  // Kegiatan yang sudah disahkan: seluruh mutasi aset terkunci (backend
  // menolak dengan 423; UI menyembunyikan aksi tulis lewat perms di bawah).
  const sealed = activity?.status_pengesahan === "disahkan";
  const isAdmin = (user?.role || "viewer") === "admin";
  const { confirm, confirmDialog } = useConfirm();

  // RBAC permissions based on user role (+ sealed gating)
  const perms = useMemo(() => {
    const role = user?.role || "viewer";
    return {
      canEdit: (role === "admin" || role === "operator") && !sealed,
      canDelete: (role === "admin" || role === "operator") && !sealed,
      canImport: role === "admin" && !sealed,
      canBulkDelete: role === "admin" && !sealed,
      canManageUsers: role === "admin",
      canManageCategories: role === "admin",
      role,
    };
  }, [user?.role, sealed]);

  // Set audit user header for all axios requests
  useEffect(() => {
    const id = axios.interceptors.request.use(config => {
      let auditName = "unknown";
      let auditId = "";
      try {
        const storedUser = localStorage.getItem('user');
        if (storedUser) {
          const parsedUser = JSON.parse(storedUser);
          auditName = parsedUser?.name || parsedUser?.username || "unknown";
          auditId = parsedUser?.id || "";
        }
      } catch {}
      if (user?.name || user?.username) auditName = user.name || user.username;
      if (user?.id) auditId = user.id;
      config.headers["X-Audit-User"] = auditName;
      config.headers["X-Audit-User-Id"] = auditId;
      return config;
    });
    return () => axios.interceptors.request.eject(id);
  }, [user]);

  // === CORE DATA STATE ===
  const [assets, setAssets] = useState([]);
  const [mobileAssets, setMobileAssets] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);
  const [mobileLoading, setMobileLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("Memuat data...");
  const [currentPage, setCurrentPage] = useState(1);
  const [mobileCurrentPage, setMobileCurrentPage] = useState(1); // halaman TERAKHIR yang dimuat di galeri/kartu
  const [mobileFirstPage, setMobileFirstPage] = useState(1);     // halaman PERTAMA yang dimuat (untuk scroll-atas dua arah)
  const [pageSize, setPageSize] = useState(50);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [stats, setStats] = useState({ totalAssets: 0, totalValue: 0, activeCount: 0, maintenanceCount: 0 });

  // === CUSTOM HOOKS ===
  const filterHook = useAssetFilters({ activityId: activity?.id });
  const {
    searchInput, setSearchInput, filterCategory, setFilterCategory,
    sortBy, setSortBy, debouncedSearch, showAdvancedFilter, setShowAdvancedFilter,
    filters, filterOptions, fetchFilterOptions, buildFilterParams,
    activeFilterCount, handleAdvancedFilterChange, handleCategoryReset,
    resetAdvancedFilters,
  } = filterHook;

  // === FORM / EDIT STATE ===
  const [editAssetForForm, setEditAssetForForm] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [formPanelVisible, setFormPanelVisible] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(null);

  // === UI PANEL STATE ===
  const [analyticsOpen, setAnalyticsOpen] = useState(false);
  const [rekapOpen, setRekapOpen] = useState(false);
  const [analyticsPanelHeight, setAnalyticsPanelHeight] = useState(240);
  const isDragging = useRef(false);
  const dragStartY = useRef(0);
  const dragStartHeight = useRef(0);
  const [inventoryMode, setInventoryMode] = useState(false);
  const [groupsOpen, setGroupsOpen] = useState(false);
  // Hitungan dilaporkan panel (saat pertama dibuka) → tampil sebagai badge di
  // kontrol segmented gabungan meski panel tertutup.
  const [rekapTotal, setRekapTotal] = useState(null);
  const [groupsCount, setGroupsCount] = useState(null);
  const [mapOpen, setMapOpen] = useState(false);
  const [viewMode, setViewMode] = useState('list');
  const viewModeRef = useRef(viewMode);
  viewModeRef.current = viewMode;
  const [auditOpen, setAuditOpen] = useState(false);
  const [auditAssetId, setAuditAssetId] = useState("");
  const [auditAssetCode, setAuditAssetCode] = useState("");
  // Kartu Inventarisasi: identitas aset yang riwayatnya sedang dibuka
  const [kartuIdentity, setKartuIdentity] = useState(null);
  // Timeline Aset — riwayat perlakuan lintas modul per identitas aset (W5)
  const [timelineAssetId, setTimelineAssetId] = useState(null);
  const [photoLightboxAsset, setPhotoLightboxAsset] = useState(null); // foto baris list → lightbox

  // Dialog visibility - consolidated into single reducer
  const [dialogs, dispatchDialog] = useReducer((state, action) => {
    if (action.type === 'OPEN') return { ...state, [action.name]: true };
    if (action.type === 'CLOSE') return { ...state, [action.name]: false };
    if (action.type === 'SET') return { ...state, [action.name]: action.value };
    return state;
  }, { categoryManager: false, import: false, userManagement: false, bulkDelete: false });
  const openDialog = useCallback(name => dispatchDialog({ type: 'OPEN', name }), []);
  const closeDialog = useCallback(name => dispatchDialog({ type: 'CLOSE', name }), []);
  const setDialog = useCallback((name, value) => dispatchDialog({ type: 'SET', name, value }), []);

  // === WEBSOCKET & OFFLINE ===
  const editAssetRef = useRef(null);
  editAssetRef.current = editAssetForForm;
  const wsNeedsRefreshRef = useRef(false);
  const wsRefreshTimerRef = useRef(null);

  const onWsAssetChange = useCallback((eventType, assetInfo) => {
    // PATCH TERTARGET: update oleh rekan cukup mengganti SATU baris (fetch
    // ringan tanpa media) — bukan refetch 50 baris + statistik per event.
    // Aset yang tak ada di halaman/filter saat ini cukup diabaikan (posisinya
    // di halaman lain); snapshot offline tetap disegarkan.
    if (eventType === "asset_updated" && assetInfo?.id) {
      // Baris yang sedang DIEDIT pengguna ini jangan ditimpa — tunda ke refresh.
      if (editAssetRef.current?.id === assetInfo.id) { wsNeedsRefreshRef.current = true; return; }
      axios.get(`${API}/assets/${assetInfo.id}?exclude_media=true`).then(res => {
        const fresh = res?.data;
        if (!fresh) return;
        if (fresh.activity_id) upsertSnapshotAsset(fresh.activity_id, fresh);
        setAssets(prev => prev.some(a => a.id === fresh.id) ? prev.map(a => a.id === fresh.id ? { ...a, ...fresh } : a) : prev);
        setMobileAssets(prev => prev.some(a => a.id === fresh.id) ? prev.map(a => a.id === fresh.id ? { ...a, ...fresh } : a) : prev);
      }).catch(() => { /* aset mungkin baru dihapus — refresh berikutnya merapikan */ });
      return;
    }
    if (eventType === "asset_deleted" && assetInfo?.id) {
      setAssets(prev => prev.filter(a => a.id !== assetInfo.id));
      setMobileAssets(prev => prev.filter(a => a.id !== assetInfo.id));
      setTotalItems(prev => Math.max(0, prev - 1));
      if (activity?.id) removeSnapshotAsset(activity.id, assetInfo.id);
      return;
    }
    // Create rekan / reconnect / sync selesai → refetch penuh (ber-debounce).
    // Deferred refresh: if user is editing, defer the refresh until form closes
    if (editAssetRef.current) {
      wsNeedsRefreshRef.current = true;
      return;
    }
    // Debounce (trailing 2s): a burst of WS events collapses into one refetch
    if (wsRefreshTimerRef.current) clearTimeout(wsRefreshTimerRef.current);
    wsRefreshTimerRef.current = setTimeout(() => {
      wsRefreshTimerRef.current = null;
      if (editAssetRef.current) {
        wsNeedsRefreshRef.current = true; // editing started during the debounce window
      } else {
        refreshData();
      }
    }, 2000);
  }, [activity?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => { if (wsRefreshTimerRef.current) clearTimeout(wsRefreshTimerRef.current); }, []);
  const { onlineUsers, connected: wsConnected, sendMessage: wsSend } = useWebSocket({
    activityId: activity?.id, userId: user?.id,
    userName: user?.name || user?.username,
    onAssetChange: onWsAssetChange, onLocksUpdate: (locks) => setRowLocks(locks),
  });
  const { isOnline } = useOfflineSync();

  // === OFFLINE READ CACHE (snapshot) ===
  // snapshotState → progres sinkron di InventoryProgressBar
  // offlineServed → banner "Mode offline — menampilkan data tersimpan"
  const [snapshotState, setSnapshotState] = useState(null);
  const [offlineServed, setOfflineServed] = useState(false);
  const [offlineLastSync, setOfflineLastSync] = useState(null);
  // Ref mirrors so plain fetch functions / stale closures read fresh values
  const isOnlineRef = useRef(isOnline);
  isOnlineRef.current = isOnline;
  const offlineServedRef = useRef(false);
  offlineServedRef.current = offlineServed;

  // Targeted row update after save (no full refresh while editing!)
  const handleRowSynced = useCallback((assetKey, serverData, isEdit) => {
    if (!serverData) return;
    // Keep the offline snapshot fresh with the confirmed server row (no-op
    // when no snapshot exists; heavy fields are stripped before writing).
    if (serverData.activity_id) upsertSnapshotAsset(serverData.activity_id, serverData);
    if (isEdit) {
      // Update the specific row in the local list with server data
      setAssets(prev => prev.map(a => a.id === assetKey ? { ...a, ...serverData } : a));
      setMobileAssets(prev => prev.map(a => a.id === assetKey ? { ...a, ...serverData } : a));
    } else {
      // For new items, replace the temp item with the server row — dan pastikan
      // HANYA ADA SATU baris ber-id server. Sebuah refetch yang berlomba (mis.
      // dipicu WebSocket) bisa sudah menyisipkan baris server (id nyata) di
      // samping baris temp; tanpa dedup ini hasilnya 2 baris kembar untuk aset
      // yang sama sampai refresh manual. NUP untuk kategori auto-nomor diberi
      // server, jadi dedup kode+NUP saja tak cukup — di sinilah kepastiannya.
      const serverId = serverData.id;
      if (serverId) {
        const dedupeReplace = (prev) => {
          const withoutDupServer = prev.filter(a => a.id !== serverId || a.id === assetKey);
          const mapped = withoutDupServer.map(a => a.id === assetKey ? { ...a, ...serverData, id: serverId } : a);
          return mapped.some(a => a.id === serverId) ? mapped : [{ ...serverData }, ...mapped];
        };
        setAssets(dedupeReplace);
        setMobileAssets(dedupeReplace);
      }
    }
  }, []);

  // Latest known row versions — conflict retries and serialized same-asset
  // saves must send the freshest If-Match, not the version captured at submit.
  const assetsStateRef = useRef([]);
  assetsStateRef.current = assets;
  const getLatestVersion = useCallback((assetId) => assetsStateRef.current.find(a => a.id === assetId)?.version ?? null, []);

  // Throttle toast konflik per-aset: tanpa ini, flush berulang / beberapa antrian
  // atas aset yang sama memunculkan toast "diubah pengguna lain" bertubi-tubi.
  const conflictToastAtRef = useRef({});

  // Rehydrated offline CREATEs need their temp rows back so the retry UI has a row
  const handleQueueRehydrate = useCallback((items) => {
    const rows = items
      .filter(it => !it.isEdit && it.payload && it.payload.activity_id === activity?.id)
      .map(it => ({ ...it.payload, id: it.tempId, thumbnail: it.payload.photo || null, created_at: it.queuedAt || new Date().toISOString() }));
    if (rows.length === 0) return;
    setAssets(prev => [...rows.filter(r => !prev.some(a => serverHasPendingRow(a, r))), ...prev]);
    setMobileAssets(prev => [...rows.filter(r => !prev.some(a => serverHasPendingRow(a, r))), ...prev]);
    setTotalItems(prev => prev + rows.length);
  }, [activity?.id]);

  const {
    syncStatuses, enqueue: enqueueOptimistic, retry: retrySync, dismiss: dismissSync,
    queueLength, consumeRefreshFlag, pendingCount, isSyncing, actionCount, flushPending, getPendingItems,
  } = useOptimisticQueue({
    onItemSaved: (assetId) => unlockAsset(assetId),
    onItemFailed: (assetId) => unlockAsset(assetId),
    onRowSynced: handleRowSynced,
    onConflict: (assetId, conflictDetail) => {
      // Another user modified this asset before our save landed.
      // Toast di-throttle per-aset (≥8 dtk) agar tidak bertubi-tubi saat beberapa
      // percobaan sinkron atas aset yang sama gagal berturut-turut.
      const now = Date.now();
      if (now - (conflictToastAtRef.current[assetId] || 0) > 8000) {
        conflictToastAtRef.current[assetId] = now;
        haptic("error"); // getar "perhatian": data diubah pengguna lain (throttle sama dgn toast)
        toast.error(conflictDetail?.message || "Data telah diubah pengguna lain. Memuat versi terbaru...", { duration: 4500 });
      }
      // Fetch the fresh row to update the local state with the winning version
      axios.get(`${API}/assets/${assetId}?exclude_media=true`).then(res => {
        if (res?.data) {
          setAssets(prev => prev.map(a => a.id === assetId ? { ...a, ...res.data } : a));
          setMobileAssets(prev => prev.map(a => a.id === assetId ? { ...a, ...res.data } : a));
        }
      }).catch((e) => {
        // Non-fatal: asset may have been deleted by another user mid-request.
        if (process.env.NODE_ENV !== "production") {
          console.warn("[dashboard] Failed to refresh asset after WS event:", assetId, e?.message);
        }
      });
    },
    onItemDismissed: (tempId, item) => {
      // User discarded a failed CREATE — remove its optimistic temp row
      if (item?.isEdit) return;
      setAssets(prev => prev.filter(a => a.id !== tempId));
      setMobileAssets(prev => prev.filter(a => a.id !== tempId));
      setTotalItems(prev => Math.max(0, prev - 1));
    },
    onRehydrate: handleQueueRehydrate,
    getLatestVersion,
  });

  // Muat-ulang ramah tapi aman: bila masih ada antrian & ONLINE → otomatis
  // sinkron (best-effort) lalu reload lancar tanpa dialog; bila OFFLINE → tahan
  // dgn konfirmasi; bila tak ada antrian → reload biasa (lihat useUnsyncedGuard).
  const flushForUnload = useCallback(() => flushPending(false), [flushPending]);
  useUnsyncedGuard({ pendingCount, actionCount, isOnline, onFlush: flushForUnload });

  // === ROW LOCKING ===
  const { rowLocks, setRowLocks, sessionId, lockAsset, unlockAsset } = useRowLocking({
    activityId: activity?.id, user, wsSend,
  });

  // Progres inventarisasi: bump refreshKey saat ada save yang baru selesai
  // (transisi status → 'saved') agar InventoryProgressBar refetch rekapitulasi.
  const [progressRefreshKey, setProgressRefreshKey] = useState(0);
  const prevSavedIdsRef = useRef(new Set());
  useEffect(() => {
    const savedIds = Object.keys(syncStatuses).filter(id => syncStatuses[id]?.status === 'saved');
    const hasNew = savedIds.some(id => !prevSavedIdsRef.current.has(id));
    prevSavedIdsRef.current = new Set(savedIds);
    if (hasNew) setProgressRefreshKey(k => k + 1);
  }, [syncStatuses]);


  // === DRAG & DROP IMPORT ===
  const { isDragOverImport, dropFile, handleDragEnter, handleDragLeave, handleDragOver, handleDrop, clearDropFile } = useDragDropImport({
    onFileDropped: () => openDialog('import'),
  });
  const handleImportClose = useCallback(() => { closeDialog('import'); clearDropFile(); }, [closeDialog, clearDropFile]);

  // === BATCH SELECTION ===
  const [selectedAssets, setSelectedAssets] = useState(new Set());
  const [showBatchPanel, setShowBatchPanel] = useState(false);
  const [batchUpdating, setBatchUpdating] = useState(false);

  const toggleSelectAsset = useCallback((assetId) => {
    setSelectedAssets(prev => {
      const next = new Set(prev);
      if (next.has(assetId)) next.delete(assetId); else next.add(assetId);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    setSelectedAssets(prev => {
      if (prev.size === assets.length && assets.length > 0) return new Set();
      return new Set(assets.map(a => a.id));
    });
  }, [assets]);

  const selectAllPages = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      params.append("activity_id", activity?.id || "");
      if (debouncedSearch) params.append("search", debouncedSearch);
      if (filterCategory) params.append("category", filterCategory);
      buildFilterParams(params);
      const r = await axios.get(`${API}/assets/all-ids?${params.toString()}`);
      const allIds = r.data.ids || [];
      setSelectedAssets(new Set(allIds));
      toast.success(`${allIds.length} aset dipilih dari semua halaman`);
    } catch { toast.error("Gagal memilih semua aset"); }
  }, [activity?.id, debouncedSearch, filterCategory, buildFilterParams]);

  const clearSelection = useCallback(() => { setSelectedAssets(new Set()); setShowBatchPanel(false); }, []);

  // Pilih/kosongkan SEMUA aset yang tampil di viewport aktif (desktop = tabel
  // `assets`; galeri/HP/tablet = `mobileAssets`) — memberi select-all/deselect
  // di semua tampilan, bukan hanya header tabel desktop.
  const toggleSelectAllVisible = useCallback(() => {
    const isDesktopList = viewModeRef.current !== 'gallery'
      && typeof window !== 'undefined'
      && window.matchMedia('(min-width: 1024px)').matches;
    const list = isDesktopList ? assets : mobileAssets;
    const ids = list.map(a => a.id);
    setSelectedAssets(prev => {
      const semua = ids.length > 0 && ids.every(id => prev.has(id));
      const next = new Set(prev);
      if (semua) ids.forEach(id => next.delete(id));
      else ids.forEach(id => next.add(id));
      return next;
    });
  }, [assets, mobileAssets]);

  // Panel "Ubah Massal" muncul otomatis saat seleksi PERTAMA (0 → >0) dan
  // hilang saat seleksi dikosongkan; tapi menutup panel (X/Batal) hanya
  // menciutkannya — seleksi TETAP dipertahankan (bug: dulu ikut terhapus).
  const prevSelSizeRef = useRef(0);
  useEffect(() => {
    if (prevSelSizeRef.current === 0 && selectedAssets.size > 0) setShowBatchPanel(true);
    else if (selectedAssets.size === 0) setShowBatchPanel(false);
    prevSelSizeRef.current = selectedAssets.size;
  }, [selectedAssets]);

  // Verifikasi hasil scan barcode/QR terhadap kegiatan yang sedang dibuka.
  // Bug sebelumnya: scan SELALU memunculkan notifikasi "berhasil" walau barang
  // sebenarnya milik kegiatan lain (tidak ada di kegiatan ini). Kini kode yang
  // terbaca dicek keberadaannya di kegiatan aktif dulu, baru beri notifikasi
  // sukses/gagal yang akurat. Daftar tetap disaring seperti sebelumnya.
  const handleScannedCode = useCallback(async (code) => {
    const term = (code || "").trim();
    if (!term) return;
    setSearchInput(term);
    if (!activity?.id) { toast.info(`Kode terbaca: ${term}`); return; }
    const tId = toast.loading(`Memverifikasi ${term}…`);
    try {
      const r = await axios.get(`${API}/assets`, {
        params: { activity_id: activity.id, search: term, page: 1, page_size: 10 },
      });
      if ((r.data?.total || 0) > 0) {
        const a = (r.data.items || [])[0];
        const nama = a?.asset_name || a?.asset_code || term;
        toast.success(`Barang ditemukan: ${nama}`, { id: tId });
      } else {
        toast.error(`Barang "${term}" tidak ada di kegiatan ini`, { id: tId });
      }
    } catch {
      // Offline / gagal jaringan: jangan klaim berhasil — beri info netral.
      toast.info(`Kode terbaca: ${term} — periksa daftar hasil`, { id: tId });
    }
  }, [activity?.id, setSearchInput]);

  const handleBatchUpdate = useCallback(async (updates) => {
    if (selectedAssets.size === 0) return;
    setBatchUpdating(true);
    try {
      const allIds = Array.from(selectedAssets);
      const CHUNK_SIZE = 200;
      if (allIds.length > CHUNK_SIZE) {
        let totalUpdated = 0;
        let compressionInfo = null;
        const chunks = [];
        for (let i = 0; i < allIds.length; i += CHUNK_SIZE) chunks.push(allIds.slice(i, i + CHUNK_SIZE));
        for (let ci = 0; ci < chunks.length; ci++) {
          toast.loading(`Memproses batch ${ci + 1}/${chunks.length}...`, { id: 'batch-progress' });
          const r = await axios.put(`${API}/assets/batch-update`, { asset_ids: chunks[ci], updates }, {
            headers: { "X-User-Id": user?.id, "X-User-Name": user?.name || user?.username }, timeout: 300000,
          });
          totalUpdated += r.data.updated || 0;
          if (r.data.photo_compression) compressionInfo = r.data.photo_compression;
        }
        toast.dismiss('batch-progress');
        const msg = compressionInfo
          ? `${totalUpdated} aset diupdate. Foto dikompres ${compressionInfo.method}: ${compressionInfo.original_kb}KB → ${compressionInfo.compressed_kb}KB (-${compressionInfo.reduction_pct}%)`
          : `${totalUpdated} aset berhasil diupdate`;
        toast.success(msg);
      } else {
        const r = await axios.put(`${API}/assets/batch-update`, { asset_ids: allIds, updates }, {
          headers: { "X-User-Id": user?.id, "X-User-Name": user?.name || user?.username }, timeout: 300000,
        });
        const ci = r.data.photo_compression;
        const msg = ci
          ? `${r.data.updated} aset diupdate. Foto dikompres ${ci.method}: ${ci.original_kb}KB → ${ci.compressed_kb}KB (-${ci.reduction_pct}%)`
          : `${r.data.updated} aset berhasil diupdate`;
        toast.success(msg);
      }
      clearSelection();
      refreshData();
    } catch (err) {
      console.error("Batch update error:", err?.response?.status, err?.response?.data, err?.message);
      toast.dismiss('batch-progress');
      const detail = getApiError(err);
      if (err.code === 'ECONNABORTED') toast.error("Request timeout — coba lagi dengan lebih sedikit aset");
      else if (err.response?.status === 413) toast.error("Data terlalu besar — kurangi jumlah foto/file");
      else toast.error(detail || `Gagal batch update: ${err.message || 'Unknown error'}`);
    } finally { setBatchUpdating(false); }
  }, [selectedAssets, user, clearSelection]);

  const handleGroupBatchEdit = useCallback((assetIds) => {
    if (!assetIds || assetIds.length === 0) return;
    setSelectedAssets(new Set(assetIds));
    setShowBatchPanel(true);
  }, []);

  // === DATA FETCHING ===
  // OFFLINE READ PATH: serve the list from the local snapshot (filter/sort/
  // paginate client-side). Returns true when data was served. TTL >7 hari
  // diperlakukan seperti tidak ada snapshot (pesan kedaluwarsa).
  const serveFromSnapshot = async (page, size, search, category, sort, appendMobile = false, prependMobile = false) => {
    if (!activity?.id) return false;
    try {
      const rows = await getSnapshotAssets(activity.id);
      if (!rows) {
        const meta = await snapshotMeta(activity.id);
        if (isSnapshotExpired(meta)) {
          toast.error("Data offline kedaluwarsa, hubungkan internet untuk sinkron ulang", { id: "snapshot-expired", duration: 6000 });
        }
        return false;
      }
      const filtered = sortSnapshotRows(filterSnapshotRows(rows, { search, category, filters }), sort);
      const totalFiltered = filtered.length;
      const totalPg = Math.max(1, Math.ceil(totalFiltered / size));
      const pg = Math.max(1, Math.min(page, totalPg));
      const pageItems = filtered.slice((pg - 1) * size, pg * size);
      // Unsynced offline CREATEs live only in the save queue — merge them on
      // page 1 exactly like doFetch does after a live refetch.
      const pendingRows = pg === 1 ? getPendingItems()
        .filter(it => !it.isEdit && it.payload && it.payload.activity_id === activity?.id)
        .map(it => ({ ...it.payload, id: it.tempId, thumbnail: it.payload.photo || null, created_at: it.queuedAt || new Date().toISOString() }))
        .filter(row => !pageItems.some(a => serverHasPendingRow(a, row))) : [];
      const merged = pendingRows.length ? [...pendingRows, ...pageItems] : pageItems;
      setAssets(merged);
      setTotalItems(totalFiltered);
      setTotalPages(totalPg);
      setCurrentPage(pg);
      if (prependMobile) {
        setMobileAssets(prev => [...pageItems, ...prev]);   // PREPEND (scroll-atas dua arah)
        setMobileFirstPage(pg);
      } else if (appendMobile && pg > 1) {
        setMobileAssets(prev => [...prev, ...pageItems]);
        setMobileCurrentPage(pg);
      } else {
        setMobileAssets(merged);
        setMobileCurrentPage(pg);
        setMobileFirstPage(pg);
      }
      const meta = await snapshotMeta(activity.id);
      setOfflineLastSync(meta?.lastSync || null);
      setOfflineServed(true);
      setLoadingMessage(`Mode offline — menampilkan ${merged.length} dari ${totalFiltered} aset tersimpan`);
      // Kembalikan baris halaman ini (append: hanya slice baru) agar pemanggil
      // seperti loadMoreMobile bisa membuka aset pertama halaman berikutnya
      // (alur simpan-lanjut lintas halaman). Array truthy → pemeriksaan
      // `if (served)` di pemanggil lama tetap benar.
      return prependMobile ? pageItems : (appendMobile && pg > 1) ? pageItems : merged;
    } catch {
      return false;
    }
  };

  const doFetch = async (page, size, search, category, sort, appendMobile = false, preserveMobile = false) => {
    // Offline: don't wait for a network timeout — serve the snapshot directly.
    if (!isOnlineRef.current) {
      const served = await serveFromSnapshot(page, size, search, category, sort, appendMobile);
      if (served) return;
    }
    try {
      setLoadingMessage(`Memuat halaman ${page}...`);
      const params = new URLSearchParams();
      if (search) params.append("search", search);
      if (category && category !== "Semua") params.append("category", category);
      params.append("sort_by", sort || "newest");
      params.append("page", String(page));
      params.append("page_size", String(size));
      if (activity?.id) params.append("activity_id", activity.id);
      buildFilterParams(params);
      const r = await axios.get(`${API}/assets?${params.toString()}`);
      const newItems = r.data.items || [];
      // Halaman di luar rentang (mis. baris terakhir baru dihapus) → mundur ke
      // halaman terakhir yang berisi data alih-alih menampilkan layar kosong.
      const totalPagesResp = r.data.total_pages || 1;
      if ((r.data.total || 0) > 0 && newItems.length === 0 && page > totalPagesResp) {
        return doFetch(totalPagesResp, size, search, category, sort, appendMobile);
      }
      // Keep unsynced CREATE rows visible: a refetch replaces the list, but
      // rows still waiting in the save queue don't exist on the server yet.
      const pendingRows = getPendingItems()
        .filter(it => !it.isEdit && it.payload && it.payload.activity_id === activity?.id)
        .map(it => ({ ...it.payload, id: it.tempId, thumbnail: it.payload.photo || null, created_at: it.queuedAt || new Date().toISOString() }))
        .filter(row => !newItems.some(a => serverHasPendingRow(a, row)));
      const merged = pendingRows.length ? [...pendingRows, ...newItems] : newItems;
      setAssets(merged);
      setTotalItems(r.data.total || 0);
      setTotalPages(r.data.total_pages || 1);
      setCurrentPage(r.data.page || 1);
      if (appendMobile && page > 1) {
        setMobileAssets(prev => [...prev, ...newItems]);
      } else if (!preserveMobile) {
        // Jendela galeri = [P, P]: JANGAN reset ke 1. Bila pindah dari halaman
        // tabel (mis. hal. 5) lalu ke galeri, jendela mulai di 5 sehingga
        // scroll-atas dapat memuat 4,3,2,1 (dua arah) dan scroll-bawah 6,7…
        setMobileAssets(merged);
        setMobileCurrentPage(r.data.page || 1);
        setMobileFirstPage(r.data.page || 1);
      }
      // preserveMobile: sengaja TIDAK menyentuh mobileAssets/halaman galeri —
      // jendela infinite-scroll + posisi scroll HP tetap; baris yang baru
      // disimpan sudah diperbarui optimis + via onRowSynced.
      setOfflineServed(false); // live data on screen again
      setLoadingMessage(`Berhasil memuat ${newItems.length} dari ${r.data.total || 0} aset`);
      // Kembalikan baris halaman ini agar pemanggil (goToPage → alur simpan-
      // lanjut lintas halaman mode list/tabel) bisa membuka aset pertamanya.
      return merged;
    } catch {
      // Network failed (offline / server unreachable) → fall back to snapshot
      const served = await serveFromSnapshot(page, size, search, category, sort, appendMobile);
      if (served) return Array.isArray(served) ? served : null;
      if (!served) {
        const meta = await snapshotMeta(activity?.id);
        if (isSnapshotExpired(meta)) {
          // serveFromSnapshot already toasted "Data offline kedaluwarsa…"
          setLoadingMessage("Data offline kedaluwarsa — hubungkan internet untuk sinkron ulang");
        } else if (!isOnlineRef.current || !navigator.onLine) {
          // Offline with no snapshot yet — actionable message, not a generic error
          toast.error("Anda sedang offline dan belum ada data tersimpan untuk kegiatan ini. Aktifkan Mode Inventarisasi saat online untuk menyiapkan data offline.", { id: "offline-no-snapshot", duration: 7000 });
          setLoadingMessage("Mode offline — data tersimpan belum tersedia");
        } else {
          toast.error("Gagal memuat data");
        }
      }
    }
  };

  // Mengembalikan array baris yang baru dimuat (halaman berikutnya) atau null
  // bila tak ada lagi/ gagal — dipakai alur simpan-lanjut lintas halaman untuk
  // membuka aset pertama halaman baru.
  const loadMoreMobile = async () => {
    if (mobileLoading || mobileCurrentPage >= totalPages) return null;
    setMobileLoading(true);
    const nextPage = mobileCurrentPage + 1;
    // Offline: append the next page straight from the snapshot
    if (!isOnlineRef.current) {
      const served = await serveFromSnapshot(nextPage, pageSize, debouncedSearch, filterCategory, sortBy, true);
      if (served) { setMobileLoading(false); return Array.isArray(served) ? served : []; }
    }
    try {
      const params = new URLSearchParams();
      if (debouncedSearch) params.append("search", debouncedSearch);
      if (filterCategory && filterCategory !== "Semua") params.append("category", filterCategory);
      params.append("sort_by", sortBy || "newest");
      params.append("page", String(nextPage));
      params.append("page_size", String(pageSize));
      if (activity?.id) params.append("activity_id", activity.id);
      buildFilterParams(params);
      const r = await axios.get(`${API}/assets?${params.toString()}`);
      const items = r.data.items || [];
      setMobileAssets(prev => [...prev, ...items]);
      setMobileCurrentPage(nextPage);
      return items;
    } catch {
      const served = await serveFromSnapshot(nextPage, pageSize, debouncedSearch, filterCategory, sortBy, true);
      if (!served) toast.error("Gagal memuat data lanjutan");
      return Array.isArray(served) ? served : null;
    }
    finally { setMobileLoading(false); }
  };
  const loadMoreMobileRef = useRef(loadMoreMobile);
  loadMoreMobileRef.current = loadMoreMobile;

  // Muat halaman SEBELUMNYA (scroll ke atas di galeri) — cermin loadMoreMobile,
  // tetapi PREPEND agar urutan global & filter tetap terjaga. Flag mobileLoading
  // yang sama menyerialkan terhadap loadMore sehingga sentinel atas & bawah tak
  // saling memicu bersamaan. Mengembalikan baris baru (untuk anchor scroll).
  const loadPrevMobile = async () => {
    if (mobileLoading || mobileFirstPage <= 1) return null;
    setMobileLoading(true);
    const prevPage = mobileFirstPage - 1;
    if (!isOnlineRef.current) {
      const served = await serveFromSnapshot(prevPage, pageSize, debouncedSearch, filterCategory, sortBy, false, true);
      if (served) { setMobileLoading(false); return Array.isArray(served) ? served : []; }
    }
    try {
      const params = new URLSearchParams();
      if (debouncedSearch) params.append("search", debouncedSearch);
      if (filterCategory && filterCategory !== "Semua") params.append("category", filterCategory);
      params.append("sort_by", sortBy || "newest");
      params.append("page", String(prevPage));
      params.append("page_size", String(pageSize));
      if (activity?.id) params.append("activity_id", activity.id);
      buildFilterParams(params);
      const r = await axios.get(`${API}/assets?${params.toString()}`);
      const items = r.data.items || [];
      setMobileAssets(prev => [...items, ...prev]);   // PREPEND
      setMobileFirstPage(prevPage);
      return items;
    } catch {
      const served = await serveFromSnapshot(prevPage, pageSize, debouncedSearch, filterCategory, sortBy, false, true);
      if (!served) toast.error("Gagal memuat data sebelumnya");
      return Array.isArray(served) ? served : null;
    }
    finally { setMobileLoading(false); }
  };
  const loadPrevMobileRef = useRef(loadPrevMobile);
  loadPrevMobileRef.current = loadPrevMobile;

  const doFetchStats = async (search, category) => {
    try {
      const params = new URLSearchParams();
      if (search) params.append("search", search);
      if (category && category !== "Semua") params.append("category", category);
      if (activity?.id) params.append("activity_id", activity.id);
      const r = await axios.get(`${API}/assets/stats?${params.toString()}`);
      setStats({ totalAssets: r.data.total_assets||0, totalValue: (r.data.total_value||0).toLocaleString('id-ID'), activeCount: r.data.active_count||0, maintenanceCount: r.data.maintenance_count||0 });
    } catch {}
  };

  // Kategori di-cache ke localStorage agar "pilih kategori" (wajib isi) TETAP
  // bisa dipakai saat OFFLINE — sehingga input aset baru bisa masuk antrean
  // walau sinyal hilang. Cache diperbarui tiap berhasil ambil dari server.
  const doFetchCategories = async () => {
    try {
      const r = await axios.get(`${API}/categories/all`);
      const list = Array.isArray(r.data) ? r.data : [];
      setCategories(list);
      try { localStorage.setItem("aman_categories_cache", JSON.stringify(list)); } catch { /* penuh/diblokir — abaikan */ }
    } catch {
      // Offline / gagal → pakai cache terakhir supaya kategori tetap tampil.
      try {
        const cached = JSON.parse(localStorage.getItem("aman_categories_cache") || "null");
        setCategories(Array.isArray(cached) ? cached : []);
      } catch { setCategories([]); }
    }
  };

  const fetchParamsRef = useRef({ debouncedSearch, filterCategory, sortBy, pageSize, currentPage });
  fetchParamsRef.current = { debouncedSearch, filterCategory, sortBy, pageSize, currentPage };

  // showLoading: user-initiated refetches (filter/sort/page-size) show the
  // list skeleton; background refreshes (post-save sync, WS) stay silent so
  // they never flash an overlay while someone is working.
  const refreshData = (page, { showLoading = false, preserveMobile = false } = {}) => {
    const p = fetchParamsRef.current;
    const pg = page !== undefined ? page : p.currentPage;
    const work = Promise.all([
      // preserveMobile: rekonsiliasi daftar desktop + hitungan TANPA menyusun
      // ulang jendela infinite-scroll HP (mencegah lompatan posisi scroll saat
      // menutup form setelah simpan; baris tersimpan sudah diperbarui optimis).
      doFetch(pg, p.pageSize, p.debouncedSearch, p.filterCategory, p.sortBy, false, preserveMobile),
      doFetchStats(p.debouncedSearch, p.filterCategory),
    ]);
    if (showLoading) {
      setPageLoading(true);
      work.finally(() => setPageLoading(false));
    }
    return work;
  };
  const refreshDataRef = useRef(refreshData);
  refreshDataRef.current = refreshData;

  // === OFFLINE SNAPSHOT SYNC ===
  // Runs when inventory mode turns ON, and again on every 'online' recovery
  // while inventory mode is active (isOnline false→true re-runs the effect).
  // Background + non-blocking; progress shows in InventoryProgressBar.
  useEffect(() => {
    if (!inventoryMode || !isOnline || !activity?.id || !user?.id) return;
    let cancelled = false;
    setSnapshotState({ phase: "syncing", pct: 0 });
    syncSnapshot(activity.id, user.id, (p) => {
      if (!cancelled) setSnapshotState({ phase: "syncing", pct: p.pct });
    })
      .then(({ count, lastSync, partial }) => {
        if (cancelled) return;
        setSnapshotState({ phase: "ready", count, lastSync, partial: !!partial });
        setOfflineLastSync(lastSync);
        // Penyimpanan perangkat penuh: cache offline hanya sebagian tersimpan,
        // tapi aplikasi tidak crash & antrian simpan tetap utuh. Beri tahu sekali.
        if (partial) {
          toast.warning(
            `Penyimpanan perangkat hampir penuh — hanya ${count} aset tersimpan untuk mode offline. Kosongkan ruang lalu sinkron ulang.`,
            { duration: 7000 }
          );
        }
      })
      .catch((e) => {
        if (cancelled) return;
        setSnapshotState({ phase: "error" });
        if (process.env.NODE_ENV !== "production") {
          console.warn("[dashboard] Snapshot sync failed:", e?.message);
        }
      });
    return () => { cancelled = true; };
  }, [inventoryMode, isOnline, activity?.id, user?.id]);

  // On reconnect while the list is showing snapshot data: the save queue
  // already auto-flushes (useOptimisticQueue) and the effect above runs the
  // delta sync — here we swap the visible list back to live server data.
  useEffect(() => {
    if (isOnline && offlineServedRef.current) refreshDataRef.current?.();
  }, [isOnline]);

  // Initial data fetch
  useEffect(() => {
    setLoading(true);
    setLoadingMessage("Memuat data aset...");
    Promise.all([doFetch(1,50,"","Semua","newest"), doFetchStats("","Semua"), doFetchCategories(), fetchFilterOptions()])
      .finally(() => { setLoading(false); setLoadingMessage(""); });
  }, [activity?.id]);

  // Re-fetch on filter/search/sort change
  const isInitialMount = useRef(true);
  useEffect(() => {
    if (isInitialMount.current) { isInitialMount.current = false; return; }
    refreshData(1, { showLoading: true });
  }, [debouncedSearch, filterCategory, sortBy, pageSize, filters.condition, filters.status, filters.location, filters.eselon1, filters.eselon2, filters.stiker, filters.inventoryStatus, filters.priceMin, filters.priceMax, filters.nomorSpm, filters.perolehanDari, filters.dateFrom, filters.dateTo, filters.user, filters.penggunaNip]);

  const goToPage = async (p) => {
    const np = Math.max(1, Math.min(p, totalPages));
    setPageLoading(true);
    setLoadingMessage(`Memuat halaman ${np} dari ${totalPages}...`);
    const items = await doFetch(np, pageSize, debouncedSearch, filterCategory, sortBy);
    setPageLoading(false);
    return items;   // baris halaman baru (untuk alur simpan-lanjut mode list)
  };
  const goToPageRef = useRef(goToPage);
  goToPageRef.current = goToPage;

  const applyFilters = () => {
    setPageLoading(true);
    Promise.all([
      doFetch(1, pageSize, debouncedSearch, filterCategory, sortBy),
      doFetchStats(debouncedSearch, filterCategory),
    ]).finally(() => setPageLoading(false));
    setShowAdvancedFilter(false);
  };

  // === PULL TO REFRESH ===
  const { pull, mainContentRef, handleTouchStart, handleTouchMove, handleTouchEnd } = usePullToRefresh({
    onRefresh: async () => {
      await Promise.all([
        doFetch(1, pageSize, debouncedSearch, filterCategory, sortBy),
        doFetchStats(debouncedSearch, filterCategory)
      ]);
      toast.success("Data berhasil diperbarui");
    },
  });

  // === FORM HANDLERS ===
  const handleEdit = useCallback(async (asset) => {
    // Only unlock previous row if it's NOT still saving in the queue
    if (editAssetForForm?.id && editAssetForForm.id !== asset.id) {
      const prevStatus = syncStatuses[editAssetForForm.id]?.status;
      if (!prevStatus || prevStatus === 'saved' || prevStatus === 'failed') {
        await unlockAsset(editAssetForForm.id);
      }
      // If 'queued' or 'saving', the lock will be released by onItemSaved after save completes
    }
    const lock = rowLocks[asset.id];
    if (lock && lock.session_id !== sessionId) { toast.error(`Aset sedang diedit oleh ${lock.user_name}`); return false; }
    const locked = await lockAsset(asset.id);
    if (!locked) return false;
    setEditAssetForForm(asset);
    setIsSidebarOpen(true);
    if (!formPanelVisible) setFormPanelVisible(true);
    return true;
  }, [rowLocks, sessionId, lockAsset, formPanelVisible, editAssetForForm, unlockAsset, syncStatuses]);

  const handleFormClose = useCallback(() => {
    if (editAssetForForm?.id) {
      const prevStatus = syncStatuses[editAssetForForm.id]?.status;
      if (!prevStatus || prevStatus === 'saved' || prevStatus === 'failed') {
        unlockAsset(editAssetForForm.id);
      }
    }
    setIsSidebarOpen(false);
    // Capture WHICH row this close belongs to. If the user opens another row
    // within the 300ms window (fast row-to-row input), this stale timer must
    // not clear that newer edit nor refresh the list under it — that was
    // wiping in-progress input whenever the previous row's background save
    // completed around the same moment.
    const closingId = editAssetForForm?.id ?? null;
    setTimeout(() => {
      // editAssetRef mirrors editAssetForForm on every render, so it reflects
      // whatever edit is open NOW (state updaters can't be read synchronously).
      const activeEdit = editAssetRef.current;
      if (activeEdit && activeEdit.id !== closingId) {
        // A newer edit opened within the window — leave its form untouched and
        // don't consume the refresh flags; they're handled on its own close.
        return;
      }
      setEditAssetForForm(null);
      // Deferred refresh: sync with server now that editing is done.
      // preserveMobile: rekonsiliasi hitungan/daftar desktop TANPA menyusun
      // ulang jendela galeri HP → posisi scroll & baris terselect tetap di
      // tempat (fokus pengguna ke data terjaga). Baris yang baru disimpan sudah
      // diperbarui optimis + via onRowSynced, jadi tak perlu muat ulang HP.
      const queueNeedsRefresh = consumeRefreshFlag();
      const wsNeedsRefresh = wsNeedsRefreshRef.current;
      wsNeedsRefreshRef.current = false;
      if (queueNeedsRefresh || wsNeedsRefresh) refreshData(undefined, { preserveMobile: true });
    }, 300);
  }, [editAssetForForm, unlockAsset, syncStatuses, consumeRefreshFlag]);

  const handleFormSubmitSuccess = useCallback(() => {
    if (editAssetForForm?.id) unlockAsset(editAssetForForm.id);
    setEditAssetForForm(null);
    wsNeedsRefreshRef.current = false;
    refreshData();
  }, [editAssetForForm, unlockAsset]);

  const handleOptimisticSubmit = useCallback((payload, isEdit, editId, usePatch = false) => {
    const assetId = isEdit ? editId : `temp_${Date.now()}`;
    // Capture the version the user started editing from (for OCC / If-Match).
    // Aset hasil scan QR bisa TIDAK ada di halaman list saat ini — pakai versi
    // dari baris edit yang terbuka sebagai fallback agar If-Match tetap terkirim.
    const baseVersion = isEdit
      ? (assets.find(a => a.id === editId)?.version
         ?? (editAssetRef.current?.id === editId ? editAssetRef.current?.version : null)
         ?? null)
      : null;
    if (isEdit && editId) {
      setAssets(prev => prev.map(a => a.id === editId ? { ...a, ...payload, thumbnail: payload.photo || a.thumbnail } : a));
      setMobileAssets(prev => prev.map(a => a.id === editId ? { ...a, ...payload, thumbnail: payload.photo || a.thumbnail } : a));
      // Offline: mirror the optimistic edit into the read snapshot so a
      // reload (served from snapshot) still shows it. Heavy fields (photo,
      // checklist) are stripped by the lib; the queue holds the real payload.
      if (!isOnlineRef.current && activity?.id) {
        const cached = assetsStateRef.current.find(a => a.id === editId);
        upsertSnapshotAsset(activity.id, { ...(cached || {}), ...payload, id: editId });
      }
      // Row stays locked until save completes (unlocked by onItemSaved callback)
    } else {
      const tempAsset = { ...payload, id: assetId, thumbnail: payload.photo || null, created_at: new Date().toISOString() };
      setAssets(prev => [tempAsset, ...prev]);
      setMobileAssets(prev => [tempAsset, ...prev]);
      setTotalItems(prev => prev + 1);
    }
    setEditAssetForForm(null);
    setIsSidebarOpen(false);
    enqueueOptimistic({ tempId: assetId, payload, isEdit, editId: isEdit ? editId : undefined, usePatch, baseVersion, nama_kegiatan: activity?.nama_kegiatan }).catch(() => {
      // Save failed — KEEP the optimistic row so the retry/dismiss UI stays
      // attached to it (syncStatuses[assetId] shows 'failed'). The temp row is
      // removed only via dismissSync → onItemDismissed.
    });
    toast.info(isEdit ? "Menyimpan perubahan..." : "Menambahkan aset...", { duration: 1500 });
  }, [enqueueOptimistic, assets, activity?.id, activity?.nama_kegiatan]);

  // TAMBAH CEPAT dari peta (klik kanan / tekan lama di area peta): aset
  // terbentuk di titik yang dipilih dengan default halaman tambah aset —
  // kategori DUMMY + kode aset + NUP berurutan otomatis + "Belum
  // Diinventarisasi" — pengguna cukup mengetik nama barang. Lewat antrean
  // optimistis yang sama dengan form (offline-first).
  const handleQuickAddPeta = useCallback(async (lat, lng, nama, fotos = []) => {
    const dummy = cariKategoriDummy(categories);
    const nup = await reserveDummyNup(activity?.id, dummy?.kode_aset, dummy?.label || "Dummy");
    const daftarFoto = Array.isArray(fotos) ? fotos.slice(0, 6) : [];
    const payload = {
      asset_code: dummy?.kode_aset || "",
      NUP: nup,
      asset_name: String(nama || "").trim(),
      category: dummy?.label || "Dummy",
      condition: "Baik", status: "Aktif",
      stiker_status: "Belum Terpasang",
      // Aturan sama dengan form aset: ada foto → barang terbukti DITEMUKAN.
      inventory_status: daftarFoto.length ? "Ditemukan" : "Belum Diinventarisasi",
      koordinat_latitude: Number(lat).toFixed(7),
      koordinat_longitude: Number(lng).toFixed(7),
      photos: daftarFoto,
      photo: daftarFoto[0] || null,
      thumbnail_index: 0,
      activity_id: activity?.id || null,
    };
    handleOptimisticSubmit(payload, false);
  }, [categories, activity?.id, handleOptimisticSubmit]);

  // Peta mengikuti filter aktif: builder query yang SAMA dengan daftar aset
  // (search + kategori + filter lanjutan), tanpa paging — peta yang paging.
  const buildMapParams = useCallback(() => {
    const params = new URLSearchParams();
    if (debouncedSearch) params.append("search", debouncedSearch);
    if (filterCategory && filterCategory !== "Semua") params.append("category", filterCategory);
    if (activity?.id) params.append("activity_id", activity.id);
    buildFilterParams(params);
    return params;
  }, [debouncedSearch, filterCategory, activity?.id, buildFilterParams]);

  // Filter yang sama untuk data snapshot saat offline.
  const mapClientFilter = useCallback(
    (rows) => filterSnapshotRows(rows, { search: debouncedSearch, category: filterCategory, filters }),
    [debouncedSearch, filterCategory, filters]
  );

  // Geser pin di Peta Aset → simpan koordinat baru otomatis lewat antrean
  // simpan yang sama dengan form (If-Match + Idempotency-Key + retry offline).
  const handleMapCoordsSave = useCallback((row, lat, lng) => {
    // Simpanan antrean melepas kunci baris saat selesai (onItemSaved) — jangan
    // izinkan geser pin aset yang sedang dibuka di form edit sesi ini, dan
    // hormati kunci sesi lain (error sinkron → pin di-revert oleh panel).
    if (editAssetRef.current?.id === row.id) {
      toast.error("Aset ini sedang dibuka di form edit — simpan/tutup form dulu");
      throw new Error("row-open-in-form");
    }
    const lock = rowLocks[row.id];
    if (lock && lock.session_id !== sessionId) {
      toast.error(`Aset sedang diedit oleh ${lock.user_name}`);
      throw new Error("row-locked");
    }
    const payload = { koordinat_latitude: lat, koordinat_longitude: lng };
    setAssets(prev => prev.map(a => (a.id === row.id ? { ...a, ...payload } : a)));
    setMobileAssets(prev => prev.map(a => (a.id === row.id ? { ...a, ...payload } : a)));
    if (activity?.id) upsertSnapshotAsset(activity.id, { ...row, ...payload, id: row.id });
    const baseVersion = assetsStateRef.current.find(a => a.id === row.id)?.version ?? row.version ?? null;
    // Fire-and-forget: antrean menjamin simpan (retry saat online kembali) —
    // kegagalan sesaat TIDAK me-revert pin; konflik ditangani UI antrean.
    enqueueOptimistic({
      tempId: row.id, payload, isEdit: true, editId: row.id, usePatch: true, baseVersion,
    }).catch(() => {});
  }, [enqueueOptimistic, activity?.id, rowLocks, sessionId]);

  // Save current asset in background + navigate to next/prev row
  const handleSaveAndNavigate = useCallback(async (payload, isEdit, editId, direction, usePatch = false) => {
    const assetId = isEdit ? editId : `temp_${Date.now()}`;
    const baseVersion = isEdit
      ? (mobileAssets.find(a => a.id === editId)?.version
         ?? assets.find(a => a.id === editId)?.version
         ?? (editAssetRef.current?.id === editId ? editAssetRef.current?.version : null)
         ?? null)
      : null;
    const isScan = typeof direction === "string" && direction.startsWith("camera:scan:");
    const isStay = direction === "camera:stay"; // simpan tanpa pindah aset (alur Simpan & Scan)
    // PATCH kosong (tidak ada perubahan) → tak perlu simpan, langsung navigasi.
    const hasChanges = !isEdit || !usePatch || (payload && Object.keys(payload).length > 0);
    // 1) Optimistic local update (row stays locked until save completes via onItemSaved)
    if (!hasChanges) { /* lewati update optimistik & antrean */ } else if (isEdit && editId) {
      setAssets(prev => prev.map(a => a.id === editId ? { ...a, ...payload, thumbnail: payload.photo || a.thumbnail } : a));
      setMobileAssets(prev => prev.map(a => a.id === editId ? { ...a, ...payload, thumbnail: payload.photo || a.thumbnail } : a));
      // Offline: mirror the optimistic edit into the read snapshot (see
      // handleOptimisticSubmit for rationale).
      if (!isOnlineRef.current && activity?.id) {
        const cached = assetsStateRef.current.find(a => a.id === editId);
        upsertSnapshotAsset(activity.id, { ...(cached || {}), ...payload, id: editId });
      }
    } else {
      const tempAsset = { ...payload, id: assetId, thumbnail: payload.photo || null, created_at: new Date().toISOString() };
      setAssets(prev => [tempAsset, ...prev]);
      setMobileAssets(prev => [tempAsset, ...prev]);
      setTotalItems(prev => prev + 1);
    }
    // 2) Enqueue background save
    if (hasChanges) {
      enqueueOptimistic({ tempId: assetId, payload, isEdit, editId: isEdit ? editId : undefined, usePatch, baseVersion, nama_kegiatan: activity?.nama_kegiatan }).catch(() => {
        // Save failed — KEEP the optimistic row (retry/dismiss UI needs it);
        // removed only via dismissSync → onItemDismissed.
      });
      toast.info("Menyimpan di background...", { duration: 1200 });
    } else if (isEdit && editId && !isScan && !isStay) {
      // Tanpa perubahan tidak ada antrean yang akan melepas kunci baris
      // (biasanya onItemSaved) — lepaskan sekarang sebelum pindah aset.
      // (Alur scan melepasnya nanti HANYA bila benar-benar pindah aset.)
      unlockAsset(editId);
    }

    // 3a-awal) Simpan tanpa pindah: form/kamera tetap pada aset yang sama —
    //     scanner dibuka lagi oleh FullCameraSheet setelah tombol ditekan.
    if (isStay) return;

    // 3a) Alur scan QR dari Mode Kamera (edit inventarisasi): cari aset hasil
    //     scan di kegiatan ini, kunci, lalu buka untuk diedit — kamera tetap
    //     terbuka karena editAsset hanya berganti (sama seperti prev/next).
    //     Pencarian substring bisa mengenai banyak baris (satu kode aset utk
    //     banyak NUP) — hanya buka otomatis bila cocok EKSAK dan tunggal.
    if (isScan) {
      const code = direction.slice("camera:scan:".length).trim();
      if (!code || !activity?.id) return;
      const tId = toast.loading(`Mencari "${code}"…`);
      try {
        const r = await axios.get(`${API}/assets`, {
          params: { activity_id: activity.id, search: code, page: 1, page_size: 50 },
        });
        const items = r.data?.items || [];
        const codeLc = code.toLowerCase();
        const exact = items.filter(a =>
          [a.kode_register, a.asset_code, a.serial_number]
            .some(v => String(v || "").toLowerCase() === codeLc));
        let found = null;
        if (exact.length === 1) found = exact[0];
        else if (exact.length === 0 && (r.data?.total || 0) === 1) found = items[0];
        if (!found) {
          if ((r.data?.total || 0) === 0) {
            toast.error(`Barang "${code}" tidak ada di kegiatan ini`, { id: tId });
          } else {
            setSearchInput(code);
            toast.info(`${exact.length > 1 ? exact.length : r.data.total} aset cocok dengan "${code}" — pilih dari daftar`, { id: tId, duration: 5000 });
          }
          return; // kunci aset yang sedang dibuka tetap dipegang
        }
        if (found.id === editId) { toast.info("QR menunjuk aset yang sedang dibuka", { id: tId }); return; }
        const lock = rowLocks[found.id];
        if (lock && lock.session_id !== sessionId) { toast.error(`Aset sedang diedit oleh ${lock.user_name}`, { id: tId }); return; }
        const locked = await lockAsset(found.id);
        if (!locked) { toast.dismiss(tId); return; }
        // Benar-benar pindah: bila tak ada perubahan tersimpan (tidak ada
        // antrean yang akan melepasnya), lepaskan kunci aset lama sekarang.
        if (!hasChanges && editId) unlockAsset(editId);
        setEditAssetForForm(found);
        toast.success(`${found.asset_name || found.asset_code}: siap diedit`, { id: tId });
      } catch {
        toast.error("Gagal mencari aset hasil scan — periksa koneksi", { id: tId });
      }
      return;
    }

    // 3) Navigate to next/prev asset. Pakai `mobileAssets` (bukan `assets`):
    //    di tabel (≥lg) isinya sama dgn halaman aktif, di galeri/kartu ia
    //    superset yang memuat baris halaman 2+ — sehingga navigasi konsisten
    //    dengan gerbang tombol Simpan (assetIndex/totalAssetsInView juga dari
    //    mobileAssets). Tanpa ini, di galeri halaman 2+ baris tak ditemukan
    //    (-1) dan form tutup alih-alih lanjut ke aset berikutnya.
    const navList = mobileAssets;
    const currentIndex = navList.findIndex(a => a.id === editId);
    const nextIndex = direction === 'next' ? currentIndex + 1 : currentIndex - 1;

    if (currentIndex !== -1 && nextIndex >= 0 && nextIndex < navList.length) {
      const nextAsset = navList[nextIndex];
      const lock = rowLocks[nextAsset.id];
      if (lock && lock.session_id !== sessionId) {
        toast.error(`Aset berikutnya sedang diedit oleh ${lock.user_name}`);
        setEditAssetForForm(null);
        setIsSidebarOpen(false);
        return;
      }
      const locked = await lockAsset(nextAsset.id);
      if (locked) {
        setEditAssetForForm(nextAsset);
      } else {
        setEditAssetForForm(null);
        setIsSidebarOpen(false);
      }
    } else if (direction === 'next' && currentIndex !== -1 && mobileCurrentPage < totalPages) {
      // Di ujung daftar yang sudah dimuat tapi masih ada halaman berikutnya:
      // muat halaman berikutnya lalu buka aset PERTAMA-nya — ritme input
      // lintas halaman tak terputus. Kedua loader mengembalikan baris baru
      // (tak bergantung state async).
      //  • Mode LIST + desktop (≥lg): tabel BERPAGINASI → geser HALAMAN tabel
      //    via goToPage supaya tampilan tabel + kontrol paginasi ikut pindah
      //    (bukan sekadar menambah baris tersembunyi yang bikin "page tak
      //    berpindah").
      //  • Galeri (semua) & kartu mobile (<lg): infinite scroll → loadMoreMobile
      //    (append).
      const isDesktopList = viewModeRef.current !== 'gallery'
        && typeof window !== 'undefined'
        && window.matchMedia('(min-width: 1024px)').matches;
      const fresh = isDesktopList
        ? await goToPageRef.current(currentPage + 1)
        : await loadMoreMobileRef.current();
      const nextAsset = (fresh && fresh.length) ? fresh[0] : null;
      if (!nextAsset) {
        // Gagal memuat / halaman kosong (loadMoreMobile sudah beri tahu bila gagal)
        setEditAssetForForm(null);
        setIsSidebarOpen(false);
        return;
      }
      const lock = rowLocks[nextAsset.id];
      if (lock && lock.session_id !== sessionId) {
        toast.error(`Aset berikutnya sedang diedit oleh ${lock.user_name}`);
        setEditAssetForForm(null);
        setIsSidebarOpen(false);
        return;
      }
      const locked = await lockAsset(nextAsset.id);
      if (locked) setEditAssetForForm(nextAsset);
      else { setEditAssetForForm(null); setIsSidebarOpen(false); }
    } else {
      toast.info(direction === 'next' ? "Sudah di aset terakhir" : "Sudah di aset pertama halaman ini");
      setEditAssetForForm(null);
      setIsSidebarOpen(false);
    }
  }, [assets, mobileAssets, mobileCurrentPage, currentPage, totalPages, lockAsset, unlockAsset, enqueueOptimistic, rowLocks, sessionId, activity?.id, activity?.nama_kegiatan, setSearchInput]);

  // Mode Kamera Penuh — "tinjau aset tersimpan": simpan aset saat ini lalu muat
  // aset yang tersimpan sebelumnya (paling atas daftar) ke form untuk ditinjau/
  // diperbaiki, tanpa keluar dari kamera. Setelah itu tombol ◀/▶ memakai
  // navigasi standar (onSaveAndNavigate) antar aset yang sudah ada.
  const handleCameraReviewSaved = useCallback(async (payload, isEdit, editId, usePatch = false, navigateOnly = false) => {
    // navigateOnly = pindah ke aset sebelumnya TANPA menyimpan aset saat ini
    // (dipakai saat aset baru masih kosong — hindari validasi/simpan).
    if (!navigateOnly) {
      const assetId = isEdit ? editId : `temp_${Date.now()}`;
      const baseVersion = isEdit ? (assets.find(a => a.id === editId)?.version ?? null) : null;
      if (isEdit && editId) {
        setAssets(prev => prev.map(a => a.id === editId ? { ...a, ...payload, thumbnail: payload.photo || a.thumbnail } : a));
        setMobileAssets(prev => prev.map(a => a.id === editId ? { ...a, ...payload, thumbnail: payload.photo || a.thumbnail } : a));
      } else {
        const tempAsset = { ...payload, id: assetId, thumbnail: payload.photo || null, created_at: new Date().toISOString() };
        setAssets(prev => [tempAsset, ...prev]);
        setMobileAssets(prev => [tempAsset, ...prev]);
        setTotalItems(prev => prev + 1);
      }
      enqueueOptimistic({ tempId: assetId, payload, isEdit, editId: isEdit ? editId : undefined, usePatch, baseVersion }).catch(() => {});
    }
    // Aset yang ditinjau = aset terbaru SEBELUM simpan ini (kalau tadi kita
    // meng-edit aset itu sendiri, ambil tetangga di atasnya).
    const target = assets.find(a => a.id !== editId) || null;
    if (!target) { toast.info("Belum ada aset lain untuk ditinjau"); return; }
    // Aset sebelumnya masih PROSES PENYIMPANAN (antrean/temp) → belum bisa
    // dibuka untuk diedit; beri notifikasi yang sesuai.
    const st = syncStatuses[target.id]?.status;
    if (String(target.id).startsWith("temp_") || st === "queued" || st === "saving" || st === "failed") {
      toast.info("Aset sebelumnya masih dalam proses penyimpanan — tunggu sebentar lalu coba lagi.");
      return;
    }
    const lock = rowLocks[target.id];
    if (lock && lock.session_id !== sessionId) { toast.error(`Aset sedang diedit oleh ${lock.user_name}`); return; }
    const locked = await lockAsset(target.id);
    if (locked) setEditAssetForForm(target);
    else toast.error("Aset sedang dikunci pengguna lain");
  }, [assets, lockAsset, enqueueOptimistic, rowLocks, sessionId, activity?.id, syncStatuses]);

  const handleDelete = useCallback(async id => {
    // Aset yang BELUM tersinkron (id "temp_") → batalkan dari antrean simpan.
    // JANGAN kirim DELETE (id itu tak ada di server) — itu gagal lalu CREATE-nya
    // tetap lolos belakangan → "aset hantu". dismissSync membuang baris temp +
    // item antrean + salinan persist sekaligus.
    if (String(id).startsWith("temp_")) {
      const ok = await confirm({
        title: "Batalkan Aset", description: "Aset ini belum tersimpan ke server. Batalkan penambahannya?",
        confirmLabel: "Batalkan", variant: "danger",
      });
      if (!ok) return false;
      dismissSync(id);
      toast.success("Dibatalkan");
      return true;
    }
    const ok = await confirm({
      title: "Hapus Aset",
      description: "Aset ini akan dihapus permanen. Lanjutkan?",
      confirmLabel: "Hapus",
      variant: "danger",
    });
    if (!ok) return false;
    // Hapus butuh koneksi (belum ada antrean hapus offline). Tanpa guard ini,
    // saat offline axios.delete gagal → refetch menyajikan snapshot yang masih
    // berisi baris tadi → baris "muncul lagi" & hapus hilang diam-diam.
    if (!isOnlineRef.current) {
      toast.error("Hapus aset memerlukan koneksi internet. Coba lagi saat online.");
      return false;
    }
    setIsDeleting(id);
    // Optimistis: baris langsung HILANG dari layar (tak perlu tunggu server /
    // refresh manual). refreshData() di bawah hanya rekonsiliasi hitungan.
    setAssets(prev => prev.filter(a => a.id !== id));
    setMobileAssets(prev => prev.filter(a => a.id !== id));
    setTotalItems(prev => Math.max(0, prev - 1));
    setSelectedAssets(prev => { if (!prev.has(id)) return prev; const n = new Set(prev); n.delete(id); return n; });
    try {
      await axios.delete(`${API}/assets/${id}`);
      if (activity?.id) removeSnapshotAsset(activity.id, id);
      toast.success("Dihapus");
      refreshDataRef.current(); // rekonsiliasi (doFetch meng-clamp halaman kosong)
      return true; // pemanggil (mis. popup peta) perlu tahu hapus benar terjadi
    } catch (err) {
      toast.error(getApiError(err, "Gagal hapus"));
      refreshDataRef.current(); // rollback: muat ulang agar baris kembali bila hapus gagal
      return false;
    } finally { setIsDeleting(null); }
  }, [confirm, activity?.id, dismissSync]);

  // Kartu Inventarisasi — riwayat pengesahan lintas kegiatan per identitas aset.
  // kode_satker kegiatan aktif ikut dikirim agar riwayat dibatasi pada satuan
  // kerja yang sama (identitas aset yang sama di satker lain tidak tampil).
  const handleOpenKartu = useCallback((asset) => {
    if (!asset) return;
    setKartuIdentity({
      kode_register: asset.kode_register || "",
      asset_code: asset.asset_code || "",
      NUP: asset.NUP || "",
      asset_name: asset.asset_name || "",
      kode_satker: activity?.kode_satker || "",
      nama_satker: activity?.nama_satker || "",
    });
  }, [activity?.kode_satker, activity?.nama_satker]);

  // Timeline Aset lintas modul — cukup id; identitas & saudara dicari backend.
  const handleOpenTimeline = useCallback((assetId) => {
    if (assetId) setTimelineAssetId(assetId);
  }, []);

  // === UI HANDLERS ===
  const handleAnalyticsToggle = useCallback(() => setAnalyticsOpen(prev => !prev), []);
  const handleAuditToggle = useCallback(() => setAuditOpen(prev => !prev), []);
  const handleViewAssetAudit = useCallback((assetId, assetCode) => { setAuditAssetId(assetId); setAuditAssetCode(assetCode); setAuditOpen(true); }, []);
  const handleClearAuditFilter = useCallback(() => { setAuditAssetId(""); setAuditAssetCode(""); }, []);

  const handleAnalyticsDragStart = useCallback((e) => {
    e.preventDefault(); e.stopPropagation();
    isDragging.current = true;
    dragStartY.current = e.touches ? e.touches[0].clientY : e.clientY;
    dragStartHeight.current = analyticsPanelHeight;
    const onMove = (ev) => { if (!isDragging.current) return; const clientY = ev.touches ? ev.touches[0].clientY : ev.clientY; const delta = clientY - dragStartY.current; setAnalyticsPanelHeight(Math.max(150, Math.min(500, dragStartHeight.current + delta))); };
    const onEnd = () => { isDragging.current = false; document.removeEventListener("mousemove", onMove); document.removeEventListener("mouseup", onEnd); document.removeEventListener("touchmove", onMove); document.removeEventListener("touchend", onEnd); };
    document.addEventListener("mousemove", onMove); document.addEventListener("mouseup", onEnd);
    document.addEventListener("touchmove", onMove, { passive: false }); document.addEventListener("touchend", onEnd);
  }, [analyticsPanelHeight]);

  const handlePrintCard = useCallback(async assetId => {
    const progress = makeDownloadProgress("kartu inventaris");
    try {
      const r = await axios.get(`${API}/assets/${assetId}/card`, { responseType: 'blob', onDownloadProgress: progress.onDownloadProgress });
      const blob = new Blob([r.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const newWindow = window.open(url, '_blank');
      if (!newWindow) { const a = document.createElement('a'); a.href = url; a.download = `kartu_inventaris_${assetId}.pdf`; document.body.appendChild(a); a.click(); document.body.removeChild(a); progress.success("Kartu inventaris berhasil diunduh"); }
      else progress.success("Kartu inventaris berhasil dibuat (ukuran KTP)");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) { console.error('Print card error:', err); progress.error(getApiError(err, "Gagal cetak kartu")); }
  }, []);

  // ── Cetak Stiker Label BMN (3 ukuran × A4/A3, ikut filter aktif) ──
  const [stikerOpen, setStikerOpen] = useState(false);
  const buildStikerParams = useCallback(() => {
    const params = new URLSearchParams();
    if (debouncedSearch) params.append("search", debouncedSearch);
    if (filterCategory && filterCategory !== "Semua") params.append("category", filterCategory);
    if (activity?.id) params.append("activity_id", activity.id);
    buildFilterParams(params);
    return params;
  }, [debouncedSearch, filterCategory, activity, buildFilterParams]);

  const handlePrintBulkCards = useCallback(async () => {
    if (assets.length === 0) { toast.error("Tidak ada aset untuk dicetak"); return; }
    const progress = makeDownloadProgress(`${assets.length} kartu inventaris`);
    try {
      const r = await axios.post(`${API}/assets/cards/bulk`, assets.map(a => a.id), { responseType: 'blob', onDownloadProgress: progress.onDownloadProgress });
      const url = URL.createObjectURL(new Blob([r.data]));
      const newWindow = window.open(url, '_blank');
      if (!newWindow) { const a = document.createElement('a'); a.href = url; a.download = `kartu_inventaris_massal_${assets.length}.pdf`; document.body.appendChild(a); a.click(); document.body.removeChild(a); progress.success(`${assets.length} kartu inventaris berhasil diunduh`); }
      else progress.success(`${assets.length} kartu inventaris berhasil dibuat`);
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) { console.error('Bulk print error:', err); progress.error(getApiError(err, "Gagal cetak kartu massal")); }
  }, [assets]);

  const handleExport = useCallback(async fmt => {
    if (!activity?.id) { toast.error("Pilih kegiatan inventarisasi terlebih dahulu"); return; }
    if (totalItems === 0) { toast.error("Tidak ada data aset untuk diexport"); return; }
    setExporting(true);
    try {
      await downloadFileWithProgress(
        `${API}/export/${fmt}?activity_id=${activity.id}&base_url=${encodeURIComponent(process.env.REACT_APP_BACKEND_URL || '')}`,
        `inventory_${activity.nama_kegiatan || 'export'}.${fmt === 'xlsx' ? 'xlsx' : fmt}`,
        {
          label: `Export ${fmt.toUpperCase()}`,
          timeout: 300000,
          timeoutMessage: 'Export timeout - data terlalu besar. Coba export dengan filter kategori.',
        }
      );
    } catch (err) {
      console.error('Export error:', err); // toast error sudah ditangani helper
    } finally { setExporting(false); }
  }, [activity, totalItems]);

  const handleExportExecutivePDF = useCallback(async () => {
    if (!activity?.id) { toast.error("Pilih kegiatan inventarisasi terlebih dahulu"); return; }
    setExporting(true);
    try {
      await downloadFileWithProgress(
        `${API}/inventory-activities/${activity.id}/executive-summary-pdf`,
        `Laporan_Eksekutif_${activity.nama_kegiatan || 'BMN'}.pdf`,
        { label: "Laporan Eksekutif" }
      );
    } catch (err) {
      console.error('Executive PDF export error:', err); // toast error sudah ditangani helper
    } finally { setExporting(false); }
  }, [activity]);

  const handlePreviewExecutive = useCallback(() => {
    if (!activity?.id) { toast.error("Pilih kegiatan inventarisasi terlebih dahulu"); return; }
    window.open(authMediaUrl(`${process.env.REACT_APP_BACKEND_URL}/api/inventory-activities/${activity.id}/executive-summary-html`), '_blank');
  }, [activity]);

  // Compute current edit position for navigation.
  // Navigasi form ("Simpan → aset berikutnya") memakai `mobileAssets`, BUKAN
  // `assets`: di layout tabel (≥lg) keduanya berisi halaman yang sama, tetapi
  // di tampilan galeri/kartu (infinite scroll) `mobileAssets` adalah SUPERSET
  // yang memuat baris halaman 2+ sedangkan `assets` beku di halaman 1. Bila
  // indeks dihitung dari `assets`, baris galeri halaman 2+ tak ditemukan
  // (indeks -1) → gerbang tombol Simpan gagal → form jatuh ke jalur tutup +
  // refresh (kolaps ke halaman 1), bukan lanjut ke aset berikutnya.
  const editAssetIndex = useMemo(() => {
    if (!editAssetForForm?.id) return -1;
    return mobileAssets.findIndex(a => a.id === editAssetForForm.id);
  }, [editAssetForForm?.id, mobileAssets]);

  // Tombol Back/Undo browser: jangan keluar aplikasi — tutup overlay teratas
  // dulu, dan bila tak ada, kembali ke daftar kegiatan (tetap di aplikasi).
  const handleAppBack = useCallback(() => {
    if (kartuIdentity) { setKartuIdentity(null); return; }
    if (dialogs.import) { closeDialog('import'); return; }
    if (dialogs.userManagement) { closeDialog('userManagement'); return; }
    if (dialogs.categoryManager) { closeDialog('categoryManager'); return; }
    if (dialogs.bulkDelete) { setDialog('bulkDelete', false); return; }
    if (auditOpen) { setAuditOpen(false); return; }
    if (selectedAssets.size > 0) { clearSelection(); return; }
    // Form edit versi mobile adalah overlay (di desktop selalu tampil) — tutup
    // hanya di layar kecil agar tidak mengganggu panel desktop.
    if (isSidebarOpen && typeof window !== 'undefined' && window.matchMedia('(max-width: 1023px)').matches) {
      handleFormClose(); return;
    }
    if (showAdvancedFilter) { setShowAdvancedFilter(false); return; }
    onBack();
  }, [kartuIdentity, dialogs, auditOpen, selectedAssets, isSidebarOpen, showAdvancedFilter, closeDialog, setDialog, clearSelection, handleFormClose, setShowAdvancedFilter, onBack]);
  useBackGuard(handleAppBack);

  // === RENDER ===
  // h-screen + overflow-hidden mengunci app-shell tepat setinggi viewport
  // (header + baris h-[calc(100vh-53px)] = 100vh). Tanpa ini, sisa sub-piksel
  // membuat DOKUMEN bisa ter-scroll saat roda mouse di atas header (yang bukan
  // area scroll) → muncul "efek turun sedikit" yang mengganggu.
  return (
    <div
      className="h-screen bg-background text-foreground overflow-hidden"
      onDragEnter={perms.canImport && !dialogs.categoryManager ? handleDragEnter : undefined}
      onDragLeave={perms.canImport && !dialogs.categoryManager ? handleDragLeave : undefined}
      onDragOver={perms.canImport && !dialogs.categoryManager ? handleDragOver : undefined}
      onDrop={perms.canImport && !dialogs.categoryManager ? handleDrop : undefined}
    >
      {/* Drag & Drop Overlay */}
      {isDragOverImport && perms.canImport && !dialogs.categoryManager && (
        <div className="fixed inset-0 z-[90] bg-blue-600/20 backdrop-blur-sm flex items-center justify-center pointer-events-none" data-testid="drag-drop-overlay">
          <div className="bg-card rounded-2xl shadow-2xl border-4 border-dashed border-blue-500 px-12 py-10 flex flex-col items-center gap-3">
            <div className="w-16 h-16 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center">
              <Package className="w-8 h-8 text-blue-600 animate-bounce" />
            </div>
            <p className="text-lg font-bold text-blue-800 dark:text-blue-300">Drop File Import</p>
            <p className="text-sm text-muted-foreground">CSV atau Excel (.xlsx / .xls)</p>
          </div>
        </div>
      )}
      {/* Export progress is surfaced non-blockingly via the download toast
          (downloadFileWithProgress) + BackgroundTaskBar — no redundant
          full-screen blocking overlay. `exporting` still disables the toolbar
          export buttons to prevent double-submits. */}
      {/* HEADER */}
      <DashboardHeader
        activity={activity} user={user} perms={perms}
        onBack={onBack} onLogout={onLogout}
        auditOpen={auditOpen} onAuditToggle={handleAuditToggle}
        onOpenUserManagement={() => openDialog('userManagement')}
        isOnline={isOnline} wsConnected={wsConnected} onlineUsers={onlineUsers}
        pendingCount={pendingCount} syncing={isSyncing} actionCount={actionCount} onSync={() => flushPending(false)}
        dark={dark} toggleDark={toggleDark}
        onShowInfo={onShowInfo}
      />

      <div className="flex h-[calc(100vh-53px)] overflow-x-hidden">
        {/* Toggle Button for Form Panel (Desktop only) */}
        {perms.canEdit && (
          <button
            onClick={() => setFormPanelVisible(prev => !prev)}
            className={`hidden lg:flex fixed top-1/2 -translate-y-1/2 z-50 bg-card border border-border rounded-r-lg items-center justify-center text-muted-foreground hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-all shadow-md hover:shadow-lg ${formPanelVisible ? 'border-l-0 w-5 h-14 flex-col' : 'w-7 h-28 flex-col gap-1'}`}
            style={{ left: formPanelVisible ? '319px' : '0px', transition: 'left 0.3s ease' }}
            title={formPanelVisible ? 'Sembunyikan Form' : 'Tampilkan Form Tambah Aset'}
            data-testid="form-panel-toggle"
          >
            {formPanelVisible ? <PanelLeftClose className="w-3.5 h-3.5" /> : (
              <>
                <PanelLeftOpen className="w-3.5 h-3.5" />
                {/* Saat terlipat, sliver diberi label vertikal agar jalan
                    kembali ke form terlihat (audit G6 #13). */}
                <span className="text-[9px] font-bold tracking-wider" style={{ writingMode: 'vertical-rl' }}>FORM</span>
              </>
            )}
          </button>
        )}

        {/* ASSET FORM SIDEBAR - only for admin/operator */}
        {perms.canEdit && (
          <div className={`hidden lg:block ${formPanelVisible ? 'w-[320px] min-w-[320px]' : 'w-0 min-w-0 overflow-hidden'}`} style={{ transition: 'width 0.3s ease, min-width 0.3s ease', willChange: 'width', contain: 'layout style' }}>
            <AssetForm isOpen={isSidebarOpen || formPanelVisible} onClose={handleFormClose} activity={activity} categories={categories} editAsset={editAssetForForm} onSubmitSuccess={handleFormSubmitSuccess} onOptimisticSubmit={handleOptimisticSubmit} onSaveAndNavigate={handleSaveAndNavigate} onCameraReviewSaved={handleCameraReviewSaved} onExitToNewAsset={() => setEditAssetForForm(null)} assetIndex={editAssetIndex} totalAssetsInView={mobileAssets.length} hasMoreToLoad={mobileCurrentPage < totalPages} saveQueueLength={queueLength} inventoryMode={inventoryMode} onShowCategoryManager={perms.canManageCategories ? () => openDialog('categoryManager') : undefined} onOpenKartu={handleOpenKartu} onOpenTimeline={handleOpenTimeline} alwaysExpanded={formPanelVisible} />
          </div>
        )}
        {perms.canEdit && (
          <div className="lg:hidden">
            <AssetForm isOpen={isSidebarOpen} onClose={handleFormClose} activity={activity} categories={categories} editAsset={editAssetForForm} onSubmitSuccess={handleFormSubmitSuccess} onOptimisticSubmit={handleOptimisticSubmit} onSaveAndNavigate={handleSaveAndNavigate} onCameraReviewSaved={handleCameraReviewSaved} onExitToNewAsset={() => setEditAssetForForm(null)} assetIndex={editAssetIndex} totalAssetsInView={mobileAssets.length} hasMoreToLoad={mobileCurrentPage < totalPages} saveQueueLength={queueLength} inventoryMode={inventoryMode} onShowCategoryManager={perms.canManageCategories ? () => openDialog('categoryManager') : undefined} onOpenKartu={handleOpenKartu} onOpenTimeline={handleOpenTimeline} />
          </div>
        )}

        {/* MAIN CONTENT */}
        <main className="flex-1 min-w-0 overflow-y-auto overflow-x-hidden" ref={mainContentRef} style={{ contain: 'layout style', willChange: 'width' }} onTouchStart={handleTouchStart} onTouchMove={handleTouchMove} onTouchEnd={handleTouchEnd}>
          {/* Pull-to-refresh indicator - Mobile only */}
          <div className="sm:hidden flex items-center justify-center overflow-hidden transition-all duration-200 bg-gradient-to-b from-blue-50 to-transparent" style={{ height: pull.pullDistance > 0 ? pull.pullDistance : 0, opacity: pull.pullDistance > 0 ? 1 : 0 }}>
            <div className="flex flex-col items-center gap-1">
              <div className={`w-8 h-8 rounded-full border-2 border-blue-500 flex items-center justify-center transition-transform duration-200 ${pull.isRefreshing ? 'animate-spin' : ''}`} style={{ transform: `rotate(${Math.min(pull.pullDistance * 3, 360)}deg)` }}>
                {pull.isRefreshing ? <Loader2 className="w-4 h-4 text-blue-500" /> : <ChevronDown className={`w-4 h-4 text-blue-500 transition-transform ${pull.pullDistance >= 80 ? 'rotate-180' : ''}`} />}
              </div>
              <span className="text-xs text-blue-600 font-medium">{pull.isRefreshing ? 'Memperbarui...' : pull.pullDistance >= 80 ? 'Lepaskan untuk refresh' : 'Tarik ke bawah'}</span>
            </div>
          </div>

          <div className="p-1.5 sm:p-3 space-y-1.5 sm:space-y-2">
            {/* Banner kegiatan disahkan — seluruh data terkunci */}
            {sealed && (
              <div className="flex items-start gap-2.5 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-300 dark:border-emerald-700 rounded-xl px-3 py-2" data-testid="sealed-banner">
                <Lock className="w-4 h-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-300">
                    Kegiatan telah disahkan{activity?.ticket_number ? ` (tiket ${activity.ticket_number})` : ""} — data terkunci
                  </p>
                  <p className="text-xs text-emerald-700/80 dark:text-emerald-400/80">
                    Data aset tidak dapat ditambah, diubah, atau dihapus. Riwayat tercatat di Kartu Inventarisasi.
                  </p>
                </div>
              </div>
            )}
            <StatsBar stats={stats} inventoryMode={inventoryMode} setInventoryMode={setInventoryMode} isOnline={isOnline} pendingCount={pendingCount} snapshotServed={offlineServed} snapshotLastSync={offlineLastSync} />
            {inventoryMode && (
              <InventoryProgressBar
                activityId={activity?.id}
                inventoryStatusFilter={filters.inventoryStatus}
                onFilterChange={handleAdvancedFilterChange}
                isOnline={isOnline} pendingCount={pendingCount}
                rowLocks={rowLocks} sessionId={sessionId}
                refreshKey={progressRefreshKey}
                snapshotState={snapshotState}
                inventoryMode={inventoryMode} setInventoryMode={setInventoryMode}
              />
            )}
            <DashboardToolbar
              searchInput={searchInput} setSearchInput={setSearchInput} onScanCode={handleScannedCode} onOpenMap={() => setMapOpen(p => !p)} mapOpen={mapOpen} categories={categories} filterCategory={filterCategory} setFilterCategory={setFilterCategory}
              activeFilterCount={activeFilterCount} showAdvancedFilter={showAdvancedFilter} setShowAdvancedFilter={setShowAdvancedFilter}
              sortBy={sortBy} setSortBy={setSortBy} exporting={exporting} handleExport={handleExport} handleExportExecutivePDF={handleExportExecutivePDF}
              handlePreviewExecutive={handlePreviewExecutive} perms={perms} openDialog={openDialog} handlePrintBulkCards={handlePrintBulkCards}
              onCetakStiker={() => setStikerOpen(true)}
              assetsCount={assets.length} filters={filters} filterOptions={filterOptions} handleAdvancedFilterChange={handleAdvancedFilterChange}
              resetAdvancedFilters={resetAdvancedFilters} handleCategoryReset={() => { handleCategoryReset(); refreshData(1); }}
              refreshData={refreshData} viewMode={viewMode} setViewMode={setViewMode}
            />

            {/* Tiga panel (Analytics/Rekapitulasi/Barang Serupa) disatukan jadi
                SATU kontrol segmented menyamping di semua viewport — hemat ruang
                (dulu tiga bar bertumpuk ~120px) & memperlebar area data. Isi
                panel dirender di bawah baris ini saat segmennya aktif. */}
            {/* Tanpa overflow-hidden + margin atas → badge notifikasi bisa
                menjorok keluar tepi atas kotak tanpa terpotong. */}
            {!mapOpen && (
            <div className="flex items-stretch rounded-xl border border-border bg-card shadow-sm divide-x divide-border mt-2" data-testid="panel-segmented">
              {!inventoryMode && (
                <PanelSegment
                  active={analyticsOpen} onClick={handleAnalyticsToggle} testid="chip-analytics"
                  icon={BarChart3} label="Analytics" roundedL
                  activeCls="bg-blue-600 text-white" iconCls="text-blue-600" />
              )}
              {!inventoryMode && (
                <PanelSegment
                  active={rekapOpen} onClick={() => setRekapOpen(p => !p)} testid="chip-rekap"
                  icon={ClipboardList} label="Rekapitulasi"
                  badge={rekapTotal != null ? `${rekapTotal} BMN` : null}
                  badgeCls="bg-blue-600 text-white"
                  activeCls="bg-blue-600 text-white" iconCls="text-blue-600" />
              )}
              <PanelSegment
                active={groupsOpen} onClick={() => setGroupsOpen(p => !p)} testid="chip-groups"
                icon={Layers} label="Barang Serupa" roundedR roundedL={inventoryMode}
                badge={groupsCount ? `${groupsCount} grup` : null}
                badgeCls="bg-violet-600 text-white"
                activeCls="bg-violet-600 text-white" iconCls="text-violet-600" />
            </div>
            )}
            {!inventoryMode && !mapOpen && analyticsOpen && <Suspense fallback={null}><AnalyticsPanel embedded activityId={activity?.id} isOpen={analyticsOpen} onToggle={handleAnalyticsToggle} panelHeight={analyticsPanelHeight} onDragStart={handleAnalyticsDragStart} /></Suspense>}
            {!inventoryMode && !mapOpen && rekapOpen && <Suspense fallback={null}><RekapitulasiPanel embedded activityId={activity?.id} isOpen={rekapOpen} onToggle={() => setRekapOpen(p => !p)} onTotal={setRekapTotal} /></Suspense>}
            {!mapOpen && groupsOpen && <Suspense fallback={null}><AssetGroupsPanel embedded activityId={activity?.id} isOpen={groupsOpen} onToggle={() => setGroupsOpen(p => !p)} onCount={setGroupsCount} onBatchEdit={perms.canEdit ? handleGroupBatchEdit : undefined} /></Suspense>}

            {mapOpen ? (
              <Suspense fallback={<div className="py-16 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-teal-600" /></div>}>
                <AssetMapFullView
                  activityId={activity?.id}
                  activityName={activity?.nama_kegiatan}
                  onClose={() => setMapOpen(false)}
                  canEdit={perms.canEdit}
                  onEditAsset={perms.canEdit ? handleEdit : undefined}
                  onDeleteAsset={perms.canDelete ? handleDelete : undefined}
                  onSaveCoords={handleMapCoordsSave}
                  buildParams={buildMapParams}
                  clientFilter={mapClientFilter}
                  activeFilterCount={activeFilterCount + (debouncedSearch ? 1 : 0)}
                  selectedIds={selectedAssets}
                  onQuickAdd={perms.canEdit ? handleQuickAddPeta : undefined}
                />
              </Suspense>
            ) : loading ? (
              <LoadingIndicator message={loadingMessage} totalItems={totalItems} pageSize={pageSize} currentPage={currentPage} />
            ) : assets.length === 0 ? (
              (activeFilterCount > 0 || searchInput.trim()) ? (
                /* Filter/pencarian aktif → hasil kosong, bukan berarti belum ada aset */
                <div className="text-center py-16" data-testid="empty-filtered">
                  <Package className="w-12 h-12 mx-auto mb-3 text-muted-foreground" />
                  <p className="text-muted-foreground mb-3">Tidak ada aset yang cocok dengan filter</p>
                  <Button
                    variant="outline" size="sm"
                    onClick={() => { setSearchInput(''); resetAdvancedFilters(); refreshData(1); }}
                    data-testid="empty-reset-filter-btn"
                  >
                    Reset filter
                  </Button>
                </div>
              ) : (
                /* Benar-benar belum ada aset pada kegiatan ini */
                <div className="text-center py-16" data-testid="empty-no-assets">
                  <Package className="w-12 h-12 mx-auto mb-3 text-muted-foreground" />
                  <p className="text-foreground/80 font-medium mb-1">Belum ada aset</p>
                  <p className="text-xs text-muted-foreground mb-3">Tambah aset pertama untuk kegiatan ini.</p>
                  {perms.canEdit && (
                    <Button
                      size="sm" className="bg-blue-600 hover:bg-blue-700 text-white gap-1"
                      onClick={() => { setEditAssetForForm(null); setIsSidebarOpen(true); }}
                      data-testid="empty-add-asset-btn"
                    >
                      <Plus className="w-4 h-4" />Tambah Aset
                    </Button>
                  )}
                </div>
              )
            ) : (<div className="relative">
              {/* Skeleton overlay for page-size / pagination / filter / sort
                  requests. The relative wrapper scopes it to the list area
                  (previously inset-0 resolved against the viewport because
                  no ancestor was positioned). */}
              {pageLoading && (
                <ListLoadingSkeleton rows={Math.min(pageSize, 12)} message={loadingMessage} variant={viewMode === 'gallery' ? 'gallery' : 'list'} />
              )}

              {selectedAssets.size > 0 && (<>
                {/* Toolbar seleksi — tampil di SEMUA viewport (HP/tablet/desktop):
                    hitungan + pilih-semua/kosongkan + buka-tutup Ubah Massal. */}
                {perms.canEdit && (
                  <div className={`flex items-center gap-1.5 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 px-2.5 py-1 ${showBatchPanel ? "rounded-t-lg border-b-0" : "rounded-lg"}`} data-testid="selection-toolbar">
                    {/* Hitungan = TEKS (tanpa bingkai). Aksi = TOMBOL (berbingkai/
                        solid) supaya jelas mana teks, mana tombol. Satu baris,
                        padat; label aksi menciut jadi ikon di layar sempit. */}
                    <span className="text-xs text-blue-800 dark:text-blue-300 flex-shrink-0 whitespace-nowrap">
                      <b className="text-sm font-bold">{selectedAssets.size}</b> terpilih
                    </span>
                    <button onClick={toggleSelectAllVisible} title="Pilih/batal semua aset di tampilan ini" className="h-7 px-2 rounded-md border border-blue-300 dark:border-blue-700 bg-white/70 dark:bg-transparent text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/40 text-xs font-medium flex items-center gap-1 flex-shrink-0 transition-colors" data-testid="select-all-visible-btn">
                      <CheckSquare className="w-3.5 h-3.5" /><span className="hidden sm:inline">Pilih semua</span>
                    </button>
                    <button onClick={clearSelection} title="Kosongkan seleksi" className="h-7 px-2 rounded-md border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 text-xs font-medium flex items-center gap-1 flex-shrink-0 transition-colors" data-testid="clear-selection-btn">
                      <X className="w-3.5 h-3.5" /><span className="hidden sm:inline">Kosongkan</span>
                    </button>
                    <button onClick={() => setShowBatchPanel(v => !v)} className="ml-auto h-7 px-2.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-1 flex-shrink-0 transition-colors" data-testid="toggle-batch-panel-btn">
                      <Pen className="w-3.5 h-3.5" />{showBatchPanel ? "Tutup" : "Ubah Massal"}
                    </button>
                  </div>
                )}
                {selectedAssets.size === assets.length && totalItems > assets.length && (
                  <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-1.5 flex items-center justify-between text-xs">
                    <span className="text-amber-800 dark:text-amber-300">{selectedAssets.size} aset di halaman ini dipilih. Total ada <b>{totalItems}</b> aset.</span>
                    <button onClick={selectAllPages} className="text-blue-600 dark:text-blue-400 hover:underline font-semibold ml-2" data-testid="select-all-pages-btn">Pilih semua {totalItems} aset</button>
                  </div>
                )}
                {/* Menutup panel (X/Batal) MENCIUTKAN saja — seleksi dipertahankan. */}
                {perms.canEdit && showBatchPanel && (
                  <Suspense fallback={null}><BatchEditPanel attached selectedCount={selectedAssets.size} categories={categories} onApply={handleBatchUpdate} onClose={() => setShowBatchPanel(false)} updating={batchUpdating} activity={activity} assets={assets} selectedAssets={selectedAssets} /></Suspense>
                )}
              </>)}

              {viewMode === 'gallery' ? (
                <AssetGalleryView assets={mobileAssets} editId={editAssetForForm?.id} onEdit={perms.canEdit ? handleEdit : undefined} onDelete={perms.canDelete ? handleDelete : undefined} onPrintCard={handlePrintCard} onLoadMore={loadMoreMobile} onLoadPrev={loadPrevMobile} hasPrev={mobileFirstPage > 1} isLoadingMore={mobileLoading} hasMore={mobileCurrentPage < totalPages} totalItems={totalItems} rowLocks={rowLocks} currentSessionId={sessionId} selectedAssets={selectedAssets} onToggleSelect={perms.canEdit ? toggleSelectAsset : undefined} />
              ) : (<>
                <div className="relative hidden lg:block">
                  <TooltipProvider>
                    <VirtualizedAssetTable assets={assets} editId={editAssetForForm?.id} onEdit={perms.canEdit ? handleEdit : undefined} onDelete={perms.canDelete ? handleDelete : undefined} onPrintCard={handlePrintCard} onOpenKartu={handleOpenKartu} onViewAudit={handleViewAssetAudit} onOpenPhoto={setPhotoLightboxAsset} pageSize={pageSize} rowLocks={rowLocks} currentSessionId={sessionId} syncStatuses={syncStatuses} onRetrySync={retrySync} onDismissSync={dismissSync} selectedAssets={selectedAssets} onToggleSelect={perms.canEdit ? toggleSelectAsset : undefined} onToggleSelectAll={perms.canEdit ? toggleSelectAll : undefined} />
                  </TooltipProvider>
                </div>
                <div className="lg:hidden">
                  <VirtualizedMobileCards assets={mobileAssets} editId={editAssetForForm?.id} onEdit={perms.canEdit ? handleEdit : undefined} onDelete={perms.canDelete ? handleDelete : undefined} onOpenKartu={handleOpenKartu} onViewAudit={handleViewAssetAudit} onPrintCard={handlePrintCard} onOpenPhoto={setPhotoLightboxAsset} onLoadMore={loadMoreMobile} isLoadingMore={mobileLoading} hasMore={mobileCurrentPage < totalPages} totalItems={totalItems} rowLocks={rowLocks} currentSessionId={sessionId} syncStatuses={syncStatuses} onRetrySync={retrySync} onDismissSync={dismissSync} selectedAssets={selectedAssets} onToggleSelect={perms.canEdit ? toggleSelectAsset : undefined} />
                </div>
                <div className="hidden lg:block">
                  <AssetPagination currentPage={currentPage} totalPages={totalPages} totalItems={totalItems} pageSize={pageSize} setPageSize={setPageSize} goToPage={goToPage} />
                </div>
              </>)}
            </div>)}
          </div>
        </main>

        <Suspense fallback={null}><AuditLogPanel activityId={activity?.id} isOpen={auditOpen} onToggle={handleAuditToggle} selectedAssetId={auditAssetId} selectedAssetCode={auditAssetCode} onClearAssetFilter={handleClearAuditFilter} /></Suspense>


        {/* Scroll to Top Button */}
        <ScrollToTop scrollRef={mainContentRef} />
      </div>

      <BulkDeleteDialog open={dialogs.bulkDelete} onClose={v => setDialog('bulkDelete', v)} activityId={activity?.id} activityName={activity?.nama_kegiatan} totalItems={totalItems} onSuccess={() => refreshData(1)} />
      <CategoryManagerDialog open={dialogs.categoryManager} onClose={v => setDialog('categoryManager', v)} categories={categories} onCategoriesChanged={doFetchCategories} />
      <CetakStikerDialog open={stikerOpen} onOpenChange={setStikerOpen}
        buildParams={buildStikerParams} totalItems={totalItems} pageAssets={assets} />
      <Suspense fallback={null}>
        {dialogs.import && <LazyImportDialog open={dialogs.import} onClose={handleImportClose} onSuccess={() => { clearDropFile(); refreshData(1); doFetchCategories(); }} activityId={activity?.id} preloadFile={dropFile} />}
        {dialogs.userManagement && <LazyUserManagementDialog open={dialogs.userManagement} onClose={() => closeDialog('userManagement')} currentUser={user} />}
        {kartuIdentity && <LazyKartuInventarisasiDialog open={!!kartuIdentity} identity={kartuIdentity} onClose={() => setKartuIdentity(null)} />}
        {timelineAssetId && <LazyAssetTimelineDialog open={!!timelineAssetId} assetId={timelineAssetId} onClose={() => setTimelineAssetId(null)} />}
        {/* Lightbox foto dari baris mode list (tabel/kartu HP) — sama seperti galeri & popup peta. */}
        {photoLightboxAsset && <PhotoLightbox asset={photoLightboxAsset} onClose={() => setPhotoLightboxAsset(null)} onEdit={perms.canEdit ? handleEdit : undefined} siblings={mobileAssets?.length ? mobileAssets : assets} onSelectAsset={setPhotoLightboxAsset} />}
      </Suspense>
      {confirmDialog}

      {/* MOBILE FAB — placed at the root level (outside <main> and its `contain:
          layout style` / `will-change: width` ancestors) so `position: fixed`
          is anchored to the viewport, not the scroll container. Previously
          the button scrolled away with the content on mobile because a
          containing-block ancestor trapped the fixed position. */}
      {perms.canEdit && (
        <div className="fixed bottom-6 right-6 z-30 lg:hidden print:hidden">
          <Button
            onClick={() => { setEditAssetForForm(null); setIsSidebarOpen(true); }}
            className="h-14 w-14 rounded-full shadow-xl bg-blue-600 hover:bg-blue-700 p-0"
            aria-label="Tambah Aset"
            data-testid="mobile-add-asset-fab"
          >
            <Plus className="w-6 h-6" />
          </Button>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// MAIN EXPORT - Wrapper Component with Activity Flow
// ============================================================================
export default function DashboardPage({ user, onLogout, dark, toggleDark, onShowInfo, onShowModules }) {
  const [selectedActivity, setSelectedActivity] = useState(null);

  useEffect(() => {
    const storedId = localStorage.getItem('currentActivityId');
    if (storedId) {
      axios.get(`${API}/inventory-activities/${storedId}`)
        .then(r => {
          setSelectedActivity(r.data);
          try { localStorage.setItem('currentActivity', JSON.stringify(r.data)); } catch {}
        })
        .catch((err) => {
          // Offline reload (no server response): fall back to the cached
          // activity object so the dashboard — and its offline snapshot —
          // can still open. A real server answer (404 etc.) clears the id.
          if (!err?.response) {
            try {
              const cached = localStorage.getItem('currentActivity');
              const parsed = cached ? JSON.parse(cached) : null;
              if (parsed?.id === storedId) { setSelectedActivity(parsed); return; }
            } catch {}
          }
          localStorage.removeItem('currentActivityId');
          localStorage.removeItem('currentActivity');
        });
    }
  }, []);

  const handleSelectActivity = (activity) => {
    setSelectedActivity(activity);
    try {
      localStorage.setItem('currentActivityId', activity.id);
      // Cached copy lets an offline reload reopen this activity's dashboard
      localStorage.setItem('currentActivity', JSON.stringify(activity));
    } catch {}
  };

  const handleBack = () => { setSelectedActivity(null); localStorage.removeItem('currentActivityId'); localStorage.removeItem('currentActivity'); };
  const handleLogout = () => { localStorage.removeItem('currentActivityId'); localStorage.removeItem('currentActivity'); onLogout(); };

  // Re-fetch the active activity after pengesahan so the sealed banner + write-lock
  // gating (driven by activity.status_pengesahan) kick in without a full reload.
  const handleActivityRefresh = useCallback(async () => {
    const id = selectedActivity?.id;
    if (!id) return;
    try {
      const r = await axios.get(`${API}/inventory-activities/${id}`);
      setSelectedActivity(r.data);
      try { localStorage.setItem('currentActivity', JSON.stringify(r.data)); } catch {}
    } catch {
      // Non-fatal: keep the current activity object if the refresh fails.
    }
  }, [selectedActivity?.id]);

  if (!selectedActivity) return <ActivitySelectionPage user={user} onLogout={handleLogout} onSelectActivity={handleSelectActivity} onShowInfo={onShowInfo} onShowModules={onShowModules} />;
  return <AssetManagementPage user={user} onLogout={handleLogout} activity={selectedActivity} onBack={handleBack} onActivityRefresh={handleActivityRefresh} dark={dark} toggleDark={toggleDark} onShowInfo={onShowInfo} />;
}
