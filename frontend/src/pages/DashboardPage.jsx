// ============================================================================
// DASHBOARD PAGE - FULL FEATURED VERSION WITH ACTIVITY-BASED WORKFLOW
// OPTIMIZED: Virtual scrolling for large datasets (1M+ assets)
// REFACTORED: Custom hooks extracted to /hooks/ for maintainability
// ============================================================================
import React, { useState, useEffect, useRef, useMemo, useCallback, memo, useReducer, lazy, Suspense } from "react";
import {
  Package, Plus, X, ChevronDown, Loader2, Star,
  Users, PanelLeftClose, PanelLeftOpen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "@/lib/utils";

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
// Heavy panels - lazy loaded (only when user opens them)
const BatchEditPanel = lazy(() => import("@/components/assets/BatchEditPanel"));
const AnalyticsPanel = lazy(() => import("@/components/assets/AnalyticsPanel"));
const RekapitulasiPanel = lazy(() => import("@/components/assets/RekapitulasiPanel"));
const AuditLogPanel = lazy(() => import("@/components/assets/AuditLogPanel"));
const AssetGroupsPanel = lazy(() => import("@/components/assets/AssetGroupsPanel"));
import DashboardHeader from "@/components/assets/DashboardHeader";
import StatsBar from "@/components/assets/StatsBar";
import DashboardToolbar from "@/components/assets/DashboardToolbar";
import AssetPagination from "@/components/assets/AssetPagination";
import ScrollToTop from "@/components/assets/ScrollToTop";
import ListLoadingSkeleton from "@/components/assets/ListLoadingSkeleton";
import ActivitySelectionPage from "@/pages/ActivitySelectionPage";

import { TooltipProvider } from "@/components/ui/tooltip";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useOfflineSync } from "@/hooks/useOfflineSync";
import { useOptimisticQueue } from "@/hooks/useOptimisticQueue";
import { useRowLocking } from "@/hooks/useRowLocking";
import { useAssetFilters } from "@/hooks/useAssetFilters";
import { usePullToRefresh } from "@/hooks/usePullToRefresh";
import { useDragDropImport } from "@/hooks/useDragDropImport";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Lazy-loaded dialogs (loaded on demand when user opens them)
const LazyImportDialog = lazy(() => import("@/components/assets/ImportDialog"));
const LazyUserManagementDialog = lazy(() => import("@/components/assets/UserManagementDialog"));

