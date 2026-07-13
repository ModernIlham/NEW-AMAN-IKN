/* eslint-env jest */
import { summarizeSyncStatuses } from "../lib/syncStatus";

// Ringkasan status antrian sinkron. Inti perbaikan bug "tanda sinkron tetap
// menyala walau sudah online & sudah ditekan Sinkronkan, lalu muncul lagi tiap
// buka halaman": item MACET (konflik 409 / terkunci 423) TIDAK boleh dihitung
// sebagai pending sinkron (yang seolah bisa diselesaikan tombol Sinkronkan),
// melainkan sebagai "perlu tindakan" manual per-baris.
describe("summarizeSyncStatuses", () => {
  test("kosong / nullish → semua nol", () => {
    const zero = { pendingCount: 0, isSyncing: false, actionCount: 0 };
    expect(summarizeSyncStatuses({})).toEqual(zero);
    expect(summarizeSyncStatuses(null)).toEqual(zero);
    expect(summarizeSyncStatuses(undefined)).toEqual(zero);
  });

  test("queued & saving → pending + sedang sinkron", () => {
    expect(summarizeSyncStatuses({ a: { status: "queued" }, b: { status: "saving" } }))
      .toEqual({ pendingCount: 2, isSyncing: true, actionCount: 0 });
  });

  test("gagal jaringan (failed tanpa locked) → pending, bisa di-flush", () => {
    expect(summarizeSyncStatuses({ a: { status: "failed" } }))
      .toEqual({ pendingCount: 1, isSyncing: false, actionCount: 0 });
  });

  test("terkunci 423 (failed + locked) → perlu tindakan, BUKAN pending", () => {
    expect(summarizeSyncStatuses({ a: { status: "failed", locked: true } }))
      .toEqual({ pendingCount: 0, isSyncing: false, actionCount: 1 });
  });

  test("konflik 409 → perlu tindakan, BUKAN pending", () => {
    expect(summarizeSyncStatuses({ a: { status: "conflict" } }))
      .toEqual({ pendingCount: 0, isSyncing: false, actionCount: 1 });
  });

  test("saved / status tak dikenal / entri null → diabaikan", () => {
    expect(summarizeSyncStatuses({ a: { status: "saved" }, b: { status: "entah" }, c: null, d: {} }))
      .toEqual({ pendingCount: 0, isSyncing: false, actionCount: 0 });
  });

  test("campuran realistis → pending & action terpisah benar", () => {
    const r = summarizeSyncStatuses({
      a: { status: "queued" },                 // pending + syncing
      b: { status: "saving" },                 // pending + syncing
      c: { status: "failed" },                 // pending (gagal jaringan)
      d: { status: "failed", locked: true },   // action (423)
      e: { status: "conflict" },               // action (409)
      f: { status: "saved" },                  // diabaikan
    });
    expect(r).toEqual({ pendingCount: 3, isSyncing: true, actionCount: 2 });
  });

  test("hanya item macet → isSyncing false meski ada tanda (tak menyesatkan 'sedang sinkron')", () => {
    const r = summarizeSyncStatuses({
      a: { status: "conflict" },
      b: { status: "failed", locked: true },
    });
    expect(r.isSyncing).toBe(false);
    expect(r.pendingCount).toBe(0);
    expect(r.actionCount).toBe(2);
  });
});
