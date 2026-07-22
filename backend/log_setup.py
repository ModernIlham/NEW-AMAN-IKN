"""Logging terstruktur + korelasi request-id (observability).

Menyediakan:
- `request_id_ctx`  : ContextVar berisi id korelasi request saat ini.
- `RequestIdLogFilter` : menyisipkan `request_id` ke SETIAP record log (default
  "-" bila di luar request, mis. saat startup / background task).
- `JsonLogFormatter` : format JSON-lines (satu objek per baris) untuk agregasi.
- `configure_logging()` : pasang handler root sekali (idempoten). Format dipilih
  via env `LOG_FORMAT` = "plain" (default, human-readable + request_id) atau
  "json"; level via `LOG_LEVEL` (default INFO).
- `RequestContextMiddleware` : ASGI MURNI (aman untuk StreamingResponse — tak
  membuffer body) yang: (1) ambil/lahirkan request-id, set contextvar; (2) sisip
  header `X-Request-ID` pada respons; (3) catat satu baris akses terstruktur
  (metode, path, status, durasi) per request.

Dipakai server.py sebagai pengganti `logging.basicConfig`. Tidak menyentuh 191
pemanggilan `logger.*` yang ada — formatter root memformat ulang semuanya.
"""
import json
import logging
import os
import re
import time
import uuid
from contextvars import ContextVar

# Id korelasi request; "-" = konteks non-request (startup, cron, dll.).
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

# Karakter aman untuk request-id dari header (cegah log/response injection).
_RID_SAFE = re.compile(r"[^A-Za-z0-9._-]")
# Buang karakter kontrol (termasuk CR/LF/TAB) sebelum menulis nilai user ke log:
# path request di-URL-decode oleh server ASGI sehingga `/x%0Ay` → "/x\ny", dan
# formatter plain menulisnya apa adanya → INJEKSI baris log. (JSON meng-escape,
# tapi kita bersihkan lintas-format.)
_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def _bersih_log(nilai, maks: int = 256) -> str:
    """Buang karakter kontrol + batasi panjang nilai user untuk baris log."""
    return _CTRL.sub("", str(nilai or ""))[:maks]
# Field terstruktur tambahan yang mungkin ditempel ke record (akses log).
_EXTRA_FIELDS = ("http_method", "http_path", "http_status", "duration_ms",
                 "client_ip")


def _bersih_request_id(raw: str) -> str:
    """Sanitasi nilai X-Request-ID dari klien: hanya [A-Za-z0-9._-], maks 64.
    Kosong/janggal → id baru. Mencegah injeksi baris log & header splitting."""
    rid = _RID_SAFE.sub("", str(raw or ""))[:64]
    return rid or uuid.uuid4().hex[:12]


class RequestIdLogFilter(logging.Filter):
    """Tempelkan `request_id` ke tiap record (dari contextvar) agar formatter
    plain (`%(request_id)s`) & JSON selalu punya field itu tanpa KeyError."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_ctx.get()
        return True


class JsonLogFormatter(logging.Formatter):
    """Satu objek JSON per baris — ramah agregator log (grep/jq/Loki)."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
        }
        for k in _EXTRA_FIELDS:
            v = getattr(record, k, None)
            if v is not None:
                data[k] = v
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


_PLAIN_FMT = "%(asctime)s [%(request_id)s] %(name)s %(levelname)s %(message)s"


def configure_logging() -> None:
    """Pasang satu handler pada root logger (idempoten). Format & level dari env.
    Mengganti `logging.basicConfig` — semua `logger.*` app ikut format ini."""
    level_name = str(os.environ.get("LOG_LEVEL", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = str(os.environ.get("LOG_FORMAT", "plain")).lower()

    handler = logging.StreamHandler()
    handler.addFilter(RequestIdLogFilter())
    if fmt == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter(_PLAIN_FMT))

    root = logging.getLogger()
    # Idempoten: buang handler lama (mis. dari basicConfig / reload) agar tak
    # dobel-log bila configure_logging terpanggil dua kali.
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(level)


# Path yang TIDAK dicatat di access log (health-check dipoll sangat sering →
# banjir log tanpa nilai). request_id tetap di-set untuk semuanya.
_ACCESS_SKIP = {"/api/health", "/health", "/api/health/deep", "/api/"}
_access_logger = logging.getLogger("app.access")


class RequestContextMiddleware:
    """ASGI murni (bukan BaseHTTPMiddleware) — tak menyentuh/membuffer body,
    jadi StreamingResponse (foto/PDF/ekspor) tetap streaming apa adanya."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        raw_rid = headers.get(b"x-request-id", b"").decode("latin-1", "replace")
        request_id = _bersih_request_id(raw_rid)
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()
        status = {"code": 0}
        rid_bytes = request_id.encode("latin-1", "replace")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message.get("status", 0)
                # Sisip X-Request-ID (buat list baru — jangan mutasi in-place).
                message["headers"] = list(message.get("headers") or []) + [
                    (b"x-request-id", rid_bytes)]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # Exception tak-tertangani menembus ke ServerErrorMiddleware (lapisan
            # LEBIH luar dari middleware ini) yang membalas 500 — send_wrapper tak
            # pernah melihat response.start, jadi status tetap 0. Catat 500 (yang
            # benar-benar diterima klien) sebelum melempar ulang.
            if status["code"] == 0:
                status["code"] = 500
            raise
        finally:
            path = scope.get("path", "-")
            if path not in _ACCESS_SKIP:
                dur_ms = round((time.perf_counter() - start) * 1000, 1)
                # Sanitasi nilai user (path bisa mengandung CR/LF dari %0A) agar
                # tak menginjeksi baris log pada format plain.
                method = _bersih_log(scope.get("method", "-"), 16)
                path_safe = _bersih_log(path)
                client = scope.get("client") or ("-",)
                _access_logger.info(
                    "%s %s -> %s (%sms)", method, path_safe, status["code"], dur_ms,
                    extra={"http_method": method, "http_path": path_safe,
                           "http_status": status["code"], "duration_ms": dur_ms,
                           "client_ip": _bersih_log(client[0], 64)})
            request_id_ctx.reset(token)
