"""Urutan Mongo yang sama untuk daftar aset dan PDF Data Aset.

Tiebreaker id mencegah baris bertukar halaman saat nilai utama sama.
"""
import re
import math
from decimal import Decimal, DecimalException, localcontext

from bson.decimal128 import Decimal128
from fastapi import HTTPException

# Harga resmi tetap disimpan sebagaimana writer lama (string/angka). Reader
# memakai Decimal128, maksimum 34 digit signifikan; null/kosong/nonfinite/
# format bukan angka diperlakukan nol. Negatif tetap negatif (data historis).
_NUMBER = r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$"
PRICE_SORT_FIELD = "_aman_price_sort"
CODE_NUP_SORTS = {"code_nup_asc", "code_nup_desc"}
_INTEGER_TEXT = r"^([0-9]+)(?:\.0+)?$"


def angka_identitas(value):
    """Deret angka tanpa pembulatan; .0 dari impor Excel dan nol awal setara."""
    match = re.fullmatch(_INTEGER_TEXT, str(value if value is not None else "").strip())
    return (match[1].lstrip("0") or "0") if match else None


def ekspresi_identitas(field):
    return {"$let": {"vars": {"parsed": {"$regexFind": {
        "input": {"$trim": {"input": {"$convert": {
            "input": f"${field}", "to": "string", "onError": "", "onNull": ""}}}},
        "regex": _INTEGER_TEXT,
    }}}, "in": {"$let": {"vars": {"digits": {"$ltrim": {
        "input": {"$ifNull": [{"$arrayElemAt": ["$$parsed.captures", 0]}, ""]},
        "chars": "0",
    }}}, "in": {
        "invalid": {"$cond": [{"$eq": ["$$parsed", None]}, 1, 0]},
        "length": {"$strLenCP": "$$digits"}, "digits": "$$digits",
    }}}}}


def urutkan_kode_nup_aset(assets, sort_by):
    # Urutan bertingkat: kode, NUP numerik, ID. Yang tidak valid selalu terakhir
    # pada tiap tingkat. Jangan float/int: angka panjang harus tetap eksak.
    assets.sort(key=lambda item: str(item.get("id") or ""))
    for field in ("NUP", "asset_code"):
        parsed = {id(item): angka_identitas(item.get(field)) for item in assets}
        assets.sort(key=lambda item: (len(parsed[id(item)] or ""), parsed[id(item)] or ""),
                    reverse=sort_by == "code_nup_desc")
        assets.sort(key=lambda item: parsed[id(item)] is None)
    return assets


def harga_desimal(value):
    try:
        text = str(value if value is not None else "").strip()
        if not re.fullmatch(_NUMBER, text):
            return Decimal(0)
        number = Decimal(text)
        return Decimal128(number).to_decimal() if number.is_finite() else Decimal(0)
    except (DecimalException, ValueError, OverflowError):
        return Decimal(0)


def batas_harga(value):
    if value is None:
        return None
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError()
        return Decimal128(number)
    except (DecimalException, ValueError, OverflowError):
        raise HTTPException(400, "Batas harga harus angka hingga 34 digit signifikan")


def ekspresi_harga():
    """Check exact representability before Mongo's otherwise rounding convert."""
    def let(variables, result):
        return {"$let": {"vars": variables, "in": result}}

    def length(value):
        return {"$strLenCP": value}

    def trim(value, operator="$trim"):
        return {operator: {"input": value, "chars": "0"}}

    valid = {"$and": [
        {"$regexMatch": {"input": "$$teks", "regex": _NUMBER}},
        {"$or": [{"$eq": ["$$significant", 0]}, {"$and": [
            {"$lte": ["$$significant", 34]}, {"$gte": ["$$power", -6176]},
            {"$lte": [{"$add": ["$$power", "$$significant"]}, 6145]},
        ]}]},
    ]}
    value = {"$cond": [valid, {"$convert": {
        "input": "$$teks", "to": "decimal", "onError": 0, "onNull": 0}}, 0]}
    value = let({
        "significant": length(trim("$$digits")),
        "power": {"$subtract": [{"$add": ["$$exponent", {"$subtract": [
            length("$$digits"), length(trim("$$digits", "$rtrim"))]}]}, length("$$fraction")]},
    }, value)
    value = let({"digits": {"$concat": ["$$integer", "$$fraction"]}}, value)
    value = let({
        "integer": {"$ifNull": [{"$arrayElemAt": ["$$captures", 0]}, ""]},
        "fraction": {"$ifNull": [{"$arrayElemAt": ["$$captures", 1]}, ""]},
        "exponent": {"$convert": {"input": {"$arrayElemAt": ["$$captures", 2]},
                                    "to": "int", "onError": 1000000000, "onNull": 0}},
    }, value)
    value = let({"captures": {"$ifNull": ["$$parsed.captures", ["", "", "0"]]}}, value)
    value = let({"parsed": {"$regexFind": {"input": "$$teks", "regex":
        r"^[+-]?([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]+))?$"}}}, value)
    return let({"teks": {"$trim": {"input": {"$convert": {
        "input": "$purchase_price", "to": "string", "onError": "", "onNull": ""}}}}}, value)


