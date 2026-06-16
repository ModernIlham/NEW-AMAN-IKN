#!/usr/bin/env python3
"""Pure-logic unit tests (no DB) for AMAN backend.

Run: MONGO_URL=... DB_NAME=... ./venv/bin/python test_pure_logic.py
Exercises real business logic: auth hashing/JWT, image+thumbnail helpers,
export formatters incl. the _xlsx_image_buffer XLSX fix, pydantic models,
and Jinja2 template compilation.
"""
import os, io, base64, sys, traceback

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "aman_test")
os.environ.setdefault("JWT_SECRET", "unit_test_secret")

from PIL import Image as PILImage
import jwt as pyjwt

P, F = 0, 0
def ok(cond, name, extra=""):
    global P, F
    if cond: P += 1; print(f"  ok   {name}")
    else: F += 1; print(f"  FAIL {name} {extra}")

def section(t): print(f"\n=== {t} ===")

def b64img(mode, size, color, fmt):
    img = PILImage.new(mode, size, color)
    buf = io.BytesIO(); img.save(buf, format=fmt); buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode()

PNG_ALPHA = b64img("RGBA", (1200, 800), (255, 0, 0, 128), "PNG")     # large + alpha
JPG_SMALL = b64img("RGB", (50, 50), (0, 128, 0), "JPEG")
PNG_DATAURI = "data:image/png;base64," + PNG_ALPHA

# ---------------------------------------------------------------- auth_utils
section("auth_utils: password hashing + JWT")
import auth_utils as au
h = au.hash_password("Secret123!")
ok(h != "Secret123!" and au.verify_password("Secret123!", h), "hash+verify roundtrip")
ok(au.verify_password("wrong", h) is False, "verify rejects wrong password")
tok = au.create_token("user-1", "alice")
dec = pyjwt.decode(tok, au.JWT_SECRET, algorithms=[au.JWT_ALGORITHM])
ok(dec["user_id"] == "user-1" and dec["username"] == "alice", "token carries claims")
import time as _t
ok(dec["exp"] > _t.time(), "token exp in the future")
try:
    pyjwt.decode(tok, "wrong-secret", algorithms=[au.JWT_ALGORITHM]); ok(False, "bad secret rejected")
except pyjwt.InvalidTokenError:
    ok(True, "bad secret rejected")

# ------------------------------------------------------------- shared_utils
section("shared_utils: otp / decode_data_url / thumbnails / compute_changes")
import shared_utils as su
otp = su.generate_otp()
ok(len(otp) == 6 and otp.isdigit(), "generate_otp -> 6 digits")
ok(len(su.generate_otp(8)) == 8, "generate_otp length param")
ok(su.decode_data_url(None) == b"" and su.decode_data_url("!!!not base64!!!") != None, "decode_data_url never raises")
ok(su.decode_data_url(PNG_DATAURI)[:8] == base64.b64decode(PNG_ALPHA)[:8], "decode_data_url strips data-uri prefix")
ok(su.decode_data_url(JPG_SMALL).startswith(b"\xff\xd8"), "decode_data_url raw base64 -> JPEG bytes")

thumb = su.create_thumbnail(PNG_DATAURI, size=64)
ok(isinstance(thumb, str) and thumb.startswith("data:image/jpeg;base64,"), "create_thumbnail -> jpeg data-uri")
ti = PILImage.open(io.BytesIO(su.decode_data_url(thumb)))
ok(ti.format == "JPEG" and ti.mode == "RGB" and max(ti.size) <= 64, "thumbnail is RGB JPEG <= size", str(ti.size))
ok(su.create_thumbnail(None) is None, "create_thumbnail(None) -> None")
ok(su.create_gallery_thumbnail(JPG_SMALL).startswith("data:image/jpeg"), "gallery_thumbnail ok")
pi = su._prepare_image(PNG_DATAURI)
ok(pi is not None and pi.mode == "RGB", "_prepare_image flattens alpha to RGB")
ok(su._prepare_image(None) is None, "_prepare_image(None) -> None")

