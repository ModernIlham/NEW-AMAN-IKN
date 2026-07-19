"""Timeline Aset — riwayat perlakuan SATU aset fisik lintas modul.

Jawaban arsitektural mandat W5: data induk BUKAN dokumen aset per kegiatan
inventarisasi (aset yang sama tercatat ulang di tiap kegiatan), melainkan
IDENTITAS aset (kode_register → fallback kode barang + NUP) beserta seluruh
perlakuan yang pernah terjadi padanya di semua modul. Endpoint ini
mengagregasi: pencatatan & pengesahan inventarisasi (lintas kegiatan),
Buku Barang (mutasi_bmn), SK PSP/idle/proses Penggunaan, Pemanfaatan,
Pemeliharaan, Pengamanan, Penilaian, Penghapusan, Pemindahtanganan,
Pemusnahan, Penertiban Wasdal, BAST, reklasifikasi, audit log, serta data
referensi SIMAN V2 (PSP resmi dll.) yang selama ini tersimpan tapi belum
dimanfaatkan modul lain.
"""
from fastapi import APIRouter, Depends, HTTPException

from auth_utils import require_user
from db import db
from shared_utils import (kode_satker_user, pastikan_akses_aset,
                          scope_query_aset)
from timeline_utils import (MODUL_LABEL, buat_event, event_dari_riwayat,
                            event_psp_siman, identitas_aset, info_psp_siman,
                            label_transaksi_buku, query_identitas,
                            ringkas_per_modul, ringkas_perubahan_audit,
                            urut_events)

timeline_router = APIRouter()

_PROJ_SAUDARA = {"_id": 0, "id": 1, "activity_id": 1, "asset_code": 1,
                 "NUP": 1, "kode_register": 1, "asset_name": 1,
                 "inventory_status": 1, "condition": 1, "status": 1,
                 "location": 1, "user": 1, "created_at": 1, "updated_at": 1,
                 "dihapus": 1}


def _fmt_rp(v) -> str:
    try:
        n = float(v or 0)
    except (TypeError, ValueError):
        return ""
    if not n:
        return ""
    return f"Rp {n:,.0f}".replace(",", ".")


def _q_satker_lunak(user, query=None) -> dict:
    """Filter kode_satker lunak (dokumen satker sendiri + era lama tanpa
    kode) untuk koleksi modul yang membawa kode_satker langsung."""
    q = dict(query or {})
    kode = kode_satker_user(user)
    if kode:
        q["kode_satker"] = {"$in": [kode, "", None]}
    return q


