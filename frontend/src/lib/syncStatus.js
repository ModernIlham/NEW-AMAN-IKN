// Ringkasan status antrian sinkron — SENGAJA dipisah tanpa dependensi berat
// (axios/idb/sonner) agar murni & mudah diuji unit.
//
// Dibedakan agar tanda sinkron di header tidak menyesatkan (bug: tanda tetap
// menyala walau sudah online & sudah ditekan Sinkronkan, lalu muncul lagi tiap
// buka halaman):
//  - pendingCount → item yang MASIH BISA disinkronkan tombol Sinkronkan
//    (queued/saving/failed jaringan). Flush global akan mencoba ulang ini.
//  - actionCount  → item MACET yang perlu tindakan manual per-baris dan TIDAK
//    akan pernah selesai lewat flush global: konflik versi 409 (status
//    "conflict") atau kegiatan terkunci 423 (status "failed" + {locked}).
//    Dulu keduanya ikut dihitung sebagai pending → tombol sinkron menyala
//    selamanya karena flush memang melewatinya (lihat flushPending).
//  - isSyncing    → benar-benar ada yang sedang diproses (queued/saving).
export function summarizeSyncStatuses(statuses) {
  let pendingCount = 0;
  let actionCount = 0;
  let isSyncing = false;
  Object.values(statuses || {}).forEach((s) => {
    if (!s || !s.status) return;
    const { status } = s;
    // Macet: perlu tindakan manual, bukan flush global.
    if (status === "conflict" || (status === "failed" && s.locked)) {
      actionCount++;
      return;
    }
    if (status === "queued" || status === "saving" || status === "failed") {
      pendingCount++;
    }
    if (status === "queued" || status === "saving") {
      isSyncing = true;
    }
  });
  return { pendingCount, isSyncing, actionCount };
}
