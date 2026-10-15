"""Real private-file transactions with fault-injected external service/DB edges."""
import importlib.util
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[3]
SPEC=importlib.util.spec_from_file_location('budget_activation',ROOT/'scripts/activate_export_budget.py')
ops=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(ops)
OLD_CAP={'enabled':False,'ok':True,'slots':2,'satker_slots':2,'error_category':None}


class Runtime:
    sha='a'*40
    def __init__(self,tmp_path,fault=None):
        self.lock_dir=tmp_path/'locks';self.env=tmp_path/'backend.env'
        self.env.write_bytes(b'# private sentinel\r\nJWT_SECRET=never-print-me\r\nOTHER=value')
        self.env.chmod(0o600);self.original=self.env.read_bytes();self.service='RUNNING'
        self.owner=None;self.events=[];self.capability=dict(OLD_CAP);self.fault=fault;self.counts={}
    def event(self,name):
        self.events.append(name);self.counts[name]=self.counts.get(name,0)+1
        if self.fault==name and self.counts[name]==1:raise RuntimeError('private-error-never-log')
    def environment_bytes(self):return self.env.read_bytes()
    def preflight(self,expected_capability=None):
        self.event('preflight')
        if expected_capability is not None:assert self.capability==expected_capability
        return self.environment_bytes(),self.env.stat(),dict(self.capability)
    def acquire(self,owner):
        self.event('acquire');assert self.owner is None;self.owner=owner
        if self.fault=='acquire_ack_lost':raise RuntimeError('ack lost')
    def assert_owner(self,owner):
        self.event('assert_owner');assert self.owner==owner
    def drain(self):self.event('drain')
    def physical_locks(self,create=False):self.event('physical');ops.lock_directory(self.lock_dir,create)
    def stop(self):
        self.event('stop');self.service='STOPPED'
        if self.fault=='stop_after_state' and self.counts['stop']==1:raise RuntimeError('stopped but ack lost')
        if self.fault=='rollback_stop' and self.counts['stop']>1:raise RuntimeError('unproven stop')
    def start(self):
        assert self.service=='STOPPED';self.service='RUNNING'
        self.capability=dict(ops.EXPECTED_CAPABILITY if b'AMAN_EXPORT_GLOBAL_BUDGET_ENABLED=1' in self.environment_bytes() else OLD_CAP)
        self.event('start')
    def install_environment(self,data,mode):
        assert self.service=='STOPPED';ops.atomic_bytes(self.env,data,mode);self.event('install')
        if self.fault=='signal_install' and self.counts['install']==1:raise KeyboardInterrupt()
    def verify(self,capability):
        assert self.service=='RUNNING';assert self.capability==capability;self.event('verify')
        if self.fault=='rollback_stop' and self.counts['verify']==1:raise RuntimeError('force compensation')
    def release(self,owner):
        self.event('release');assert self.owner==owner;self.owner=None
        if self.fault=='release_ack_lost':raise RuntimeError('committed ack lost')
        if self.fault=='release_new_owner':self.owner='restore:new';raise RuntimeError('new owner admitted')
    def smoke(self):
        self.event('smoke')
        assert self.owner is None and self.capability==ops.EXPECTED_CAPABILITY
        if self.fault=='smoke_new_restore':self.owner='restore:new';raise RuntimeError('restore started')
        if self.fault=='signal_smoke':raise KeyboardInterrupt()
        return {'blocked_status':429,'document_status':200,'accounts_created':0,'customer_data_read':False}


def test_activation_and_explicit_rollback_preserve_all_original_bytes(tmp_path):
    runtime=Runtime(tmp_path);journal=tmp_path/'journal'
    result=ops.activate(runtime,journal)
    assert result['ok'] and result['capability']==ops.EXPECTED_CAPABILITY
    assert runtime.environment_bytes().startswith(runtime.original+b'\n# AMAN')
    assert stat.S_IMODE(runtime.env.stat().st_mode)==0o600
    assert stat.S_IMODE(journal.stat().st_mode)==0o700
    assert stat.S_IMODE((journal/'backend.env').stat().st_mode)==0o600
    assert (journal/'backend.env').read_bytes()==runtime.original
    assert runtime.owner is None
    result=ops.activate(runtime,journal,rollback=True)
    assert result['operation']=='rollback'
    assert runtime.environment_bytes()==runtime.original and runtime.capability==OLD_CAP
    assert runtime.owner is None


@pytest.mark.parametrize('fault',['drain','physical','stop','stop_after_state','install','start','verify','signal_install'])
def test_each_pre_release_failure_retains_or_restores_healthy_old_config(tmp_path,fault):
    runtime=Runtime(tmp_path,fault)
    with pytest.raises(RuntimeError):ops.activate(runtime,tmp_path/'journal')
    assert runtime.environment_bytes()==runtime.original
    assert runtime.service=='RUNNING' and runtime.capability==OLD_CAP
    assert runtime.owner is None


