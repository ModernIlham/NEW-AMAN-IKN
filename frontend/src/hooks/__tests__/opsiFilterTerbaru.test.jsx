import { act, renderHook } from "@testing-library/react";
import axios from "axios";
import { useAssetFilters } from "../useAssetFilters";
import { HASIL_USANG } from "../usePenjagaPermintaan";

jest.mock("axios", () => ({ get: jest.fn() }));
function tertunda() {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
}
beforeEach(() => jest.resetAllMocks());

test.each(["activityId", "userId", "kodeSatker"])("opsi terlambat dari %s lama tidak menghapus pilihan terkini", async field => {
  const a = tertunda(), b = tertunda();
  axios.get.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);
  const awal = { activityId: "A", userId: "U", kodeSatker: "S" };
  const { result, rerender } = renderHook(useAssetFilters, { initialProps: awal });
  const fetchLama = result.current.fetchFilterOptions;
  const lama = fetchLama();
  rerender({ ...awal, [field]: "baru" });
  const baru = result.current.fetchFilterOptions();
  await act(async () => { b.resolve({ data: { eselon_jalur: [["Unit Baru", "Bagian Baru", "", "", ""]] } }); await baru; });
  act(() => result.current.handleAdvancedFilterChange("eselon1", ["Unit Baru"]));
  act(() => result.current.handleAdvancedFilterChange("eselon2", ["Bagian Baru"]));
  const pilihan = result.current.filters;
  expect(pilihan.eselon1).toEqual(["Unit Baru"]);
  expect(pilihan.eselon2).toEqual(["Bagian Baru"]);
  await act(async () => { a.resolve({ data: { eselon_jalur: [["Unit Lama", "Bagian Lama", "", "", ""]] } }); expect(await lama).toBe(HASIL_USANG); });
  expect(result.current.filterOptions.eselon_jalur[0][0]).toBe("Unit Baru");
  expect(result.current.filters).toEqual(pilihan);
  expect(await fetchLama()).toBe(HASIL_USANG);
  expect(axios.get).toHaveBeenCalledTimes(2);
});

test("dua request opsi pada lingkup sama hanya menerima yang terakhir", async () => {
  const a = tertunda(), b = tertunda();
  axios.get.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);
  const { result } = renderHook(() => useAssetFilters({ activityId: "A" }));
  const lama = result.current.fetchFilterOptions(), baru = result.current.fetchFilterOptions();
  await act(async () => { b.resolve({ data: { categories: ["Baru"] } }); await baru; });
  await act(async () => { a.resolve({ data: { categories: ["Lama"] } }); expect(await lama).toBe(HASIL_USANG); });
  expect(result.current.filterOptions.categories).toEqual(["Baru"]);
});

test("opsi setelah unmount diabaikan", async () => {
  const a = tertunda(); axios.get.mockReturnValue(a.promise);
  const { result, unmount } = renderHook(() => useAssetFilters({ activityId: "A" }));
  const lama = result.current.fetchFilterOptions(); unmount();
  a.resolve({ data: { categories: ["Lama"] } });
  expect(await lama).toBe(HASIL_USANG);
});
