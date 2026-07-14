"""Koersi id GridFS — logika murni (tanpa Mongo/IO) agar teruji unit.

Byte foto/dokumen disimpan di GridFS dan dirujuk oleh id yang DISIMPAN sebagai
STRING (mis. `str(ObjectId())`). Semua jalur unduh harus mengubahnya jadi
`ObjectId` HANYA bila valid; kalau tidak, pakai apa adanya. `ObjectId(x)`
MELEMPAR untuk string non-24-hex — bila jalur unduh memanggilnya tanpa penjaga,
id tak-valid → exception → None diam-diam → regen cover `photo_ops` gagal →
thumbnail di mode daftar jadi BASI (bug "cover tak berubah setelah hapus+ganti").
"""


def coerce_gridfs_id(gridfs_id):
    """Kembalikan `ObjectId(gridfs_id)` bila `gridfs_id` valid ObjectId, kalau
    tidak kembalikan `gridfs_id` apa adanya. Fungsi murni."""
    from bson import ObjectId
    return ObjectId(gridfs_id) if ObjectId.is_valid(str(gridfs_id)) else gridfs_id
