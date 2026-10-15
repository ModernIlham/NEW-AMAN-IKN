"""Actual deployer DB-binding predicate without private-value diagnostics."""
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[3]
source=(ROOT/'scripts/deploy_vps.sh').read_text().split("<<'PYDATABASE'\n",1)[1].split('\nPYDATABASE',1)[0]
namespace={'__name__':'binding_unit'};exec(compile(source,'deploy_database_binding','exec'),namespace)
verify=namespace['verify_database_binding']

@pytest.mark.parametrize('override,accepted',[
    ('',True),('MONGO_URL=mongodb://private.fixture/\0DB_NAME=fixture',True),
    ('MONGO_URL=mongodb://other.fixture/',False),('DB_NAME=other',False),
])
def test_loaded_process_must_bind_same_database(tmp_path,override,accepted):
    (tmp_path/'backend').mkdir();(tmp_path/'backend/.env').write_text('MONGO_URL=mongodb://private.fixture/\nDB_NAME=fixture\n')
    config=tmp_path/'supervisor.conf';config.write_text('[program:inventarisasi-backend]\nenvironment=PATH="/safe"\n')
    process=tmp_path/'proc/123';process.mkdir(parents=True);(process/'environ').write_bytes(override.encode())
    if accepted:verify(tmp_path,123,config,tmp_path/'proc')
    else:
        with pytest.raises(ValueError) as error:verify(tmp_path,123,config,tmp_path/'proc')
        assert 'fixture' not in str(error.value)

@pytest.mark.parametrize('key',['MONGO_URL','DB_NAME'])
def test_supervisor_storage_override_is_rejected_before_any_mutation(tmp_path,key):
    (tmp_path/'backend').mkdir();(tmp_path/'backend/.env').write_text('MONGO_URL=mongodb://private.fixture/\n')
    config=tmp_path/'supervisor.conf';config.write_text('[program:inventarisasi-backend]\nenvironment='+key+'="private-sentinel"\n')
    with pytest.raises(ValueError) as error:verify(tmp_path,123,config,tmp_path/'proc')
    assert 'private-sentinel' not in str(error.value)
