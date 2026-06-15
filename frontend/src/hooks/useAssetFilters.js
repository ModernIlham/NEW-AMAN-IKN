/**
 * useAssetFilters - Manages all filter state for asset listing.
 * Includes search, category filter, advanced filters, and filter options.
 */
import { useState, useCallback, useMemo, useReducer, useEffect, useRef } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function useDebounce(value, delay) {
  const [dv, setDv] = useState(value);
  useEffect(() => { const h = setTimeout(() => setDv(value), delay); return () => clearTimeout(h); }, [value, delay]);
  return dv;
}

export function useAssetFilters({ activityId }) {
  const [searchInput, setSearchInput] = useState("");
  const [filterCategory, setFilterCategory] = useState("Semua");
  const [sortBy, setSortBy] = useState("newest");
  const debouncedSearch = useDebounce(searchInput, 300);

  const [showAdvancedFilter, setShowAdvancedFilter] = useState(false);

  const initialFilterState = useMemo(() => ({
    condition: "", status: "", location: "", eselon1: "", eselon2: "",
    stiker: "", inventoryStatus: "", priceMin: "", priceMax: "",
    nomorSpm: "", perolehanDari: ""
  }), []);

  const [filters, dispatchFilter] = useReducer((state, action) => {
    if (action.type === 'SET') return { ...state, [action.field]: action.value };
    if (action.type === 'RESET') return initialFilterState;
    return state;
  }, initialFilterState);

  const [filterOptions, setFilterOptions] = useState({
    locations: [], eselon1s: [], eselon2s: [], conditions: [],
    statuses: [], stiker_statuses: [], inventory_statuses: []
  });

  // Fetch filter options
  const fetchFilterOptions = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (activityId) params.append("activity_id", activityId);
      const r = await axios.get(`${API}/assets/filter-options?${params.toString()}`);
      setFilterOptions(r.data);
    } catch (e) {
      // Filter options are enhancement-only; fall back to empty options on failure.
      if (process.env.NODE_ENV !== "production") {
        console.warn("[useAssetFilters] Failed to fetch filter options:", e?.message);
      }
    }
  }, [activityId]);

  // Build advanced filter query params
  const buildFilterParams = useCallback((params) => {
    if (filters.condition) params.append("condition", filters.condition);
    if (filters.status) params.append("status", filters.status);
    if (filters.location) params.append("location", filters.location);
    if (filters.eselon1) params.append("eselon1_filter", filters.eselon1);
    if (filters.eselon2) params.append("eselon2_filter", filters.eselon2);
    if (filters.stiker) params.append("stiker_status", filters.stiker);
    if (filters.inventoryStatus) params.append("inventory_status", filters.inventoryStatus);
    if (filters.priceMin) params.append("price_min", filters.priceMin);
    if (filters.priceMax) params.append("price_max", filters.priceMax);
    if (filters.nomorSpm) params.append("nomor_spm", filters.nomorSpm);
    if (filters.perolehanDari) params.append("perolehan_dari", filters.perolehanDari);
    return params;
  }, [filters]);

  // Count active filters
  const activeFilterCount = useMemo(() => [
    filterCategory !== "Semua" && filterCategory,
    filters.condition, filters.status, filters.location,
    filters.eselon1, filters.eselon2, filters.stiker,
    filters.inventoryStatus, filters.priceMin, filters.priceMax,
    filters.nomorSpm, filters.perolehanDari
  ].filter(Boolean).length, [filterCategory, filters]);

  const handleAdvancedFilterChange = useCallback((field, value) => {
    dispatchFilter({ type: 'SET', field, value: value || "" });
  }, []);

  const handleCategoryReset = useCallback(() => {
    setFilterCategory("Semua");
  }, []);

  const resetAdvancedFilters = useCallback(() => {
    setFilterCategory("Semua");
    dispatchFilter({ type: 'RESET' });
    setShowAdvancedFilter(false);
  }, []);

  return {
    searchInput, setSearchInput,
    filterCategory, setFilterCategory,
    sortBy, setSortBy,
    debouncedSearch,
    showAdvancedFilter, setShowAdvancedFilter,
    filters, dispatchFilter,
    filterOptions, fetchFilterOptions,
    buildFilterParams,
    activeFilterCount,
    handleAdvancedFilterChange,
    handleCategoryReset,
    resetAdvancedFilters,
  };
}
