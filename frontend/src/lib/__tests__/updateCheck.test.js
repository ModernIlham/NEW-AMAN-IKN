import { startUpdateCheck } from "../updateCheck";
import { toast } from "sonner";
jest.mock("sonner", () => ({ toast: { info: jest.fn() } }));
let original, worker, listeners, script;
beforeEach(() => {
  jest.useFakeTimers(); original = Object.getOwnPropertyDescriptor(navigator, "serviceWorker");
  listeners = new Map(); worker = { controller: { postMessage: jest.fn() }, addEventListener: jest.fn((type, cb) => listeners.set(type, cb)), removeEventListener: jest.fn((type, cb) => { if (listeners.get(type) === cb) listeners.delete(type); }), ready: Promise.resolve() };
  Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: worker });
  script = document.createElement("script"); script.src = "/static/js/main.abc123.js"; document.head.appendChild(script);
});
afterEach(() => { script.remove(); if (original) Object.defineProperty(navigator, "serviceWorker", original); else delete navigator.serviceWorker; jest.useRealTimers(); });
test("pin memakai bundle tab yang berjalan saat controller berubah, tanpa memuat ulang draf", async () => {
  const input = document.createElement("input"); input.value = "Belum disimpan"; document.body.appendChild(input);
  const cleanup = startUpdateCheck(); await Promise.resolve();
  expect(worker.controller.postMessage).toHaveBeenLastCalledWith({ type: "AMAN_PIN_RELEASE", main: "/static/js/main.abc123.js" });
  listeners.get("controllerchange")(); listeners.get("message")({ data: { type: "AMAN_CACHE_RELEASE", releaseId: "new-release" } });
  expect(worker.controller.postMessage).toHaveBeenLastCalledWith({ type: "AMAN_PIN_RELEASE", main: "/static/js/main.abc123.js" });
  expect(input.value).toBe("Belum disimpan"); cleanup(); input.remove();
  expect(listeners.size).toBe(0); const calls = worker.controller.postMessage.mock.calls.length; jest.advanceTimersByTime(60000); expect(worker.controller.postMessage).toHaveBeenCalledTimes(calls);
});
test("install tertahan anggaran menampilkan tindakan jelas dan tidak menghapus state pengguna", () => {
  const cleanup = startUpdateCheck(); listeners.get("message")({ data: { type: "AMAN_CACHE_UPDATE_BLOCKED", reason: "cache_budget_protected" } });
  expect(toast.info).toHaveBeenCalledWith(expect.stringContaining("setelah menyimpan perubahan"), expect.objectContaining({ duration: Infinity })); cleanup();
});
