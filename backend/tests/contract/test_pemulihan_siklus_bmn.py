"""Regresi lintas register, penyimpanan Mongo nyata, respons HTTP dan cetak ulang."""
import asyncio
import uuid

import pytest
from fastapi import HTTPException

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


async def test_catat_penerimaan_bersamaan_hanya_sekali(contract):
    db, http, auth = contract.db, contract.http, contract.headers["a"]
    nama = "Kertas kontrak " + uuid.uuid4().hex
    master = await http.post("/api/persediaan", headers=auth, json={
        "kode_barang": "1010301001", "nama_barang": nama})
    assert master.status_code == 200
    item = master.json()
    p = await http.post("/api/pengadaan", headers=auth, json={
        "jenis": "hibah_masuk", "pihak": "Pemberi", "nomor_bast": nama, "tanggal_bast": "2025-07-10",
        "barang": [{"kode": item["kode_barang"], "uraian": nama, "psd_master_id": item["id"],
                    "jumlah": 10, "harga_satuan": 2000}]})
    assert p.status_code == 200
    pid = p.json()["id"]
    url = f"/api/pengadaan/{pid}/catat-semua"
    replies = await asyncio.gather(*(http.post(url, headers=auth, json={}) for _ in range(2)))
    assert 200 in [r.status_code for r in replies]
    assert all(r.status_code in {200, 409} for r in replies)
    assert (await http.post(url, headers=auth, json={})).status_code == 200
    assert (await db.persediaan.find_one({"id": item["id"]}))["stok"] == 10
    jurnal = await db.transaksi_persediaan.find({"perolehan_id": pid}).to_list(None)
    assert [(j["kode_sakti"], j["jumlah"]) for j in jurnal] == [("M04", 10)]


async def test_pemulihan_unit_dan_lpb(contract, monkeypatch):
    from routes import assets, persuratan
    http, auth = contract.http, contract.headers["a"]
    p = await http.post("/api/pengadaan", headers=auth, json={
        "jenis": "pembelian", "sifat": "non_kontrak", "nomor_kontrak": "SALAH", "no_spm": "SPM-UJI",
        "pihak": "Penyedia", "nomor_bast": uuid.uuid4().hex, "tanggal_bast": "2025-07-10",
        "barang": [{"kode": "3050102901", "uraian": "Perangkat", "jumlah": 3, "harga_satuan": 2000000}]})
    assert p.status_code == 200
    pid = p.json()["id"]
    url = f"/api/pengadaan/{pid}/catat-semua"
    payload = {"activity_id": "contract-activity-a", "booking_nomor": True}
    normal = assets.buat_aset_draft

    async def gagal_unit_kedua(*args, **kwargs):
        if kwargs["sumber"]["unit"] == 2:
            raise HTTPException(409, "Konflik sementara")
        return await normal(*args, **kwargs)

    with monkeypatch.context() as m:
        m.setattr(assets, "buat_aset_draft", gagal_unit_kedua)
        awal = await http.post(url, headers=auth, json=payload)
        assert awal.status_code == 200
        assert awal.json()["aset_dibuat"] == 1 and awal.json()["gagal"]
    booking = persuratan.booking_nomor_lpb

    async def gagal_setelah_booking(*args, **kwargs):
        await booking(*args, **kwargs)
        raise HTTPException(503, "Respons dari persuratan terputus")

    with monkeypatch.context() as m:
        m.setattr(persuratan, "booking_nomor_lpb", gagal_setelah_booking)
        assert (await http.post(url, headers=auth, json=payload)).status_code == 503
    akhir = await http.post(url, headers=auth, json=payload)
    assert akhir.status_code == 200
    lpb = await contract.db.lpb.find_one({"id": akhir.json()["lpb_id"]})
    assert len({b["asset_id"] for b in lpb["items"]}) == 3
    assert lpb["total_nilai"] == 6000000
    assert await contract.db.surat.count_documents({"perihal": {"$regex": p.json()["nomor_bast"]}}) == 1
    rows = await contract.db.assets.find({"perolehan_id": pid}).to_list(None)
    assert len(rows) == 3
    assert all(a["nomor_spm"] == "SPM-UJI" and not a["nomor_kontrak"] and
               a["jenis_dokumen_pengadaan"] == "Non Kontrak/Penerimaan Barang" for a in rows)
    assert await contract.db.mutasi_bmn.count_documents({"ref_id": pid, "kode_transaksi": "101"}) == 3


