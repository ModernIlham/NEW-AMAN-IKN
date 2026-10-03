"""Batas transport portal: bukti terbatas dan respons pribadi tak di-cache."""
from starlette.responses import JSONResponse


class PortalPemegangMiddleware:
    MAX_BODY = 5 * 1024 * 1024  # 3 MiB bukti biner → 4 MiB base64 + metadata.

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or not (
                path == "/api/portal-pemegang" or path.startswith("/api/portal-pemegang/")):
            return await self.app(scope, receive, send)

        async def private_send(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", [])
                           if k.lower() not in {b"cache-control", b"pragma",
                                                b"referrer-policy", b"x-content-type-options"}]
                message = {**message, "headers": headers + [
                    (b"cache-control", b"private, no-store"),
                    (b"pragma", b"no-cache"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-content-type-options", b"nosniff"),
                ]}
            await send(message)

        # Baca terukur SEBELUM parser JSON/Pydantic mengalokasikan payload besar.
        # Juga berlaku untuk chunked transfer tanpa Content-Length.
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.MAX_BODY:
                response = JSONResponse(
                    {"detail": "Unggahan terlalu besar. Maksimal total bukti 3 MB."},
                    status_code=413)
                return await response(scope, receive, private_send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        sent = False

        async def limited_receive():
            nonlocal sent
            if sent:
                return await receive()
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, limited_receive, private_send)
