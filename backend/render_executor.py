"""Bounded executor for pure document builders; no Motor objects in threads."""
import asyncio
import functools
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="aman-render")
_INFLIGHT = threading.BoundedSemaphore(4)  # two builders plus two queued


async def run_renderer(builder, *args, **kwargs):
    if not _INFLIGHT.acquire(blocking=False):
        raise HTTPException(429, "Antrean penyusunan dokumen penuh; coba lagi setelah pekerjaan selesai.", headers={"Retry-After": "5"})
    future = None
    try:
        future = asyncio.get_running_loop().run_in_executor(_EXECUTOR, functools.partial(builder, *args, **kwargs))
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            # A cancelled Future does not stop its Python thread. Keep both the
            # queue budget and outer physical render resource until it exits.
            while not future.done():
                try:
                    await asyncio.shield(future)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if future.done() and not future.cancelled():
                try:
                    future.result()
                except Exception:
                    pass
            raise
    finally:
        _INFLIGHT.release()
