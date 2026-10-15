"""Durasi berakhir saat HTTP masih hidup: grace menunggu, tanpa retry/ignore."""
import importlib.util
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import subprocess
import sys
import threading
import time

import pytest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"scripts/loadtest"))
from run import locust_command


@pytest.mark.skipif(importlib.util.find_spec("locust") is None,reason="Bukti HTTP membutuhkan Locust pinned; jalankan pada profile loadtest")
def test_real_request_crossing_duration_is_not_cancelled_and_real_failures_stay_failures(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        fail=False
        def log_message(self,*args):pass
        def do_GET(self):
            time.sleep(4)
            body=b'{"ok":true}'
            self.send_response(500 if self.fail else 200);self.send_header("Content-Length",str(len(body)));self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    fixture=tmp_path/"delayed.py"
    fixture.write_text('''import json,os
from pathlib import Path
from locust import HttpUser,task,events
class Delayed(HttpUser):
 @task
 def request(self):
  with self.client.get("/",name="delayed",timeout=30,catch_response=True) as response:
   if response.status_code!=200:response.failure("incomplete")
@events.test_stop.add_listener
def stopped(environment,**kwargs):
 value={"requests":environment.stats.total.num_requests,"failures":environment.stats.total.num_failures}
 Path(os.environ["GRACE_PROOF_OUTPUT"]).write_text(json.dumps(value))
''')
    outcomes=[]
    try:
        for grace,failure in [(False,False),(True,False),(True,True)]:
            Handler.fail=failure
            prefix=tmp_path/("real-failure" if failure else "grace" if grace else "forced")
            command=locust_command("http://127.0.0.1:"+str(server.server_port),1,1,3,prefix)
            command[command.index("-f")+1]=str(fixture)
            if not grace:
                index=command.index("--stop-timeout");del command[index:index+2]
            output=prefix.with_suffix(".json")
            result=subprocess.run(command,env=dict(os.environ,GRACE_PROOF_OUTPUT=str(output)),
                                  capture_output=True,text=True,timeout=50)
            value=json.loads(output.read_text())
            outcomes.append((result.returncode,value))
        old_rc,old=outcomes[0];new_rc,new=outcomes[1]
        assert old_rc!=0 or old["requests"]==0 or old["failures"]>0
        assert new_rc==0 and new["requests"]>=1 and new["failures"]==0
        error_rc,error=outcomes[2]
        assert error_rc!=0 and error["failures"]>=1
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
