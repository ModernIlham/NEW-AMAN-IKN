"""Master Pegawai — data kepegawaian menyeluruh satker (adopsi SIMAN-G).

BERBEDA dari Referensi Pejabat (khusus pejabat penatausahaan/penanda tangan):
master ini menampung SELURUH pegawai + unit kerjanya, sebagai rujukan lintas
modul. Semua user login dapat melihat; admin mengelola (CRUD). NIP unik bila
diisi. Pola sama dengan referensi pejabat/ruangan.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from shared_utils import kode_satker_user, log_audit, scope_query_field_satker
from pejabat_utils import STATUS_KEPEGAWAIAN
from pegawai_utils import (
    AGAMA, DIGIT_BANK, JENIS_IDENTITAS_WNA, JENIS_JABATAN, JENIS_KELAMIN,
    KATEGORI_PEGAWAI, KEWARGANEGARAAN, PANGKAT_GOLONGAN, STATUS_PEGAWAI,
    STATUS_PERKAWINAN, SUB_KATEGORI_NON_ASN, baris_impor_ke_pegawai,
    kelompok_unit_kerja, pegawai_perlu_serah_terima, rekap_eselon,
    validate_pegawai,
)

pegawai_router = APIRouter()

_PROJ = {"_id": 0}


class PegawaiIn(BaseModel):
    nama: str
    nip: Optional[str] = ""
    gelar_depan: Optional[str] = ""
    gelar_belakang: Optional[str] = ""
    kewarganegaraan: Optional[str] = ""
    jenis_identitas_wna: Optional[str] = ""
    nomor_identitas_wna: Optional[str] = ""
    jenis_kelamin: Optional[str] = ""
    tempat_lahir: Optional[str] = ""
    tanggal_lahir: Optional[str] = ""
    agama: Optional[str] = ""
    status_perkawinan: Optional[str] = ""
    status_kepegawaian: Optional[str] = ""
    sub_kategori_non_asn: Optional[str] = ""
    pangkat_golongan: Optional[str] = ""
    jabatan: Optional[str] = ""
    jenis_jabatan: Optional[str] = ""
    kategori_pegawai: Optional[str] = ""
    eselon: Optional[str] = ""
    eselon1: Optional[str] = ""
    eselon2: Optional[str] = ""
    eselon3: Optional[str] = ""
    eselon4: Optional[str] = ""
    eselon5: Optional[str] = ""
    unit_kerja: Optional[str] = ""
    unit_organisasi: Optional[str] = ""
    npwp: Optional[str] = ""
    pendidikan_terakhir: Optional[str] = ""
    no_hp: Optional[str] = ""
    email: Optional[str] = ""
    alamat: Optional[str] = ""
    nama_bank: Optional[str] = ""
    no_rekening: Optional[str] = ""
    nomor_kontrak: Optional[str] = ""
    tgl_mulai_kontrak: Optional[str] = ""
    tgl_selesai_kontrak: Optional[str] = ""
    tmt_jabatan: Optional[str] = ""
    status: Optional[str] = "aktif"
    keterangan: Optional[str] = ""


def _bersih(p: PegawaiIn) -> dict:
    doc = {
        "nama": str(p.nama or "").strip(),
        "nip": str(p.nip or "").strip(),
        "gelar_depan": str(p.gelar_depan or "").strip(),
        "gelar_belakang": str(p.gelar_belakang or "").strip(),
        "kewarganegaraan": str(p.kewarganegaraan or "").strip().lower(),
        "jenis_identitas_wna": str(p.jenis_identitas_wna or "").strip().lower(),
        "nomor_identitas_wna": str(p.nomor_identitas_wna or "").strip(),
        "jenis_kelamin": str(p.jenis_kelamin or "").strip().upper(),
        "tempat_lahir": str(p.tempat_lahir or "").strip(),
        "tanggal_lahir": str(p.tanggal_lahir or "").strip()[:10],
        "agama": str(p.agama or "").strip(),
        "status_perkawinan": str(p.status_perkawinan or "").strip(),
        "status_kepegawaian": str(p.status_kepegawaian or "").strip(),
        "sub_kategori_non_asn": str(p.sub_kategori_non_asn or "").strip(),
        "pangkat_golongan": str(p.pangkat_golongan or "").strip(),
        "jabatan": str(p.jabatan or "").strip(),
        "jenis_jabatan": str(p.jenis_jabatan or "").strip(),
        "kategori_pegawai": str(p.kategori_pegawai or "").strip(),
        "eselon": str(p.eselon or "").strip(),
        "eselon1": str(p.eselon1 or "").strip(),
        "eselon2": str(p.eselon2 or "").strip(),
        "eselon3": str(p.eselon3 or "").strip(),
        "eselon4": str(p.eselon4 or "").strip(),
        "eselon5": str(p.eselon5 or "").strip(),
        "unit_kerja": str(p.unit_kerja or "").strip(),
        "unit_organisasi": str(p.unit_organisasi or "").strip(),
        "npwp": str(p.npwp or "").strip(),
        "pendidikan_terakhir": str(p.pendidikan_terakhir or "").strip(),
        "no_hp": str(p.no_hp or "").strip(),
        "email": str(p.email or "").strip(),
        "alamat": str(p.alamat or "").strip(),
        "nama_bank": str(p.nama_bank or "").strip(),
        "no_rekening": str(p.no_rekening or "").strip(),
        "nomor_kontrak": str(p.nomor_kontrak or "").strip(),
        "tgl_mulai_kontrak": str(p.tgl_mulai_kontrak or "").strip()[:10],
        "tgl_selesai_kontrak": str(p.tgl_selesai_kontrak or "").strip()[:10],
        "tmt_jabatan": str(p.tmt_jabatan or "").strip()[:10],
        "status": str(p.status or "aktif").strip() or "aktif",
        "keterangan": str(p.keterangan or "").strip(),
    }
    # Unit kerja efektif = Eselon terdalam bila field unit_kerja kosong (agar
    # rekap & tampilan tetap punya satu label unit meski data berjenjang).
    if not doc["unit_kerja"]:
        from pegawai_utils import unit_kerja_terdalam
        doc["unit_kerja"] = unit_kerja_terdalam(doc)
    return doc


async def _nip_bentrok(nip: str, kecuali_id: str = "", kode: str = "") -> bool:
    """True bila NIP sudah dipakai pegawai LAIN di satker sama (NIP kosong tak
    pernah bentrok). Dibatasi satker agar admin satker A tak terganggu data
    satker B yang tak terlihat olehnya."""
    if not nip:
        return False
    q = {"nip": nip}
    if kode:
        q["kode_satker"] = {"$in": [kode, "", None]}
    if kecuali_id:
        q["id"] = {"$ne": kecuali_id}
    return await db.pegawai.find_one(q, _PROJ) is not None


@pegawai_router.get("/pegawai/referensi")
async def referensi_pegawai(_user: dict = Depends(require_user)):
    """Referensi pilihan (untuk dropdown UI)."""
    def _opt(d):
        return [{"kode": k, "uraian": v} for k, v in d.items()]
    return {
        "jenis_kelamin": _opt(JENIS_KELAMIN),
        "status_kepegawaian": _opt(STATUS_KEPEGAWAIAN),
        "jenis_jabatan": _opt(JENIS_JABATAN),
        "kategori_pegawai": _opt(KATEGORI_PEGAWAI),
        "sub_kategori_non_asn": _opt(SUB_KATEGORI_NON_ASN),
        "agama": _opt(AGAMA),
        "status_perkawinan": _opt(STATUS_PERKAWINAN),
        "status": _opt(STATUS_PEGAWAI),
        "kewarganegaraan": _opt(KEWARGANEGARAAN),
        "jenis_identitas_wna": _opt(JENIS_IDENTITAS_WNA),
        # saran pangkat MENGIKUTI status kepegawaian + peta digit bank utk
        # peringatan lunak rekening (pola form KERJA-BARENG).
        "pangkat_golongan": PANGKAT_GOLONGAN,
        "digit_bank": DIGIT_BANK,
    }


@pegawai_router.get("/pegawai/rekap-unit")
async def rekap_unit_pegawai(_user: dict = Depends(require_user)):
    """Rekap jumlah pegawai per unit kerja & per Eselon I (untuk ringkasan)."""
    semua = await db.pegawai.find(
        scope_query_field_satker(_user), _PROJ).to_list(20000)
    kelompok = kelompok_unit_kerja(semua)
    return {
        "unit": [{"unit_kerja": g["unit_kerja"], "jumlah": g["jumlah"]} for g in kelompok],
        "eselon1": rekap_eselon(semua, "eselon1"),
        "jumlah_pegawai": len(semua),
        "jumlah_unit": len(kelompok),
    }


@pegawai_router.get("/pegawai")
async def list_pegawai(_user: dict = Depends(require_user)):
    """Daftar seluruh pegawai satker (terurut nama)."""
    items = await db.pegawai.find(
        scope_query_field_satker(_user), _PROJ).sort("nama", 1).to_list(20000)
    return {"items": items, "jumlah": len(items)}


async def _jumlah_aset_per_nip(user) -> dict:
    """Peta NIP → jumlah aset yang dipegang (aset ter-scope satker user)."""
    from shared_utils import scope_query_aset
    q = await scope_query_aset(user, {
        "dihapus": {"$ne": True},
        "pengguna_nip": {"$nin": ["", None]},
    })
    peta = {}
    async for g in db.assets.aggregate([
            {"$match": q},
            {"$group": {"_id": "$pengguna_nip", "n": {"$sum": 1}}}]):
        nip = str(g["_id"] or "").strip()
        if nip:
            peta[nip] = g["n"]
    return peta


@pegawai_router.get("/pegawai/perlu-serah-terima")
async def daftar_perlu_serah_terima(_user: dict = Depends(require_user)):
    """Pegawai BERISIKO yang masih memegang aset — status keluar/mutasi/
    pensiun/nonaktif/diperbantukan atau kontrak Non-ASN habis/segera habis
    (pola alert "pemegang keluar"): bahan tindak lanjut serah terima BMN via
    modul Penggunaan (BAST pengembalian / mutasi pemegang)."""
    pegawai = await db.pegawai.find(
        scope_query_field_satker(_user),
        {"_id": 0, "id": 1, "nama": 1, "nip": 1, "status": 1,
         "unit_kerja": 1, "tgl_selesai_kontrak": 1}).to_list(20000)
    peta_aset = await _jumlah_aset_per_nip(_user)
    hari_ini = datetime.now(timezone.utc).date().isoformat()
    items = pegawai_perlu_serah_terima(pegawai, peta_aset, hari_ini)
    # lengkapi unit kerja utk tampilan
    unit = {p.get("id"): p.get("unit_kerja") for p in pegawai}
    for it in items:
        it["unit_kerja"] = unit.get(it["id"], "")
    return {"items": items, "jumlah": len(items)}


@pegawai_router.get("/pegawai/{pegawai_id}/aset")
async def aset_dipegang_pegawai(pegawai_id: str,
                                _user: dict = Depends(require_user)):
    """Daftar aset yang tercatat dipegang seorang pegawai (via NIP)."""
    from shared_utils import pastikan_akses_dok_satker, scope_query_aset
    peg = await db.pegawai.find_one({"id": pegawai_id}, _PROJ)
    if not peg:
        raise HTTPException(status_code=404, detail="Pegawai tidak ditemukan")
    await pastikan_akses_dok_satker(_user, peg)
    nip = str(peg.get("nip") or "").strip()
    if not nip:
        return {"pegawai": {"id": pegawai_id, "nama": peg.get("nama"),
                            "nip": ""}, "items": [], "jumlah": 0}
    q = await scope_query_aset(_user, {
        "pengguna_nip": nip, "dihapus": {"$ne": True}})
    items = await db.assets.find(q, {
        "_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
        "condition": 1, "location": 1, "activity_id": 1, "bast_file_id": 1,
    }).sort("asset_code", 1).to_list(2000)
    return {"pegawai": {"id": pegawai_id, "nama": peg.get("nama"),
                        "nip": nip},
            "items": items, "jumlah": len(items)}


@pegawai_router.post("/pegawai")
async def buat_pegawai(payload: PegawaiIn, user: dict = Depends(require_admin)):
    """Tambah pegawai (admin)."""
    doc = _bersih(payload)
    errors = validate_pegawai(doc)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    kode = kode_satker_user(user)
    if await _nip_bentrok(doc["nip"], kode=kode):
        raise HTTPException(status_code=400, detail=f"NIP {doc['nip']} sudah terdaftar")
    now = datetime.now(timezone.utc).isoformat()
    doc.update({"id": str(uuid.uuid4()), "kode_satker": kode,
                "created_at": now, "updated_at": now})
    await db.pegawai.insert_one(dict(doc))
    await log_audit("buat_pegawai", "", doc["id"],
                    username=user.get("username", "system"),
                    detail=f"Tambah pegawai {doc['nama']}")
    return {"ok": True, "id": doc["id"]}


@pegawai_router.get("/pegawai/template-impor")
async def template_impor_pegawai(_user: dict = Depends(require_user)):
    """Template CSV impor massal pegawai (header lengkap + 1 baris contoh)."""
    import csv as _csv
    import io

    from pegawai_utils import HEADER_IMPOR
    buf = io.StringIO()
    w = _csv.writer(buf)
    w.writerow(HEADER_IMPOR)
    w.writerow(["198501012010011001", "Budi Santoso", "Laki-laki", "Jakarta",
                "1985-01-01", "PNS", "Penata (III/c)",
                "Analis Pengelolaan BMN", "Pejabat Pelaksana",
                "Sekretariat", "Bagian Umum", "", "", "", "081200000000",
                "budi@instansi.go.id", "BRI", "1234567890", "", "", "",
                "AKTIF", ""])
    return Response(
        content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="template_impor_pegawai.csv"'})


@pegawai_router.post("/pegawai/impor")
async def impor_pegawai(file: UploadFile = File(...),
                        user: dict = Depends(require_admin)):
    """Impor massal pegawai dari Excel (.xlsx) / CSV. Tiap baris dinormalkan
    (status kepegawaian & status keberadaan yang beragam dipetakan, NIP
    dibersihkan dari artefak, unit kerja diambil dari Eselon terdalam). Upsert
    per NIP dalam satker; baris tanpa NIP disisipkan baru. Data lapangan yang
    tak baku hanya diberi catatan (best-effort), tidak menggagalkan seluruh
    impor."""
    nama = str(file.filename or "").lower()
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Berkas maksimal 15MB")

    rows = []
    if nama.endswith((".xlsx", ".xlsm")):
        import io

        from openpyxl import load_workbook
        try:
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception:
            raise HTTPException(status_code=400,
                                detail="Berkas Excel tidak dapat dibaca")
        ws = wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        try:
            header = [str(h or "").strip() for h in next(it)]
        except StopIteration:
            header = []
        for r in it:
            rows.append({header[i]: r[i]
                         for i in range(min(len(header), len(r)))})
    elif nama.endswith(".csv"):
        import csv as _csv
        import io
        reader = _csv.DictReader(io.StringIO(data.decode("utf-8-sig",
                                                         errors="replace")))
        rows = list(reader)
    else:
        raise HTTPException(status_code=400,
                            detail="Format harus .xlsx atau .csv")

    kode = kode_satker_user(user)
    now = datetime.now(timezone.utc).isoformat()
    dilewati = 0
    catatan = []
    seen_nip = set()
    from pymongo import InsertOne, UpdateOne
    ops = []
    for idx, raw in enumerate(rows, start=2):
        doc, _peringatan = baris_impor_ke_pegawai(raw)
        if not doc["nama"]:
            dilewati += 1
            continue
        # Validasi lunak: abaikan keluhan NIP (data lapangan sering non-baku).
        errors = [e for e in validate_pegawai(doc) if "NIP" not in e]
        if errors:
            dilewati += 1
            if len(catatan) < 200:
                catatan.append(f"Baris {idx} ({doc['nama']}): {'; '.join(errors)}")
            continue
        doc["kode_satker"] = kode
        doc["updated_at"] = now
        nip = doc["nip"]
        if nip and nip not in seen_nip:
            seen_nip.add(nip)
            ops.append(UpdateOne(
                {"nip": nip, "kode_satker": {"$in": [kode, "", None]}},
                {"$set": doc,
                 "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
                upsert=True))
        else:
            doc["id"] = str(uuid.uuid4())
            doc["created_at"] = now
            ops.append(InsertOne(dict(doc)))

    dibuat = diperbarui = 0
    if ops:
        res = await db.pegawai.bulk_write(ops, ordered=False)
        dibuat = (res.upserted_count or 0) + (res.inserted_count or 0)
        diperbarui = res.modified_count or 0
    await log_audit("impor_pegawai", "", "impor",
                    username=user.get("username", "system"),
                    detail=(f"Impor pegawai: {dibuat} baru, {diperbarui} "
                            f"diperbarui, {dilewati} dilewati"))
    return {"ok": True, "dibaca": len(rows), "dibuat": dibuat,
            "diperbarui": diperbarui, "dilewati": dilewati,
            "catatan": catatan}


@pegawai_router.put("/pegawai/{pegawai_id}")
async def ubah_pegawai(pegawai_id: str, payload: PegawaiIn,
                       user: dict = Depends(require_admin)):
    """Ubah pegawai (admin)."""
    doc = _bersih(payload)
    errors = validate_pegawai(doc)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    if await _nip_bentrok(doc["nip"], kecuali_id=pegawai_id,
                          kode=kode_satker_user(user)):
        raise HTTPException(status_code=400, detail=f"NIP {doc['nip']} sudah terdaftar")
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.pegawai.update_one({"id": pegawai_id}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Pegawai tidak ditemukan")
    await log_audit("ubah_pegawai", "", pegawai_id,
                    username=user.get("username", "system"),
                    detail=f"Ubah pegawai {doc['nama']}")
    # Peringatan lunak: status berubah ke non-aktif padahal masih memegang
    # aset → dorong proses serah terima (tidak memblokir penyimpanan).
    peringatan = ""
    if doc["status"] not in ("aktif", "cuti", "tugas_belajar") and doc["nip"]:
        dipegang = await db.assets.count_documents(
            {"pengguna_nip": doc["nip"], "dihapus": {"$ne": True}})
        if dipegang:
            peringatan = (
                f"{doc['nama']} masih tercatat memegang {dipegang} aset — "
                "proses serah terima di modul Penggunaan (BAST pengembalian "
                "atau mutasi pemegang)")
    return {"ok": True, "id": pegawai_id, "peringatan": peringatan}


@pegawai_router.delete("/pegawai/{pegawai_id}")
async def hapus_pegawai(pegawai_id: str, user: dict = Depends(require_admin)):
    """Hapus pegawai (admin). Ditolak bila NIP-nya masih dipakai aset (temuan #34)."""
    peg = await db.pegawai.find_one({"id": pegawai_id}, {"_id": 0, "nip": 1, "nama": 1})
    if peg and str(peg.get("nip") or "").strip():
        dipakai = await db.assets.count_documents(
            {"pengguna_nip": str(peg["nip"]).strip(), "dihapus": {"$ne": True}})
        if dipakai:
            raise HTTPException(
                status_code=409,
                detail=f"Pegawai {peg.get('nama')} (NIP {peg['nip']}) masih tercatat "
                       f"sebagai pengguna pada {dipakai} aset — pindahkan aset atau "
                       f"ubah status pegawai menjadi nonaktif, jangan dihapus.")
    res = await db.pegawai.delete_one({"id": pegawai_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pegawai tidak ditemukan")
    await log_audit("hapus_pegawai", "", pegawai_id,
                    username=user.get("username", "system"),
                    detail="Hapus pegawai")
    return {"ok": True, "id": pegawai_id}
