"""Pembacaan unggahan berbatas sebelum parsing, job, atau layanan eksternal."""
from fastapi import HTTPException, UploadFile


async def baca_unggahan_terbatas(file: UploadFile, maks: int, pesan: str) -> bytes:
    """Baca paling banyak batas + 1 byte; jangan percaya metadata ukuran.

    UploadFile sudah melewati parser multipart. Batas ini menjaga pembacaan
    aplikasi sesudahnya, bukan menggantikan batas request di reverse proxy.
    """
    isi = bytearray()
    while True:
        bagian = await file.read(min(1024 * 1024, maks + 1 - len(isi)))
        if not bagian:
            return bytes(isi)
        isi.extend(bagian)
        if len(isi) > maks:
            raise HTTPException(status_code=400, detail=pesan)
