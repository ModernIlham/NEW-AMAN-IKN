# OPT-18 — Profil query, indeks terukur, dan cursor opt-in

## Lingkup dan metode

Dua dataset sintetis Mongo nyata: 10.000 dan 50.000 aset; scope kegiatan masing-masing
2.000 dan 10.000 aset. Indeks startup aplikasi dipasang pada database lokal
`aman_ci_*` yang memiliki marker/manifest seed sendiri. `profile_asset_reads.py`
mengambil konstruktor pipeline handler checkout, menjalankan explain executionStats,
lalu tujuh sampel query berulang dengan cache hangat. Artefak hanya angka agregat,
tanpa isi aset, token, kredensial, atau explain mentah. Skrip menolak target nonloopback,
database biasa, credentials/options URL, manifest/marker/count yang tidak cocok.

Waktu berikut adalah waktu query lokal pada mesin cloud bersama, bukan latensi API,
uji konkurensi, cold-cache, atau kapasitas produksi. p95 dari tujuh sampel memakai
nearest-rank; variasi penjadwalan terlihat pada run kedua. Jumlah key/doc yang dibaca
menjadi bukti utama perubahan akses. Tidak ada query yang memakai disk dalam run ini.

## Hasil 50k, scope 10k, projection LIST sebenarnya

| Query | Key/doc examined | p50 / p95 ms sebelum | Hasil/keputusan |
| --- | --- | --- | --- |
| Halaman awal, 50 row | 50 / 50 | 8,42 / 12,56 | Indeks activity+created_at+id sudah tepat |
| Halaman akhir, skip 9950 | 10000 / 50 | 1622,48 / 2602,75 | Mahal; cursor opt-in ditambahkan |
| Cursor created_at+id pada posisi akhir | 50 / 50 | 7,26 / 9,20 | Pemindaian turun; planner memakai merge/sort OR |
| Nama ascending sebelum indeks baru | 10000 / 10000 | 40,50 / 47,76 | Sort dalam memori |
| Nama ascending setelah indeks baru | 50 / 50 | 4,24 / 12,23 | Indeks activity+asset_name+id, tanpa sort |
| Harga Decimal computed | 10000 / 10000 | 132,73 / 240,53 | Koreksi numerik tetap; belum menambah shadow field |
| Substring contoh fixture | 50 / 50 | 4,22 / 4,78 | Banyak kecocokan di awal; tidak membuktikan regex umum murah |
| Multi-filter category+condition | 1193 / 1193 | 11,13 / 11,42 | Kandidat indeks lain belum terbukti perlu |
| Count exact | 10001 / 0 | 8,60 / 14,45 | Tetap exact, semantik tidak diganti estimasi |
| Statistik | 10000 / 10000 | 79,48 / 199,25 | Agregasi tetap scoped, cache namespace tetap |
| Analytics | 10000 / 10000 | 146,72 / 159,49 | Group/sort bounded oleh scope; belum read model |
| Groups | 10000 / 10000 | 119,19 / 297,28 | Group/sort tetap; limit hasil bukan limit sumber |
| Snapshot keyset, 1000 row | 1000 / 1000 | 60,94 / 67,69 | Indeks snapshot sudah efektif |

Run setelah indeks: halaman akhir tetap membaca 10000 key (p50 1256 ms), cursor
50 key (p50 9,98 ms); perubahan waktu tidak diatribusikan ke indeks nama. Semua
sampel tersimpan di `query-50k-before-name-index.json` dan
`query-50k-after-name-index.json`; baseline10k ada di `query-10k.json`.

## Biaya indeks

Hanya indeks nama `(activity_id:1, asset_name:1, id:1)` ditambahkan setelah bukti
explain. Indeks lama dipertahankan. Skrip eksperimen `profile_asset_index.py`
memerlukan `--allow-local-index-change`, guard dataset yang sama, dan hanya
memutasi indeks kandidat/probe milik run sintetis. Semua probe dibersihkan;
50.000 row sumber tetap utuh.

