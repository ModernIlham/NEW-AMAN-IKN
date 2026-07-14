"""Uji koersi id GridFS (fix bug cover foto tak berubah di daftar).

`get_photo_from_gridfs` dulu memakai `ObjectId(gridfs_id)` tanpa penjaga →
id non-24-hex melempar → None diam-diam → regen cover `photo_ops` gagal →
thumbnail daftar basi. Helper toleran ini menutup akar masalahnya."""
from bson import ObjectId
from gridfs_id_utils import coerce_gridfs_id


def test_valid_objectid_dikoersi():
    hexid = "507f1f77bcf86cd799439011"
    out = coerce_gridfs_id(hexid)
    assert isinstance(out, ObjectId)
    assert out == ObjectId(hexid)


def test_objectid_instance_tetap_objectid():
    oid = ObjectId()
    out = coerce_gridfs_id(oid)
    assert isinstance(out, ObjectId)
    assert out == oid


def test_id_tak_valid_dikembalikan_apa_adanya():
    # Non-24-hex: JANGAN melempar — kembalikan apa adanya (biar driver yang
    # menilai). Ini yang mencegah return None diam-diam pada jalur unduh.
    assert coerce_gridfs_id("bukan-objectid") == "bukan-objectid"
    assert coerce_gridfs_id("") == ""
    assert coerce_gridfs_id("12345") == "12345"


def test_tak_melempar_untuk_input_aneh():
    # Kontrak utama: tak pernah melempar (dulu ObjectId(x) melempar untuk ini).
    for bad in ["", "xyz", "not hex 24", "zzzzzzzzzzzzzzzzzzzzzzzz"]:
        coerce_gridfs_id(bad)  # tidak boleh raise
