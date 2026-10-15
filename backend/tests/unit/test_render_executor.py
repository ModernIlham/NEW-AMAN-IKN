import asyncio
import threading

import pytest
from fastapi import HTTPException

from render_executor import run_renderer


def test_slow_builder_keeps_event_loop_responsive_and_returns_exception():
    async def scenario():
        ready, finish = threading.Event(), threading.Event()
        def builder():
            assert threading.get_ident() != main_thread
            ready.set()
            finish.wait(timeout=3)
            return b"document"
        main_thread = threading.get_ident()
        task = asyncio.create_task(run_renderer(builder))
        while not ready.is_set():
            await asyncio.sleep(.001)
        ticks = 0
        for _ in range(5):
            await asyncio.sleep(.005)
            ticks += 1
        assert not task.done() and ticks == 5
        finish.set()
        assert await task == b"document"
        def bad():
            raise ValueError("invalid document")
        with pytest.raises(ValueError, match="invalid document"):
            await run_renderer(bad)
    asyncio.run(scenario())


def test_queue_is_bounded_and_cancelled_thread_keeps_its_slot():
    async def scenario():
        finish = threading.Event()
        started = [threading.Event(), threading.Event()]
        def builder(index):
            if index < 2:
                started[index].set()
            finish.wait(timeout=3)
            return index
        tasks = [asyncio.create_task(run_renderer(builder, index)) for index in range(4)]
        while not all(item.is_set() for item in started):
            await asyncio.sleep(.001)
        with pytest.raises(HTTPException) as error:
            await run_renderer(lambda: "must not enter unbounded queue")
        assert error.value.status_code == 429
        tasks[0].cancel()
        await asyncio.sleep(.01)
        assert not tasks[0].done()
        with pytest.raises(HTTPException):
            await run_renderer(lambda: "cancel must not release live thread capacity")
        finish.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert isinstance(results[0], asyncio.CancelledError) and results[1:] == [1, 2, 3]
        assert await run_renderer(lambda: "available again") == "available again"
    asyncio.run(scenario())
