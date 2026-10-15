"""Actual health attests loaded budget config, never claims physical lock proof."""
import json

import pytest

pytestmark=[pytest.mark.integration,pytest.mark.asyncio(loop_scope="session")]


@pytest.mark.parametrize("flag",["0","1"])
async def test_health_reports_actual_loaded_budget_flag_and_cap_without_storage_io(contract,monkeypatch,flag):
    import export_budget
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_BUDGET_ENABLED",flag)
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_SLOTS","1")
    monkeypatch.setenv("AMAN_EXPORT_SATKER_SLOTS","1")
    def forbidden(*args,**kwargs):
        raise AssertionError("health must not touch physical configuration")
    monkeypatch.setattr(export_budget,"_lock_directory",forbidden)
    monkeypatch.setattr(export_budget,"_configuration",forbidden)
    before=await contract.db.export_resource_budget.count_documents({})
    response=await contract.http.get("/api/health")
    assert response.status_code==200,response.text
    value=response.json()
    assert value["ok"] is True and value["release_sha"]
    capability=value["capabilities"]["export_global_budget"]
    assert capability=={"enabled":flag=="1","ok":True,"slots":1,"satker_slots":1,"error_category":None}
    assert await contract.db.export_resource_budget.count_documents({})==before
    assert all(private not in json.dumps(capability) for private in ["pid","uid","path","database","secret"])


@pytest.mark.parametrize("flag,global_slots,satker_slots,error",[
    ("1","NaN","1","invalid_capacity_configuration"),
    ("1","0","1","invalid_capacity_configuration"),
    ("1","1","2","invalid_capacity_configuration"),
    ("private-invalid-flag","1","1","invalid_enable_flag"),
])
async def test_health_never_reports_invalid_budget_configuration_as_ready(contract,monkeypatch,flag,global_slots,satker_slots,error):
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_BUDGET_ENABLED",flag)
    monkeypatch.setenv("AMAN_EXPORT_GLOBAL_SLOTS",global_slots)
    monkeypatch.setenv("AMAN_EXPORT_SATKER_SLOTS",satker_slots)
    response=await contract.http.get("/api/health")
    assert response.status_code==200,response.text
    capability=response.json()["capabilities"]["export_global_budget"]
    assert capability["ok"] is False and capability["slots"]==0 and capability["satker_slots"]==0
    assert capability["error_category"]==error
    assert "private-invalid-flag" not in response.text and "NaN" not in response.text