@pytest.mark.parametrize('fault',['release_ack_lost','release_new_owner'])
def test_unknown_release_ack_never_mutates_after_release(tmp_path,fault):
    runtime=Runtime(tmp_path,fault);journal=tmp_path/'journal'
    with pytest.raises(RuntimeError,match='preserve current healthy'):ops.activate(runtime,journal)
    assert runtime.events[-1]=='release'
    assert runtime.capability==ops.EXPECTED_CAPABILITY and runtime.service=='RUNNING'
    assert runtime.events.count('stop')==1 and runtime.events.count('release')==1
    assert runtime.owner==('restore:new' if fault=='release_new_owner' else None)
    assert json.loads((journal/'state.json').read_text())['phase']=='release_acknowledgement_unknown'


def test_unknown_acquire_ack_never_touches_service_or_config(tmp_path):
    runtime=Runtime(tmp_path,'acquire_ack_lost');journal=tmp_path/'journal'
    with pytest.raises(RuntimeError,match='acquisition unverified'):ops.activate(runtime,journal)
    assert runtime.events==['preflight','acquire']
    assert runtime.owner and runtime.environment_bytes()==runtime.original


def test_failed_compensation_retains_mutex_and_private_snapshot(tmp_path):
    runtime=Runtime(tmp_path,'rollback_stop');journal=tmp_path/'journal'
    with pytest.raises(RuntimeError,match='RECOVERY_REQUIRED'):ops.activate(runtime,journal)
    assert runtime.owner is not None and (journal/'backend.env').read_bytes()==runtime.original
    assert json.loads((journal/'state.json').read_text())['phase']=='recovery_required'


def test_later_operator_change_cannot_be_overwritten_by_journal(tmp_path):
    runtime=Runtime(tmp_path);journal=tmp_path/'journal';ops.activate(runtime,journal)
    runtime.env.write_bytes(runtime.environment_bytes()+b'\nOTHER_OPERATOR_CHANGE=1\n')
    events=list(runtime.events)
    with pytest.raises(ValueError,match='changed'):ops.activate(runtime,journal,rollback=True)
    assert runtime.events==events


def test_physical_slot_is_never_unlinked_or_stolen(tmp_path):
    import fcntl
    directory=tmp_path/'locks';directory.mkdir(mode=0o700)
    target=directory/'cpu-0.lock';target.touch(mode=0o600);inode=target.stat().st_ino
    fd=os.open(target,os.O_RDWR);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:
        with pytest.raises(BlockingIOError):ops.lock_directory(directory)
        assert target.stat().st_ino==inode
    finally:os.close(fd)
    ops.lock_directory(directory)


@pytest.mark.parametrize('case',['symlink','capacity','permission','unexpected'])
def test_unsafe_physical_configuration_rejected(tmp_path,case):
    directory=tmp_path/'locks';directory.mkdir(mode=0o700)
    if case=='symlink':(directory/'cpu-0.lock').symlink_to(tmp_path/'elsewhere')
    elif case=='capacity':(directory/'configuration.json').write_text('{"schema":1,"capacity":2,"satker_slots":2}')
    elif case=='permission':directory.chmod(0o755)
    else:(directory/'unexpected.txt').write_text('unknown')
    with pytest.raises((ValueError,FileNotFoundError)):ops.lock_directory(directory)


def test_private_data_never_appears_in_results_or_errors(tmp_path,capsys):
    runtime=Runtime(tmp_path,'verify')
    with pytest.raises(RuntimeError) as error:ops.activate(runtime,tmp_path/'journal')
    text=str(error.value)+''.join(capsys.readouterr())
    assert 'never-print-me' not in text and 'private-error-never-log' not in text


def test_post_release_public_smoke_runs_outside_first_mutex(tmp_path):
    runtime=Runtime(tmp_path);journal=tmp_path/'journal'
    result=ops.activate_with_smoke(runtime,journal)
    assert runtime.events.index('release')<runtime.events.index('smoke')
    assert result['public_document_smoke']['document_status']==200
    assert json.loads((journal/'state.json').read_text())['smoke']['accounts_created']==0


@pytest.mark.parametrize('fault',['smoke','signal_smoke'])
def test_failed_post_release_smoke_uses_fresh_mutex_and_drain_before_rollback(tmp_path,fault):
    runtime=Runtime(tmp_path,fault);journal=tmp_path/'journal'
    with pytest.raises(RuntimeError,match='fresh-mutex rollback restored'):ops.activate_with_smoke(runtime,journal)
    assert runtime.counts['acquire']==2 and runtime.counts['drain']==2
    assert runtime.environment_bytes()==runtime.original and runtime.capability==OLD_CAP and runtime.owner is None
    assert runtime.events.index('smoke')<len(runtime.events)-1-runtime.events[::-1].index('acquire')


def test_new_restore_during_smoke_is_never_overwritten(tmp_path):
    runtime=Runtime(tmp_path,'smoke_new_restore');journal=tmp_path/'journal'
    with pytest.raises(RuntimeError,match='RECOVERY_REQUIRED'):ops.activate_with_smoke(runtime,journal)
    assert runtime.owner=='restore:new' and runtime.capability==ops.EXPECTED_CAPABILITY
    assert runtime.counts['stop']==1 and runtime.counts['install']==1