async def test_cetakan_lbkp_terkunci_dan_koreksi_berversi(contract):
    http, auth = contract.http, contract.headers["a"]
    tahun = 2036
    periode = await http.post("/api/pelaporan/periode", headers=auth, json={"tahun": tahun, "semester": 1})
    assert periode.status_code == 200, periode.text
    url = "/api/pelaporan/periode/" + periode.json()["id"]
    cetak = f"/api/pembukuan/lbkp-pdf?tahun={tahun}&semester=1"
    pertama = await http.post(url + "/kunci", headers=auth)
    assert pertama.status_code == 200, pertama.text
    versi = pertama.json()["arsip_lbkp"]
    asli = await http.get(cetak, headers=auth)
    assert asli.status_code == 200 and asli.content.startswith(b"%PDF")
    await contract.db.assets.insert_one({"id": uuid.uuid4().hex, "activity_id": "",
        "kode_satker": contract.users["a"]["kode_satker"], "perolehan_transfer": {"tiket_id": "uji-lbkp"},
        "purchase_date": f"{tahun}-01-04", "asset_code": "3050102902", "purchase_price": "6100000"})
    assert (await http.get(cetak, headers=auth)).content == asli.content
    assert (await http.post(url + "/buka", headers=auth, json={"alasan": "Penerimaan susulan"})).status_code == 200
    revisi = await http.post(url + "/kunci", headers=auth)
    assert revisi.status_code == 200 and revisi.json()["arsip_lbkp"] != versi
    assert (await http.get(cetak, headers=auth)).content != asli.content
    assert (await http.get(url + "/lbkp/" + versi, headers=auth)).content == asli.content
    assert (await http.get(url + "/lbkp/" + versi, headers=contract.headers["b"])).status_code == 404


async def test_lanjutkan_draf_lama_dengan_lpb_sebagian(contract):
    db, http, auth = contract.db, contract.http, contract.headers["a"]
    kode, tanggal = "3050102903", "2025-07-10"
    nomor = "BA-" + uuid.uuid4().hex
    dibuat = await http.post("/api/pengadaan", headers=auth, json={
        "jenis": "pembelian", "pihak": "Penyedia", "nomor_bast": nomor, "tanggal_bast": tanggal,
        "barang": [{"kode": kode, "uraian": "Kursi", "jumlah": 3, "harga_satuan": 2000000}]})
    assert dibuat.status_code == 200
    pid, aid = dibuat.json()["id"], uuid.uuid4().hex
    await db.assets.insert_one({
        "id": aid, "perolehan_id": pid, "activity_id": "contract-activity-a", "asset_code": kode,
        "asset_name": "Kursi", "NUP": "1", "purchase_price": "2000000",
        "notes": f"Draft otomatis dari perolehan Pengadaan (BAST {nomor}) (unit 1/3)"})
    await db.pengadaan.update_one({"id": pid}, {"$set": {
        "barang.0.asset_id": aid, "barang.0.asset_code": kode, "barang.0.NUP": "1"}})
    await db.lpb.insert_one({"id": uuid.uuid4().hex, "perolehan_id": pid, "kategori": "aset",
                             "items": [{"asset_id": aid}], "total_nilai": 2000000})
    url = f"/api/pengadaan/{pid}/catat-semua"
    result = await http.post(url, headers=auth, json={"booking_nomor": False})
    assert result.status_code == 200, result.text
    assert result.json()["aset_dibuat"] == 2
    assert await db.assets.count_documents({"perolehan_id": pid}) == 3
    baru = await db.lpb.find_one({"id": result.json()["lpb_id"]})
    assert {b["nup"] for b in baru["items"]} == {"2", "3"}
    assert baru["total_nilai"] == 4000000
    assert (await http.post(url, headers=auth, json={})).json()["lpb_id"] == ""
