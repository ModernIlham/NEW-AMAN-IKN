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

// Panjang minimum kata kunci pencarian. Di server, pencarian teks bebas memakai
// regex 16-field yang tak bisa memakai index (COLLSCAN dalam lingkup satker),
// sehingga kata kunci 1 huruf ("a") memindai hampir seluruh aset percuma. Di
// bawah ambang ini kata kunci DIPERLAKUKAN KOSONG (tak memicu request & tak
// dikirim ke server). Nilai yang DIKETIK pengguna tetap terlihat (SearchInput
// menyimpan state lokal sendiri) — hanya kata kunci "efektif" yang dijepit.
const MIN_SEARCH_LEN = 2;

// ============================================================================
// FILTER MULTI-PILIH
// ============================================================================
// Filter berbasis PILIHAN boleh memuat beberapa nilai sekaligus; nilai-nilai
// dalam satu filter berarti "ATAU", antar-filter tetap "DAN". Dikirim ke
// server sebagai PARAMETER BERULANG (?status=A&status=B) — bukan dipisah
// koma, sebab nilai nyata seperti "Gedung A, Lantai 2" memang mengandung
// koma dan akan terpecah jadi dua filter yang salah.
//
// Filter teks bebas (SPM, perolehan, pengguna, NIK/NIP) tetap tunggal: itu
// pencocokan substring satu frasa. Harga & tanggal tetap tunggal karena
// keduanya RENTANG — dua batas sudah mewakili banyak nilai.
export const FILTER_MULTI = new Set([
  "condition", "status", "location", "eselon1", "eselon2",
  "stiker", "inventoryStatus",
]);

// Nama parameter HTTP per field multi (nama di server berbeda untuk sebagian).
const PARAM_MULTI = {
  condition: "condition", status: "status", location: "location",
  eselon1: "eselon1_filter", eselon2: "eselon2_filter",
  stiker: "stiker_status", inventoryStatus: "inventory_status",
};

/** Terima array / string tunggal / null → array bersih tanpa duplikat. */
export function normalkanMulti(v) {
  const mentah = Array.isArray(v) ? v : (v ? [v] : []);
  const keluar = [];
  for (const x of mentah) {
    const s = String(x ?? "").trim();
    if (s && !keluar.includes(s)) keluar.push(s);
  }
  return keluar;
}

/**
 * Querystring filter → objek untuk body JSON (mis. batch PDF ZIP).
 *
 * `Object.fromEntries(new URLSearchParams(qs))` TIDAK boleh dipakai di sini:
 * untuk parameter berulang ia hanya menyimpan kemunculan TERAKHIR, sehingga
 * "condition=Rusak Berat&condition=Rusak Ringan" diam-diam menyusut jadi satu
 * nilai. Kegagalannya konsisten-internal — banner di dalam PDF ikut menulis
 * satu nilai dan datanya memang cocok — jadi pembaca tak punya petunjuk bahwa
 * separuh filternya hilang. Kunci multi-nilai dikirim sebagai ARRAY; backend
 * (`nilai_filter`) menerima keduanya.
 */
export function objekFilter(qs) {
  const u = new URLSearchParams(qs || "");
  const keluar = {};
  for (const kunci of new Set(u.keys())) {
    const nilai = u.getAll(kunci);
    keluar[kunci] = nilai.length > 1 ? nilai : nilai[0];
  }
  return keluar;
}

