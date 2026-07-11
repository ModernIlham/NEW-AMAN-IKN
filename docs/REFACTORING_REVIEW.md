# Review Refactoring — AMAN IKN

> Tujuan: set refactoring **terkecil** dengan payoff **terbesar**, agar pengembangan
> lanjutan cepat & aman dan kebutuhan refactoring besar di masa depan minimal.
> Disusun dari review 3-dimensi (struktur frontend, struktur backend, testing/DevEx)
> dengan bukti file:baris. Tidak ada rekomendasi big-bang rewrite.

## Ringkasan eksekutif

Fondasi aplikasi sudah baik (OCC/If-Match, idempotency, guard pengesahan terpusat,
design-system laporan, antrean offline). Masalah strukturalnya adalah **duplikasi
yang terbukti drift** — bukan arsitektur yang salah. Bukti paling nyata: menambah
1 field aset (`pengguna_nip`) menyentuh **13+ titik**, dan 5 titik (ekspor CSV/XLSX,
impor, template) **sempat terlewat** sebelum ditambal.

## Prioritas TINGGI (kerjakan lebih dulu)

| # | Rekomendasi | Effort | Payoff |
|---|---|---|---|
| 1 | **Registry field aset tunggal** — `backend/asset_fields.py` (nama + flag patchable/batchable/tracked/projection/export) → turunkan `PATCHABLE_FIELDS`, `BATCH_ALLOWED_FIELDS`, `TRACKED_FIELDS`, bagian skalar `LIST_PROJECTION`, kolom CSV/XLSX, mapping impor. Frontend: `lib/assetFields` → `emptyForm`, `buildEditFormData`, `TEXT_FIELDS`, `SNAPSHOT_FIELDS`. + 1 pytest anti-drift vs model Pydantic. | sedang | Tambah field: 13+ titik → ~3 titik. Kelas bug "field ada di form tapi hilang di export/patch/offline/audit" hilang struktural (kelas bug ini BARU SAJA terjadi). |
| 2 | **Auth di level router + query-builder pencarian bersama** — `dependencies=[Depends(require_user)]` pada `assets_router`/`batch_router` (opt-out eksplisit untuk endpoint token media). **Ada lubang nyata sekarang**: `batch.py` lock/heartbeat/unlock/locks/groups/all-ids tanpa `require_user`; `get_all_asset_ids` memakai `$regex` mentah tanpa `re.escape` (fix ReDoS tidak merambat). Ekstrak `build_asset_search_query()` dipakai GET /assets & all-ids. | kecil | Lubang auth tertutup; endpoint baru otomatis ter-gate; filter select-all tidak drift dari filter list. |
| 3 | **Ekstrak `TeamMemberListEditor` + `ActivityFormDialog`** dari `ActivitySelectionPage.jsx` (1.665 baris, 34 useState; blok editor tim di-copy-paste 3×). | kecil | Ubah baris anggota tim = 1 tempat; halaman turun <±900 baris; dialog terisolasi dari state list/backup/lightbox. |
| 4 | **Hook data-layer `useAssetListData`** dari `DashboardPage.jsx` (AssetManagementPage 1.250 baris, 37 useState) — pindahkan `serveFromSnapshot`/`doFetch`+merge antrean/`loadMoreMobile`/refresh/rekonsiliasi WS; `filterSnapshotRows`/`sortSnapshotRows`/`serverHasPendingRow` sudah pure → `lib/snapshotQuery.js` + unit test. Jangan tambah Redux/Zustand — masalahnya kolokasi, bukan kurang library. | sedang | Jalur paling rapuh (offline-fallback, pending-merge) jadi unit-testable; fitur dashboard baru tak menyentuh jalur fetch. |
| 5 | **Konsolidasi pipeline foto → `backend/photo_store.py`** — abstraksi `PhotoSet` (tiga array sejajar sebagai satu nilai) dengan `from_asset/add/keep/replace_all/commit/rollback`; aturan "unggah dulu → update dokumen → hapus blob lama" + padding indeks legacy hidup di SATU tempat. Area ini punya riwayat bug data-loss nyata. | sedang | Kelas bug terberbahaya (kehilangan foto aset negara, orphan blob, indeks geser) dikunci satu implementasi teruji. |
| 6 | **CI minimal (GitHub Actions)** — backend: `compileall` + smoke pytest; frontend: `yarn build` (sekaligus lint CRA); opsional `ruff`. Saat ini **55+ PR merge tanpa gerbang otomatis apa pun**. | kecil | Regresi build/import ketahuan di PR, bukan di VPS. Prasyarat agar 17.500 baris test yang ada benar-benar terpakai. |
| 7 | **Smoke pytest bebas-infra** — port `check_pure_logic.py` ke pytest asli; fixture `httpx.ASGITransport` terhadap `server:app` + Mongo service container; tandai 59 test live-server `@pytest.mark.integration`. | sedang | `pytest` jalan di mesin baru/CI dalam detik; regresi auth/model/format ketahuan sebelum deploy. |
| 8 | **Bersihkan discovery pytest** — hapus 15 skrip test legacy di root (era scaffold) + `test_result.md` 101KB; tambah `pytest.ini` (`testpaths=backend/tests`, marker `integration`, default `-m "not integration"`); dokumentasikan cara menjalankan test di README. | kecil | `pytest` deterministik; developer tak meniru kode test fosil. |

