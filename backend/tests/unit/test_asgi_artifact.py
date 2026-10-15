"""Real ASGI producers exercise ordering, backpressure, failures and memory."""
import asyncio
import tracemalloc

import pytest
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

from asgi_artifact import stream_asgi_artifact


class Sink:
    def __init__(self):
        self.writes = []
        self.closed = self.aborted = False

    async def write(self, chunk):
        self.writes.append(len(chunk))

    async def close(self):
        self.closed = True

    async def abort(self):
        self.aborted = True


async def capture(app, sink, **kwargs):
    async def open_sink(headers):
        return sink
    return await stream_asgi_artifact(
        app, "/api/export?x=1", {"authorization": "Bearer fixture", "x-satker-aktif": "A"},
        open_sink, max_bytes=kwargs.pop("max_bytes", 100 * 1024 * 1024),
        timeout=kwargs.pop("timeout", 1), **kwargs)


def producer(chunks, *, status=200, fail=False):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/pdf")]})
        for chunk in chunks:
            await send({"type": "http.response.body", "body": chunk, "more_body": True})
        if fail:
            raise RuntimeError("producer failed after a chunk")
        await send({"type": "http.response.body", "body": b""})
    return app


@pytest.mark.asyncio
async def test_first_chunk_written_before_producer_finishes_and_writes_bounded():
    sink = Sink()

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200})
        await send({"type": "http.response.body", "body": b"a" * 200000,
                    "more_body": True})
        assert sum(sink.writes) == 200000
        assert not sink.closed
        await send({"type": "http.response.body", "body": b"last"})

    result = await capture(app, sink)
    assert result.size == 200004 and sink.closed and not sink.aborted
    assert max(sink.writes) <= 65536


@pytest.mark.asyncio
async def test_slow_sink_applies_backpressure_to_real_producer():
    entered, release = asyncio.Event(), asyncio.Event()
    sent = []
    sink = Sink()
    original_write = sink.write

    async def slow_write(chunk):
        entered.set()
        await release.wait()
        await original_write(chunk)
    sink.write = slow_write

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200})
        for i in range(20):
            await send({"type": "http.response.body", "body": b"x" * 65536,
                        "more_body": True})
            sent.append(i)
        await send({"type": "http.response.body", "body": b""})

    task = asyncio.create_task(capture(app, sink))
    await entered.wait()
    await asyncio.sleep(0)
    assert sent == []  # producer cannot finish even its first send
    release.set()
    await task
    assert len(sent) == 20


@pytest.mark.asyncio
async def test_size_cap_stops_producer_and_aborts_partial_upload():
    sink, produced = Sink(), []

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200})
        try:
            for i in range(100):
                produced.append(i)
                await send({"type": "http.response.body", "body": b"x" * 65536,
                            "more_body": True})
        finally:
            produced.append("stopped")

    with pytest.raises(RuntimeError, match="plafon"):
        await capture(app, sink, max_bytes=100000)
    assert produced == [0, 1, "stopped"]
    assert sink.aborted and not sink.closed and sum(sink.writes) == 65536


@pytest.mark.asyncio
async def test_declared_length_mismatch_aborts_upload():
    sink = Sink()
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-length", b"20")]})
        await send({"type": "http.response.body", "body": b"short"})
    with pytest.raises(RuntimeError, match="Content-Length"):
        await capture(app, sink)
    assert sink.aborted and not sink.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["producer", "write", "close", "incomplete", "timeout", "cancel"])
async def test_faults_abort_and_never_publish(fault):
    sink = Sink()
    stopped = asyncio.Event()

    async def app(scope, receive, send):
        try:
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"first", "more_body": True})
            if fault == "producer":
                raise RuntimeError("producer failed")
            if fault in ("timeout", "cancel"):
                await asyncio.Event().wait()
            if fault != "incomplete":
                await send({"type": "http.response.body", "body": b"last"})
        finally:
            stopped.set()

    async def fail(*args):
        raise RuntimeError("sink failed")
    if fault in ("write", "close"):
        setattr(sink, fault, fail)
    task = asyncio.create_task(capture(app, sink, timeout=0.02))
    if fault == "cancel":
        await asyncio.sleep(0.001)
        task.cancel()
    with pytest.raises((RuntimeError, TimeoutError, asyncio.CancelledError)):
        await task
    assert sink.aborted and stopped.is_set()


@pytest.mark.asyncio
async def test_full_fastapi_middleware_dependencies_and_auth_still_run():
    app, events = FastAPI(), []

    @app.middleware("http")
    async def audit(request, call_next):
        events.append("middleware")
        return await call_next(request)

    async def authorize(authorization=Header(None), x_satker_aktif=Header(None)):
        assert authorization == "Bearer fixture" and x_satker_aktif == "A"
        raise HTTPException(403, detail="Satker forbidden")

    @app.get("/api/export")
    async def export(_=Depends(authorize)):
        raise AssertionError("Unauthorized producer must never run")

    sink = Sink()
    result = await capture(app, sink)
    assert result.status == 403 and b"Satker forbidden" in result.error_body
    assert events == ["middleware"] and not sink.writes and not sink.closed


@pytest.mark.asyncio
async def test_real_streaming_response_and_error_body_limit():
    app = FastAPI()
    sink = Sink()

    @app.get("/api/export")
    async def export():
        async def chunks():
            yield b"first"
            assert sink.writes == [5]
            yield b"last"
        return StreamingResponse(chunks(), media_type="application/pdf")

    assert (await capture(app, sink)).size == 9
    result = await capture(producer([b"e" * 100000], status=429), Sink())
    assert result.status == 429 and len(result.error_body) == 4096


@pytest.mark.asyncio
async def test_transport_peak_memory_does_not_scale_with_body_size():
    peaks = []
    for mib in (8, 32, 64):
        # Producer and sink themselves retain no body, so this measures only
        # actual ASGI transport overhead, not a mocked HTTP client.
        class CountingSink(Sink):
            async def write(self, chunk):
                self.count = getattr(self, "count", 0) + len(chunk)

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            for _ in range(mib * 16):
                await send({"type": "http.response.body", "body": b"x" * 65536,
                            "more_body": True})
            await send({"type": "http.response.body", "body": b""})

        sink = CountingSink()
        tracemalloc.start()
        result = await capture(app, sink)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append(peak)
        assert result.size == sink.count == mib * 1024 * 1024
    assert max(peaks) < 1024 * 1024, peaks
    assert max(peaks) - min(peaks) < 256 * 1024, peaks
