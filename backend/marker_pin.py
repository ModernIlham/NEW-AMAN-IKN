"""Desain pin portabel: JSON skalar kecil, aman untuk peta publik/luring.

Ikon custom hanya PNG 64×64 yang dikodekan ulang (tanpa metadata). Tidak ada
SVG/HTML/URL pengguna yang masuk ke divIcon. Batas keras menjaga snapshot,
ekspor, dan perubahan massal tetap kecil. Kosong = pin lama, tanpa migrasi.
"""
import asyncio
import base64
import io
import json
import re

from fastapi import HTTPException
from PIL import Image

IKON_PIN = frozenset({
    "building", "warehouse", "house", "landmark", "monitor", "laptop",
    "printer", "camera", "router", "phone", "car", "truck", "bus", "bike",
    "armchair", "sofa", "archive", "package", "boxes", "wrench", "hammer",
    "plug", "zap", "lightbulb", "trees", "signpost", "cone", "droplets",
    "hospital", "school", "university", "hotel", "store", "church", "factory",
    "tent", "door", "fence", "tablet", "keyboard", "mouse", "cpu",
    "harddrive", "server", "database", "wifi", "network", "usb", "cable",
    "battery", "charging", "circuit", "memory", "scanner", "barcode", "qrcode",
    "ship", "sailboat", "plane", "train", "tram", "ambulance", "forklift",
    "tractor", "construction", "container", "bed", "table", "desk", "floorlamp",
    "ceilinglamp", "rockingchair", "blinds", "briefcase", "drill", "nut", "bolt",
    "cog", "gauge", "weight", "power", "paintbrush", "paintroller", "axe",
    "pickaxe", "ruler", "fuel", "parking", "milestone", "route", "map",
    "mappin", "compass", "navigation", "dam", "waves", "mountain", "trash",
    "recycle", "bath", "shower", "fridge", "washer", "microwave", "cookingpot",
    "utensils", "coffee", "cup", "ac", "fan", "heater", "tv",
    "radio", "speaker", "headphones", "microphone", "video", "webcam", "projector",
    "music", "piano", "guitar", "film", "satellite", "radiotower", "antenna",
    "key", "lock", "shield", "siren", "extinguisher", "cctv", "facescan",
    "fingerprint", "bell", "flashlight", "alert", "lifebuoy", "stethoscope", "heart",
    "cross", "pill", "syringe", "microscope", "testtube", "flask", "dna",
    "thermometer", "accessibility", "document", "files", "folder", "clipboard", "book",
    "library", "notebook", "pen", "pencil", "calculator", "calendar", "mail",
    "inbox", "stamp", "scale", "gavel", "presentation", "sprout", "flower",
    "leaf", "pine", "shovel", "wheat", "fish", "bird", "rabbit",
    "dumbbell", "volleyball", "goal", "medal", "trophy", "timer", "binoculars",
    "backpack", "umbrella", "telescope",
    "buildinglow", "castle", "houseplus", "houseplug", "housewifi", "bricks", "cuboid",
    "doorclosed", "paneldoor", "vault", "busfront", "carfront", "taxi", "caravan",
    "cablecar", "rocket", "shipwheel", "anchor", "traintrack", "railway", "planestart",
    "planeland", "luggage", "packageopen", "packagecheck", "packageplus", "packageout", "packagefind",
    "truckelectric", "pcase", "monitorup", "monitorcheck", "monitordot", "monitorplay", "monitorphone",
    "laptopminimal", "mousepointer", "touchpad", "hdmi", "ethernet", "webpanel", "cloud",
    "cloudupload", "clouddownload", "servercog", "servercrash", "harddiskdown", "harddiskup", "pcchip",
    "bot", "workflow", "braces", "caliper", "rulerpen", "draftcompass", "trianglemeasure",
    "compassmeasure", "electricpole", "electricplug", "electricunplug", "batteryfull", "batterylow", "batterywarning",
    "batterypack", "wind", "magnet", "testelectric", "radar", "scanline", "settings",
    "toolcase", "anvil", "scissors", "brushclean", "droplet", "glasswater", "bubbles",
    "wavesladder", "recyclebin", "leafcircle", "earth", "earthlock", "treesdeciduous", "palm",
    "sun", "moon", "rain", "drizzle", "lightning", "snow", "cloudsnow",
    "cloudfog", "tornado", "rainbow", "sunrise", "sunset", "flame", "flamekindling",
    "thermohigh", "thermolow", "umbrellaopen", "cloudsun", "cloudmoon", "banknote", "coins",
    "wallet", "creditcard", "receipt", "receipttax", "shoppingcart", "basket", "shoppingbag",
    "tags", "tag", "ticket", "piggybank", "chartcolumn", "chartline", "chartpie",
    "chartarea", "trendingup", "percent", "handcoins", "palette", "pencilpaint", "penline",
    "highlighter", "eraser", "paintbucket", "spraycan", "pipette", "ribbon", "frame",
    "image", "images", "notepad", "paperclip", "sticky", "origami", "wand",
    "gem", "flowerart", "puzzle", "apple", "banana", "cherry", "citrus",
    "grape", "carrot", "salad", "egg", "milk", "beef", "fishfood",
    "sandwich", "pizza", "cake", "cookie", "croissant", "souppot", "dessert",
    "kitchenknife", "person", "users", "contact", "idcard", "badgeid", "hardhat",
    "briefcasework", "handshake", "helpdesk", "baby", "footprints", "hand", "handhelp",
    "heartlove", "smile", "megaphone", "speech", "message", "phonecall", "phoneclassic",
    "flag", "flagtri", "star", "circle", "square", "triangle", "diamond",
    "hexagon", "octagon", "pentagon", "target", "crosshair", "locate", "check",
    "crossmark", "question", "info", "warningtriangle", "ban", "bookmark", "shirt",
    "glasses", "watch", "crown", "dog", "cat", "rat", "turtle",
    "snail", "shrimp", "worm", "paw", "bug", "brain", "bone",
    "ear", "eye", "handheart", "heartplus", "bandage", "pillbottle", "venetianmask",
    "scanheart", "testtubes", "swords", "club", "spade", "tenttree", "mountainsnow",
    "rollercoaster", "ferriswheel", "drum", "drumstick", "designpin",
})
BATAS_JSON = 14000
BATAS_GAMBAR = 10000
AWAL_PNG = "data:image/png;base64,"
BAWAAN = {"v": 1, "mode": "icon", "icon": "package", "text": "A", "image": "",
          "circle": True, "circleColor": "#ffffff", "strokeColor": "#334155",
          "strokeWidth": 1, "iconColor": "#0f172a"}


