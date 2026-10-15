"""Cardinalité bounded, streaming, absence PII, alert hysteresis/recovery."""
import asyncio
import json
from types import SimpleNamespace

import httpx
from fastapi import APIRouter,FastAPI
from fastapi.responses import StreamingResponse
import pytest

from runtime_observability import AlertEngine,BUCKETS,RuntimeMetrics,RuntimeMetricsMiddleware,age_seconds


class Clock:
    def __init__(self): self.value=0
    def __call__(self): return self.value


def test_raw_ids_search_nip_and_query_never_enter_route_metrics():
    clock=Clock()
    metrics=RuntimeMetrics(enabled=True,max_routes=3,clock=clock)
    metrics.configure_routes([SimpleNamespace(path="/api/assets/{asset_id}")])
    for index in range(2000):
        metrics.observe("GET","/api/assets/"+str(index)+"?search=private-nip-123456789012345678",404,10)
    metrics.observe("GET","/api/assets/{asset_id}",200,23)
    snapshot=metrics.snapshot()
    text=json.dumps(snapshot)
    assert "private-nip" not in text and "123456789012345678" not in text and "search=" not in text
    assert len(snapshot["routes"])==2
    assert snapshot["routes"]["GET <unmatched>"]["requests"]==2000
    assert snapshot["routes"]["GET /api/assets/{asset_id}"]["p95_upper_bound_ms"]==25


def test_known_routes_overflow_and_minute_windows_do_not_grow_forever():
    clock=Clock()
    metrics=RuntimeMetrics(enabled=True,max_routes=3,clock=clock)
    metrics.configure_routes([SimpleNamespace(path="/api/route/"+str(index)) for index in range(100)])
    for index in range(100):
        metrics.observe("GET","/api/route/"+str(index),200,2)
    assert len(metrics.snapshot()["routes"])==4
    for index in range(20):
        clock.value+=60
        metrics.observe("GET","/api/route/0",503,40000)
    value=metrics.snapshot()
    assert len(metrics.windows)<=5
    assert value["totals"]["requests"]==5
    assert value["totals"]["p95_upper_bound_ms"] is None
    assert value["totals"]["status_counts"]=={"503":5}
    assert value["scope"]=="process" and value["observer_update_ns_average"]>0


def test_disabled_metrics_are_explicit_and_collect_nothing():
    metrics=RuntimeMetrics(enabled=False)
    metrics.observe("GET","/private",200,10)
    assert metrics.snapshot()["totals"]["requests"]==0
    assert metrics.snapshot()["enabled"] is False


def test_alert_hysteresis_dedup_and_pending_recovery_cooldown():
    clock=Clock()
    engine=AlertEngine(fail_samples=2,recover_samples=2,cooldown=60,clock=clock)
    assert engine.update("core_dependency",True) is None
    alarm=engine.update("core_dependency",True)
    assert alarm["alert_state"]=="active"
    for _ in range(100): assert engine.update("core_dependency",True) is None
    assert engine.update("core_dependency",False) is None
    assert engine.update("core_dependency",False) is None
    assert engine.snapshot()["core_dependency"]["notification_pending"] is True
    clock.value=61
    recovery=engine.update("core_dependency",False)
    assert recovery["alert_state"]=="recovered"
    assert engine.update("core_dependency",False) is None
    with pytest.raises(ValueError): engine.update("request-user-id-secret",True)


def test_optional_warning_does_not_impersonate_core503_and_recovery_is_distinct():
    metrics=RuntimeMetrics(enabled=True)
    metrics.engine=AlertEngine(fail_samples=1,recover_samples=1,cooldown=0)
    metrics.probes={"collected":True,"core_ok":True,"redis_ok":False,"index_failures":1,
                    "maintenance":True,"recovery_required":True,"disk_free_mb":10000,"disk_free_percent":50}
    events=metrics.evaluate()
    names={event["alert_name"] for event in events}
    assert {"redis_warning","index_warning","maintenance","recovery_required"}.issubset(names)
    assert "core_dependency" not in names
    metrics.probes.update(core_ok=False,redis_ok=True,index_failures=0,maintenance=False,recovery_required=False)
    events=metrics.evaluate()
    assert any(e["alert_name"]=="core_dependency" and e["alert_state"]=="active" for e in events)
    assert any(e["alert_name"]=="redis_warning" and e["alert_state"]=="recovered" for e in events)


