"""Bounded in-process GET transport. Every ASGI send awaits its GridFS write.

There is no response body accumulator or unbounded producer queue. This bounds
transport overhead, while a renderer may still allocate its own complete file.
The original ASGI application (including auth, middleware and rate limits) runs
unchanged. A sink is committed only after the app returns a complete response.
"""
import asyncio
import contextlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit


@dataclass
class ArtifactResponse:
    status: int
    headers: dict
    size: int = 0
    error_body: bytes = b""


async def stream_asgi_artifact(app, path, headers, open_sink, *, max_bytes,
                               timeout, chunk_size=65536, error_limit=4096):
    """GET a relative path, awaiting a bounded write before accepting more body.

    ``open_sink(headers)`` returns an async write/close/abort GridFS-like sink.
    Non-200 bodies retain at most ``error_limit`` bytes and never create a blob.
    App failures, deadlines, cancellation, size limits and close failures abort
    the upload; callers must publish its reference only after this returns.
    """
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("Only relative application paths are supported")
    if chunk_size <= 0 or max_bytes < 0 or error_limit < 0:
        raise ValueError("Invalid streaming limits")
    parts = urlsplit(path)
    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": unquote(parts.path), "raw_path": parts.path.encode("ascii"),
        "query_string": parts.query.encode("ascii"), "root_path": "",
        "headers": [(b"host", b"internal")] + [
            (str(k).lower().encode("latin-1"), str(v).encode("latin-1"))
            for k, v in headers.items()],
        "client": ("127.0.0.1", 0), "server": ("internal", 80),
    }
    sent_request = False
    never_disconnected = asyncio.Event()
    response = None
    sink: Any = None
    complete = False

    async def receive():
        nonlocal sent_request
        if not sent_request:
            sent_request = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await never_disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal response, sink, complete
        if message["type"] == "http.response.start":
            if response is not None:
                raise RuntimeError("ASGI response started twice")
            response = ArtifactResponse(message["status"], {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in message.get("headers", [])})
            if response.status == 200:
                declared = response.headers.get("content-length")
                if declared is not None and int(declared) > max_bytes:
                    raise RuntimeError("Hasil melebihi plafon ukuran unduhan")
                sink = await open_sink(response.headers)
        elif message["type"] == "http.response.body":
            if response is None or complete:
                raise RuntimeError("Invalid ASGI response body sequence")
            body = message.get("body", b"")
            if response.status == 200:
                if response.size + len(body) > max_bytes:
                    raise RuntimeError("Hasil melebihi plafon ukuran unduhan")
                # Copy only one bounded piece, even when the renderer sends a
                # complete bytes object in one ASGI message.
                for offset in range(0, len(body), chunk_size):
                    await sink.write(body[offset:offset + chunk_size])
                response.size += len(body)
            elif len(response.error_body) < error_limit:
                response.error_body += body[:error_limit - len(response.error_body)]
            complete = not message.get("more_body", False)

    try:
        async with asyncio.timeout(timeout):
            await app(scope, receive, send)
            if response is None or not complete:
                raise RuntimeError("ASGI producer returned an incomplete response")
            if sink is not None:
                declared = response.headers.get("content-length")
                if declared is not None and int(declared) != response.size:
                    raise RuntimeError("ASGI response length does not match Content-Length")
                await sink.close()
        return response
    except BaseException:
        if sink is not None:
            with contextlib.suppress(Exception):
                async with asyncio.timeout(5):
                    await sink.abort()
        raise
