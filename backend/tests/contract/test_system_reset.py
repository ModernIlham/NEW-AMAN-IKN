"""Destructive reset contract uses its own loopback DB, separate from fixture."""
import asyncio
import os
from pathlib import Path
import sys
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


@pytest.mark.parametrize("scenario", ["success-race", "rollback", "failed-rollback", "killed-worker"])
async def test_system_reset_is_fenced_verified_and_recoverable(contract, tmp_path, scenario):
    assert os.environ["AMAN_CONTRACT_MONGO_URL"].startswith("mongodb://")
    probe = Path(__file__).with_name("_reset_probe.py")
    database = "aman_ci_reset_" + uuid.uuid4().hex
    process = await asyncio.create_subprocess_exec(sys.executable, str(probe), scenario, database, str(tmp_path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        output, errors = await asyncio.wait_for(process.communicate(), 90)
    except BaseException:
        process.kill()
        await process.wait()
        raise
    assert process.returncode == 0, errors.decode()[-7000:]
    assert '"passed": true' in output.decode()
