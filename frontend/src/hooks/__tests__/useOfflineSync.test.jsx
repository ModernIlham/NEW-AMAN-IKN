import { act, renderHook } from "@testing-library/react";
import { useOfflineSync } from "../useOfflineSync";
import { checkReachable } from "../../lib/connectivity";
jest.mock("../../lib/connectivity", () => ({ checkReachable: jest.fn(), REACHABILITY_RETRY_MS: 10000 }));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), warning: jest.fn() } }));
beforeEach(() => { jest.useFakeTimers(); });
afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });
test("hasil probe lama tidak mengumumkan online setelah offline berikutnya", async () => {
  let done; checkReachable.mockReturnValue(new Promise(resolve => { done = resolve; }));
  const p = renderHook(() => useOfflineSync());
  act(() => window.dispatchEvent(new Event("offline")));
  await act(async () => { done(true); });
  expect(p.result.current.isOnline).toBe(false);
});
test("backend mati saat WiFi tetap terhubung terdeteksi dan dipulihkan lewat probe berkala", async () => {
  checkReachable.mockResolvedValueOnce(false).mockResolvedValue(true);
  const p = renderHook(() => useOfflineSync());
  await act(async () => {});
  expect(p.result.current.isOnline).toBe(false);
  await act(async () => { jest.advanceTimersByTime(10000); });
  expect(p.result.current.isOnline).toBe(true);
});
