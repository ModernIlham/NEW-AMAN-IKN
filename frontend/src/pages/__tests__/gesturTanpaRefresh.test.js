import fs from "fs";
import path from "path";

const halaman = fs.readFileSync(path.join(__dirname, "../DashboardPage.jsx"), "utf8");
const css = fs.readFileSync(path.join(__dirname, "../../index.css"), "utf8");

test("daftar, galeri, dan peta tidak mewarisi penangkap gestur refresh", () => {
  expect(halaman).not.toMatch(/usePullToRefresh|handleTouch(Start|Move|End)|Lepaskan untuk refresh|Tarik ke bawah/);
  const main = halaman.match(/<main\b[^>]*>/)[0];
  expect(main).toContain('data-testid="asset-main-content"');
  expect(main).toContain("overscroll-y-contain");
  expect(main).not.toMatch(/onTouch|onPointer|touch-action/);
  expect(halaman).toContain("const mainContentRef = useRef(null)");
  expect(halaman).toContain("<ScrollToTop scrollRef={mainContentRef}");
  expect(css).toMatch(/html\s*\{\s*overscroll-behavior-y:\s*none;\s*\}/);
});

test("toolbar memakai muat ulang eksplisit dengan callback stabil", () => {
  expect(halaman).toContain("useMuatUlangManual(refreshData)");
  const toolbar = halaman.match(/<DashboardToolbar\b[\s\S]*?\/>/)[0];
  expect(toolbar).toContain("onRefreshData={onRefreshData} refreshing={refreshing}");
});
