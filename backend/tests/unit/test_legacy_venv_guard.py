"""Legacy activation must never fall through to system pip for a pipless env."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("script",["update-all.sh","vps-fix.sh","vps-deploy.sh"])
@pytest.mark.parametrize("layout",["managed-root","stable-symlink","pipless-directory"])
def test_legacy_entrypoints_stop_before_any_mutation_for_managed_environment(tmp_path,script,layout):
    app=tmp_path/"app";(app/"backend").mkdir(parents=True)
    if layout=="managed-root":(app/"backend/.venv-releases").mkdir()
    elif layout=="stable-symlink":(app/"backend/venv").symlink_to(tmp_path/"not-followed",target_is_directory=True)
    else:(app/"backend/venv").mkdir()
    commands=tmp_path/"commands";commands.mkdir()
    audit=tmp_path/"unexpected-command"
    for name in ["git","mkdir","cp","pip","python3.11","sudo","date"]:
        path=commands/name
        path.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$0" >> "$GUARD_AUDIT"\nexit 99\n')
        path.chmod(0o755)
    result=subprocess.run(["bash",str(ROOT/"scripts"/script)],cwd=ROOT,
        env=dict(os.environ,APP_DIR=str(app),GUARD_AUDIT=str(audit),PATH=str(commands)+os.pathsep+os.environ["PATH"]),
        capture_output=True,text=True,timeout=10)
    assert result.returncode==1
    assert "managed/pipless" in result.stderr and "deploy_vps.sh" in result.stderr
    assert not audit.exists()