// ============================================================================
// ASSET MANAGEMENT DASHBOARD (within Activity context)
// ============================================================================
function AssetManagementPage({ user, onLogout, activity, onBack, dark, toggleDark, onShowInfo }) {
  // RBAC permissions based on user role
  const perms = useMemo(() => {
    const role = user?.role || "viewer";
    return {
      canEdit: role === "admin" || role === "operator",
      canDelete: role === "admin" || role === "operator",
      canImport: role === "admin",
      canBulkDelete: role === "admin",
      canManageUsers: role === "admin",
      canManageCategories: role === "admin",
      role,
    };
  }, [user?.role]);

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
  const [mobileCurrentPage, setMobileCurrentPage] = useState(1);
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
  const [viewMode, setViewMode] = useState('list');
  const [auditOpen, setAuditOpen] = useState(false);
  const [auditAssetId, setAuditAssetId] = useState("");
  const [auditAssetCode, setAuditAssetCode] = useState("");

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

  const onWsAssetChange = useCallback(() => {
    // Deferred refresh: if user is editing, defer the refresh until form closes
    if (editAssetRef.current) {
      wsNeedsRefreshRef.current = true;
    } else {
      refreshData();
    }
  }, []);
  const { onlineUsers, connected: wsConnected, sendMessage: wsSend } = useWebSocket({
    activityId: activity?.id, userId: user?.id,
    userName: user?.name || user?.username,
    onAssetChange: onWsAssetChange, onLocksUpdate: (locks) => setRowLocks(locks),
  });
  const { isOnline, pendingCount, syncing, queueOperation, syncPending } = useOfflineSync({ onSyncComplete: onWsAssetChange });

  // Targeted row update after save (no full refresh while editing!)
  const handleRowSynced = useCallback((assetKey, serverData, isEdit) => {
    if (!serverData) return;
    if (isEdit) {
      // Update the specific row in the local list with server data
      setAssets(prev => prev.map(a => a.id === assetKey ? { ...a, ...serverData } : a));
      setMobileAssets(prev => prev.map(a => a.id === assetKey ? { ...a, ...serverData } : a));
    } else {
      // For new items, replace the temp item with the server-generated item
      const serverId = serverData.id;
      if (serverId && serverId !== assetKey) {
        setAssets(prev => prev.map(a => a.id === assetKey ? { ...a, ...serverData, id: serverId } : a));
        setMobileAssets(prev => prev.map(a => a.id === assetKey ? { ...a, ...serverData, id: serverId } : a));
      }
    }
  }, []);

  const { syncStatuses, enqueue: enqueueOptimistic, retry: retrySync, dismiss: dismissSync, queueLength, consumeRefreshFlag } = useOptimisticQueue({
    onItemSaved: (assetId) => unlockAsset(assetId),
    onItemFailed: (assetId) => unlockAsset(assetId),
    onRowSynced: handleRowSynced,
    onConflict: (assetId, conflictDetail) => {
      // Another user modified this asset before our save landed.
      // Show a toast and refresh the row so the user sees the latest server state.
      toast.error(conflictDetail?.message || "Data telah diubah pengguna lain. Memuat versi terbaru...", { duration: 4500 });
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
  });

  // === ROW LOCKING ===
  const { rowLocks, setRowLocks, sessionId, lockAsset, unlockAsset } = useRowLocking({
    activityId: activity?.id, user, wsSend,
  });

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
  const doFetch = async (page, size, search, category, sort, appendMobile = false) => {
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
      setAssets(newItems);
      setTotalItems(r.data.total || 0);
      setTotalPages(r.data.total_pages || 1);
      setCurrentPage(r.data.page || 1);
      if (appendMobile && page > 1) {
        setMobileAssets(prev => [...prev, ...newItems]);
      } else {
        setMobileAssets(newItems);
        setMobileCurrentPage(1);
      }
      setLoadingMessage(`Berhasil memuat ${newItems.length} dari ${r.data.total || 0} aset`);
    } catch { toast.error("Gagal memuat data"); }
  };

  const loadMoreMobile = async () => {
    if (mobileLoading || mobileCurrentPage >= totalPages) return;
    setMobileLoading(true);
    const nextPage = mobileCurrentPage + 1;
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
      setMobileAssets(prev => [...prev, ...(r.data.items || [])]);
      setMobileCurrentPage(nextPage);
    } catch { toast.error("Gagal memuat data lanjutan"); }
    finally { setMobileLoading(false); }
  };

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

  const doFetchCategories = async () => { try { const r = await axios.get(`${API}/categories/all`); setCategories(Array.isArray(r.data) ? r.data : []); } catch { setCategories([]); } };

  const fetchParamsRef = useRef({ debouncedSearch, filterCategory, sortBy, pageSize, currentPage });
  fetchParamsRef.current = { debouncedSearch, filterCategory, sortBy, pageSize, currentPage };

  // showLoading: user-initiated refetches (filter/sort/page-size) show the
  // list skeleton; background refreshes (post-save sync, WS) stay silent so
  // they never flash an overlay while someone is working.
  const refreshData = (page, { showLoading = false } = {}) => {
    const p = fetchParamsRef.current;
    const pg = page !== undefined ? page : p.currentPage;
    const work = Promise.all([
      doFetch(pg, p.pageSize, p.debouncedSearch, p.filterCategory, p.sortBy),
      doFetchStats(p.debouncedSearch, p.filterCategory),
    ]);
    if (showLoading) {
      setPageLoading(true);
      work.finally(() => setPageLoading(false));
    }
    return work;
  };

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
  }, [debouncedSearch, filterCategory, sortBy, pageSize, filters.condition, filters.status, filters.location, filters.eselon1, filters.eselon2, filters.stiker, filters.inventoryStatus, filters.priceMin, filters.priceMax]);

  const goToPage = async (p) => {
    const np = Math.max(1, Math.min(p, totalPages));
    setPageLoading(true);
    setLoadingMessage(`Memuat halaman ${np} dari ${totalPages}...`);
    await doFetch(np, pageSize, debouncedSearch, filterCategory, sortBy);
    setPageLoading(false);
  };

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
    if (lock && lock.session_id !== sessionId) { toast.error(`Aset sedang diedit oleh ${lock.user_name}`); return; }
    const locked = await lockAsset(asset.id);
    if (!locked) return;
    setEditAssetForForm(asset);
    setIsSidebarOpen(true);
    if (!formPanelVisible) setFormPanelVisible(true);
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
      // Deferred refresh: sync with server now that editing is done
      const queueNeedsRefresh = consumeRefreshFlag();
      const wsNeedsRefresh = wsNeedsRefreshRef.current;
      wsNeedsRefreshRef.current = false;
      if (queueNeedsRefresh || wsNeedsRefresh) refreshData();
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
    // Capture the version the user started editing from (for OCC / If-Match)
    const baseVersion = isEdit ? (assets.find(a => a.id === editId)?.version ?? null) : null;
    if (isEdit && editId) {
      setAssets(prev => prev.map(a => a.id === editId ? { ...a, ...payload, thumbnail: payload.photo || a.thumbnail } : a));
      setMobileAssets(prev => prev.map(a => a.id === editId ? { ...a, ...payload, thumbnail: payload.photo || a.thumbnail } : a));
      // Row stays locked until save completes (unlocked by onItemSaved callback)
    } else {
      const tempAsset = { ...payload, id: assetId, thumbnail: payload.photo || null, created_at: new Date().toISOString() };
      setAssets(prev => [tempAsset, ...prev]);
      setMobileAssets(prev => [tempAsset, ...prev]);
      setTotalItems(prev => prev + 1);
    }
    setEditAssetForForm(null);
    setIsSidebarOpen(false);
    enqueueOptimistic({ tempId: assetId, payload, isEdit, editId: isEdit ? editId : undefined, usePatch, baseVersion }).catch(() => {
      if (!isEdit) {
        setAssets(prev => prev.filter(a => a.id !== assetId));
        setMobileAssets(prev => prev.filter(a => a.id !== assetId));
        setTotalItems(prev => Math.max(0, prev - 1));
      }
    });
    toast.info(isEdit ? "Menyimpan perubahan..." : "Menambahkan aset...", { duration: 1500 });
  }, [enqueueOptimistic, assets]);

  // Save current asset in background + navigate to next/prev row
  const handleSaveAndNavigate = useCallback(async (payload, isEdit, editId, direction, usePatch = false) => {
    const assetId = isEdit ? editId : `temp_${Date.now()}`;
    const baseVersion = isEdit ? (assets.find(a => a.id === editId)?.version ?? null) : null;
    // 1) Optimistic local update (row stays locked until save completes via onItemSaved)
    if (isEdit && editId) {
      setAssets(prev => prev.map(a => a.id === editId ? { ...a, ...payload, thumbnail: payload.photo || a.thumbnail } : a));
      setMobileAssets(prev => prev.map(a => a.id === editId ? { ...a, ...payload, thumbnail: payload.photo || a.thumbnail } : a));
    } else {
      const tempAsset = { ...payload, id: assetId, thumbnail: payload.photo || null, created_at: new Date().toISOString() };
      setAssets(prev => [tempAsset, ...prev]);
      setMobileAssets(prev => [tempAsset, ...prev]);
      setTotalItems(prev => prev + 1);
    }
    // 2) Enqueue background save
    enqueueOptimistic({ tempId: assetId, payload, isEdit, editId: isEdit ? editId : undefined, usePatch, baseVersion }).catch(() => {
      if (!isEdit) {
        setAssets(prev => prev.filter(a => a.id !== assetId));
        setMobileAssets(prev => prev.filter(a => a.id !== assetId));
        setTotalItems(prev => Math.max(0, prev - 1));
      }
    });
    toast.info("Menyimpan di background...", { duration: 1200 });

    // 3) Navigate to next/prev asset
    const currentIndex = assets.findIndex(a => a.id === editId);
    const nextIndex = direction === 'next' ? currentIndex + 1 : currentIndex - 1;

    if (nextIndex >= 0 && nextIndex < assets.length) {
      const nextAsset = assets[nextIndex];
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
    } else {
      toast.info(direction === 'next' ? "Sudah di aset terakhir halaman ini" : "Sudah di aset pertama halaman ini");
      setEditAssetForForm(null);
      setIsSidebarOpen(false);
    }
  }, [assets, lockAsset, enqueueOptimistic, rowLocks, sessionId]);

  const handleDelete = useCallback(async id => {
    if (!window.confirm("Hapus aset ini?")) return;
    setIsDeleting(id);
    try { await axios.delete(`${API}/assets/${id}`); toast.success("Dihapus"); refreshData(); }
    catch { toast.error("Gagal hapus"); }
    finally { setIsDeleting(null); }
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
    try {
      toast.info("Membuat kartu inventaris...");
      const r = await axios.get(`${API}/assets/${assetId}/card`, { responseType: 'blob' });
      const blob = new Blob([r.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const newWindow = window.open(url, '_blank');
      if (!newWindow) { const a = document.createElement('a'); a.href = url; a.download = `kartu_inventaris_${assetId}.pdf`; document.body.appendChild(a); a.click(); document.body.removeChild(a); toast.success("Kartu inventaris berhasil didownload"); }
      else toast.success("Kartu inventaris berhasil dibuat (ukuran KTP)");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) { console.error('Print card error:', err); toast.error(getApiError(err, "Gagal cetak kartu")); }
  }, []);

  const handlePrintBulkCards = useCallback(async () => {
    if (assets.length === 0) { toast.error("Tidak ada aset untuk dicetak"); return; }
    try {
      toast.info(`Membuat ${assets.length} kartu inventaris...`);
      const r = await axios.post(`${API}/assets/cards/bulk`, assets.map(a => a.id), { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([r.data]));
      const newWindow = window.open(url, '_blank');
      if (!newWindow) { const a = document.createElement('a'); a.href = url; a.download = `kartu_inventaris_massal_${assets.length}.pdf`; document.body.appendChild(a); a.click(); document.body.removeChild(a); toast.success(`${assets.length} kartu inventaris berhasil didownload`); }
      else toast.success(`${assets.length} kartu inventaris berhasil dibuat`);
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) { console.error('Bulk print error:', err); toast.error(getApiError(err, "Gagal cetak kartu massal")); }
  }, [assets]);

  const handleExport = useCallback(async fmt => {
    if (!activity?.id) { toast.error("Pilih kegiatan inventarisasi terlebih dahulu"); return; }
    if (totalItems === 0) { toast.error("Tidak ada data aset untuk diexport"); return; }
    setExporting(true);
    toast.info(`Memproses export ${fmt.toUpperCase()}... Mohon tunggu.`, { duration: 5000 });
    try {
      const r = await axios.get(`${API}/export/${fmt}?activity_id=${activity.id}&base_url=${encodeURIComponent(process.env.REACT_APP_BACKEND_URL || '')}`, { responseType: 'blob', timeout: 300000 });
      const blob = new Blob([r.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `inventory_${activity.nama_kegiatan || 'export'}.${fmt === 'xlsx' ? 'xlsx' : fmt}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      toast.success(`Export ${fmt.toUpperCase()} berhasil`);
    } catch (err) {
      console.error('Export error:', err);
      let errorMsg = 'Gagal export';
      try {
        if (err.response?.data instanceof Blob) {
          const text = await err.response.data.text();
          const json = JSON.parse(text);
          errorMsg = json.detail || errorMsg;
        } else if (err.response?.data?.detail) {
          errorMsg = err.response.data.detail;
        }
      } catch {}
      if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        errorMsg = 'Export timeout - data terlalu besar. Coba export dengan filter kategori.';
      }
      toast.error(errorMsg);
    } finally { setExporting(false); }
  }, [activity, totalItems]);

  const handleExportExecutivePDF = useCallback(async () => {
    if (!activity?.id) { toast.error("Pilih kegiatan inventarisasi terlebih dahulu"); return; }
    setExporting(true);
    try {
      const r = await axios.get(`${API}/inventory-activities/${activity.id}/executive-summary-pdf`, { responseType: 'blob' });
      const blob = new Blob([r.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Laporan_Eksekutif_${activity.nama_kegiatan || 'BMN'}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      toast.success("Download Laporan Eksekutif berhasil");
    } catch (err) {
      console.error('Executive PDF export error:', err);
      let errorMsg = 'Gagal download Laporan Eksekutif';
      try {
        if (err.response?.data instanceof Blob) {
          const text = await err.response.data.text();
          const json = JSON.parse(text);
          errorMsg = json.detail || errorMsg;
        }
      } catch {}
      toast.error(errorMsg);
    } finally { setExporting(false); }
  }, [activity]);

  const handlePreviewExecutive = useCallback(() => {
    if (!activity?.id) { toast.error("Pilih kegiatan inventarisasi terlebih dahulu"); return; }
    window.open(`${process.env.REACT_APP_BACKEND_URL}/api/inventory-activities/${activity.id}/executive-summary-html`, '_blank');
  }, [activity]);

  // Compute current edit position for navigation
  const editAssetIndex = useMemo(() => {
    if (!editAssetForForm?.id) return -1;
    return assets.findIndex(a => a.id === editAssetForForm.id);
  }, [editAssetForForm?.id, assets]);

  // === RENDER ===
  return (
    <div
      className="min-h-screen bg-background text-foreground overflow-x-hidden"
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
      {/* Global loading overlay */}
      {exporting && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-[100] flex items-center justify-center">
          <div className="bg-card rounded-2xl shadow-2xl px-8 py-6 flex flex-col items-center gap-3">
            <Loader2 className="w-10 h-10 animate-spin text-blue-600" />
            <p className="text-sm font-medium text-foreground">Mengexport data...</p>
            <p className="text-xs text-muted-foreground">Mohon tunggu sebentar</p>
          </div>
        </div>
      )}
      {/* HEADER */}
      <DashboardHeader
        activity={activity} user={user} perms={perms}
        onBack={onBack} onLogout={onLogout}
        auditOpen={auditOpen} onAuditToggle={handleAuditToggle}
        onOpenUserManagement={() => openDialog('userManagement')}
        isOnline={isOnline} wsConnected={wsConnected} onlineUsers={onlineUsers}
        pendingCount={pendingCount} syncing={syncing} onSync={syncPending}
        dark={dark} toggleDark={toggleDark}
        onShowInfo={onShowInfo}
      />

      <div className="flex h-[calc(100vh-53px)] overflow-x-hidden">
        {/* Toggle Button for Form Panel (Desktop only) */}
        {perms.canEdit && (
          <button
            onClick={() => setFormPanelVisible(prev => !prev)}
            className={`hidden lg:flex fixed top-1/2 -translate-y-1/2 z-50 w-5 h-14 bg-card border border-border rounded-r-lg items-center justify-center text-muted-foreground hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-all shadow-md hover:shadow-lg ${formPanelVisible ? 'border-l-0' : ''}`}
            style={{ left: formPanelVisible ? '319px' : '0px', transition: 'left 0.3s ease' }}
            title={formPanelVisible ? 'Sembunyikan Form' : 'Tampilkan Form'}
          >
            {formPanelVisible ? <PanelLeftClose className="w-3.5 h-3.5" /> : <PanelLeftOpen className="w-3.5 h-3.5" />}
          </button>
        )}

        {/* ASSET FORM SIDEBAR - only for admin/operator */}
        {perms.canEdit && (
          <div className={`hidden lg:block ${formPanelVisible ? 'w-[320px] min-w-[320px]' : 'w-0 min-w-0 overflow-hidden'}`} style={{ transition: 'width 0.3s ease, min-width 0.3s ease', willChange: 'width', contain: 'layout style' }}>
            <AssetForm isOpen={isSidebarOpen || formPanelVisible} onClose={handleFormClose} activity={activity} categories={categories} editAsset={editAssetForForm} onSubmitSuccess={handleFormSubmitSuccess} onOptimisticSubmit={handleOptimisticSubmit} onSaveAndNavigate={handleSaveAndNavigate} assetIndex={editAssetIndex} totalAssetsInView={assets.length} saveQueueLength={queueLength} inventoryMode={inventoryMode} onShowCategoryManager={perms.canManageCategories ? () => openDialog('categoryManager') : undefined} alwaysExpanded={formPanelVisible} />
          </div>
        )}
        {perms.canEdit && (
          <div className="lg:hidden">
            <AssetForm isOpen={isSidebarOpen} onClose={handleFormClose} activity={activity} categories={categories} editAsset={editAssetForForm} onSubmitSuccess={handleFormSubmitSuccess} onOptimisticSubmit={handleOptimisticSubmit} onSaveAndNavigate={handleSaveAndNavigate} assetIndex={editAssetIndex} totalAssetsInView={assets.length} saveQueueLength={queueLength} inventoryMode={inventoryMode} onShowCategoryManager={perms.canManageCategories ? () => openDialog('categoryManager') : undefined} />
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

          <div className="p-3 sm:p-4 space-y-3">
            <StatsBar stats={stats} inventoryMode={inventoryMode} setInventoryMode={setInventoryMode} isOnline={isOnline} pendingCount={pendingCount} />
            <DashboardToolbar
              searchInput={searchInput} setSearchInput={setSearchInput} categories={categories} filterCategory={filterCategory} setFilterCategory={setFilterCategory}
              activeFilterCount={activeFilterCount} showAdvancedFilter={showAdvancedFilter} setShowAdvancedFilter={setShowAdvancedFilter}
              sortBy={sortBy} setSortBy={setSortBy} exporting={exporting} handleExport={handleExport} handleExportExecutivePDF={handleExportExecutivePDF}
              handlePreviewExecutive={handlePreviewExecutive} perms={perms} openDialog={openDialog} handlePrintBulkCards={handlePrintBulkCards}
              assetsCount={assets.length} filters={filters} filterOptions={filterOptions} handleAdvancedFilterChange={handleAdvancedFilterChange}
              resetAdvancedFilters={resetAdvancedFilters} handleCategoryReset={() => { handleCategoryReset(); refreshData(1); }}
              refreshData={refreshData} viewMode={viewMode} setViewMode={setViewMode}
            />

            {!inventoryMode && <Suspense fallback={null}><AnalyticsPanel activityId={activity?.id} isOpen={analyticsOpen} onToggle={handleAnalyticsToggle} panelHeight={analyticsPanelHeight} onDragStart={handleAnalyticsDragStart} /></Suspense>}
            {!inventoryMode && <Suspense fallback={null}><RekapitulasiPanel activityId={activity?.id} isOpen={rekapOpen} onToggle={() => setRekapOpen(p => !p)} /></Suspense>}
            <Suspense fallback={null}><AssetGroupsPanel activityId={activity?.id} isOpen={groupsOpen} onToggle={() => setGroupsOpen(p => !p)} onBatchEdit={perms.canEdit ? handleGroupBatchEdit : undefined} /></Suspense>

            {loading ? (
              <LoadingIndicator message={loadingMessage} totalItems={totalItems} pageSize={pageSize} currentPage={currentPage} />
            ) : assets.length === 0 ? (
              <div className="text-center py-16"><Package className="w-12 h-12 mx-auto mb-3 text-muted-foreground" /><p className="text-muted-foreground">Data tidak ditemukan</p></div>
            ) : (<div className="relative">
              {/* Skeleton overlay for page-size / pagination / filter / sort
                  requests. The relative wrapper scopes it to the list area
                  (previously inset-0 resolved against the viewport because
                  no ancestor was positioned). */}
              {pageLoading && (
                <ListLoadingSkeleton rows={Math.min(pageSize, 12)} message={loadingMessage} />
              )}

              {selectedAssets.size > 0 && (<>
                {selectedAssets.size === assets.length && totalItems > assets.length && (
                  <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-1.5 flex items-center justify-between text-xs">
                    <span className="text-amber-800 dark:text-amber-300">{selectedAssets.size} aset di halaman ini dipilih. Total ada <b>{totalItems}</b> aset.</span>
                    <button onClick={selectAllPages} className="text-blue-600 dark:text-blue-400 hover:underline font-semibold ml-2" data-testid="select-all-pages-btn">Pilih semua {totalItems} aset</button>
                  </div>
                )}
                <Suspense fallback={null}><BatchEditPanel selectedCount={selectedAssets.size} categories={categories} onApply={handleBatchUpdate} onClose={clearSelection} updating={batchUpdating} activity={activity} assets={assets} selectedAssets={selectedAssets} /></Suspense>
              </>)}

              {viewMode === 'gallery' ? (
                <AssetGalleryView assets={mobileAssets} editId={editAssetForForm?.id} onEdit={perms.canEdit ? handleEdit : undefined} onDelete={perms.canDelete ? handleDelete : undefined} onPrintCard={handlePrintCard} onLoadMore={loadMoreMobile} isLoadingMore={mobileLoading} hasMore={mobileCurrentPage < totalPages} totalItems={totalItems} rowLocks={rowLocks} currentSessionId={sessionId} selectedAssets={selectedAssets} onToggleSelect={perms.canEdit ? toggleSelectAsset : undefined} />
              ) : (<>
                <div className="relative hidden lg:block">
                  <TooltipProvider>
                    <VirtualizedAssetTable assets={assets} editId={editAssetForForm?.id} onEdit={perms.canEdit ? handleEdit : undefined} onDelete={perms.canDelete ? handleDelete : undefined} onPrintCard={handlePrintCard} onViewAudit={handleViewAssetAudit} pageSize={pageSize} rowLocks={rowLocks} currentSessionId={sessionId} syncStatuses={syncStatuses} onRetrySync={retrySync} onDismissSync={dismissSync} selectedAssets={selectedAssets} onToggleSelect={perms.canEdit ? toggleSelectAsset : undefined} onToggleSelectAll={perms.canEdit ? toggleSelectAll : undefined} />
                  </TooltipProvider>
                </div>
                <div className="lg:hidden">
                  <VirtualizedMobileCards assets={mobileAssets} editId={editAssetForForm?.id} onEdit={perms.canEdit ? handleEdit : undefined} onDelete={perms.canDelete ? handleDelete : undefined} onLoadMore={loadMoreMobile} isLoadingMore={mobileLoading} hasMore={mobileCurrentPage < totalPages} totalItems={totalItems} rowLocks={rowLocks} currentSessionId={sessionId} syncStatuses={syncStatuses} onRetrySync={retrySync} onDismissSync={dismissSync} selectedAssets={selectedAssets} onToggleSelect={perms.canEdit ? toggleSelectAsset : undefined} />
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
      <Suspense fallback={null}>
        {dialogs.import && <LazyImportDialog open={dialogs.import} onClose={handleImportClose} onSuccess={() => { clearDropFile(); refreshData(1); doFetchCategories(); }} activityId={activity?.id} preloadFile={dropFile} />}
        {dialogs.userManagement && <LazyUserManagementDialog open={dialogs.userManagement} onClose={() => closeDialog('userManagement')} currentUser={user} />}
      </Suspense>

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
export default function DashboardPage({ user, onLogout, dark, toggleDark, onShowInfo }) {
  const [selectedActivity, setSelectedActivity] = useState(null);

  useEffect(() => {
    const storedId = localStorage.getItem('currentActivityId');
    if (storedId) {
      axios.get(`${API}/inventory-activities/${storedId}`)
        .then(r => setSelectedActivity(r.data))
        .catch(() => localStorage.removeItem('currentActivityId'));
    }
  }, []);

  const handleSelectActivity = (activity) => {
    setSelectedActivity(activity);
    try { localStorage.setItem('currentActivityId', activity.id); } catch {}
  };

  const handleBack = () => { setSelectedActivity(null); localStorage.removeItem('currentActivityId'); };
  const handleLogout = () => { localStorage.removeItem('currentActivityId'); onLogout(); };

  if (!selectedActivity) return <ActivitySelectionPage user={user} onLogout={handleLogout} onSelectActivity={handleSelectActivity} />;
  return <AssetManagementPage user={user} onLogout={handleLogout} activity={selectedActivity} onBack={handleBack} dark={dark} toggleDark={toggleDark} onShowInfo={onShowInfo} />;
}
