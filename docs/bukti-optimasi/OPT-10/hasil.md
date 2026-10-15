# OPT-10 — Liveness dan admission unduhan

Implementasi 15 Oktober 2026:

- Heartbeat dimulai sebelum antre semaphore dan jeda, berlanjut selama render,
  retry429, dan upload. Exception ditangani tiap iterasi sehingga satu gangguan
  Mongo tidak membunuh heartbeat. Task dibatalkan dan di-await di finally.
- Writer menambahkan `active_lock:true`; index partial unique
  `unduhan_satu_aktif_per_owner` pada `dibuat_oleh`, filter `active_lock:true`,
  mengarbitrase admission lintas proses. Count lama hanya pagar kompatibilitas
  untuk legacy jobs. DuplicateKey menjadi409.
- Setiap admission memverifikasi index lewat create_index idempoten. Startup
  index di repository bersifat best effort, sehingga gagal/missing/conflicting
  index harus menolak admission503, bukan berpura-pura aman memakai count.
- Transisi unduhan hanya mencocokkan queued/running. Done/error/reaper melepas
  active_lock atomik; heartbeat atau hasil terlambat tidak menghidupkan terminal
  state. Job generik juga menolak perubahan setelah done/error/failed/cancelled.
- DELETE queued/running ditolak409 dan tidak melepaskan klaim. Physical cancel
  melalui tombol hapus tidak diperkenalkan.
- Admission membaca deploy gate `restore_control.GLOBAL` uncached dan menolak503
  ketika state=deploying,active=true. Deploy wajib drain writer lease middleware
  setelah gate diklaim, sebelum pemeriksaan queued/running; lihat OPT-08.

## Bukti

`test_unduhan_lifecycle.py`: fail-once heartbeat pulih, antre semaphore tetap
berdenyut, cancel membersihkan heartbeat+klaim, terminal tidak ditimpa, hapus
running409, dua admission dengan count sama-sama nol hanya satu diterima,
user berbeda independen, index tidak tersedia503, deploy gate503, audit read-only,
dan reply publikasi Mongo hilang tidak menghapus blob yang committed.

`backend/tests/contract/test_unduhan.py`: Mongo partial unique nyata, request API
konkuren melalui auth+middleware, berbeda owner, dan running-delete409. Tambahan
dua proses Python independen memakai handler yang sama, dua koneksi Motor, dan
barrier setelah count sama-sama nol membuktikan pemenang tunggal200+409.
Seluruh fixture menggunakan DB localhost terisolasi milik contract fixture.

Hasil lokal: **52 tes unit terfokus lulus**, **3 tes kontrak Mongo/GridFS nyata
lulus**; komando reproduksi tersimpan pada bukti OPT-09.

## Migrasi dan rollback

Audit **read-only**, tidak menulis/membatalkan/menghapus pekerjaan:

```bash
.venv/bin/python backend/audit_unduhan_claims.py
```

Exit2 berarti ada legacy aktif, owner aktif duplikat, atau terminal lock tidak
konsisten. Jangan membackfill active_lock ke job berjalan atau membunuh job hanya
agar index terbentuk. Pada rollout pertama, tahan admission di ingress,
tunggu queued/running lama selesai, jalankan audit, lalu ganti seluruh worker.
Setelah versi ini terpasang, deploy gate dan writer-lease drain OPT-08 menutup
admission race. Rollback harus memakai drain yang sama dan mempertahankan index
serta data tambahan; jangan drop index saat worker masih mengeksekusi.

Heartbeat bukan durable worker: proses mati tetap berakhir error melalui reaper,
bukan resume artifact otomatis. Pemisahan worker, lease/fencing dan global budget
memerlukan OPT-22. Batas satu job per owner global lintas satker disengaja:
berpindah satker tidak menyediakan slot tambahan untuk username yang sama.
