"""Harness load/stress AMAN — Locust.

Mensimulasikan pola pemakaian nyata satker: login → menelusuri daftar/statistik
aset (baca berat) → sesekali menambah aset (tulis) → sesekali laporan/ekspor
(mahal). Dipakai untuk mengukur throughput maksimum & titik jenuh sebelum
menaikkan batas rate-limit atau menambah worker.

Prasyarat:
  pip install locust

Menjalankan (contoh 200 pengguna, ramp 20/dtk, 5 menit, headless):
  locust -f scripts/loadtest/locustfile.py \\
      --host https://staging.example.go.id \\
      --headless -u 200 -r 20 -t 5m --csv hasil_loadtest

Atau UI web:
  locust -f scripts/loadtest/locustfile.py --host https://staging.example.go.id

Konfigurasi via environment (semua opsional kecuali kredensial):
  AMAN_USERNAME / AMAN_PASSWORD  kredensial login (default admin/admin123 — DEV)
  AMAN_ACTIVITY_ID               id kegiatan utk uji-tulis (POST /assets).
                                 Bila kosong → tugas tulis DINONAKTIFKAN (baca saja).
  AMAN_DATASET_FILE              berkas NDJSON body aset (dari generator sintetis).
                                 Bila kosong → body minimal dibangun inline.
  AMAN_ENABLE_HEAVY             "1" → aktifkan tugas mahal (laporan/ekspor).
  AMAN_THINK_MIN / AMAN_THINK_MAX  jeda "berpikir" pengguna dtk (default 1..5).

⚠️  HANYA jalankan terhadap lingkungan UJI/STAGING, jangan produksi.
"""
import json
import os
import random
import uuid

from locust import HttpUser, between, task
from locust.exception import StopUser

# ── Konfigurasi dari environment ──
USERNAME = os.environ.get("AMAN_USERNAME", "admin")
PASSWORD = os.environ.get("AMAN_PASSWORD", "admin123")
ACTIVITY_ID = os.environ.get("AMAN_ACTIVITY_ID", "").strip()
DATASET_FILE = os.environ.get("AMAN_DATASET_FILE", "").strip()
ENABLE_HEAVY = os.environ.get("AMAN_ENABLE_HEAVY", "0") == "1"
THINK_MIN = float(os.environ.get("AMAN_THINK_MIN", "1"))
THINK_MAX = float(os.environ.get("AMAN_THINK_MAX", "5"))


def _muat_dataset():
    """Muat body aset dari NDJSON hasil generator sintetis (bila ada)."""
    if not DATASET_FILE or not os.path.exists(DATASET_FILE):
        return []
    baris = []
    with open(DATASET_FILE, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                try:
                    baris.append(json.loads(ln))
                except json.JSONDecodeError:
                    pass
    return baris


_DATASET = _muat_dataset()


def _body_aset_minimal():
    """Body aset ringkas bila tak ada dataset — cukup untuk uji-tulis."""
    n = random.randint(1, 10**9)
    return {
        "asset_code": f"LOAD.{n % 100000:05d}",
        "NUP": str(n % 9999 + 1),
        "asset_name": "Aset Uji Beban",
        "category": "Peralatan dan Mesin",
        "condition": "Baik",
        "status": "Aktif",
        "inventory_status": "Belum Diinventarisasi",
    }


class SatkerUser(HttpUser):
    """Satu pengguna satker yang berperilaku realistis."""

    wait_time = between(THINK_MIN, THINK_MAX)

    def on_start(self):
        self.token = None
        self.headers = {}
        resp = self.client.post(
            "/api/auth/login",
            json={"username": USERNAME, "password": PASSWORD},
            name="POST /auth/login",
        )
        if resp.status_code == 200:
            try:
                self.token = resp.json().get("access_token")
            except Exception:
                self.token = None
        if self.token:
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            # Tanpa token, hentikan pengguna ini agar hasil tak bias 401 —
            # kegagalan login sudah tercatat di statistik "POST /auth/login".
            raise StopUser()

    # ── Baca (mayoritas trafik) ──
    @task(10)
    def telusuri_daftar(self):
        self.client.get("/api/assets?limit=50&skip=0", headers=self.headers,
                        name="GET /assets (list)")

    @task(4)
    def statistik(self):
        self.client.get("/api/assets/stats", headers=self.headers,
                        name="GET /assets/stats")

    @task(3)
    def analitik(self):
        self.client.get("/api/assets/analytics", headers=self.headers,
                        name="GET /assets/analytics")

    @task(2)
    def snapshot_offline(self):
        self.client.get("/api/assets/offline-snapshot?limit=200",
                        headers=self.headers, name="GET /assets/offline-snapshot")

    # ── Tulis (jarang; hanya bila ACTIVITY_ID diset) ──
    @task(1)
    def tambah_aset(self):
        if not ACTIVITY_ID:
            return  # uji-tulis dinonaktifkan
        body = dict(random.choice(_DATASET)) if _DATASET else _body_aset_minimal()
        body["activity_id"] = ACTIVITY_ID
        # Kode unik agar tak bentrok keunikan (kecuali sengaja menguji 400).
        body["asset_code"] = f"{body.get('asset_code', 'LOAD')}-{uuid.uuid4().hex[:6]}"
        headers = dict(self.headers)
        headers["Idempotency-Key"] = uuid.uuid4().hex
        self.client.post("/api/assets", json=body, headers=headers,
                        name="POST /assets (create)")

    # ── Mahal (opsional; laporan/ekspor) ──
    @task(1)
    def laporan_mahal(self):
        if not ENABLE_HEAVY:
            return
        self.client.get("/api/assets/analytics?heavy=1", headers=self.headers,
                        name="GET /assets/analytics (heavy)")
