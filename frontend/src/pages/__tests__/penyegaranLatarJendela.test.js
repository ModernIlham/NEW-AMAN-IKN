/**
 * Penjaga wiring: penyegaran yang TIDAK dipicu gulir pengguna tidak boleh
 * meruntuhkan jendela infinite-scroll HP/galeri.
 *
 * `refreshData()` biasa memanggil doFetch(currentPage) yang mengganti seluruh
 * jendela dengan SATU halaman (di HP hampir selalu halaman 1). Dipanggil dari
 * event WebSocket (rekan menambah aset), pengguna yang sedang menggulir jauh
 * di bawah terlempar ke posisi lain — direproduksi di Chromium: aset #211 →
 * #43 tanpa gulir sama sekali. Perilakunya diuji di usePenyegaranAset &
 * pemuatDaftarAset; berkas ini menjaga pemanggilnya.
 */
import fs from "fs";
import path from "path";

const HALAMAN = fs.readFileSync(path.join(__dirname, "..", "DashboardPage.jsx"), "utf8");

test("event WebSocket memakai penyegaran jendela yang senyap", () => {
  const ws = HALAMAN.slice(HALAMAN.indexOf("const onWsAssetChange = useCallback"));
  const timer = ws.slice(ws.indexOf("wsRefreshTimerRef.current = setTimeout"), ws.indexOf("}, 2000);"));
  expect(timer).toContain("refreshData(undefined, { refreshWindow: true, latar: true });");
  expect(timer).not.toMatch(/refreshData\(\);/);
});

test("tersambung ulang, simpan via form, dan hapus berhasil mempertahankan jendela", () => {
  expect(HALAMAN).toContain("if (isOnline && offlineServedRef.current) refreshDataRef.current?.(undefined, { refreshWindow: true, latar: true });");
  const simpan = HALAMAN.slice(HALAMAN.indexOf("const handleFormSubmitSuccess"));
  expect(simpan.slice(0, simpan.indexOf("}, ["))).toContain("refreshData(undefined, { refreshWindow: true });");
  const hapus = HALAMAN.slice(HALAMAN.indexOf("await axios.delete(`${API}/assets/${id}`);"));
  expect(hapus.slice(0, hapus.indexOf("return true;"))).toContain("refreshDataRef.current(undefined, { refreshWindow: true });");
});
