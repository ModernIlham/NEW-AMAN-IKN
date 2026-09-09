import React, { useEffect } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import DashboardToolbar from "../DashboardToolbar";
import { useAssetFilters } from "@/hooks/useAssetFilters";
import { usePenyegaranAset } from "@/hooks/usePenyegaranAset";

jest.mock("@/components/assets", () => ({
  CategorySelect: () => null, TinifyQuotaIndicator: () => null,
  TinifyQuotaMobile: () => null, AdvancedFilter: () => null,
}));
jest.mock("@/components/assets/QrScanButton", () => () => null);
jest.mock("@/components/assets/StatsBar", () => ({ InventoryModeSwitch: () => null }));

// Kotak cari dan kedua lapis debounce ASLI; hanya komponen di luar reset
// yang disederhanakan. Pemuatan mencatat parameter dari render yang dipakai.
function LayarUji({ muatan }) {
  const f = useAssetFilters({ activityId: "uji-reset" });
  const refresh = usePenyegaranAset({
    ...f, currentPage: 4, pageSize: 50, setPageLoading: () => {},
    doFetch: async (page, size, search, category, sort) => {
      muatan.push({ page, search, filter: f.buildFilterParams(new URLSearchParams()).toString(), sort });
    },
    doFetchStats: async () => {},
  });
  useEffect(() => { refresh(1, { showLoading: true }); },
    [refresh, f.debouncedSearch, f.filterCategory, f.filters, f.sortBy]);
  return <>
    <DashboardToolbar {...f} categories={[]} assetsCount={0} perms={{}} />
    <button onClick={() => {
      f.setFilterCategory(["Mebel", "Peralatan"]);
      f.handleAdvancedFilterChange("condition", ["Baik"]);
      f.setSortBy("name_desc");
    }}>Aktifkan filter</button>
    <button onClick={f.resetAllFilters}>Reset semua</button>
    <button onClick={f.resetAdvancedFilters}>Reset lanjutan</button>
    <output data-testid="query-efektif">{f.debouncedSearch}</output>
  </>;
}

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());
const waktu = async (ms) => { await act(async () => { jest.advanceTimersByTime(ms); }); };
const ketik = (value) => fireEvent.change(screen.getByTestId("search-input"), { target: { value } });
const klik = (nama) => fireEvent.click(screen.getByRole("button", { name: nama }));

async function pasang(query = "") {
  const muatan = [];
  render(<LayarUji muatan={muatan} />);
  klik("Aktifkan filter");
  if (query) { ketik(query); await waktu(250); await waktu(300); }
  muatan.length = 0;
  return muatan;
}

test("reset pencarian dan filter hanya memuat keadaan kosong, tanpa menunggu debounce", async () => {
  const muatan = await pasang("meja");
  klik("Reset semua");
  expect(screen.getByTestId("query-efektif")).toBeEmptyDOMElement();
  expect(screen.getByTestId("search-input")).toHaveValue("");
  expect(muatan).toEqual([{ page: 1, search: "", filter: "", sort: "name_desc" }]);
  await waktu(1000);
  expect(muatan).toHaveLength(1);
});

test("reset membatalkan kata kunci yang masih menunggu debounce di hook", async () => {
  const muatan = await pasang();
  ketik("lemari");
  await waktu(250); // masuk state halaman, belum menjadi query efektif
  klik("Reset semua");
  muatan.length = 0;
  await waktu(1000);
  expect(screen.getByTestId("query-efektif")).toBeEmptyDOMElement();
  expect(muatan).toHaveLength(0);
});

test("reset membatalkan draf lokal sebelum kotak cari mengirimkannya", async () => {
  const muatan = await pasang();
  ketik("kursi");
  await waktu(100); // state halaman masih kosong
  klik("Reset semua");
  expect(screen.getByTestId("search-input")).toHaveValue("");
  muatan.length = 0;
  await waktu(250); await waktu(300);
  expect(muatan).toHaveLength(0);
  expect(screen.getByTestId("query-efektif")).toBeEmptyDOMElement();
});

test("mengetik segera setelah reset tidak menghidupkan query sebelumnya", async () => {
  const muatan = await pasang("meja");
  klik("Reset semua");
  ketik("kursi");
  await waktu(250); await waktu(300);
  expect(muatan.map(m => m.search)).toEqual(["", "kursi"]);
  expect(muatan.every(m => m.filter === "")).toBe(true);
});

test("reset filter lanjutan tetap mempertahankan kata pencarian", async () => {
  const muatan = await pasang("meja");
  klik("Reset lanjutan");
  await waktu(1000);
  expect(screen.getByTestId("search-input")).toHaveValue("meja");
  expect(muatan).toEqual([{ page: 1, search: "meja", filter: "", sort: "name_desc" }]);
});

test("mengetik biasa tetap menunggu debounce dan minimum dua karakter", async () => {
  const muatan = await pasang();
  ketik("m"); await waktu(250); await waktu(300);
  expect(muatan).toHaveLength(0);
  ketik("me"); await waktu(249);
  expect(muatan).toHaveLength(0);
  await waktu(1); await waktu(299);
  expect(muatan).toHaveLength(0);
  await waktu(1);
  expect(muatan.map(m => m.search)).toEqual(["me"]);
});
