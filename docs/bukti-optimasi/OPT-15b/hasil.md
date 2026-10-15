# OPT-15b — Pembacaan restore berbatas

Pembaca `iter_json_documents` mendukung array JSON lama padat maupun format
satu dokumen per baris. Ia menahan satu dokumen plus chunk 64 KiB, menolak JSON
terpotong/trailing data, dan tidak pernah memuat seluruh koleksi. Penerapan
menggunakan batch maksimum 200 dokumen atau ambang 4 MiB, dengan satu dokumen
maksimum tetap dibatasi BSON. GridFS dan uploads dibaca/ditulis dalam chunk
256 KiB. Metadata/manifest tetap struktur terbatas 64 MiB, bukan streaming
metadata tak terbatas.

Uji relatif tracemalloc membandingkan parser lama `json.loads(zf.read())` dan
parser baru pada 5.000 dokumen berisi 2.000 karakter; pembaca baru harus memakai
kurang dari 1/5 peak pembaca lama. Tes legacy/rollback/portal serta drill Mongo
membuktikan format tetap dapat dipulihkan. OPT-15a laporan berada di paket lain.