def normalisasi_marker_pin(value):
    """Validasi ringan tanpa I/O/Pillow; juga dipakai model Pydantic."""
    if value is None or value == "":
        return ""
    if not isinstance(value, str) or len(value) > BATAS_JSON:
        raise ValueError("Desain marker harus JSON ringkas (maksimal 14.000 karakter)")
    try:
        raw = json.loads(value)
    except (ValueError, RecursionError) as exc:
        raise ValueError("Desain marker tidak valid") from exc
    if not isinstance(raw, dict) or set(raw) - set(BAWAAN):
        raise ValueError("Properti desain marker tidak dikenal")
    d = {**BAWAAN, **raw}
    if type(d["v"]) is not int or d["v"] != 1 or d["mode"] not in ("icon", "text", "custom"):
        raise ValueError("Jenis desain marker tidak valid")
    if not isinstance(d["icon"], str) or d["icon"] not in IKON_PIN:
        raise ValueError("Ikon marker tidak dikenal")
    if not isinstance(d["text"], str) or not re.fullmatch(r"[A-Za-z0-9]{1,3}", d["text"]):
        raise ValueError("Huruf marker harus 1–3 huruf Latin atau angka")
    if type(d["circle"]) is not bool:
        raise ValueError("Pilihan lingkaran marker tidak valid")
    if type(d["strokeWidth"]) not in (int, float) or d["strokeWidth"] not in (0, 1, 2, 3):
        raise ValueError("Ketebalan garis marker harus 0–3")
    for k in ("circleColor", "strokeColor", "iconColor"):
        if not isinstance(d[k], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", d[k]):
            raise ValueError("Warna marker harus kode heksadesimal enam digit")
        d[k] = d[k].lower()
    if d["mode"] == "custom":
        if not isinstance(d["image"], str) or not d["image"].startswith(AWAL_PNG):
            raise ValueError("Ikon custom harus PNG standar 64×64")
        try:
            blob = base64.b64decode(d["image"][len(AWAL_PNG):], validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("Isi ikon custom tidak valid") from exc
        if len(blob) > BATAS_GAMBAR or not blob.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Ikon custom harus PNG maksimal 10 KB")
    else:
        d["image"] = ""
    # Hilangkan data tak relevan agar ganti jenis tidak membawa teks/gambar lama.
    if d["mode"] != "text":
        d["text"] = "A"
    if d["mode"] != "icon":
        d["icon"] = "package"
    return json.dumps(d, separators=(",", ":"), ensure_ascii=True)


def _standarkan(value):
    value = normalisasi_marker_pin(value)
    if not value:
        return value
    d = json.loads(value)
    if d["mode"] != "custom":
        return value
    try:
        blob = base64.b64decode(d["image"][len(AWAL_PNG):], validate=True)
        with Image.open(io.BytesIO(blob)) as src:
            if src.format != "PNG" or src.size != (64, 64) or getattr(src, "n_frames", 1) != 1:
                raise ValueError("Ikon custom harus PNG statis 64×64")
            src.load()
            # Kanvas baru memastikan metadata/EXIF/chunk tambahan tidak ikut.
            clean = Image.new("RGBA", (64, 64))
            clean.paste(src.convert("RGBA"))
            out = io.BytesIO()
            clean.save(out, format="PNG", optimize=True)
        if out.tell() > BATAS_GAMBAR:
            raise ValueError("Ikon terlalu rinci; gunakan gambar sederhana maksimal 10 KB")
        d["image"] = AWAL_PNG + base64.b64encode(out.getvalue()).decode("ascii")
        return json.dumps(d, separators=(",", ":"))
    except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("Ikon custom rusak atau tidak dapat dibaca") from exc


async def bersihkan_marker_doc(doc):
    """Dipanggil SEBELUM tulisan pada create/PUT/PATCH/batch/impor."""
    if "marker_pin" in doc:
        try:
            doc["marker_pin"] = await asyncio.to_thread(_standarkan, doc["marker_pin"])
        except ValueError as exc:
            raise HTTPException(422, detail=str(exc)) from exc


def marker_pin_publik(value):
    """Allowlist ulang saat baca data lama/restore, tanpa menerbitkan key liar."""
    try:
        return normalisasi_marker_pin(value)
    except ValueError:
        return ""
