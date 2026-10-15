"""Validasi target, konfigurasi, dan respons; tidak memerlukan Locust."""
import csv
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse

PRODUCTION_HOST = "amanikn-inventarisasi.com"
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
TRANSPORT_ERROR_TYPES={"ConnectionError","ProtocolError","ReadTimeout","ConnectTimeout","Timeout",
    "TimeoutError","RemoteDisconnected","ConnectionResetError","ConnectionAbortedError","BrokenPipeError",
    "SSLError","NewConnectionError","MaxRetryError","ChunkedEncodingError","ContentDecodingError",
    "IncompleteRead","InvalidHeader","gaierror","OSError"}


def transport_exception_kind(error):
    """Bounded type-only diagnostics: never serialize exception text/URL/headers."""
    pending=[error];seen=set();names=[]
    while pending and len(seen)<8:
        item=pending.pop(0)
        if not isinstance(item,BaseException) or id(item) in seen:continue
        seen.add(id(item))
        name=type(item).__name__
        name=name if name in TRANSPORT_ERROR_TYPES else "OtherTransportError"
        number=getattr(item,"errno",None)
        if number in {32,54,104,110,111}:name+="(errno="+str(number)+")"
        if name not in names:names.append(name)
        pending.extend(arg for arg in item.args if isinstance(arg,BaseException))
        pending.extend(getattr(item,key,None) for key in ["__cause__","__context__","reason"])
    return ">".join(names[:4]) or "OtherTransportError"


def safe_host(raw, allowed=""):
    parsed = urlparse(raw)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if hostname == PRODUCTION_HOST or hostname.endswith("." + PRODUCTION_HOST):
        raise ValueError("Target produksi dilarang untuk load test")
    if (parsed.scheme not in {"http", "https"} or not hostname or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("Host wajib origin HTTP(S) tanpa credentials/path/query")
    _ = parsed.port  # Reject invalid port before any request.
    allowlist = {item.strip().lower().rstrip(".") for item in allowed.split(",") if item.strip()}
    if hostname not in LOOPBACK and hostname not in allowlist:
        raise ValueError("Host bukan loopback atau hostname staging dalam AMAN_STAGING_HOSTS")
    if hostname not in LOOPBACK and parsed.scheme != "https":
        raise ValueError("Staging eksternal wajib HTTPS")
    return raw.rstrip("/")


def duration_seconds(raw):
    match = re.fullmatch(r"([1-9][0-9]*)([sm])", str(raw))
    if not match:
        raise ValueError("Durasi wajib detik/menit, misalnya 30s atau 5m")
    result = int(match[1]) * (60 if match[2] == "m" else 1)
    if not 3 <= result <= 1800:
        raise ValueError("Durasi harus 3 detik sampai 30 menit")
    return result


def bounded_int(value, low, high, label):
    result = int(value)
    if not low <= result <= high:
        raise ValueError(f"{label} harus {low}..{high}")
    return result


def load_pool(path="", username="", password="", activity=""):
    if path:
        source = Path(path)
        if os.name != "nt" and source.stat().st_mode & 0o077:
            raise ValueError("Berkas pool akun wajib privat (mode 0600)")
        result = json.loads(source.read_text())
        accounts = result.get("accounts", [])
    else:
        accounts = [{"username": username.strip(), "password": password, "activity_id":activity}]
    if not accounts or len(accounts) > 100:
        raise ValueError("Pool wajib berisi 1..100 akun")
    for account in accounts:
        if not account.get("username") or not (account.get("access_token") or account.get("password")):
            raise ValueError("Pool akun tidak memiliki identitas/token atau password")
        if not account.get("activity_id"):
            raise ValueError("Setiap akun wajib memiliki activity_id untuk snapshot dan verifikasi dataset")
    return accounts


def json_object(response, keys):
    if response.status_code != 200:
        raise ValueError(f"HTTP {response.status_code}; diharapkan 200")
    value = response.json()
    if not isinstance(value, dict) or any(key not in value for key in keys):
        raise ValueError("Schema respons tidak sesuai")
    return value


def list_result(response, expected=None, activity=None, snapshot=False, cursor=False):
    result = json_object(response, ["items", "total"] + (["server_time", "next_cursor"] if snapshot else []))
    if not isinstance(result["items"], list) or not isinstance(result["total"], int):
        raise ValueError("items/total tidak valid")
    if expected is not None and result["total"] != expected:
        raise ValueError("Jumlah dataset server tidak sesuai manifest seed")
    if len(result["items"]) > result["total"] or any(not isinstance(row, dict) or not row.get("id") for row in result["items"]):
        raise ValueError("Daftar tidak lengkap atau identitas aset hilang")
    if activity and any(row.get("activity_id") != activity for row in result["items"]):
        raise ValueError("Isolasi activity_id gagal")
    limit = result.get("limit", 200) if snapshot else result.get("page_size", 50)
    skip = result.get("skip", 0) if snapshot else (result.get("page",1)-1)*limit
    if not cursor and len(result["items"]) != min(limit, max(0,result["total"]-skip)):
        raise ValueError("Daftar/snapshot parsial tidak sesuai total/pagination")
    return result


def csv_artifact(response, expected=None, maximum=64 * 1024 * 1024):
    if response.status_code != 200 or "text/csv" not in response.headers.get("Content-Type", ""):
        raise ValueError(f"Artifact CSV gagal: HTTP {response.status_code}/content type")
    chunks=[]
    size=0
    for chunk in response.iter_content(chunk_size=65536):
        size+=len(chunk)
        if size>maximum:
            response.close()
            raise ValueError("Artifact melampaui batas client 64 MiB")
        chunks.append(chunk)
    content=b"".join(chunks)
    lines = (line for line in content.decode("utf-8-sig").splitlines() if not line.startswith("#"))
    reader = csv.DictReader(lines,strict=True)
    if not reader.fieldnames or not {"asset_code", "asset_name", "NUP"}.issubset(reader.fieldnames):
        raise ValueError("Header artifact bukan CSV aset")
    count = 0
    try:
        for row in reader:
            if None in row or any(value is None for value in row.values()) or not row.get("asset_code"):
                raise ValueError("Baris artifact CSV tidak valid/terpotong")
            count += 1
    except csv.Error as exc:
        raise ValueError("Artifact CSV terpotong atau quote tidak valid") from exc
    if not count or expected is not None and count != expected:
        raise ValueError("Artifact kosong atau jumlah baris tidak sesuai dataset server")
    return {"rows": count, "bytes": size}