export function useAssetFilters({ activityId }) {
  const [searchInput, setSearchInput] = useState("");
  const [filterCategory, setFilterCategory] = useState("Semua");
  const [sortBy, setSortBy] = useState("newest");
  const rawDebouncedSearch = useDebounce(searchInput, 300);
  // Kata kunci EFEKTIF: < MIN_SEARCH_LEN (setelah dipangkas) → "" (tanpa cari).
  const debouncedSearch = rawDebouncedSearch.trim().length >= MIN_SEARCH_LEN ? rawDebouncedSearch : "";

  const [showAdvancedFilter, setShowAdvancedFilter] = useState(false);

  // Tujuh filter berbasis PILIHAN menyimpan ARRAY nilai (boleh lebih dari
  // satu); sisanya — teks bebas, rentang harga, rentang tanggal — tetap
  // string tunggal. `FILTER_MULTI` adalah satu-satunya sumber kebenaran
  // pembeda itu, dipakai ulang oleh penghitung filter aktif, perakit
  // parameter, dan penyaring luring supaya ketiganya tak bisa drift.
  const initialFilterState = useMemo(() => ({
    condition: [], status: [], location: [], eselon1: [], eselon2: [],
    stiker: [], inventoryStatus: [], priceMin: "", priceMax: "",
    nomorSpm: "", perolehanDari: "", user: "", penggunaNip: "",
    dateFrom: "", dateTo: ""
  }), []);

  const [filters, dispatchFilter] = useReducer((state, action) => {
    if (action.type === 'SET') {
      // Filter multi selalu disimpan sebagai array — pemanggil lama yang
      // mengirim satu string (mis. chip cepat di bilah progres) tetap sah.
      const val = FILTER_MULTI.has(action.field)
        ? normalkanMulti(action.value)
        : (action.value || "");
      return { ...state, [action.field]: val };
    }
    if (action.type === 'TOGGLE') {
      const kini = normalkanMulti(state[action.field]);
      const nilai = String(action.value ?? "").trim();
      if (!nilai) return state;
      return {
        ...state,
        [action.field]: kini.includes(nilai)
          ? kini.filter(x => x !== nilai)
          : [...kini, nilai],
      };
    }
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
    // Multi-pilih → satu entri per nilai (append, bukan set). Satu nilai
    // menghasilkan URL yang identik dengan versi lama.
    for (const [field, nama] of Object.entries(PARAM_MULTI)) {
      for (const v of normalkanMulti(filters[field])) params.append(nama, v);
    }
    if (filters.priceMin) params.append("price_min", filters.priceMin);
    if (filters.priceMax) params.append("price_max", filters.priceMax);
    if (filters.nomorSpm) params.append("nomor_spm", filters.nomorSpm);
    if (filters.perolehanDari) params.append("perolehan_dari", filters.perolehanDari);
    if (filters.user) params.append("user_filter", filters.user);
    if (filters.penggunaNip) params.append("pengguna_nip", filters.penggunaNip);
    if (filters.dateFrom) params.append("beli_dari", filters.dateFrom);
    if (filters.dateTo) params.append("beli_sampai", filters.dateTo);
    return params;
  }, [filters]);

  // Jumlah filter aktif — satu filter dihitung SEKALI meski memuat banyak
  // nilai (angka ini menjawab "berapa penyempitan yang sedang berlaku",
  // bukan "berapa nilai yang dicentang"; jumlah nilai per filter tampil di
  // pemicunya masing-masing).
  const activeFilterCount = useMemo(() => [
    filterCategory !== "Semua" && filterCategory,
    filters.condition?.length, filters.status?.length, filters.location?.length,
    filters.eselon1?.length, filters.eselon2?.length, filters.stiker?.length,
    filters.inventoryStatus?.length, filters.priceMin, filters.priceMax,
    filters.nomorSpm, filters.perolehanDari, filters.user, filters.penggunaNip,
    filters.dateFrom, filters.dateTo
  ].filter(Boolean).length, [filterCategory, filters]);

  const handleAdvancedFilterChange = useCallback((field, value) => {
    dispatchFilter({ type: 'SET', field, value });
  }, []);

  /** Centang/lepas SATU nilai pada filter multi — dipakai chip cepat. */
  const toggleFilterValue = useCallback((field, value) => {
    dispatchFilter({ type: 'TOGGLE', field, value });
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
    toggleFilterValue,
    handleCategoryReset,
    resetAdvancedFilters,
  };
}
