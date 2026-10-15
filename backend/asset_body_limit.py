"""Bound asset mutation bodies and concurrent parsers, including chunked."""
import json


class AssetBodyLimitMiddleware:
    MAX_BODY_BYTES = 14 * 1024 * 1024
    MAX_IN_FLIGHT = 4  # Per ASGI process; no unbounded wait queue.

    def __init__(self, app):
        self.app = app
        self.in_flight = 0

    async def _reject(self, send, status=413):
        message = ("Ukuran unggahan aset maksimal 14 MB. Kurangi lampiran atau ukuran berkas."
                   if status == 413 else "Terlalu banyak penyimpanan aset berjalan. Coba lagi sebentar.")
        body = json.dumps({"detail": message}).encode()
        headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
        if status == 429:
            headers.append((b"retry-after", b"1"))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        protected = (scope.get("type") == "http" and scope.get("method") in {"POST", "PUT", "PATCH"}
                     and (path == "/api/assets" or path.startswith("/api/assets/")))
        if not protected:
            return await self.app(scope, receive, send)
        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    if int(value) > self.MAX_BODY_BYTES:
                        return await self._reject(send)
                except ValueError:
                    pass
        # ASGI calls on one process event loop: no await between admission check
        # and increment. Hold the budget through parsing/route/response lifetime.
        if self.in_flight >= self.MAX_IN_FLIGHT:
            return await self._reject(send, 429)
        self.in_flight += 1
        try:
            return await self._bounded(scope, receive, send)
        finally:
            self.in_flight -= 1

    async def _bounded(self, scope, receive, send):
        chunks, length = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            length += len(chunk)
            if length > self.MAX_BODY_BYTES:
                return await self._reject(send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        chunks.clear()
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return await self.app(scope, bounded_receive, send)