@pytest.mark.asyncio
async def test_real_asgi_middleware_counts_stream_to_completion_and_failure_without_body_capture():
    metrics=RuntimeMetrics(enabled=True)
    app=FastAPI()
    @app.get("/assets/{asset_id}")
    async def item(asset_id:str):
        async def body():
            yield b"private-photo-content"
            await asyncio.sleep(.01)
            yield b"remaining-photo-content"
        return StreamingResponse(body())
    @app.get("/failed/{asset_id}")
    async def failed(asset_id:str):
        raise RuntimeError("private detail must not enter metrics")
    metrics.configure_routes(app.routes)
    app.add_middleware(RuntimeMetricsMiddleware,observer=metrics)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,raise_app_exceptions=False),base_url="http://fixture") as client:
        response=await client.get("/assets/private-nip-123456789012345678?token=secret")
        assert response.content==b"private-photo-contentremaining-photo-content"
        assert (await client.get("/failed/secret-id")).status_code==500
    value=metrics.snapshot()
    text=json.dumps(value)
    assert "GET /assets/{asset_id}" in value["routes"]
    assert value["routes"]["GET /failed/{asset_id}"]["errors_5xx"]==1
    assert "private-photo" not in text and "private-nip" not in text and "secret-id" not in text
    assert value["routes"]["GET /assets/{asset_id}"]["duration_ms_sum"]>=10


def test_age_parser_never_reports_negative_or_exposes_values():
    assert age_seconds("invalid")==None
    assert age_seconds("2999-01-01T00:00:00Z")==0


@pytest.mark.asyncio
async def test_collector_samples_current_process_and_cancels_cleanly(monkeypatch):
    import runtime_observability as module
    async def probe():
        return {"collected":True,"core_ok":True,"index_failures":0}
    monkeypatch.setattr(module,"collect_probes",probe)
    observer=RuntimeMetrics(enabled=True)
    task=asyncio.create_task(module.collector(observer))
    await asyncio.sleep(1.08)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert observer.probes["core_ok"] is True
    assert len(observer.loop_lags)==1
    assert observer.resources["rss_bytes"]>0
    assert observer.resources["rss_source"] in ["current_proc_statm","peak_ru_maxrss_linux"]


def test_alert_transition_fields_survive_json_log_formatter_without_sensitive_dimensions():
    import logging
    from log_setup import JsonLogFormatter
    event=AlertEngine(fail_samples=1,cooldown=0).update("redis_warning",True,False)
    record=logging.LogRecord("fixture",logging.WARNING,"fixture",1,"runtime_alert",(),None)
    for key,value in event.items(): setattr(record,key,value)
    value=json.loads(JsonLogFormatter().format(record))
    assert value["event"]=="runtime_alert" and value["alert_name"]=="redis_warning"
    assert value["alert_state"]=="active" and value["observed_value"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("mounted",[False,True])
async def test_nested_includes_reused_at_multiple_prefixes_keep_only_declared_templates(mounted):
    metrics=RuntimeMetrics(enabled=True)
    child=APIRouter(prefix="/assets")
    @child.get("/{asset_id}")
    async def asset(asset_id:str):
        return {"body":"private-body"}
    parent=APIRouter(prefix="/api")
    parent.include_router(child,prefix="/inventory")
    included=FastAPI()
    included.include_router(parent,prefix="/first")
    included.include_router(parent,prefix="/second")
    app=FastAPI()
    if mounted:
        app.mount("/tenants/{tenant_id}",included)
    else:
        app=included
    metrics.configure_routes(app.routes)
    app.add_middleware(RuntimeMetricsMiddleware,observer=metrics)
    prefix="/tenants/private-tenant" if mounted else ""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://fixture") as client:
        for inclusion in ["first","second"]:
            for index in range(20):
                response=await client.get(prefix+f"/{inclusion}/api/inventory/assets/private-id-{index}?token=private-token")
                assert response.status_code==200
        assert (await client.get(prefix+"/unknown/private-path?search=private-nip")).status_code==404
    value=metrics.snapshot()
    template_prefix="/tenants/{tenant_id}" if mounted else ""
    for inclusion in ["first","second"]:
        key="GET "+template_prefix+f"/{inclusion}/api/inventory/assets/{{asset_id}}"
        assert value["routes"][key]["requests"]==20
    assert value["routes"]["GET <unmatched>"]["requests"]==1
    assert len(value["routes"])==3
    serialized=json.dumps(value)
    assert all(private not in serialized for private in ["private-tenant","private-id","private-token","private-path","private-nip","private-body"])


def test_route_identity_and_converter_template_are_registered_without_request_labels():
    app=FastAPI()
    @app.get("/assets/{asset_id:int}")
    async def asset(asset_id:int):
        return {}
    metrics=RuntimeMetrics(enabled=True)
    metrics.configure_routes(app.routes)
    route=next(route for route in app.routes if getattr(route,"path",None)=="/assets/{asset_id:int}")
    assert metrics.route_template(route,"/assets/123")=="/assets/{asset_id}"
    assert metrics.route_template(route,"/assets/private-nip") is None
    assert metrics.route_template(SimpleNamespace(path=route.path),"/assets/123") is None
    before=set(metrics.routes)
    for index in range(2000):
        assert metrics.route_template(route,"/assets/private-nip-"+str(index)) is None
    assert metrics.routes==before
