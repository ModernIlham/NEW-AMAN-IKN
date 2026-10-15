# OPT-17 — Template rute pada FastAPI0.143.1

Gate runtime dependency baru menemukan regresi metrik: `app.routes` dapat
berisi lazy `_IncludedRouter` tanpa `path`, sedangkan `scope.route` menunjuk
APIRoute asli sebelum prefix include diterapkan. Akibatnya request aset yang
sah tercatat `<unmatched>` dan bukan `/api/assets/{asset_id}`.

Registry sekarang menelusuri konfigurasi router asli, prefix include dan mount
secara rekursif. Selected route object identity diikat ke template statis yang
didaftarkan saat startup. Jika router dipasang pada dua prefix, path request
hanya dicocokkan sementara ke regex deklarasi tersebut; label hasil selalu
template allowlist, tanpa path konkret, query, ID tenant/aset, token, atau body.
Tidak ada penambahan label berdasarkan input request. Limit cardinality,
histogram/window dan format endpoint tetap berlaku.

Verifikasi:

- Runtime baru `/workspace/.aman/security-runtime-a`: Python3.11.17,
  FastAPI0.143.1, pytest9.0.3. Dua kontrak Mongo/Redis endpoint observability
  lulus10,98 detik; assertion `GET /api/assets/{asset_id}` tidak diubah.
- Dua belas unit lulus2,34 detik pada runtime baru, termasuk nested include,
  router yang dipakai di dua prefix, mount dengan parameter tenant, route
  converter, unknown-route identity, streaming/failure, bounded labels dan
  absennya PII. Runtime sebelumnya juga12 unit lulus2,94 detik.
- `git diff --check` bersih. Source hanya runtime_observability.py dan unit
  terkait; server/deploy/domain data tidak diubah oleh perbaikan ini.