@timeline_router.get("/assets/{asset_id}/timeline")
async def get_timeline_aset(asset_id: str, user: dict = Depends(require_user)):
    """Timeline lengkap satu aset fisik: seluruh dokumen `assets` dengan
    identitas sama (lintas kegiatan inventarisasi) + event dari semua modul."""
    aset = await db.assets.find_one({"id": asset_id}, _PROJ_SAUDARA)
    if not aset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(user, aset)

    identitas = identitas_aset(aset)
    q_ident = query_identitas(identitas)

    # ── Saudara: semua dokumen aset dengan identitas fisik sama ──
    saudara = [aset]
    if q_ident:
        q = await scope_query_aset(user, q_ident)
        saudara = await db.assets.find(q, _PROJ_SAUDARA).sort(
            "created_at", 1).to_list(50)
        if not any(s["id"] == asset_id for s in saudara):
            saudara.append(aset)
    ids = [s["id"] for s in saudara]

    # Info kegiatan asal tiap saudara (nomor tiket, nama, status pengesahan).
    act_ids = sorted({s.get("activity_id") for s in saudara
                     if s.get("activity_id")})
    kegiatan = {a["id"]: a async for a in db.inventory_activities.find(
        {"id": {"$in": act_ids}},
        {"_id": 0, "id": 1, "ticket_number": 1, "name": 1, "status": 1,
         "status_pengesahan": 1, "tanggal_mulai": 1, "kode_satker": 1})}

    events = []

    # ── 1. Inventarisasi: pencatatan per kegiatan + pengesahan lintas kegiatan ──
    for s in saudara:
        keg = kegiatan.get(s.get("activity_id") or "", {})
        label_keg = " — ".join(x for x in (
            keg.get("ticket_number"), keg.get("name")) if x) or "kegiatan tak dikenal"
        detail = "; ".join(x for x in (
            f"Status: {s.get('inventory_status')}" if s.get("inventory_status") else "",
            f"Kondisi: {s.get('condition')}" if s.get("condition") else "",
            f"Lokasi: {s.get('location')}" if s.get("location") else "") if x)
        events.append(buat_event(
            "inventarisasi", "pencatatan",
            f"Dicatat di kegiatan {label_keg}",
            tanggal=s.get("created_at", ""), detail=detail,
            ref_id=s.get("activity_id", ""),
            status=s.get("inventory_status", "")))

    if q_ident:
        q_hist = dict(q_ident)
        # inventory_history memakai field identitas yang sama dengan assets
        kode = kode_satker_user(user)
        if kode:
            q_hist = {"$and": [q_ident, {"$or": [
                {"kode_satker": kode},
                {"kode_satker": {"$in": ["", None]}},
                {"kode_satker": {"$exists": False}}]}]}
        async for h in db.inventory_history.find(
                q_hist, {"_id": 0}).sort("tanggal_pengesahan", -1).limit(100):
            detail = "; ".join(x for x in (
                f"Kondisi: {h.get('condition')}" if h.get("condition") else "",
                f"Dokumen: {h.get('dokumen_checked')}/{h.get('dokumen_total')}"
                if h.get("dokumen_total") else "",
                f"Petugas: {h.get('petugas')}" if h.get("petugas") else "") if x)
            events.append(buat_event(
                "inventarisasi", "pengesahan",
                f"Disahkan dalam {h.get('ticket_number') or h.get('activity_name') or 'kegiatan'}",
                tanggal=h.get("tanggal_pengesahan", ""), detail=detail,
                ref_id=h.get("activity_id", ""),
                status=h.get("inventory_status", "")))

    # ── 2. Buku Barang (jurnal pembukuan) ──
    async for m in db.mutasi_bmn.find(
            {"asset_id": {"$in": ids}}, {"_id": 0}).sort(
            "tanggal_buku", -1).limit(100):
        nilai = _fmt_rp(m.get("nilai"))
        detail = "; ".join(x for x in (
            m.get("keterangan", ""), f"Nilai: {nilai}" if nilai else "",
            f"Sumber: {m.get('sumber_modul')}" if m.get("sumber_modul") else "") if x)
        events.append(buat_event(
            "pembukuan", "jurnal",
            f"Buku Barang — {label_transaksi_buku(m.get('kode_transaksi'))}",
            tanggal=m.get("tanggal_buku", ""), detail=detail,
            ref_id=m.get("id", ""), status=m.get("kode_transaksi", "")))

    # ── 3. Penggunaan: SK PSP, BMN idle, proses penggunaan ──
    async for p in db.psp.find(_q_satker_lunak(
            user, {"aset.asset_id": {"$in": ids}}), {"_id": 0}).limit(50):
        judul = (f"SK PSP {p.get('nomor_sk')}" if p.get("nomor_sk")
                 else "Usulan PSP (draf)")
        events.append(buat_event(
            "penggunaan", "psp", judul,
            tanggal=p.get("tanggal_sk") or p.get("created_at", ""),
            detail="; ".join(x for x in (
                f"Jenis: {p.get('jenis')}" if p.get("jenis") else "",
                f"Penetap: {p.get('penetap')}" if p.get("penetap") else "") if x),
            ref_id=p.get("id", ""), status=p.get("status_pengajuan", "")))
    async for d in db.bmn_idle.find(_q_satker_lunak(
            user, {"asset_id": {"$in": ids}}), {"_id": 0}).limit(50):
        events.extend(event_dari_riwayat(
            d, "penggunaan", f"BMN Idle ({d.get('alasan') or 'tanpa alasan'})",
            ref_id=d.get("id", "")))
    async for d in db.penggunaan_proses.find(_q_satker_lunak(
            user, {"aset.asset_id": {"$in": ids}}), {"_id": 0}).limit(50):
        judul = " ".join(x for x in (
            "Proses", d.get("jenis_proses"), d.get("arah")) if x)
        events.extend(event_dari_riwayat(d, "penggunaan", judul,
                                         ref_id=d.get("id", "")))

    # ── 4. Pemanfaatan ──
    async for d in db.pemanfaatan.find(_q_satker_lunak(
            user, {"asset_id": {"$in": ids}}), {"_id": 0}).limit(50):
        detail = "; ".join(x for x in (
            f"Periode {d.get('mulai')} s.d. {d.get('berakhir')}"
            if d.get("mulai") else "",
            f"Perjanjian: {d.get('nomor_perjanjian')}"
            if d.get("nomor_perjanjian") else "") if x)
        events.append(buat_event(
            "pemanfaatan", "perjanjian",
            f"Pemanfaatan {d.get('bentuk') or ''} — mitra {d.get('mitra') or '-'}",
            tanggal=d.get("mulai") or d.get("created_at", ""), detail=detail,
            ref_id=d.get("id", "")))

    # ── 5. Pemeliharaan ──
    async for d in db.pemeliharaan.find(
            {"asset_id": {"$in": ids}}, {"_id": 0}).sort(
            "tanggal", -1).limit(100):
        kondisi = ""
        if d.get("kondisi_sebelum") or d.get("kondisi_setelah"):
            kondisi = (f"Kondisi {d.get('kondisi_sebelum') or '?'} → "
                       f"{d.get('kondisi_setelah') or '?'}")
        biaya = _fmt_rp(d.get("biaya"))
        detail = "; ".join(x for x in (
            d.get("uraian", ""), kondisi,
            f"Biaya: {biaya}" if biaya else "") if x)
        events.append(buat_event(
            "pemeliharaan", "pelaksanaan",
            f"Pemeliharaan {d.get('jenis') or ''}",
            tanggal=d.get("tanggal", ""), detail=detail,
            ref_id=d.get("id", "")))

    # ── 6. Pengamanan: kasus + dokumen ──
    async for d in db.pengamanan_kasus.find(_q_satker_lunak(
            user, {"asset_id": {"$in": ids}}), {"_id": 0}).limit(50):
        events.extend(event_dari_riwayat(
            d, "pengamanan",
            f"Kasus pengamanan ({d.get('kategori') or 'umum'})",
            ref_id=d.get("id", "")))
    async for d in db.pengamanan_dokumen.find(
            {"asset_id": {"$in": ids}}, {"_id": 0}).limit(50):
        events.append(buat_event(
            "pengamanan", "dokumen",
            f"Dokumen pengamanan: {d.get('jenis') or 'dokumen'}",
            tanggal=d.get("created_at", ""),
            detail=d.get("keterangan", ""), ref_id=d.get("id", "")))

    # ── 7. Penilaian (koreksi nilai / revaluasi) ──
    async for d in db.penilaian_koreksi.find(
            {"asset_id": {"$in": ids}}, {"_id": 0}).sort(
            "tanggal_dokumen", -1).limit(50):
        detail = (f"Nilai {_fmt_rp(d.get('nilai_lama')) or '0'} → "
                  f"{_fmt_rp(d.get('nilai_baru')) or '0'}")
        events.append(buat_event(
            "penilaian", "koreksi_nilai",
            f"Koreksi nilai — {d.get('jenis_dokumen') or ''} "
            f"{d.get('nomor_dokumen') or ''}".strip(),
            tanggal=d.get("tanggal_dokumen", ""), detail=detail,
            ref_id=d.get("id", ""), status=d.get("status_sakti", "")))

    # ── 8. Penghapusan / Pemindahtanganan / Pemusnahan ──
    async for d in db.usulan_penghapusan.find(_q_satker_lunak(
            user, {"asset_id": {"$in": ids}}), {"_id": 0}).limit(50):
        events.extend(event_dari_riwayat(
            d, "penghapusan",
            f"Usulan penghapusan ({d.get('jalur') or 'umum'})",
            ref_id=d.get("id", "")))
        if d.get("nomor_sk"):
            events.append(buat_event(
                "penghapusan", "sk_terbit",
                f"SK Penghapusan terbit — {d.get('nomor_sk')}",
                tanggal=d.get("tanggal_sk", ""), ref_id=d.get("id", ""),
                status=d.get("status", "")))
    async for d in db.pemindahtanganan.find(_q_satker_lunak(
            user, {"aset.asset_id": {"$in": ids}}), {"_id": 0}).limit(50):
        events.extend(event_dari_riwayat(
            d, "pemindahtanganan",
            f"Pemindahtanganan {d.get('bentuk') or ''} — {d.get('pihak') or '-'}",
            ref_id=d.get("id", "")))
    async for d in db.pemusnahan.find(_q_satker_lunak(
            user, {"aset.asset_id": {"$in": ids}}), {"_id": 0}).limit(50):
        events.append(buat_event(
            "pemusnahan", "berita_acara",
            f"BA Pemusnahan {d.get('nomor_ba') or ''} ({d.get('cara') or '-'})",
            tanggal=d.get("tanggal_ba", ""),
            detail=d.get("keterangan", ""), ref_id=d.get("id", "")))

    # ── 9. Wasdal (penertiban) ──
    async for d in db.penertiban.find(_q_satker_lunak(
            user, {"asset_id": {"$in": ids}}), {"_id": 0}).limit(50):
        detail = "; ".join(x for x in (
            d.get("uraian", ""),
            f"Tindak lanjut: {d.get('tindak_lanjut')}"
            if d.get("tindak_lanjut") else "") if x)
        events.append(buat_event(
            "wasdal", "penertiban",
            f"Penertiban ({d.get('sumber') or 'wasdal'})",
            tanggal=d.get("tanggal_dasar") or d.get("created_at", ""),
            detail=detail, ref_id=d.get("id", ""), status=d.get("status", "")))
        if d.get("tanggal_selesai"):
            events.append(buat_event(
                "wasdal", "penertiban_selesai", "Penertiban selesai",
                tanggal=d.get("tanggal_selesai", ""),
                ref_id=d.get("id", ""), status="selesai"))

    # ── 10. BAST serah terima ──
    async for d in db.bast_serah_terima.find(
            {"asset_ids": {"$in": ids}}, {"_id": 0,
            "id": 1, "jenis": 1, "nomor": 1, "tanggal": 1,
            "pihak_kedua": 1}).sort("tanggal", -1).limit(50):
        penerima = ((d.get("pihak_kedua") or {}).get("nama") or "").strip()
        events.append(buat_event(
            "bast", "serah_terima",
            f"BAST {d.get('jenis') or ''} — {d.get('nomor') or 'tanpa nomor'}",
            tanggal=d.get("tanggal", ""),
            detail=f"Penerima: {penerima}" if penerima else "",
            ref_id=d.get("id", "")))

    # ── 11. Jejak pada dokumen aset: reklasifikasi + SIMAN V2 ──
    for s in saudara:
        for r in s.get("riwayat_reklasifikasi", []) or []:
            if not isinstance(r, dict):
                continue
            events.append(buat_event(
                "pembukuan", "reklasifikasi",
                f"Reklasifikasi {r.get('kode_lama')}/{r.get('nup_lama')} → "
                f"{r.get('kode_baru')}/{r.get('nup_baru')}",
                tanggal=r.get("tanggal", ""), detail=r.get("alasan", ""),
                ref_id=s.get("id", "")))
    # Subdoc siman perlu diambil terpisah (tak ada di proyeksi saudara).
    siman_sub = (await db.assets.find_one(
        {"id": asset_id}, {"_id": 0, "siman": 1}) or {}).get("siman") or {}
    if siman_sub.get("diperiksa_pada"):
        events.append(buat_event(
            "siman", "pembandingan",
            "Dibandingkan dengan data SIMAN V2",
            tanggal=siman_sub.get("diperiksa_pada", ""),
            detail=f"Hasil: {siman_sub.get('status')}"
            if siman_sub.get("status") else "",
            status=siman_sub.get("status", "")))
    if siman_sub.get("disinkron_pada"):
        events.append(buat_event(
            "siman", "sinkron", "Data SIMAN V2 diterapkan ke aset",
            tanggal=siman_sub.get("disinkron_pada", "")))
    events.extend(event_psp_siman(siman_sub))

    # ── 12. Audit log (pencatatan teknis) ──
    async for a in db.audit_logs.find(
            {"asset_id": {"$in": ids}}, {"_id": 0, "action": 1,
            "changes": 1, "detail": 1, "timestamp": 1, "username": 1}
            ).sort("timestamp", -1).limit(60):
        aksi = str(a.get("action") or "").strip()
        ringkas = ringkas_perubahan_audit(a.get("changes"))
        if aksi == "update" and not ringkas:
            continue  # update tanpa perubahan terlacak = derau
        detail = "; ".join(x for x in (
            ringkas, str(a.get("detail") or "").strip(),
            f"Oleh: {a.get('username')}" if a.get("username") else "") if x)
        events.append(buat_event(
            "aset", f"audit_{aksi}" if aksi else "audit",
            f"Perubahan data aset ({aksi or 'aksi'})",
            tanggal=a.get("timestamp", ""), detail=detail))

    events = urut_events(events)
    return {
        "aset": {k: aset.get(k) for k in (
            "id", "asset_code", "NUP", "kode_register", "asset_name",
            "status", "condition", "inventory_status", "location", "user",
            "activity_id", "dihapus")},
        "identitas": identitas,
        "saudara": [{
            "asset_id": s["id"],
            "activity_id": s.get("activity_id", ""),
            "kegiatan": kegiatan.get(s.get("activity_id") or "", {}),
            "inventory_status": s.get("inventory_status", ""),
            "condition": s.get("condition", ""),
            "created_at": s.get("created_at", ""),
        } for s in saudara],
        "jumlah_kegiatan": len({s.get("activity_id") for s in saudara
                                if s.get("activity_id")}),
        "psp_siman": info_psp_siman(siman_sub),
        "events": events,
        "ringkasan": ringkas_per_modul(events),
        "label_modul": MODUL_LABEL,
    }
