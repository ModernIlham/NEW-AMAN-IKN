"""Test logika murni (tanpa DB/server) — port pytest dari check_pure_logic.py.

Menguji logika bisnis nyata: hashing+JWT auth, helper gambar/thumbnail,
formatter ekspor termasuk _xlsx_image_buffer, model pydantic, dan kompilasi
template Jinja2.
"""
import asyncio
import base64
import io
import time
from pathlib import Path

import jwt as pyjwt
import pytest
from PIL import Image as PILImage

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _b64img(mode, size, color, fmt):
    img = PILImage.new(mode, size, color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


PNG_ALPHA = _b64img("RGBA", (1200, 800), (255, 0, 0, 128), "PNG")  # besar + alpha
JPG_SMALL = _b64img("RGB", (50, 50), (0, 128, 0), "JPEG")
PNG_DATAURI = "data:image/png;base64," + PNG_ALPHA


# ---------------------------------------------------------------- auth_utils
def test_password_hash_roundtrip():
    import auth_utils as au
    h = au.hash_password("Secret123!")
    assert h != "Secret123!"
    assert au.verify_password("Secret123!", h)
    assert au.verify_password("wrong", h) is False


def test_verify_password_dummy_always_false_and_runs_bcrypt():
    # Penyetara waktu login untuk user tak-ada: harus SELALU False, tak pernah
    # melempar (termasuk input kosong/aneh), dan benar-benar menjalankan bcrypt
    # (durasi > 0) agar timing setara kasus user ada — anti-enumerasi.
    import auth_utils as au
    assert au.verify_password_dummy("apa saja") is False
    assert au.verify_password_dummy("") is False
    assert au.verify_password_dummy(None) is False
    t0 = time.perf_counter()
    au.verify_password_dummy("x")
    assert time.perf_counter() - t0 > 0.0


def test_jwt_token_claims_and_secret():
    import auth_utils as au
    tok = au.create_token("user-1", "alice")
    dec = pyjwt.decode(tok, au.JWT_SECRET, algorithms=[au.JWT_ALGORITHM])
    assert dec["user_id"] == "user-1" and dec["username"] == "alice"
    assert dec["exp"] > time.time()
    with pytest.raises(pyjwt.InvalidTokenError):
        pyjwt.decode(tok, "wrong-secret", algorithms=[au.JWT_ALGORITHM])


def test_media_token_scope():
    import auth_utils as au
    tok = au.create_media_token("user-1", "alice")
    dec = pyjwt.decode(tok, au.JWT_SECRET, algorithms=[au.JWT_ALGORITHM])
    assert dec.get("scope") == "media"


def test_rate_limit_key_per_user_vs_ip():
    # AUTH-B: kunci rate-limit = per-USER dari JWT (Bearer atau ?token=), jatuh
    # ke per-IP bila tanpa/rusak token. Adil untuk satker ber-NAT bersama.
    import shared_utils as su
    import auth_utils as au

    class _H(dict):
        def get(self, k, d=""):
            return dict.get(self, k, d)

    class _Req:
        def __init__(self, auth=None, token=None, host="10.0.0.1"):
            self.headers = _H({"authorization": auth} if auth else {})
            self.query_params = _H({"token": token} if token else {})
            self.client = type("C", (), {"host": host})()

    tok = au.create_token("user-9", "bob")
    assert su._rate_limit_key(_Req(auth=f"Bearer {tok}")) == "u:user-9"
    assert su._rate_limit_key(_Req(token=tok)) == "u:user-9"
    assert su._rate_limit_key(_Req(host="203.0.113.5")) == "ip:203.0.113.5"
    assert su._rate_limit_key(_Req(auth="Bearer garbage", host="203.0.113.5")) == "ip:203.0.113.5"


def test_token_carries_sesi_epoch_for_revocation():
    # AUTH-C: token akses & media membawa klaim sesi_epoch (default 0, dan nilai
    # yang diberikan diteruskan) → dipakai _decode_bearer mencabut token lama
    # setelah reset/ubah password.
    import auth_utils as au
    dec0 = pyjwt.decode(au.create_token("u1", "alice"), au.JWT_SECRET,
                        algorithms=[au.JWT_ALGORITHM])
    assert dec0.get("sesi_epoch") == 0
    dec3 = pyjwt.decode(au.create_token("u1", "alice", 3), au.JWT_SECRET,
                        algorithms=[au.JWT_ALGORITHM])
    assert dec3.get("sesi_epoch") == 3
    decm = pyjwt.decode(au.create_media_token("u1", "alice", 5), au.JWT_SECRET,
                        algorithms=[au.JWT_ALGORITHM])
    assert decm.get("sesi_epoch") == 5 and decm.get("scope") == "media"


def test_ws_decode_rejects_media_scope_and_garbage():
    # AUTH-C2: _decode_ws_token menerima token sesi (bawa user_id+epoch) tapi
    # MENOLAK token ber-scope media (umur 30 hari, tak boleh untuk kanal WS),
    # token kosong, dan token rusak.
    import auth_utils as au
    import routes.websocket as wsmod
    p = wsmod._decode_ws_token(au.create_token("u1", "alice", 2))
    assert p and p["user_id"] == "u1" and p.get("sesi_epoch") == 2
    assert wsmod._decode_ws_token(au.create_media_token("u1", "alice", 2)) is None
    assert wsmod._decode_ws_token("") is None
    assert wsmod._decode_ws_token("garbage.token.value") is None


# ------------------------------------------------------------- shared_utils
def test_generate_otp():
    import shared_utils as su
    otp = su.generate_otp()
    assert len(otp) == 6 and otp.isdigit()
    assert len(su.generate_otp(8)) == 8


def test_decode_data_url_never_raises():
    import shared_utils as su
    assert su.decode_data_url(None) == b""
    assert su.decode_data_url("!!!not base64!!!") is not None
    assert su.decode_data_url(PNG_DATAURI)[:8] == base64.b64decode(PNG_ALPHA)[:8]
    assert su.decode_data_url(JPG_SMALL).startswith(b"\xff\xd8")


def test_create_thumbnail():
    import shared_utils as su
    thumb = su.create_thumbnail(PNG_DATAURI, size=64)
    assert isinstance(thumb, str) and thumb.startswith("data:image/jpeg;base64,")
    ti = PILImage.open(io.BytesIO(su.decode_data_url(thumb)))
    assert ti.format == "JPEG" and ti.mode == "RGB" and max(ti.size) <= 64
    assert su.create_thumbnail(None) is None
    assert su.create_gallery_thumbnail(JPG_SMALL).startswith("data:image/jpeg")


def test_prepare_image_flattens_alpha():
    import shared_utils as su
    pi = su._prepare_image(PNG_DATAURI)
    assert pi is not None and pi.mode == "RGB"
    assert su._prepare_image(None) is None


def test_compute_changes():
    import shared_utils as su
    ch = su.compute_changes({"asset_name": "Old", "location": "A"},
                            {"asset_name": "New", "location": "A"})
    assert any(c["field"] == "asset_name" and c["from"] == "Old" and c["to"] == "New" for c in ch)
    assert all(c["field"] != "location" for c in ch)
    assert su.compute_changes({"asset_name": "X"}, {"asset_name": "X"}) == []
    chp = su.compute_changes({"photos": ["a"]}, {"photos": ["a", "b", "c"]})
    assert any(c["field"] == "photos" and "1 foto" in c["from"] and "3 foto" in c["to"] for c in chp)
    chd = su.compute_changes(
        {"document_checklist": [{"checked": True}, {"checked": False}]},
        {"document_checklist": [{"checked": True}, {"checked": True}]},
    )
    assert any(c["field"] == "document_checklist" for c in chd)


def test_reserve_idempotency_key_fast_path():
    import shared_utils as su
    assert asyncio.run(su.reserve_idempotency_key("")) == "new"


# -------------------------------------------------------------------- exports
def test_csv_checklist_formatter():
    import routes.exports as ex
    checklist = [
        {"name": "BAST", "checked": True, "notes": "ok",
         "photos": ["p1", "p2"], "documents": [{"name": "d.pdf"}]},
        {"name": "Foto", "checked": False, "notes": "", "photos": [], "documents": []},
    ]
    csvd = ex.format_document_checklist_for_csv(checklist, "asset-9", "http://x")
    assert "BAST:" in csvd["kelengkapan_items"] and "✓" in csvd["kelengkapan_items"]
    assert csvd["kelengkapan_foto_links"].count("doc-file/0/photo/") == 2
    assert "d.pdf=" in csvd["kelengkapan_pdf_links"]
    assert ex.format_document_checklist_for_csv([], "a", "")["kelengkapan_items"] == ""
    xl = ex.format_document_checklist_for_xlsx(checklist, "asset-9", "http://x")
    assert len(xl) == 2 and xl[0]["status"].startswith("✓")


def _reshape_checklist_like_projection(checklist):
    """Tiru hasil aggregation $project pada export_csv: buang isi base64
    (item.photos → panjang saja; documents → nama saja), pertahankan yang
    dipakai formatter. Cerminan Python dari $map di routes/exports.py."""
    out = []
    for it in checklist:
        item = {"name": it.get("name"), "checked": it.get("checked"),
                "notes": it.get("notes")}
        item["photos"] = [1 for _ in (it.get("photos") or [])]
        docs = []
        for d in (it.get("documents") or []):
            nd = {}
            if isinstance(d, dict) and "name" in d:  # $$d.name hilang → field diomit
                nd["name"] = d.get("name")
            docs.append(nd)
        item["documents"] = docs
        out.append(item)
    return out


def test_csv_projection_setara_penuh():
    # AUDIT PERF: export_csv membuang byte base64 document_checklist via
    # aggregation. Buktikan keluaran formatter IDENTIK untuk data penuh vs
    # data ter-proyeksi, dan bahwa hasil proyeksi tak lagi memuat base64.
    import routes.exports as ex
    penuh = [
        {"name": "BAST", "checked": True, "notes": "ok",
         "photos": ["data:image/jpeg;base64,AAAABBBB", "data:image/jpeg;base64,CCCC"],
         "documents": [{"name": "surat.pdf", "data": "JVBERi0xLjcKJUVSU..."},
                       {"name": "lampiran.pdf", "data": "aGVhdnlieXRlcw=="}]},
        {"name": "Foto Fisik", "checked": False, "notes": "",
         "photos": ["data:image/jpeg;base64,DDDD"], "documents": []},
        {"name": "Tanpa Nama Dok", "checked": True, "notes": "x",
         "photos": [], "documents": [{"data": "tanpa-nama-key"}]},
    ]
    ringkas = _reshape_checklist_like_projection(penuh)
    hasil_penuh = ex.format_document_checklist_for_csv(penuh, "aset-1", "http://x")
    hasil_ringkas = ex.format_document_checklist_for_csv(ringkas, "aset-1", "http://x")
    assert hasil_penuh == hasil_ringkas  # keluaran CSV identik
    # Hasil proyeksi tak boleh membawa base64/byte dokumen apa pun.
    blob = repr(ringkas)
    assert "base64" not in blob and "JVBER" not in blob and "heavybytes" not in blob
    assert "aGVhdnlieXRlcw" not in blob and "tanpa-nama-key" not in blob
    # Jumlah foto & tautan tetap benar (2 foto item pertama, 1 foto item kedua).
    assert hasil_ringkas["kelengkapan_foto_links"].count("doc-file/0/photo/") == 2
    assert "surat.pdf=" in hasil_ringkas["kelengkapan_pdf_links"]


@pytest.mark.parametrize("label,data,mx", [
    ("png-alpha-datauri", PNG_DATAURI, 640),
    ("raw-b64", PNG_ALPHA, 110),
    ("jpeg-in", JPG_SMALL, 900),
])
def test_xlsx_image_buffer(label, data, mx):
    import routes.exports as ex
    buf = ex._xlsx_image_buffer(data, mx, quality=70)
    img = PILImage.open(buf)
    assert img.format == "JPEG" and img.mode == "RGB" and max(img.size) <= mx


def test_xlsx_image_buffer_embeddable():
    import xlsxwriter
    import routes.exports as ex
    wb_io = io.BytesIO()
    wb = xlsxwriter.Workbook(wb_io, {"in_memory": True})
    ws = wb.add_worksheet()
    ws.insert_image(0, 0, "c.jpg", {
        "image_data": ex._xlsx_image_buffer(PNG_DATAURI, 640),
        "x_scale": 0.22, "y_scale": 0.22,
    })
    wb.close()
    assert wb_io.getvalue()[:2] == b"PK"  # .xlsx valid


# --------------------------------------------------------------------- models
def test_pydantic_models():
    from pydantic import ValidationError
    import models as m
    a = m.AssetCreate(asset_code="A-1", asset_name="Laptop", category="Elektronik")
    assert a.condition == "Baik" and a.inventory_status == "Belum Diinventarisasi"
    with pytest.raises(ValidationError):
        m.AssetCreate(asset_name="x")
    u = m.UserCreate(username="bob", password="pw")
    assert u.name == ""
    with pytest.raises(ValidationError):
        m.UserCreate(username="bob")
    assert m.DocumentCheckItem(name="BAST").checked is False


# ------------------------------------------------------------------ templates
def test_jinja_templates_compile():
    from jinja2 import Environment, FileSystemLoader
    tpl_dir = BACKEND_DIR / "templates"
    env = Environment(loader=FileSystemLoader(str(tpl_dir)))
    html_templates = [p.name for p in tpl_dir.glob("*.html")]
    assert html_templates, "tidak ada template .html ditemukan"
    for name in html_templates:
        env.get_template(name)  # TemplateSyntaxError bila rusak


# ------------------------------------------------------------------ app wiring
def test_app_imports_and_routes_registered():
    """Import server:app menarik SEMUA modul route — smoke test wiring:
    salah import/salah nama simbol di route mana pun akan gagal di sini."""
    import server
    paths = {getattr(r, "path", "") for r in server.app.routes}
    assert any(p.startswith("/api/assets") for p in paths)
    assert any(p.startswith("/api/auth") for p in paths)
    assert len(paths) > 40
