"""Endpoint observability nyata: auth pusat, cardinality, Mongo probes tanpa PII."""
import json
from datetime import datetime,timedelta,timezone
import logging
import uuid

import pytest

pytestmark=[pytest.mark.integration,pytest.mark.asyncio(loop_scope="session")]


async def test_actual_endpoint_is_central_admin_only_and_uses_route_templates(contract):
    from runtime_observability import OBS,collect_probes
    before=OBS.enabled
    OBS.enabled=True
    OBS.configure_routes(contract.app.routes)
    OBS.windows.clear()
    OBS.known.clear()
    try:
        assert (await contract.http.get("/api/system/observability")).status_code in [401,403]
        assert (await contract.http.get("/api/system/observability",headers=contract.headers["a"])).status_code==403
        for index in range(30):
            await contract.http.get("/api/assets/private-identifier-"+str(index)+"?search=private-nip-123456789012345678&token=private-token",
                                    headers=contract.headers["a"])
        response=await contract.http.get("/api/system/observability",headers=contract.headers["root"])
        assert response.status_code==200,response.text
        value=response.json()
        assert value["scope"]=="process" and value["enabled"] is True
        assert value["release_sha"]==(await contract.http.get("/api/health")).json()["release_sha"]
        assert "GET /api/assets/{asset_id}" in value["routes"]
        text=json.dumps(value)
        assert "private-identifier" not in text and "private-nip" not in text and "private-token" not in text
        assert len(value["routes"])<=value["max_route_keys"]
        probes=await collect_probes()
        assert probes["core_ok"] is True and probes["collected"] is True
        assert "background_jobs" in probes["queues"] and "unduhan" in probes["queues"]
        assert contract.database not in json.dumps(probes)
    finally:
        OBS.enabled=before
        OBS.windows.clear()
        OBS.known.clear()


async def test_actual_queue_probe_alert_transition_and_healthy_recovery_are_exposed_and_logged(contract,caplog):
    from runtime_observability import OBS,AlertEngine,collect_probes
    previous=(OBS.enabled,OBS.engine,OBS.probes,OBS.queue_threshold)
    identifier="observability-fixture-"+uuid.uuid4().hex
    baseline=await collect_probes()
    OBS.enabled=True
    OBS.engine=AlertEngine(fail_samples=2,recover_samples=2,cooldown=0)
    OBS.queue_threshold=baseline.get("oldest_queue_age_seconds",0)+30
    caplog.set_level(logging.INFO,logger="runtime_observability")
    try:
        await contract.db.background_jobs.insert_one({"id":identifier,"status":"queued",
            "created_at":(datetime.now(timezone.utc)-timedelta(seconds=OBS.queue_threshold+600)).isoformat()})
        OBS.probes=await collect_probes()
        assert OBS.probes["core_ok"] is True
        assert OBS.probes["queues"]["background_jobs"]["oldest_age_seconds"]>OBS.queue_threshold
        OBS.evaluate()
        assert OBS.engine.snapshot()["export_queue_age"]["active"] is False
        OBS.evaluate()
        response=await contract.http.get("/api/system/observability",headers=contract.headers["root"])
        assert response.status_code==200
        assert response.json()["alerts"]["export_queue_age"]["active"] is True
        # Real database completion produces a healthy probe; no injected
        # "healthy" value or external notification is used.
        await contract.db.background_jobs.delete_one({"id":identifier})
        OBS.probes=await collect_probes()
        assert OBS.probes["oldest_queue_age_seconds"]<OBS.queue_threshold
        OBS.evaluate();OBS.evaluate()
        response=await contract.http.get("/api/system/observability",headers=contract.headers["root"])
        assert response.json()["alerts"]["export_queue_age"]["active"] is False
        records=[record for record in caplog.records if getattr(record,"alert_name",None)=="export_queue_age"]
        assert [record.alert_state for record in records]==["active","recovered"]
        assert all(record.event=="runtime_alert" for record in records)
        assert identifier not in json.dumps(response.json())
    finally:
        await contract.db.background_jobs.delete_one({"id":identifier})
        OBS.enabled,OBS.engine,OBS.probes,OBS.queue_threshold=previous
