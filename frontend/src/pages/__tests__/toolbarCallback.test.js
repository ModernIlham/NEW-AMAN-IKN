/** Penjaga wiring: uji perilaku callback ada di usePenyegaranAset.test.jsx. */
import fs from "fs";
import path from "path";

const HALAMAN = fs.readFileSync(path.join(__dirname, "..", "DashboardPage.jsx"), "utf8");
const TOOLBAR = HALAMAN.match(/<DashboardToolbar\b[\s\S]*?\/>/)[0];

test("toolbar tidak mendapat callback arrow baru pada tiap render halaman", () => {
  expect(TOOLBAR).not.toMatch(/=>/);
  expect(TOOLBAR).toContain("onOpenMap={handleMapToggle}");
  expect(TOOLBAR).toContain("onCetakStiker={handleCetakStiker}");
  // Toolbar hanya mengubah state filter/urutan; pemiliknya yang memuat ulang.
  expect(TOOLBAR).not.toContain("refreshData=");
  expect(HALAMAN).toMatch(/const handleMapToggle = useCallback\(\(\) => setMapOpen\(p => !p\), \[\]\)/);
  expect(HALAMAN).toMatch(/const handleCetakStiker = useCallback\(\(\) => setStikerOpen\(true\), \[\]\)/);
});

test("perubahan urutan tetap memuat halaman pertama melalui efek pemilik toolbar", () => {
  // Penjaga anti-hampa untuk harness interaksi urutTanpaFetchGanda: menghapus
  // fetch di kontrol hanya benar selama pemilik masih memantau sortBy.
  const bagian = HALAMAN.slice(HALAMAN.indexOf("// Re-fetch on filter/search/sort change"));
  const efek = bagian.slice(0, bagian.indexOf("]);") + 3);
  const deps = efek.slice(efek.indexOf("}, ["));
  expect(efek).toContain("refreshData(1, { showLoading: true });");
  expect(deps).toMatch(/\bsortBy\b/);
});

test("penyegaran menerima pembaca data DAN parameter terbaru dari halaman", () => {
  const wiring = HALAMAN.match(/const refreshData = usePenyegaranAset\(\{([\s\S]*?)\}\)/)?.[1];
  expect(wiring).toBeDefined();
  for (const nama of ["doFetch", "doFetchStats", "debouncedSearch", "filterCategory", "sortBy", "pageSize", "currentPage", "setPageLoading"]) {
    expect(wiring).toMatch(new RegExp(`\\b${nama}\\b`));
  }
});

test("reset hasil kosong memakai callback atomik dan membatalkan draf toolbar", () => {
  const tombol = HALAMAN.match(/<Button\b[^>]*data-testid="empty-reset-filter-btn"[^>]*>/)?.[0];
  expect(tombol).toBeDefined();
  expect(tombol).toContain("onClick={resetAllFilters}");
  expect(tombol).not.toContain("refreshData");
  expect(TOOLBAR).toContain("searchResetKey={searchResetKey}");
});
