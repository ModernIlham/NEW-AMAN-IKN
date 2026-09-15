"""Pemindahan identitas satker: stempel lintas modul, bukan isi naskah terbit."""
import logging
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException

logger = logging.getLogger(__name__)


async def ganti_kode_satker(database, lama, baru, nama):
    if not str(lama or "").strip() or not str(baru or "").strip() or lama == baru:
        raise HTTPException(400, "Migrasi memerlukan dua kode satker terisi dan berbeda; data lintas-satker tidak boleh dipindahkan massal.")
    master_awal = await database.satker.find_one({"kode_satker": lama})
    if not master_awal:
        kegiatan = await database.inventory_activities.find_one({"kode_satker": lama})
        if not kegiatan:
            raise HTTPException(404, "Satker sumber tidak ditemukan")
        await database.satker.update_one({"kode_satker": lama}, {"$setOnInsert": {
            "id": str(uuid.uuid4()), "kode_satker": lama,
            "nama_satker": kegiatan.get("nama_satker", ""), "aktif": True,
            "alamat": kegiatan.get("alamat_satker", ""),
        }}, upsert=True)
        master_awal = await database.satker.find_one({"kode_satker": lama})
    # Kode tujuan harus baru. Menggabungkan dua satker lewat edit kegiatan
    # bukan rename dan berisiko benturan akun, nomor, serta indeks per-satker.
    koleksi = [n for n in await database.list_collection_names()
               if not n.startswith("system.") and "." not in n]
    for n in koleksi:
        if await database[n].find_one({"kode_satker": baru}, {"_id": 1}):
            raise HTTPException(409, "Kode satker tujuan sudah dipakai. Penggabungan dua satker tidak dapat dilakukan lewat edit kegiatan.")

    # Kunci lintas worker pada master sumber mencegah dua migrasi kode
    # bersamaan memecah data satker. Kunci tidak kedaluwarsa otomatis:
    # proses yang mati paksa memerlukan pemeriksaan, bukan migrasi kedua.
    token = str(uuid.uuid4())
    if master_awal:
        kunci = await database.satker.update_one(
            {"_id": master_awal["_id"], "kode_satker": lama, "migrasi_kode": {"$exists": False}},
            {"$set": {"migrasi_kode": {"token": token, "tujuan": baru, "pada": datetime.now(timezone.utc).isoformat()}}})
        if not kunci.matched_count:
            raise HTTPException(409, "Satker sedang dipindahkan atau menunggu pemeriksaan migrasi sebelumnya. Jangan jalankan perubahan kode lain.")

    # Semua koleksi ber-stempel ikut: termasuk e-sign, denah, pejabat,
    # ruangan, persuratan dan setelan yang tidak ada di daftar statis lama.
    # Master dipindah TERAKHIR supaya kegagalan parsial dapat diketahui
    # dari kode lama. Tidak mengubah nomor/naskah/PDF/blob yang telah terbit.
    # Deret tersimpan juga harus lanjut: jangan hanya seed dari dokumen yang
    # masih ada, karena nomor yang dibatalkan/dihapus tetap pernah dipakai.
    async def salin_counter():
        async for c in database.counters.find({}):
            cid = c.get("_id")
            if not isinstance(cid, str):
                continue
            bagian = cid.split(":")
            if (len(bagian) < 2 or bagian[1] != lama
                    or not cid.startswith(("surat_", "inventory_activity_ticket_", "ba_perbaikan_seq:"))):
                continue
            bagian[1] = baru
            tujuan = ":".join(bagian)
            isi = {k: v for k, v in c.items() if k not in ("_id", "seq")}
            await database.counters.update_one(
                {"_id": tujuan}, {"$max": {"seq": c.get("seq", 0)}, "$setOnInsert": isi}, upsert=True)
    rincian, pemulihan = {}, []
    boleh_lepas_kunci = True
    try:
        await salin_counter()
        for n in koleksi:
            if n == "satker":
                continue
            ubah_nama = n in ("inventory_activities", "inventory_history")
            proyeksi = {"_id": 1, **({"nama_satker": 1} if ubah_nama else {})}
            docs = await database[n].find({"kode_satker": lama}, proyeksi).to_list(None)
            if not docs:
                continue
            # Catat SEBELUM update: kegagalan update_many dapat parsial.
            pemulihan.append((n, docs, ubah_nama))
            perubahan = {"kode_satker": baru, **({"nama_satker": nama} if ubah_nama else {})}
            hasil = await database[n].update_many(
                {"kode_satker": lama, "_id": {"$in": [d["_id"] for d in docs]}}, {"$set": perubahan})
            if hasil.matched_count != len(docs):
                raise RuntimeError("Dokumen berubah saat pemindahan")
            rincian[n] = hasil.modified_count
        # Jangan laporkan sukses bila penulis lain menambah stempel lama
        # selama migrasi. Operator bisa mencoba lagi setelah aktivitas reda.
        for n in koleksi:
            if n != "satker" and await database[n].find_one({"kode_satker": lama}, {"_id": 1}):
                raise RuntimeError("Data satker berubah selama migrasi")
        await database.satker.update_one(
            {"kode_satker": lama}, {"$set": {"kode_satker": baru, "nama_satker": nama}})
    except Exception as err:
        # Kompensasi hanya dokumen yang dipindahkan run ini. Jangan mengubah
        # dokumen milik tujuan yang mungkin ditulis pihak lain bersamaan.
        gagal_pulih = False
        if master_awal:
            try:
                await database.satker.update_one(
                    {"_id": master_awal["_id"], "kode_satker": baru},
                    {"$set": {"kode_satker": lama, "nama_satker": master_awal.get("nama_satker", "")}})
            except Exception:
                gagal_pulih = True
        for n, docs, ubah_nama in reversed(pemulihan):
            for d in docs:
                perubahan = {"$set": {"kode_satker": lama}}
                if ubah_nama:
                    if "nama_satker" in d:
                        perubahan["$set"]["nama_satker"] = d["nama_satker"]
                    else:
                        perubahan["$unset"] = {"nama_satker": ""}
                try:
                    await database[n].update_one({"_id": d["_id"], "kode_satker": baru}, perubahan)
                except Exception:
                    gagal_pulih = True
        logger.error("Migrasi kode satker gagal; pemulihan=%s", "perlu pemeriksaan" if gagal_pulih else "selesai")
        boleh_lepas_kunci = not gagal_pulih
        raise HTTPException(503, "Perubahan kode satker belum selesai. " + (
            "Pemulihan gagal; hentikan perubahan dan minta administrator memeriksa data."
            if gagal_pulih else "Data dikembalikan; coba kembali setelah tidak ada penyuntingan bersamaan.")) from err
    finally:
        if master_awal and boleh_lepas_kunci:
            await database.satker.update_one(
                {"_id": master_awal["_id"], "migrasi_kode.token": token},
                {"$unset": {"migrasi_kode": ""}})
    return rincian
