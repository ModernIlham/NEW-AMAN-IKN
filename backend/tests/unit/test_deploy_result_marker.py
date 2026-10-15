"""Workflow check output accepts only the bounded terminal status record."""
import json
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[3] / "scripts/deploy_vps.sh"


@pytest.mark.parametrize("exit_code,phase,recovery", [
    (0, "verifikasi_akhir", 0), (19, "build_frontend", 0),
    (70, "verifikasi_akhir", 1), (70, "private-must-not-appear", 1),
])
def test_terminal_marker_has_only_validated_public_fields(exit_code, phase, recovery):
    shell = '''
source "$1"
AMAN_EMIT_DEPLOY_RESULT=1
DEPLOY_SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
DEPLOY_FASE="$3"
AMAN_DEPLOY_RECOVERY="$4"
AMAN_PRIVATE_SENTINEL=must-never-appear
(exit "$2")
aman_env_bersihkan
'''
    result = subprocess.run(["bash", "-s", "--", str(SCRIPT), str(exit_code), phase, str(recovery)],
                            input=shell, text=True, capture_output=True, timeout=5)
    assert result.returncode == exit_code
    lines = [line for line in result.stdout.splitlines() if line.startswith("AMAN_DEPLOY_RESULT ")]
    assert len(lines) == 1
    record = json.loads(lines[0].removeprefix("AMAN_DEPLOY_RESULT "))
    assert record == {"exit_code":exit_code,"phase":phase if phase != "private-must-not-appear" else "unknown",
                      "deploy_sha":"a"*40,"recovery_required":bool(recovery)}
    assert "private-must-not-appear" not in result.stdout and "must-never-appear" not in result.stdout
