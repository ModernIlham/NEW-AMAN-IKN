"""API fixture loopback untuk smoke nyata; tidak berpura-pura mengukur AMAN."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from urllib.parse import parse_qs, urlparse


class FixtureAPI:
    def __init__(self):
        self.requests = []
        parent = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                path = urlparse(self.path)
                query = parse_qs(path.query)
                parent.requests.append(path.path)
                if self.headers.get("Authorization") != "Bearer fixture-only-token":
                    return self.reply(401,{"detail":"Unauthenticated fixture"})
                aid = query.get("activity_id",[""])[0]
                if path.path in {"/api/assets","/api/assets/offline-snapshot","/api/export/csv"} and aid != "fixture-only-activity":
                    return self.reply(422,{"detail":"activity_id required"})
                item = {"id":"fixture-asset", "activity_id":aid, "asset_code":"LT.1", "asset_name":"Fixture", "NUP":"1"}
                if path.path == "/api/assets":
                    return self.reply(200,{"items":[item],"total":1,"page":1,"page_size":50,"total_pages":1})
                if path.path == "/api/assets/offline-snapshot":
                    return self.reply(200,{"items":[item],"total":1,"limit":200,"skip":0,"server_time":"2026-10-15T00:00:00Z","next_cursor":""})
                if path.path == "/api/assets/stats":
                    return self.reply(200,{"total_assets":1,"total_value":0})
                if path.path == "/api/assets/analytics":
                    return self.reply(200,{"by_category":[]})
                if path.path == "/api/export/csv":
                    data = b"asset_code,asset_name,NUP\nLT.1,Fixture,1\n"
                    self.send_response(200)
                    self.send_header("Content-Type","text/csv")
                    self.end_headers()
                    return self.wfile.write(data)
                return self.reply(404,{"detail":"Missing fixture route"})
            def reply(self,status,value):
                data=json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type","application/json")
                self.send_header("Content-Length",str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        self.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        self.host="http://127.0.0.1:"+str(self.server.server_port)

    def __enter__(self):
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        return self

    def __exit__(self,*args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