def harga_json(value):
    """Finite JSON number normally, exact decimal text beyond IEEE754 range.

    Source nonfinite values are zeroed by ekspresi_harga. Nonfinite aggregate
    means Decimal128 overflow; refuse rather than publish an invented total.
    """
    number = value.to_decimal() if isinstance(value, Decimal128) else Decimal(str(value))
    if not number.is_finite():
        raise HTTPException(413, "Jumlah nilai laporan melampaui kapasitas angka. Persempit lingkup laporan.")
    floating = float(number)
    return floating if math.isfinite(floating) and (floating != 0 or number == 0) else str(number)


def harga_float(value):
    """Finite legacy float adapter for document renderers with numeric formats."""
    number = float(harga_desimal(value))
    if not math.isfinite(number):
        raise HTTPException(413, "Nilai aset melampaui kapasitas laporan ini. Persempit lingkup atau gunakan ekspor CSV.")
    return number


def jumlah_harga_eksak(values):
    try:
        with localcontext() as context:
            context.prec = 34
            result = sum((harga_desimal(value) for value in values), Decimal(0))
            return Decimal128(result).to_decimal()
    except (DecimalException, OverflowError):
        raise HTTPException(413, "Jumlah nilai laporan melampaui kapasitas angka. Persempit lingkup laporan.")


def harga_teks_eksak(value):
    return str(value.to_decimal() if isinstance(value, Decimal128) else Decimal(str(value)))


def tahapan_urutan_aset(sort_by):
    if sort_by in CODE_NUP_SORTS:
        direction = -1 if sort_by == "code_nup_desc" else 1
        fields = {"_aman_code_sort": ekspresi_identitas("asset_code"),
                  "_aman_nup_sort": ekspresi_identitas("NUP")}
        sort = {}
        for field in fields:
            sort.update({f"{field}.invalid": 1, f"{field}.length": direction,
                         f"{field}.digits": direction})
        return [{"$set": fields}, {"$sort": {**sort, "id": 1}}, {"$unset": list(fields)}]
    if sort_by in {"price_asc", "price_desc"}:
        return [{"$set": {PRICE_SORT_FIELD: ekspresi_harga()}},
                {"$sort": {PRICE_SORT_FIELD: 1 if sort_by == "price_asc" else -1, "id": 1}},
                {"$unset": PRICE_SORT_FIELD}]
    return [{"$sort": dict(ASSET_SORT_OPTIONS.get(sort_by, ASSET_SORT_OPTIONS["newest"]))}]


def urutkan_harga_aset(assets, sort_by):
    # Dua stable sorts menjaga ID ascending untuk kedua arah harga.
    assets.sort(key=lambda item: str(item.get("id") or ""))
    assets.sort(key=lambda item: harga_desimal(item.get("purchase_price")),
                reverse=sort_by == "price_desc")
    return assets


ASSET_SORT_OPTIONS = {
    # Reader wajib memakai tahapan_urutan_aset / urutkan_kode_nup_aset agar
    # NUP string dan numerik setara; pasangan ini juga menjadi daftar pilihan.
    "code_nup_asc": [("asset_code", 1), ("NUP", 1), ("id", 1)],
    "code_nup_desc": [("asset_code", -1), ("NUP", -1), ("id", 1)],
    "newest": [("created_at", -1), ("id", 1)],
    "oldest": [("created_at", 1), ("id", 1)],
    "name_asc": [("asset_name", 1), ("id", 1)],
    "name_desc": [("asset_name", -1), ("id", 1)],
    "price_asc": [("purchase_price", 1), ("id", 1)],
    "price_desc": [("purchase_price", -1), ("id", 1)],
    "category_asc": [("category", 1), ("id", 1)],
    "category_desc": [("category", -1), ("id", 1)],
    "location_asc": [("location", 1), ("id", 1)],
    "eselon1_asc": [("eselon1", 1), ("id", 1)],
    "condition_asc": [("condition", 1), ("id", 1)],
    "status_asc": [("status", 1), ("id", 1)],
}
