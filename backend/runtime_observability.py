"""Observabilitas bounded per-process; tanpa payload, query, identitas, atau PII.

Collector optional AMAN_OBSERVABILITY_ENABLED=1. Snapshot bukan agregat seluruh
worker. Fixed histogram/window mencegah raw latency samples tumbuh tanpa batas.
"""
import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime,timezone
import logging
import math
import os
from pathlib import Path
import shutil
import time
from release_info import RELEASE_SHA
from starlette.routing import compile_path
try:
    import resource
except ImportError:  # Windows developer environment; Linux VPS uses /proc.
    resource=None

logger=logging.getLogger(__name__)
BUCKETS=(5,10,25,50,100,250,500,1000,2000,5000,10000,30000)
METHODS={"GET","POST","PUT","PATCH","DELETE","HEAD","OPTIONS"}
STATUS_CODES={200,201,202,204,206,304,400,401,403,404,409,413,422,423,429,500,502,503,504}
ALERTS={"core_dependency","redis_warning","index_warning","maintenance","recovery_required",
        "disk_critical","disk_warning","backup_stale","export_queue_age","event_loop_lag",
        "http_server_error","request_p95","probe_unavailable"}
ROOT=Path(__file__).resolve().parent


def setting(name,default,low,high):
    try:
        value=float(os.environ.get(name,default))
        return value if math.isfinite(value) and low<=value<=high else default
    except ValueError:
        return default


@dataclass
class AlertState:
    active:bool=False
    bad:int=0
    good:int=0
    notified:bool=False
    last_emitted:float=float("-inf")


class AlertEngine:
    def __init__(self,fail_samples=3,recover_samples=3,cooldown=60,clock=time.monotonic):
        self.fail_samples,self.recover_samples,self.cooldown=fail_samples,recover_samples,cooldown
        self.clock=clock
        self.states={name:AlertState() for name in ALERTS}

    def update(self,name,bad,value=None,severity="warning"):
        if name not in self.states:
            raise ValueError("Unknown bounded alert")
        state=self.states[name]
        state.bad=state.bad+1 if bad else 0
        state.good=state.good+1 if not bad else 0
        if state.bad>=self.fail_samples:
            state.active=True
        elif state.good>=self.recover_samples:
            state.active=False
        now=self.clock()
        if state.active!=state.notified and now-state.last_emitted>=self.cooldown:
            state.notified=state.active
            state.last_emitted=now
            return {"event":"runtime_alert","alert_name":name,
                "alert_state":"active" if state.active else "recovered","severity":severity,
                "observed_value":value,"process_id":os.getpid()}
        return None

    def snapshot(self):
        return {name:{"active":state.active,"notification_pending":state.active!=state.notified}
                for name,state in sorted(self.states.items())}


def empty_histogram():
    return {"count":0,"errors_5xx":0,"status_counts":{},"latency_buckets":[0]*(len(BUCKETS)+1),"duration_ms_sum":0.0}


def add_histogram(target,source):
    target["count"]+=source["count"]
    target["errors_5xx"]+=source["errors_5xx"]
    target["duration_ms_sum"]+=source["duration_ms_sum"]
    for code,count in source["status_counts"].items():
        target["status_counts"][code]=target["status_counts"].get(code,0)+count
    for index,count in enumerate(source["latency_buckets"]):
        target["latency_buckets"][index]+=count


def summarize(histogram):
    result={"requests":histogram["count"],"errors_5xx":histogram["errors_5xx"],
        "status_counts":histogram["status_counts"],"latency_bucket_counts":histogram["latency_buckets"],
        "duration_ms_sum":round(histogram["duration_ms_sum"],2)}
    for percentile in [50,95,99]:
        rank=math.ceil(histogram["count"]*percentile/100)
        found=None
        if rank:
            seen=0
            for index,count in enumerate(histogram["latency_buckets"]):
                seen+=count
                if seen>=rank:
                    found=BUCKETS[index] if index<len(BUCKETS) else None
                    break
        result[f"p{percentile}_upper_bound_ms"]=found
    return result


def configured_route_templates(routes, prefix="", ancestors=frozenset()):
    """Walk trusted route declarations, including lazy includes and mounts.

    FastAPI 0.143 keeps the original APIRoute in scope while adding prefixes
    through _IncludedRouter. Do not build metric dimensions from request data
    or rely on flat app.routes, which only contains wrapper branches there.
    """
    for route in routes:
        if id(route) in ancestors:
            continue
        branch = ancestors | {id(route)}
        included = getattr(route, "original_router", None)
        context = getattr(route, "include_context", None)
        include_prefix = getattr(context, "prefix", None)
        if included is not None and isinstance(include_prefix, str):
            yield from configured_route_templates(included.routes, prefix + include_prefix, branch)
            continue
        path = getattr(route, "path", None)
        children = getattr(route, "routes", None)
        if children:
            yield from configured_route_templates(children, prefix + (path or ""), branch)
        elif isinstance(path, str):
            pattern, template, _ = compile_path(prefix + path)
            yield route, pattern, template