ch = su.compute_changes({"asset_name": "Old", "location": "A"}, {"asset_name": "New", "location": "A"})
ok(any(c["field"] == "asset_name" and c["from"] == "Old" and c["to"] == "New" for c in ch), "compute_changes detects field change")
ok(all(c["field"] != "location" for c in ch), "compute_changes ignores unchanged field")
ok(su.compute_changes({"asset_name": "X"}, {"asset_name": "X"}) == [], "compute_changes identical -> []")
chp = su.compute_changes({"photos": ["a"]}, {"photos": ["a", "b", "c"]})
ok(any(c["field"] == "photos" and "1 foto" in c["from"] and "3 foto" in c["to"] for c in chp), "compute_changes counts photos")
chd = su.compute_changes(
    {"document_checklist": [{"checked": True}, {"checked": False}]},
    {"document_checklist": [{"checked": True}, {"checked": True}]},
)
ok(any(c["field"] == "document_checklist" for c in chd), "compute_changes counts doc-checklist completion")

# -------------------------------------------------------------------- exports
section("exports: checklist formatters + _xlsx_image_buffer (the XLSX fix)")
import routes.exports as ex
checklist = [
    {"name": "BAST", "checked": True, "notes": "ok", "photos": ["p1", "p2"], "documents": [{"name": "d.pdf"}]},
    {"name": "Foto", "checked": False, "notes": "", "photos": [], "documents": []},
]
csvd = ex.format_document_checklist_for_csv(checklist, "asset-9", "http://x")
ok("BAST:" in csvd["kelengkapan_items"] and "✓" in csvd["kelengkapan_items"], "csv formatter items+status")
ok(csvd["kelengkapan_foto_links"].count("doc-file/0/photo/") == 2, "csv formatter 2 foto links")
ok("d.pdf=" in csvd["kelengkapan_pdf_links"], "csv formatter pdf link")
ok(ex.format_document_checklist_for_csv([], "a", "")["kelengkapan_items"] == "", "csv formatter empty")
xl = ex.format_document_checklist_for_xlsx(checklist, "asset-9", "http://x")
ok(len(xl) == 2 and xl[0]["status"].startswith("✓"), "xlsx formatter rows+status")

for label, data, mx in [("png-alpha-datauri", PNG_DATAURI, 640), ("raw-b64", PNG_ALPHA, 110), ("jpeg-in", JPG_SMALL, 900)]:
    buf = ex._xlsx_image_buffer(data, mx, quality=70)
    img = PILImage.open(buf)
    ok(img.format == "JPEG" and img.mode == "RGB" and max(img.size) <= mx,
       f"_xlsx_image_buffer({label}) -> RGB JPEG <= {mx}px", str(img.size))
# end-to-end: the buffer is embeddable by xlsxwriter
import xlsxwriter
wb_io = io.BytesIO(); wb = xlsxwriter.Workbook(wb_io, {"in_memory": True})
ws = wb.add_worksheet()
ws.insert_image(0, 0, "c.jpg", {"image_data": ex._xlsx_image_buffer(PNG_DATAURI, 640), "x_scale": 0.22, "y_scale": 0.22})
wb.close(); wb_io.seek(0)
ok(wb_io.getvalue()[:2] == b"PK", "xlsxwriter embeds _xlsx_image_buffer output (valid .xlsx)")

# --------------------------------------------------------------------- models
section("models: pydantic validation")
from pydantic import ValidationError
import models as m
a = m.AssetCreate(asset_code="A-1", asset_name="Laptop", category="Elektronik")
ok(a.condition == "Baik" and a.inventory_status == "Belum Diinventarisasi", "AssetCreate defaults applied")
try:
    m.AssetCreate(asset_name="x"); ok(False, "AssetCreate missing required rejected")
except ValidationError:
    ok(True, "AssetCreate missing required rejected")
u = m.UserCreate(username="bob", password="pw")
ok(u.name == "", "UserCreate default name")
try:
    m.UserCreate(username="bob"); ok(False, "UserCreate missing password rejected")
except ValidationError:
    ok(True, "UserCreate missing password rejected")
dci = m.DocumentCheckItem(name="BAST")
ok(dci.checked is False, "DocumentCheckItem default checked=False")

# ------------------------------------------------------------------ templates
section("templates: Jinja2 compilation (syntax check)")
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError
env = Environment(loader=FileSystemLoader("templates"))
for tpl in os.listdir("templates"):
    if not tpl.endswith(".html"):
        continue
    try:
        env.get_template(tpl); ok(True, f"template compiles: {tpl}")
    except TemplateSyntaxError as e:
        ok(False, f"template syntax error: {tpl}", str(e))

section("idempotency: reserve_idempotency_key fast-path (no key, no DB)")
import asyncio as _aio
ok(_aio.run(su.reserve_idempotency_key("")) == "new", "reserve_idempotency_key('') -> 'new'")

print(f"\n==================  PASSED {P}  FAILED {F}  ==================")
sys.exit(1 if F else 0)
