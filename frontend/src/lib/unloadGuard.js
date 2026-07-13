// Penentu apakah muat-ulang / penutupan halaman perlu ditahan demi keamanan
// data offline. SENGAJA murni (tanpa DOM/React) agar mudah diuji unit.
//
// Konteks: antrian tulis offline (useOptimisticQueue) SUDAH persist di IndexedDB
// dan auto-flush saat online, jadi data tidak benar-benar hilang saat reload.
// Namun pengguna bisa saja menutup/menyegarkan aplikasi (atau berpindah ke versi
// baru) di TENGAH proses sinkron tanpa sadar masih ada yang tertunda. Guard ini
// dasar pengambilan keputusan untuk menampilkan dialog konfirmasi bawaan peramban.
//
//  - pendingCount → item yang masih bisa/akan disinkronkan (queued/saving/gagal
//    jaringan). Ini "data yang perlu disinkronkan" inti.
//  - actionCount  → item macet (konflik 409 / kegiatan terkunci 423) yang butuh
//    tindakan manual. Tetap dihitung sebagai "belum tersinkron" agar pengguna
//    tidak menutup aplikasi dengan menganggap semua sudah beres.
export function hasUnsyncedWork({ pendingCount = 0, actionCount = 0 } = {}) {
  const p = Number(pendingCount) || 0;
  const a = Number(actionCount) || 0;
  return p + a > 0;
}
