/** Penjaga wiring: uji perilaku callback ada di usePenyegaranAset.test.jsx. */
import fs from "fs";
import path from "path";

const HALAMAN = fs.readFileSync(path.join(__dirname, "..", "DashboardPage.jsx"), "utf8");
const TOOLBAR = HALAMAN.match(/<DashboardToolbar\b[\s\S]*?\/>/)[0];

test("toolbar tidak mendapat callback arrow baru pada tiap render halaman", () => {
  expect(TOOLBAR).not.toMatch(/=>/);
  expect(TOOLBAR).toContain("onOpenMap={handleMapToggle}");
  expect(TOOLBAR).toContain("onCetakStiker={handleCetakStiker}");
  expect(TOOLBAR).toContain("refreshData={refreshData}");
  expect(HALAMAN).toMatch(/const handleMapToggle = useCallback\(\(\) => setMapOpen\(p => !p\), \[\]\)/);
  expect(HALAMAN).toMatch(/const handleCetakStiker = useCallback\(\(\) => setStikerOpen\(true\), \[\]\)/);
});

test("penyegaran menerima pembaca data DAN parameter terbaru dari halaman", () => {
  const wiring = HALAMAN.match(/const refreshData = usePenyegaranAset\(\{([\s\S]*?)\}\)/)?.[1];
  expect(wiring).toBeDefined();
  for (const nama of ["doFetch", "doFetchStats", "debouncedSearch", "filterCategory", "sortBy", "pageSize", "currentPage", "setPageLoading"]) {
    expect(wiring).toMatch(new RegExp(`\\b${nama}\\b`));
  }
});
