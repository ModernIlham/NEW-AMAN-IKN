import { act, renderHook } from "@testing-library/react";
import { useWebSocket } from "../useWebSocket";
class FakeWebSocket {
  static OPEN = 1;
  static instances = [];
  constructor(url) { this.url = url; this.readyState = 1; this.send = jest.fn(); this.close = jest.fn(); FakeWebSocket.instances.push(this); }
}
const savedWS = global.WebSocket;
beforeEach(() => { jest.useFakeTimers(); global.WebSocket = FakeWebSocket; FakeWebSocket.instances = []; });
afterEach(() => { global.WebSocket = savedWS; jest.useRealTimers(); });
const message = type => ({ data: JSON.stringify({ type, reason: "ring_gap" }) });
test("gap dikoaleskan, event koneksi kegiatan lama ditolak, unmount membatalkan resync tertunda", () => {
  const resync = jest.fn(), assetChange = jest.fn();
  const { rerender, unmount } = renderHook(p => useWebSocket({ ...p, onResync: resync, onAssetChange: assetChange }),
    { initialProps: { activityId: "A", userId: "u" } });
  const a = FakeWebSocket.instances[0], oldMessage = a.onmessage;
  act(() => { a.onopen(); a.onmessage(message("resync_required")); a.onmessage(message("resync_required")); });
  act(() => jest.advanceTimersByTime(200)); expect(resync).toHaveBeenCalledTimes(1);
  rerender({ activityId: "B", userId: "u" });
  const b = FakeWebSocket.instances[1];
  act(() => { oldMessage(message("resync_required")); jest.advanceTimersByTime(300); });
  expect(resync).toHaveBeenCalledTimes(1); expect(assetChange).not.toHaveBeenCalled();
  act(() => b.onmessage(message("resync_required"))); unmount();
  act(() => jest.advanceTimersByTime(300)); expect(resync).toHaveBeenCalledTimes(1);
});
test("reconnect memicu catch-up sekali; callback close/message lama tidak mengubah koneksi baru", () => {
  const resync = jest.fn();
  const { result } = renderHook(() => useWebSocket({ activityId: "A", userId: "u", onResync: resync }));
  const a = FakeWebSocket.instances[0];
  act(() => a.onopen());
  act(() => jest.advanceTimersByTime(5000));
  const oldClose = a.onclose, oldMessage = a.onmessage;
  act(() => { a.onclose({ code: 1006 }); jest.advanceTimersByTime(3000); });
  const b = FakeWebSocket.instances[1];
  act(() => { b.onopen(); oldClose({ code: 1006 }); oldMessage(message("resync_required")); jest.advanceTimersByTime(200); });
  expect(result.current.connected).toBe(true); expect(resync).toHaveBeenCalledTimes(1);
});
