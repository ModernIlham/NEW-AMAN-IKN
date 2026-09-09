import React, { useEffect, useRef } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DashboardToolbar from "../DashboardToolbar";
import { useAssetFilters } from "@/hooks/useAssetFilters";
import { usePenyegaranAset } from "@/hooks/usePenyegaranAset";

// Hanya bagian di luar pengurutan yang diganti; kedua Select Radix, state
// filter, dan hook penyegaran tetap kode produksi, bukan salinan handler.
jest.mock("@/components/assets", () => ({
  CategorySelect: () => null,
  TinifyQuotaIndicator: () => null,
  TinifyQuotaMobile: () => null,
  AdvancedFilter: () => null,
}));
jest.mock("@/components/assets/QrScanButton", () => () => null);
jest.mock("@/components/assets/StatsBar", () => ({ InventoryModeSwitch: () => null }));

beforeAll(() => {
  window.HTMLElement.prototype.hasPointerCapture = () => false;
  window.HTMLElement.prototype.releasePointerCapture = () => {};
  window.HTMLElement.prototype.scrollIntoView = () => {};
});

function LayarUji({ doFetch, doFetchStats, setPageLoading }) {
  const filter = useAssetFilters({ activityId: "kegiatan-uji" });
  const refreshData = usePenyegaranAset({
    ...filter, doFetch, doFetchStats, setPageLoading,
    currentPage: 4, pageSize: 50,
  });
  // Kontrak pemilik toolbar di DashboardPage: perubahan urutan memuat
  // halaman pertama sesudah state diterapkan. Wiring aslinya dijaga terpisah.
  const awal = useRef(true);
  useEffect(() => {
    if (awal.current) { awal.current = false; return; }
    refreshData(1, { showLoading: true });
  }, [refreshData, filter.sortBy]);

  return <DashboardToolbar {...filter} categories={[]} assetsCount={20}
    perms={{}} refreshData={refreshData} />;
}

function pasang() {
  const doFetch = jest.fn().mockResolvedValue([]);
  const doFetchStats = jest.fn().mockResolvedValue({});
  const setPageLoading = jest.fn();
  render(<LayarUji {...{ doFetch, doFetchStats, setPageLoading }} />);
  const pengguna = userEvent.setup({ pointerEventsCheck: 0 });
  // jsdom tidak menerapkan breakpoint CSS; kedua cabang sengaja diuji.
  const pemicu = screen.getAllByRole("combobox");
  expect(pemicu).toHaveLength(2);
  return { doFetch, doFetchStats, setPageLoading, pengguna, pemicu };
}

test.each([["desktop", 0], ["HP/tablet", 1]])(
  "%s: satu pilihan urutan hanya membaca urutan baru pada halaman pertama", async (_, index) => {
    const { doFetch, doFetchStats, setPageLoading, pengguna, pemicu } = pasang();
    expect(doFetch).not.toHaveBeenCalled();
    await pengguna.click(pemicu[index]);
    await pengguna.click(await screen.findByRole("option", { name: "Terlama" }));
    await waitFor(() => expect(doFetch).toHaveBeenCalledTimes(1));
    expect(doFetch).toHaveBeenCalledWith(1, 50, "", [], "oldest", false, false);
    expect(doFetchStats).toHaveBeenCalledTimes(1);
    expect(doFetchStats).toHaveBeenCalledWith("");
    expect(setPageLoading.mock.calls).toEqual([[true], [false]]);
    pemicu.forEach(el => expect(el).toHaveTextContent("Terlama"));
  },
);

test.each([["desktop", 0], ["HP/tablet", 1]])(
  "%s: beberapa pilihan berturut-turut tidak menyisipkan permintaan urutan sebelumnya", async (_, index) => {
    const { doFetch, doFetchStats, pengguna, pemicu } = pasang();
    for (const nama of ["Terlama", index === 0 ? "Nama A-Z" : "A-Z", "Terbaru"]) {
      await pengguna.click(pemicu[index]);
      await pengguna.click(await screen.findByRole("option", { name: nama }));
    }
    expect(doFetch.mock.calls.map(a => a[4])).toEqual(["oldest", "name_asc", "newest"]);
    expect(doFetch.mock.calls.map(a => a[0])).toEqual([1, 1, 1]);
    expect(doFetchStats).toHaveBeenCalledTimes(3);
  },
);

test.each([["desktop", 0], ["HP/tablet", 1]])(
  "%s: memilih ulang nilai aktif tidak memuat ulang", async (_, index) => {
    const { doFetch, doFetchStats, pengguna, pemicu } = pasang();
    await pengguna.click(pemicu[index]);
    await pengguna.click(await screen.findByRole("option", { name: "Terbaru" }));
    expect(doFetch).not.toHaveBeenCalled();
    expect(doFetchStats).not.toHaveBeenCalled();
  },
);
