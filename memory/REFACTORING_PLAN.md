# REFACTORING STATUS: Backend Modular Architecture

> **Status: COMPLETED + EXTENDED (v2.1 Juli 2025)** — Refactoring dari monolith ke 19 route modules berhasil. Ditambah modul `event_bus.py` untuk cross-worker fanout.

---

## 1. Arsitektur Saat Ini (Post-Refactoring v2.1)

### Struktur Backend Routes

```
backend/
├── server.py              # Entry point (~302 baris) - router mounting, indexes, event_bus lifecycle, health, system reset
├── db.py                  # MongoDB connection (23 baris)
├── models.py              # 16 Pydantic models + version field (218 baris)
├── auth_utils.py          # JWT helpers (46 baris)
├── shared_utils.py        # Shared utilities + idempotency helpers (312 baris)
├── event_bus.py           # NEW v2.1: Cross-worker WS fanout via capped collection (138 baris)
└── routes/                # 19 route modules (~10.500 baris total)
    ├── auth.py            # Register, Login, OTP, Heartbeat
    ├── assets.py          # CRUD aset + OCC + Idempotency + GridFS rollback (~1.098 baris)
    ├── activities.py      # CRUD kegiatan, satker, cascade delete
    ├── categories.py      # CRUD kategori, bulk import
    ├── batch.py           # Row locking atomic + batch update + groups + all-ids
    ├── exports.py         # CSV/PDF/XLSX export, doc-file serve, bulk delete
    ├── imports.py         # CSV/XLSX import, validasi
    ├── reports.py         # 13+ laporan PDF, report settings (2.410 baris)
    ├── cards.py           # KTP card PDF
    ├── backup.py          # Background backup & restore
    ├── audit.py           # Audit log query
    ├── media.py           # Kompresi gambar (4 service chain)
    ├── pdf_compress.py    # Kompresi PDF (2 service chain)
    ├── documents.py       # PPT & DOCX generator (1.053 baris)
    ├── users.py           # User management
    ├── validation.py      # Asset validation
    ├── templates.py       # CSV/XLSX template download
    ├── websocket.py       # WebSocket + event_bus integration + server heartbeat (188 baris)
    └── __init__.py
```

**Total Backend v2.1: ~10.500 baris**

### Collections MongoDB (v2.1)

| Collection | Purpose | Catatan |
|------------|---------|---------|
| `assets` | Aset utama + `version` field | OCC via $inc |
| `inventory_activities` | Kegiatan |  |
| `users` | Admin & user biasa | |
| `audit_logs` | Activity log |  |
| `row_locks` | Row-level lock (TTL) | Atomic acquire via find_one_and_update + insert_one fallback |
| `row_presence` | User presence |  |
| `otp_store` | Email OTP (TTL 11min) |  |
| `idempotency_keys` | **NEW v2.1** Cache response 5min (TTL index) | Mencegah duplikat retry |
| `ws_events` | **NEW v2.1** Capped 10MB/20k docs | Tailable cursor cross-worker fanout |
| `fs.files` + `fs.chunks` | GridFS photos | Auto-rollback on write failure |

### Router Mounting Order (server.py)

Urutan include_router penting karena FastAPI route matching:

```python
# MUST be before assets_router (specific routes before {asset_id} catch-all)
api_router.include_router(auth_router)
api_router.include_router(categories_router)
api_router.include_router(batch_router)       # lock, heartbeat, unlock, batch-update, groups, all-ids
api_router.include_router(exports_router)      # export/csv, export/pdf, export/xlsx, bulk-delete
api_router.include_router(assets_router)       # CRUD /assets, /assets/{id}
api_router.include_router(imports_router)
api_router.include_router(templates_router)
api_router.include_router(validation_router)
api_router.include_router(cards_router)
api_router.include_router(activities_router)
api_router.include_router(users_router)
api_router.include_router(reports_router)
api_router.include_router(ws_router)
api_router.include_router(backup_router)
api_router.include_router(audit_router)
api_router.include_router(media_router)
api_router.include_router(pdf_compress_router)
api_router.include_router(documents_router)
```

---

## 2. Aturan Arsitektur

1. **Setiap router hanya import dari**: `db`, `models`, `auth_utils`, `shared_utils`
2. **TIDAK BOLEH cross-import antar router** — setiap file mandiri
3. **API path TIDAK berubah** — frontend tidak perlu diubah
4. **Shared constants** (VALID_STATUSES dll) di `shared_utils.py`
5. **Path directives** menggunakan `Path(__file__)` relative — tidak ada hardcoded `/app/`

---

## 3. Dependensi Antar Module

```
server.py
  ├── db.py (MongoDB connection)
  ├── shared_utils.py (constants, cache, limiter)
  └── routes/*
        ├── db.py (direct MongoDB access)
        ├── models.py (Pydantic models)
        ├── auth_utils.py (JWT verification)
        └── shared_utils.py (cache, audit, thumbnail, constants)
```

Tidak ada dependensi circular. Setiap route module sepenuhnya mandiri.

---

## 4. Refactoring yang Masih Bisa Dilakukan (P2)

### reports.py (2.410 baris)
- Extract common PDF helpers: `safe_price()`, `fmt_rp()`, page numbering
- Separate report types ke sub-modules

### documents.py (1.053 baris)
- Pisah PPT dan DOCX ke file terpisah

### AssetForm.jsx (1.284 baris)
- Split ke: IdentitasSection, DetailSection, StatusSection, FotoSection, DokumenSection

### ActivitySelectionPage.jsx (1.150 baris)
- Split ke: ActivityCard, SatkerForm, TimSection, EselonEditor