class RuntimeMetrics:
    def __init__(self,enabled=False,max_routes=256,window_seconds=300,clock=time.monotonic):
        self.enabled,self.max_routes,self.window_seconds,self.clock=enabled,max_routes,window_seconds,clock
        self.routes=set()
        self.route_patterns={}
        self.known=set()
        self.windows={}
        self.update_ns=0
        self.updates=0
        self.started=clock()
        self.resources={}
        self.probes={"collected":False}
        self.loop_lags=deque(maxlen=60)
        self.task=None
        self.release_sha=RELEASE_SHA
        self.engine=AlertEngine(int(setting("AMAN_ALERT_FAILURE_SAMPLES",3,1,120)),
            int(setting("AMAN_ALERT_RECOVERY_SAMPLES",3,1,120)),
            setting("AMAN_ALERT_COOLDOWN_SECONDS",60,1,3600),clock)
        self.error_threshold=setting("AMAN_SLO_ERROR_RATIO",.01,.0001,.1)
        self.p95_threshold=setting("AMAN_SLO_P95_MS",2000,10,30000)
        self.loop_threshold=setting("AMAN_SLO_LOOP_LAG_MS",200,1,10000)
        self.queue_threshold=setting("AMAN_SLO_QUEUE_AGE_SECONDS",120,1,86400)
        self.backup_threshold=setting("AMAN_SLO_BACKUP_AGE_HOURS",48,1,720)

    def configure_routes(self,routes):
        self.routes=set()
        self.route_patterns={}
        for route,pattern,template in configured_route_templates(routes):
            self.routes.add(template)
            self.route_patterns.setdefault(id(route),[]).append((pattern,template))

    def route_template(self,route,request_path):
        # Identity binds this to the framework-selected, configured route.
        # Only static declared templates can leave this method. Request paths
        # are transient match inputs, never stored or added to the allowlist.
        for pattern,template in self.route_patterns.get(id(route),()):
            if pattern.fullmatch(request_path):
                return template
        return None

    def _trim(self):
        cutoff=int(self.clock()//60)-math.ceil(self.window_seconds/60)+1
        for key in list(self.windows):
            if key<cutoff:
                del self.windows[key]

    def observe(self,method,template,status,duration_ms):
        if not self.enabled:
            return
        began=time.perf_counter_ns()
        self._trim()
        method=method if method in METHODS else "OTHER"
        template=template if template in self.routes else "<unmatched>"
        key=method+" "+template
        if key not in self.known:
            if len(self.known)>=self.max_routes:
                key="OTHER <overflow>"
            else:
                self.known.add(key)
        bucket=self.windows.setdefault(int(self.clock()//60),{})
        stat=bucket.setdefault(key,empty_histogram())
        stat["count"]+=1
        stat["errors_5xx"]+=int(500<=status<=599)
        code=str(status) if status in STATUS_CODES else "other"
        stat["status_counts"][code]=stat["status_counts"].get(code,0)+1
        index=next((index for index,value in enumerate(BUCKETS) if duration_ms<=value),len(BUCKETS))
        stat["latency_buckets"][index]+=1
        stat["duration_ms_sum"]+=duration_ms
        self.updates+=1
        self.update_ns+=time.perf_counter_ns()-began

    def snapshot(self):
        self._trim()
        combined={}
        for window in self.windows.values():
            for key,value in window.items():
                add_histogram(combined.setdefault(key,empty_histogram()),value)
        total=empty_histogram()
        for value in combined.values():
            add_histogram(total,value)
        return {"enabled":self.enabled,"scope":"process","process_id":os.getpid(),
            "aggregation_note":"Setiap worker memiliki histogram sendiri; jangan menjumlahkan percentile atau menganggap snapshot ini seluruh VPS",
            "release_sha":self.release_sha,"uptime_seconds":round(self.clock()-self.started,1),
            "window_seconds":self.window_seconds,"max_route_keys":self.max_routes+1,
            "window_bucket_seconds":60,
            "latency_bucket_upper_bounds_ms":[*BUCKETS,"overflow"],
            "totals":summarize(total),"routes":{key:summarize(value) for key,value in sorted(combined.items())},
            "observer_updates":self.updates,"observer_update_ns_total":self.update_ns,
            "observer_update_ns_average":round(self.update_ns/self.updates) if self.updates else 0,
            "resources":self.resources,"event_loop_lag_last_ms":self.loop_lags[-1] if self.loop_lags else None,
            "event_loop_lag_max_60_samples_ms":max(self.loop_lags,default=None),"probes":self.probes,
            "alerts":self.engine.snapshot(),"thresholds":{"error_ratio":self.error_threshold,
                "p95_ms":self.p95_threshold,"loop_lag_ms":self.loop_threshold,"queue_age_seconds":self.queue_threshold,
                "backup_age_hours":self.backup_threshold},
            "external_notifications":"not_configured; local transition logs only"}

    def evaluate(self):
        totals=self.snapshot()["totals"]
        p=self.probes
        checks={
            "probe_unavailable":(p.get("collected") is False and bool(p.get("failure_kind")),None,"warning"),
            "core_dependency":(p.get("core_ok") is False,p.get("core_ok"),"critical"),
            "redis_warning":(p.get("redis_ok") is False,p.get("redis_ok"),"warning"),
            "index_warning":(p.get("index_failures",0)>0,p.get("index_failures",0),"warning"),
            "maintenance":(p.get("maintenance",False),p.get("maintenance",False),"info"),
            "recovery_required":(p.get("recovery_required",False),p.get("recovery_required",False),"critical"),
            "disk_critical":(p.get("disk_free_mb",1e12)<1024,p.get("disk_free_mb"),"critical"),
            "disk_warning":(p.get("disk_free_percent",100)<15,p.get("disk_free_percent"),"warning"),
            "backup_stale":(p.get("backup_enabled",False) and (p.get("backup_age_hours") is None or p.get("backup_age_hours",0)>self.backup_threshold),p.get("backup_age_hours"),"warning"),
            "export_queue_age":(p.get("oldest_queue_age_seconds",0)>self.queue_threshold,p.get("oldest_queue_age_seconds",0),"warning"),
            "event_loop_lag":(bool(self.loop_lags) and self.loop_lags[-1]>self.loop_threshold,self.loop_lags[-1] if self.loop_lags else None,"warning"),
            "http_server_error":(totals["requests"]>=100 and totals["errors_5xx"]/totals["requests"]>=self.error_threshold,totals["errors_5xx"],"warning"),
            "request_p95":(totals["requests"]>=100 and (totals["p95_upper_bound_ms"] is None or totals["p95_upper_bound_ms"]>self.p95_threshold),totals["p95_upper_bound_ms"],"warning")}
        events=[]
        for name,(bad,value,severity) in checks.items():
            event=self.engine.update(name,bad,value,severity)
            if event:
                events.append(event)
                level=(logging.INFO if event["alert_state"]=="recovered" else
                       logging.ERROR if severity=="critical" else logging.WARNING if severity=="warning" else logging.INFO)
                logger.log(level,"runtime_alert",extra=event)
        return events


OBS=RuntimeMetrics(os.environ.get("AMAN_OBSERVABILITY_ENABLED","0")=="1")


class RuntimeMetricsMiddleware:
    def __init__(self,app,observer=None):
        self.app=app
        self.observer=observer or OBS
        self.failed_update_logged=False

    async def __call__(self,scope,receive,send):
        if scope.get("type")!="http" or not self.observer.enabled:
            return await self.app(scope,receive,send)
        began=time.perf_counter()
        # Capture before a mounted child changes root_path. Strip only this
        # application's deployment prefix; nested mount prefixes remain part
        # of the trusted configured template (including their parameters).
        request_path=scope.get("path","")
        root_path=scope.get("root_path","")
        if root_path and (request_path==root_path or request_path.startswith(root_path+"/")):
            request_path=request_path[len(root_path):] or "/"
        status=500
        async def record_start(message):
            nonlocal status
            if message["type"]=="http.response.start":
                status=int(message["status"])
            await send(message)
        try:
            await self.app(scope,receive,record_start)
        finally:
            route=scope.get("route")
            try:
                template=self.observer.route_template(route,request_path)
                self.observer.observe(scope.get("method"),template,status,
                                      (time.perf_counter()-began)*1000)
            except Exception:
                # Optional instrumentation must never turn a committed HTTP
                # operation into a retriable error or break a media stream.
                if not self.failed_update_logged:
                    logger.warning("runtime_observability_update_failed")
                    self.failed_update_logged=True


def process_resources():
    try:
        resident=int(Path("/proc/self/statm").read_text().split()[1])*os.sysconf("SC_PAGE_SIZE")
        rss_source="current_proc_statm"
    except (OSError,ValueError,IndexError):
        resident=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 if resource else None
        rss_source="peak_ru_maxrss_linux" if resource else "unavailable"
    try:
        fd=len(os.listdir("/proc/self/fd"))
    except OSError:
        fd=None
    return {"rss_bytes":resident,"rss_source":rss_source,"fd_count":fd}


def age_seconds(raw):
    if raw is None:
        return None
    try:
        stamp=datetime.fromisoformat(raw.replace("Z","+00:00")) if isinstance(raw,str) else raw
        if stamp.tzinfo is None:
            stamp=stamp.replace(tzinfo=timezone.utc)
        return max(0,(datetime.now(timezone.utc)-stamp).total_seconds())
    except (ValueError,TypeError,AttributeError):
        return None


async def collect_probes():
    from db import db
    result={"collected":True,"sampled_at":datetime.now(timezone.utc).isoformat(),"failure_kind":None}
    started=time.perf_counter()
    try:
        await asyncio.wait_for(db.command("ping",maxTimeMS=1000),timeout=1)
        await asyncio.wait_for(db["fs.files"].find_one({}, {"_id":1},max_time_ms=1000),timeout=1)
        result["core_ok"]=True
    except Exception:
        result["core_ok"]=False
        result["failure_kind"]="core_dependency_unavailable"
        return result
    result["db_probe_latency_ms"]=round((time.perf_counter()-started)*1000,2)
    from indexes import kegagalan_indeks
    result["index_failures"]=len(kegagalan_indeks())
    from redis_utils import redis_aktif,ping
    if redis_aktif():
        try:
            result["redis_ok"]=bool(await asyncio.wait_for(ping(),timeout=1))
        except Exception:
            result["redis_ok"]=False
    else:
        result["redis_ok"]=None
    control=await db.restore_control.find_one({"_id":"GLOBAL"},{"state":1,"destructive_started":1},max_time_ms=1000)
    from pemeliharaan import pemeliharaan_dari_kontrol
    result["maintenance"]=pemeliharaan_dari_kontrol(control)
    result["recovery_required"]=bool(control and control.get("state")=="recovery_required")
    queue={}
    ages=[]
    for name in ["background_jobs","unduhan"]:
        query={"status":{"$in":["queued","running","importing"]}}
        count=await db[name].count_documents(query,maxTimeMS=1000)
        oldest=await db[name].find_one(query,{"created_at":1},sort=[("created_at",1)],max_time_ms=1000)
        age=age_seconds((oldest or {}).get("created_at"))
        queue[name]={"active":count,"oldest_age_seconds":age}
        if age is not None:
            ages.append(age)
    result["queues"]=queue
    result["oldest_queue_age_seconds"]=max(ages,default=0)
    backup=await db.report_settings.find_one({"type":"backup_otomatis"},{"aktif":1,"terakhir_sukses":1},max_time_ms=1000) or {}
    result["backup_enabled"]=bool(backup.get("aktif"))
    age=age_seconds(backup.get("terakhir_sukses"))
    result["backup_age_hours"]=age/3600 if age is not None else None
    disk=shutil.disk_usage(ROOT)
    result["disk_free_mb"]=disk.free//(1024*1024)
    result["disk_free_percent"]=round(disk.free/disk.total*100,1)
    return result


async def collector(observer=OBS):
    loop=asyncio.get_running_loop()
    next_tick=loop.time()+1
    probe_due=0
    while True:
        await asyncio.sleep(max(0,next_tick-loop.time()))
        now=loop.time()
        observer.loop_lags.append(round(max(0,now-next_tick)*1000,2))
        observer.resources=process_resources()
        next_tick=now+1
        if now>=probe_due:
            try:
                observer.probes={**observer.probes,**await asyncio.wait_for(collect_probes(),timeout=3)}
            except asyncio.CancelledError:
                raise
            except Exception:
                observer.probes={**observer.probes,"collected":False,"failure_kind":"bounded_probe_failed"}
            probe_due=loop.time()+30
            # Do not count probe latency as event-loop scheduling lag.
            next_tick=loop.time()+1
        observer.evaluate()


def start_observability(app):
    OBS.configure_routes(app.routes)
    if OBS.enabled and (OBS.task is None or OBS.task.done()):
        OBS.task=asyncio.create_task(collector())


async def stop_observability():
    task,OBS.task=OBS.task,None
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.warning("runtime_observability_collector_stopped_unexpectedly")
