# Aktivasi budget global setelah rilis sehat

Workflow manual activate-export-budget memakai controller SHA penuh yang tepat,
main ancestry dan successful CI push/main. Git HEAD produksi dan actual process
health SHA harus sama sebelum mutasi. Tidak ada perubahan nginx/Supervisor;
feature override Supervisor/inherited environment yang bertentangan ditolak.

Controller scripts/activate_export_budget.py mengambil mutex GLOBAL, drain
writer/unduhan/background/queue/holders tanpa TTL takeover, memeriksa UID dan
physical flock, lalu membuktikan STOPPED. Empat override ditambahkan atomik ke
backend/.env tanpa mengubah prefix byte asli: ENABLED=1, GLOBAL_SLOTS=1,
SATKER_SLOTS=1, LOCK_DIR=/var/lib/aman/export-locks. Original bytes/mode tersimpan
privat0700/0600 di /var/lib/aman/operations/budget-<run>. Durable worker dan
checklist-write tetap off. Existing physical configuration selain1/1 ditolak;
lock aktif tidak dihapus atau dicuri.

Sesudah fresh process/capability1/1/deep health, mutex dilepas agar admission
smoke dapat bekerja. Controller menahan cpu-0 flock, mengamati antrean dan health
responsif, meminta public static proposal DOCX hingga429+RetryAfter, melepas
flock lalu meminta dokumen sama hingga200 ZIP DOCX valid berbatas2MiB. Dua
request dokumen ini tidak membuat akun atau membaca data pelanggan. Queue,
holders dan writer lease harus kembali kosong. Hasil aktual lokal:
[budget-native-smoke.json](budget-native-smoke.json), 429→200/48065byte/16,36s,
DB sementara dihapus. Auth/satker parity dibuktikan kontrak API terpisah.

Smoke gagal memicu rollback dengan mutex BARU, drain baru, SHA/config tetap dan
fresh process/health lama. Environment yang diubah operator atau restore owner
baru tidak ditimpa. Unknown acquire/release ack menyimpan jurnal dan exit70;
setelah release attempt tidak ada kompensasi tanpa ownership baru.

24unit fault tests lulus sebelum final integration: byte/mode rollback,
semua edge service/env, physical lock, sinyal, unknownack, owner restore baru,
dan fresh-mutex rollback sesudah smoke. Root menjalankan workflow produksi
setelah main CI/deploy sehat dan mencatat Checks API evidence; bukti lokal ini
bukan klaim aktivasi produksi sudah selesai.