Eksperimen terpisah dengan covered projection: 10000 key+doc/sort menjadi
50 key/0 doc/tanpa sort; median40,31→0,76 ms. Full LIST di tabel atas tetap
membaca50 doc, sehingga hasil covered tidak dipakai untuk klaim halaman penuh.
Build304 ms; ukuran indeks kandidat684032 byte (668 KiB); jumlah indeks41→42.
Total index bytes sesudah probe menyertakan alokasi historis dan indeks lain,
sehingga selisih total dari profil berbeda tidak dianggap ukuran kandidat.
Lima batch insert500 row median186,56→180,01 ms, delete215,86→249,29 ms.
Sampel tulis ini bising dan bulk, bukan biaya API; tidak membuktikan write-SLO
produksi. Amati latensi tulis/storage produksi setelah rilis sebelum menghapus
indeks lama atau menambah kandidat lain.

## Kontrak cursor dan pemakaian memori

`GET /assets?pagination=cursor` opt-in, hanya newest/oldest; sort tak dikenal
mengikuti newest. Desktop/page/total lama tetap default. Cursor signed-purpose
tersendiri mengikat user/role/satker, kueri akhir termasuk activity/filter, sort,
page_size, dan epoch dataset. Batas token2048 byte, TTL30 menit; malformed400,
konteks/expiry/restore409. Cursor bukan bearer token. Urutan sama dengan page
API pada data statis, termasuk tieID ascending dan created_at null/missing.
Tipe created_at lain ditolak400 pada cursor, sementara API page lama tetap ada.

Respons menyatakan `consistency=mutable_dataset`: bukan snapshot immutable.
Insert di depan anchor muncul pada pemuatan ulang; insert di belakang dapat
muncul pada halaman berikut. Update yang memindahkan row melintasi anchor dapat
mengulang ID; pemakai cursor perlu dedup/reconcile. Anchor terhapus tetap dapat
dilanjutkan. Frontend page yang ada tidak diam-diam dialihkan ke cursor.

Lookup PSP sebelumnya mengumpulkan semua SK cocok lewat `to_list(None)` dan
membuat peta seluruh anggota SK, termasuk ID di luar halaman. Sekarang cursor
SK dialirkan batch1 dan peta hanya menyimpan ID aset yang diminta; latest-date,
status ditetapkan, SIMAN fallback dan scope satker dipertahankan. Eksperimen
projection `$filter` Mongo untuk SK10000 anggota mengurangi599009→3009 byte,
tetapi median5,90→25,23 ms; pipeline itu tidak diaktifkan. Streaming membatasi
heap pada satu SK dan peta ID terpilih, tanpa klaim latensi PSP lebih cepat.

## Keputusan read model dan verifikasi

Read model harga/count/stats tidak diaktifkan saat ini: query awal/snapshot
sudah indexed, count exact murah pada scope uji, computed price/stats masih
memenuhi budget lokal tunggal yang diamati. Denormalisasi akan menambah kontrak
semua writer/restore tanpa bukti beban representatif yang memerlukannya.
Tinjau ulang bila scope, media, concurrency atau tail latency produksi melewati
budget yang disepakati; gunakan replay filter representatif, termasuk substring
yang langka/tidak cocok. Ini penutupan pekerjaan kondisional, bukan janji
50k row merupakan batas kapasitas sistem.

`test_asset_cursor.py` menguji parity tiga sort, null/missing/ties, foreign satker,
filter/owner/page_size/sort, malformed/expiry/epoch/bearer misuse, anchor deletion,
insert/update antarhalaman, dan PSP official/latest/scope dengan1000 anggota
lain. Enam unit guard profiler dan unit limit lolos pada run fokus. Kontrak
Mongo+Redis dijalankan terpisah dari unit agar konfigurasi DB aman. Rollback:
abaikan `pagination=cursor`, indeks lama tetap ada; tidak ada backfill/schema
resmi yang perlu dikembalikan.

Verifikasi akhir scope data:32 kontrak Mongo+Redis lulus11,88 detik pada enam
file (cursor, media limits, photo commit, finite stats, numeric/search sync,
report completeness). Unit domain/Meili/stats/limit/profiler/G3:85 lulus2,06 detik;
legacy cover/G3:17 lulus1,54 detik. `git diff --check` bersih. Gate penuh memakai
snapshot immutable koordinator; angka-angka ini bukan hasil produksi.

Gate fokus final setelah perbaikan delayed-write dan geo:50 kontrak data Mongo+
Redis lulus24,34 detik;118 unit lintas reader/metadata/render lulus9,75 detik.
Runtime source dibekukan sebelum snapshot full-suite koordinator.
