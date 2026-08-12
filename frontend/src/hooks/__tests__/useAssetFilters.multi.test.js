/**
 * Kontrak kawat filter multi-pilih + penyaring LURING.
 *
 * Dua hal yang paling mudah rusak diam-diam:
 *  - URL: banyak nilai HARUS jadi parameter berulang, dan nilai yang MEMUAT
 *    KOMA ("Gedung A, Lantai 2") tak boleh terpecah jadi dua filter.
 *  - Luring: penyaring snapshot sisi klien harus memberi hasil yang sama
 *    dengan server; kalau tidak, daftar berubah isi saat sinyal hilang.
 */
import { renderHook, act } from "@testing-library/react";

import { useAssetFilters, normalkanMulti, objekFilter, FILTER_MULTI }
  from "../useAssetFilters";

jest.mock("axios", () => ({ get: jest.fn(() => Promise.resolve({ data: {} })) }));

const pakai = () => renderHook(() => useAssetFilters({ activityId: "keg-1" }));

describe("normalkanMulti", () => {
  test("menerima string tunggal maupun array, buang kosong & duplikat", () => {
    expect(normalkanMulti("Baik")).toEqual(["Baik"]);
    expect(normalkanMulti([" Baik ", "Baik", "", null, undefined]))
      .toEqual(["Baik"]);
    expect(normalkanMulti(null)).toEqual([]);
  });
});

describe("state filter", () => {
  test("tujuh filter berbasis pilihan berawal sebagai array kosong", () => {
    const { result } = pakai();
    for (const f of FILTER_MULTI) {
      expect(Array.isArray(result.current.filters[f])).toBe(true);
      expect(result.current.filters[f]).toHaveLength(0);
    }
    // Teks bebas & rentang tetap string.
    expect(result.current.filters.nomorSpm).toBe("");
    expect(result.current.filters.priceMin).toBe("");
  });

  test("toggleFilterValue menambah lalu melepas satu nilai", () => {
    const { result } = pakai();
    act(() => result.current.toggleFilterValue("inventoryStatus", "Ditemukan"));
    act(() => result.current.toggleFilterValue("inventoryStatus", "Sengketa"));
    expect(result.current.filters.inventoryStatus)
      .toEqual(["Ditemukan", "Sengketa"]);

    act(() => result.current.toggleFilterValue("inventoryStatus", "Ditemukan"));
    expect(result.current.filters.inventoryStatus).toEqual(["Sengketa"]);
  });

  test("satu filter berisi banyak nilai dihitung SEKALI", () => {
    const { result } = pakai();
    act(() => result.current.handleAdvancedFilterChange(
      "condition", ["Baik", "Rusak Ringan", "Rusak Berat"]));
    expect(result.current.activeFilterCount).toBe(1);

    act(() => result.current.handleAdvancedFilterChange("status", ["Aktif"]));
    expect(result.current.activeFilterCount).toBe(2);
  });

  test("reset mengembalikan semua filter ke kosong", () => {
    const { result } = pakai();
    act(() => result.current.handleAdvancedFilterChange("status", ["Aktif"]));
    act(() => result.current.handleAdvancedFilterChange("nomorSpm", "123"));
    act(() => result.current.resetAdvancedFilters());
    expect(result.current.filters.status).toEqual([]);
    expect(result.current.filters.nomorSpm).toBe("");
    expect(result.current.activeFilterCount).toBe(0);
  });
});

describe("kontrak kawat buildFilterParams", () => {
  const params = (result) => {
    const p = new URLSearchParams();
    result.current.buildFilterParams(p);
    return p;
  };

  test("banyak nilai jadi PARAMETER BERULANG", () => {
    const { result } = pakai();
    act(() => result.current.handleAdvancedFilterChange(
      "status", ["Aktif", "Dihentikan"]));
    const p = params(result);
    expect(p.getAll("status")).toEqual(["Aktif", "Dihentikan"]);
    expect(p.toString()).toBe("status=Aktif&status=Dihentikan");
  });

  test("nilai bermuatan koma tetap SATU nilai", () => {
    const { result } = pakai();
    act(() => result.current.handleAdvancedFilterChange(
      "location", ["Gedung A, Lantai 2"]));
    expect(params(result).getAll("location")).toEqual(["Gedung A, Lantai 2"]);
  });

  test("dua nilai yang salah satunya memuat koma tak terpecah", () => {
    // Kasus paling berbahaya kalau kontrak kawat memakai pemisah koma:
    // "Gedung A, Lantai 2" + "Gudang" akan sampai di server sebagai TIGA
    // filter ("Gedung A", "Lantai 2", "Gudang") — daftar berisi aset yang
    // tak pernah diminta, dan ekspor/laporan ikut salah.
    const { result } = pakai();
    act(() => result.current.handleAdvancedFilterChange(
      "location", ["Gedung A, Lantai 2", "Gudang"]));
    expect(params(result).getAll("location"))
      .toEqual(["Gedung A, Lantai 2", "Gudang"]);
  });

  test("satu nilai menghasilkan URL yang identik dengan versi lama", () => {
    const { result } = pakai();
    act(() => result.current.handleAdvancedFilterChange("condition", ["Baik"]));
    expect(params(result).toString()).toBe("condition=Baik");
  });

  test("nama parameter server dipertahankan", () => {
    const { result } = pakai();
    act(() => {
      result.current.handleAdvancedFilterChange("eselon1", ["Setjen"]);
      result.current.handleAdvancedFilterChange("eselon2", ["Biro Umum"]);
      result.current.handleAdvancedFilterChange("stiker", ["Sudah"]);
      result.current.handleAdvancedFilterChange("inventoryStatus", ["Ditemukan"]);
    });
    const p = params(result);
    expect(p.get("eselon1_filter")).toBe("Setjen");
    expect(p.get("eselon2_filter")).toBe("Biro Umum");
    expect(p.get("stiker_status")).toBe("Sudah");
    expect(p.get("inventory_status")).toBe("Ditemukan");
  });

  test("filter kosong tak mengirim parameter apa pun", () => {
    const { result } = pakai();
    expect(params(result).toString()).toBe("");
  });
});

describe("objekFilter — body JSON batch PDF ZIP", () => {
  test("parameter berulang jadi ARRAY, bukan nilai terakhir saja", () => {
    // Object.fromEntries akan menyisakan "Rusak Ringan" saja — separuh filter
    // hilang tanpa error, dan banner di dalam PDF ikut menulis satu nilai
    // sehingga pembaca tak punya petunjuk apa pun.
    const o = objekFilter("condition=Rusak+Berat&condition=Rusak+Ringan&status=Aktif");
    expect(o.condition).toEqual(["Rusak Berat", "Rusak Ringan"]);
    expect(o.status).toBe("Aktif");
  });

  test("nilai bermuatan koma tetap utuh", () => {
    const o = objekFilter("location=Gedung+A%2C+Lantai+2&location=Gudang");
    expect(o.location).toEqual(["Gedung A, Lantai 2", "Gudang"]);
  });

  test("querystring kosong menghasilkan objek kosong", () => {
    expect(objekFilter("")).toEqual({});
    expect(objekFilter(undefined)).toEqual({});
  });
});