## Prioritas SEDANG

| # | Rekomendasi | Effort |
|---|---|---|
| 9 | **Ekstrak write-path bersama** (`routes/asset_write.py`): `audit_actor()` (kini di-copy 5× di assets.py, dan `batch.py` memakai header yang bisa dispoof — inkonsistensi keamanan), `check_if_match`/`raise_conflict` (blok OCC duplikat PUT vs PATCH), `idempotent_guard`, `after_asset_write` (invalidate+audit+notify). Bukan service layer penuh. | sedang |
| 10 | **Pecah `assets.py` (2.007 baris)** — pindahkan streaming media+preview → `routes/asset_media.py`, BAST → ikut, migrasi → `routes/admin_migrations.py`. URL tidak berubah; murni pemindahan mekanis. | kecil |
| 11 | **DRY `reports.py` (2.964 baris)** — `report_context()` (fetch activity+settings+assets, kini diulang 10×), angkat `safe_price`/`fmt` ke modul, `pdf_response()`; lalu (opsional) pecah jadi package `routes/reports/{common,official,executive,satker}.py`. | sedang |
| 12 | **Pecah `AssetForm.jsx` (2.295 baris)** — (a) data statis + kartu info → `inventoryInfo.jsx` (~300 baris, zero-risk); (b) `hooks/usePhotoManager.js`; (c) `lib/buildAssetPatch.js` fungsi PURE untuk diff-patch (logika payload PATCH — termasuk kasus wipe-foto offline — jadi unit-testable). Jangan rewrite ke react-hook-form. | sedang |
| 13 | **Metadata UI per field di registry** (label/placeholder/testid) dipakai AssetForm + InventoryFieldSheet + BatchEditPanel — fase 2 dari #1. | sedang |
| 14 | **`.env.example` (backend & frontend)** + fail-fast ramah untuk `MONGO_URL` (kini `KeyError` mentah; tiru pola `JWT_SECRET`). | kecil |
| 15 | **Kurasi `requirements.txt`** — hasil `pip freeze` ~140 pin berisi paket tak terpakai (litellm, openai, stripe, boto3, pandas, grpcio…); pisahkan runtime vs dev. | sedang |
| 16 | **Hidupkan eslint frontend** — dependensi eslint 9 + plugin react-hooks sudah terpasang tapi TANPA config & skrip; aktifkan `react-hooks/exhaustive-deps` (area rawan: useOfflineSync/useOptimisticQueue). | kecil |

## Prioritas RENDAH

- Konsolidasi `BASE_URL` test ke `conftest` (42/59 file membaca env sendiri dengan default kosong).
- Ganti cek sealed inline di `imports.py` dengan `ensure_activity_not_sealed`.

## Urutan pengerjaan yang disarankan

1. **Gerbang dulu**: #6 CI + #8 pytest hygiene + #16 eslint (semuanya kecil) — supaya refactoring berikutnya punya jaring pengaman.
2. **Tutup lubang**: #2 auth router-level (ada lubang nyata sekarang).
3. **Bunuh duplikasi termahal**: #1 registry field (backend dulu, frontend menyusul), #3 TeamMemberListEditor.
4. **Amankan area bug-mahal**: #5 photo_store, #4 useAssetListData, #12 buildAssetPatch — masing-masing dengan unit test dari #7.
5. Sisanya (#9–#11, #13–#15) menyusul secara mekanis per-PR kecil.

Prinsip: setiap langkah dimigrasi **bertahap dan diverifikasi identik** (assert
set-equality list lama vs turunan registry sebelum list lama dihapus; test suite
integrasi yang ada sebagai jaring pengaman untuk pemindahan modul).
